# Multi-agent RAG

A small assistant for technical, business and compliance questions. It retrieves
relevant documents, resolves annotated conflicts and returns answers with sources.
Includes a Python core, Jupyter notebook, FastAPI service and optional React UI.

## Start with Docker

Install and start **Docker Desktop**. Open a terminal in this project folder.
On the first run, create your local configuration (keep an existing `.env`):

```sh
cp .env.example .env
docker compose --profile ui up --build -d
```

- **Chat:** http://localhost:5173
- **API / Swagger:** http://localhost:8000/docs
- **Notebook:** run `docker compose logs notebook` and open the
  `http://127.0.0.1:8888/lab?token=...` link, including the token.
  Open `notebooks/demo.ipynb` → **Kernel → Restart Kernel and Run All Cells**.
  If Jupyter asks for a password, paste the token from that link.

The first run downloads the images and embedding model. Later runs reuse the cache.
For API and notebook only, omit `--profile ui`. After changing code, rerun the start
command to rebuild. To stop everything: `docker compose --profile ui down`.

## Mock or real LLM

By default, **MiniLM runs locally to compute real embeddings**, while Python rules
simulate planning and extract text from retrieved documents. No API key or GPU is needed.

For generated answers, edit `.env`:

```dotenv
RAG_MODE=live
OPENAI_API_KEY=your-key
```

Run `docker compose --profile ui up -d` again to apply the configuration, then restart
any open notebook kernel. `OPENAI_MODEL` selects the model. Live mode sends questions
and retrieved passages to OpenAI and incurs API usage; it never silently falls back to mock.

## Development without Docker

Use Python 3.13. On macOS/Linux:

```sh
python3.13 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt -c constraints.txt
python -m uvicorn rag_system.api:app --host 127.0.0.1 --port 8000
```

On Windows, activate with `.venv\Scripts\Activate.ps1`. Native Python does not load
`.env`; set environment variables in your terminal for live mode.
Run `python -m jupyterlab` for the notebook. For React, use Node 22.12+ and run
`npm ci` then `npm run dev` inside `frontend`.

## Checks

```sh
docker compose exec api python -m pytest -q
docker compose exec -e RUN_SEMANTIC=1 api python -m pytest -q
docker compose exec api python -m scripts.evaluate
```

The first suite uses test doubles; the second includes MiniLM. The paid live test is
opt-in (`RUN_LIVE_LLM=1`) and requires an API key. Native equivalents use the same
`python -m ...` commands. Run `python -m ruff check .` and
`python -m ruff format --check .` for Python style; `npm run build` checks React.

## Scope

The corpus contains 18 short synthetic English documents. Documents, vectors,
feedback and metrics live in memory; restarting resets them. Notebook and API have
independent state. Use one API worker. This local application has no authentication
or conversational memory. Live answer quality has not yet been verified.

See the [code and concepts guide (Bulgarian)](docs/code_walkthrough.bg.md) for the
execution flow, Python examples, evaluation limits and steps toward production.
