import argparse
import os
from pathlib import Path
from typing import Iterable

import httpx

API_BASE = os.getenv("API_BASE", "http://localhost:8000/api")
API_KEY = os.getenv("APP_API_KEY", "")

IGNORE_DIRS = {".git", "node_modules", "__pycache__"}
IGNORE_FILES = {".env"}
BINARY_EXTS = {".png", ".jpg", ".jpeg", ".gif", ".pdf", ".zip", ".exe", ".dll"}


def is_binary(path: Path) -> bool:
    if path.suffix.lower() in BINARY_EXTS:
        return True
    try:
        with path.open("rb") as f:
            chunk = f.read(1024)
            return b"\0" in chunk
    except OSError:
        return True


def iter_files(root: Path) -> Iterable[Path]:
    for path in root.rglob("*"):
        if path.is_dir() and path.name in IGNORE_DIRS:
            continue
        if path.is_file():
            if path.name in IGNORE_FILES or is_binary(path):
                continue
            yield path


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Import text files into the Memory Journal backend."
    )
    parser.add_argument("path", type=Path, help="Path to directory or file")
    args = parser.parse_args()

    targets = [args.path]
    if args.path.is_dir():
        targets = list(iter_files(args.path))

    headers = {}
    if API_KEY:
        headers["X-API-Key"] = API_KEY
        headers["Authorization"] = f"Bearer {API_KEY}"
    with httpx.Client(timeout=15.0) as client:
        for file_path in targets:
            if file_path.is_dir():
                continue
            content = file_path.read_text(errors="ignore")
            payload = {
                "source_type": "file",
                "source_app": "cli",
                "title": file_path.name,
                "url_or_path": str(file_path),
                "content": content,
                "metadata": {"size": file_path.stat().st_size},
            }
            resp = client.post(f"{API_BASE}/ingest", json=payload, headers=headers)
            status = resp.status_code
            print(f"[{status}] {file_path}")


if __name__ == "__main__":
    main()
