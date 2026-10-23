# Deploying Filing Lens on Replit

One Replit app runs the FastAPI backend (`api.py`) and serves the vibe-coded front end (`frontend/dist`) from the same origin.

## 1. Before importing: make sure the BM25 files are in GitHub

The hosted app needs `data/processed/chunks_*.pkl` (keyword-search corpus). Vectors stay in Pinecone.

```bash
git ls-files data/processed        # should list chunks_fixed.pkl, chunks_section.pkl, chunks_table_aware.pkl
# if they are missing:
git add -f data/processed/chunks_*.pkl && git commit -m "Add BM25 corpora for hosted app"
git push
```

## 2. Import and configure

1. Replit → **Create App** → **Import from GitHub** → `kdhandapani-hub/filing-lens`.
2. **Secrets** (padlock icon). Add each as its own secret:

| Secret | Value |
|---|---|
| `NEBIUS_API_KEY` | your Nebius key |
| `NEBIUS_EMBED_MODEL` | `Qwen/Qwen3-Embedding-8B` |
| `NEBIUS_CHAT_MODEL` | `deepseek-ai/DeepSeek-V4.1-Flash` |
| `NEBIUS_CHAT_EXTRA_BODY` | `{"chat_template_kwargs": {"thinking": false}}` |
| `PINECONE_API_KEY` | your Pinecone key |
| `PINECONE_INDEX` | `week2-financial-rag` |
| `LANGSMITH_TRACING` | `true` |
| `LANGSMITH_API_KEY` | your LangSmith key |
| `LANGSMITH_PROJECT` | `filing-lens-prod` (keeps app traffic apart from eval runs) |
| `APP_ACCESS_CODE` | a code you choose; share it only with graders |

`OPENAI_API_KEY` is not needed here; it's only for the eval judge.

3. Click **Run**. `build.sh` installs dependencies (the first run takes a few minutes), then `start.sh` starts the API.
4. Open `/api/health` in the webview. Wait until `"status": "ready"`.
5. Open `/docs` and try `POST /api/ask` with header `X-Access-Code`. This confirms the backend works before any UI exists.

## 3. Vibe-code the front end

Open **Agent** and paste the prompt from [`docs/REPLIT_AGENT_PROMPT.md`](REPLIT_AGENT_PROMPT.md) (everything below the line). It tells the Agent to build only inside `frontend/` and leave the backend alone.

After it finishes: click **Run** again (the build step compiles the UI), then go through the acceptance checks at the end of the prompt.

If the Agent edits anything outside `frontend/`, undo it from the file history or checkpoint before deploying.

## 4. Deploy

**Deploy** → **Autoscale** → the build and run commands come from `.replit` → add the same Secrets to the deployment if Replit asks → **Deploy**.

- Autoscale sleeps when idle. The first request after a pause pays a warm-up of about 10–20 seconds; the UI shows "Starting up…" during it. Open the link a minute before recording the demo.
- Costs draw from your Replit credit; check the deployment pricing shown before confirming.

## 5. Commit the front end back to GitHub

In Replit's **Git** pane: commit `frontend/` (not `frontend/dist` or `node_modules`, which are ignored) and push, so the repo holds the full project.
