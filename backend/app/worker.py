from __future__ import annotations

from redis import Redis
from rq import Connection, Worker

from app.core.config import get_settings
from app.services.tasks import QUEUE_NAME


def main() -> None:
    settings = get_settings()
    redis_conn = Redis.from_url(settings.redis_url)
    with Connection(redis_conn):
        worker = Worker([QUEUE_NAME])
        worker.work()


if __name__ == "__main__":
    main()
