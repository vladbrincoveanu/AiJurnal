import { useMemo, useState } from "react";
import { useMutation } from "@tanstack/react-query";
import axios from "axios";

type EventRead = {
  id: string;
  title?: string | null;
  source_type: string;
  source_app: string;
  summary?: string | null;
  content: string;
  created_at: string;
};

const API_BASE =
  (import.meta.env.VITE_API_BASE as string | undefined) ||
  "http://localhost:8000/api";
const API_KEY = import.meta.env.VITE_APP_API_KEY as string | undefined;

const client = axios.create({
  baseURL: API_BASE,
});

client.interceptors.request.use((config) => {
  if (API_KEY) {
    config.headers = config.headers ?? {};
    config.headers["X-API-Key"] = API_KEY;
    config.headers.Authorization = `Bearer ${API_KEY}`;
  }
  config.headers = config.headers ?? {};
  config.headers["Content-Type"] = "application/json";
  return config;
});

const sourceTypes = ["note", "web", "file", "chat"] as const;

export default function App() {
  const [title, setTitle] = useState("");
  const [url, setUrl] = useState("");
  const [content, setContent] = useState("");
  const [sourceType, setSourceType] = useState<(typeof sourceTypes)[number]>(
    "note",
  );
  const [sourceApp, setSourceApp] = useState("web");
  const [searchQuery, setSearchQuery] = useState("");
  const [searchResults, setSearchResults] = useState<EventRead[]>([]);

  const ingestPayload = useMemo(
    () => ({
      source_type: sourceType,
      source_app: sourceApp || "web",
      title: title || undefined,
      url_or_path: url || undefined,
      content,
      metadata: {
        captured_at: new Date().toISOString(),
      },
    }),
    [content, sourceApp, sourceType, title, url],
  );

  const ingestMutation = useMutation({
    mutationFn: async () => {
      await client.post("/ingest", ingestPayload);
    },
    onSuccess: () => {
      setTitle("");
      setUrl("");
      setContent("");
    },
  });

  const searchMutation = useMutation({
    mutationFn: async () => {
      const response = await client.post<EventRead[]>("/search", {
        query: searchQuery,
        limit: 5,
      });
      return response.data;
    },
    onSuccess: (data) => setSearchResults(data),
  });

  return (
    <div className="min-h-screen bg-slate-950 text-slate-50">
      <div className="max-w-4xl mx-auto px-4 py-10 space-y-10">
        <header>
          <h1 className="text-3xl font-semibold tracking-tight">
            AIJournal Playground
          </h1>
          <p className="text-slate-400 mt-2">
            Capture snippets and search them immediately through the API.
          </p>
          <p className="text-xs text-slate-500 mt-2">
            API base: <code>{API_BASE}</code>
          </p>
        </header>

        <section className="bg-slate-900/60 border border-slate-800 rounded-lg p-6 space-y-4">
          <h2 className="text-xl font-semibold">Ingest memory</h2>
          <div className="grid gap-4">
            <label className="block">
              <span className="text-sm text-slate-400">Source type</span>
              <select
                value={sourceType}
                onChange={(e) =>
                  setSourceType(e.target.value as (typeof sourceTypes)[number])
                }
                className="mt-1 w-full rounded border border-slate-700 bg-slate-900 px-3 py-2"
              >
                {sourceTypes.map((type) => (
                  <option key={type} value={type}>
                    {type}
                  </option>
                ))}
              </select>
            </label>

            <label className="block">
              <span className="text-sm text-slate-400">Source app</span>
              <input
                value={sourceApp}
                onChange={(e) => setSourceApp(e.target.value)}
                placeholder="browser, cli, ios-shortcut..."
                className="mt-1 w-full rounded border border-slate-700 bg-slate-900 px-3 py-2"
              />
            </label>

            <label className="block">
              <span className="text-sm text-slate-400">Title</span>
              <input
                value={title}
                onChange={(e) => setTitle(e.target.value)}
                className="mt-1 w-full rounded border border-slate-700 bg-slate-900 px-3 py-2"
              />
            </label>

            <label className="block">
              <span className="text-sm text-slate-400">URL or path</span>
              <input
                value={url}
                onChange={(e) => setUrl(e.target.value)}
                className="mt-1 w-full rounded border border-slate-700 bg-slate-900 px-3 py-2"
              />
            </label>

            <label className="block">
              <span className="text-sm text-slate-400">Content</span>
              <textarea
                value={content}
                onChange={(e) => setContent(e.target.value)}
                rows={4}
                className="mt-1 w-full rounded border border-slate-700 bg-slate-900 px-3 py-2"
              />
            </label>

            <button
              onClick={() => ingestMutation.mutate()}
              disabled={ingestMutation.isPending}
              className="rounded bg-emerald-500/90 hover:bg-emerald-500 disabled:opacity-60 px-4 py-2 font-medium"
            >
              {ingestMutation.isPending ? "Saving..." : "Save memory"}
            </button>
            {ingestMutation.isSuccess && (
              <p className="text-sm text-emerald-400">
                Event queued for processing.
              </p>
            )}
            {ingestMutation.isError && (
              <p className="text-sm text-rose-400">
                Failed to save. Check console/logs.
              </p>
            )}
          </div>
        </section>

        <section className="bg-slate-900/60 border border-slate-800 rounded-lg p-6 space-y-4">
          <h2 className="text-xl font-semibold">Semantic search</h2>
          <div className="flex gap-3">
            <input
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              placeholder="Search memories..."
              className="flex-1 rounded border border-slate-700 bg-slate-900 px-3 py-2"
            />
            <button
              onClick={() => searchMutation.mutate()}
              disabled={!searchQuery}
              className="rounded bg-indigo-500/90 hover:bg-indigo-500 px-4 py-2 font-medium disabled:opacity-40"
            >
              Search
            </button>
          </div>
          {searchMutation.isError && (
            <p className="text-sm text-rose-400">
              Search failed. Check API logs.
            </p>
          )}
          <div className="space-y-3">
            {searchResults.map((event) => (
              <article
                key={event.id}
                className="border border-slate-800 rounded-md p-4 bg-slate-950/60"
              >
                <div className="flex items-center justify-between text-xs uppercase tracking-wide text-slate-500">
                  <span>{event.source_type}</span>
                  <span>{new Date(event.created_at).toLocaleString()}</span>
                </div>
                <h3 className="text-lg font-semibold mt-2">
                  {event.title || "Untitled"}
                </h3>
                <p className="text-sm text-slate-400 mt-2 whitespace-pre-wrap">
                  {(event.summary || event.content).slice(0, 280)}…
                </p>
              </article>
            ))}
            {searchMutation.isSuccess && searchResults.length === 0 && (
              <p className="text-sm text-slate-500">No results yet.</p>
            )}
          </div>
        </section>
      </div>
    </div>
  );
}
