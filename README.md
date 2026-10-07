# Multi-agent RAG

A small assistant for technical, business and compliance questions. It retrieves
relevant documents, resolves annotated conflicts and returns answers with sources.
Includes a Python core, Jupyter notebook, FastAPI service and optional React UI.

## Read the code

Start with one question in `notebooks/demo.ipynb`, then follow this path:

1. [`bootstrap.py`](rag_system/bootstrap.py) — creates the store, LLM and agents.
2. [`Orchestrator._query()`](rag_system/orchestrator.py) — the complete workflow:
   plan → retrieve → resolve conflicts → generate → synthesize → respond.
3. [`domain_agents.py`](rag_system/domain_agents.py) and
   [`vector_store.py`](rag_system/vector_store.py) — context selection and cited claims.
4. [`models.py`](rag_system/models.py) — messages shared through the orchestrator.
5. [`utils.py`](rag_system/utils.py) — conflict policy and answer status rules.

Three domain agents share one implementation, with domain-filtered knowledge.
Calls are sequential in one process; JSON seeds an in-memory NumPy vector store.
These choices keep the small corpus easy to inspect. API, notebook and optional UI
use the same core. The [code guide](docs/code_walkthrough.bg.md) includes a 30-minute tour.

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
LLM_PROVIDER=openai
OPENAI_API_KEY=your-key
```

Run `docker compose --profile ui up -d` again to apply the configuration, then restart
any open notebook kernel. `OPENAI_MODEL` selects the model. This provider sends questions
and retrieved passages to OpenAI and incurs API usage; it never silently falls back to mock.

### Free local LLM with Ollama

Install [Ollama](https://ollama.com/download) on the host and start it (`ollama serve`
in another terminal if the app is not running). Download the model once:

```sh
ollama pull qwen3:4b
```

For Docker Desktop, set these values in `.env` (no API key needed):

```dotenv
RAG_MODE=live
LLM_PROVIDER=ollama
OLLAMA_MODEL=qwen3:4b
OLLAMA_URL=http://host.docker.internal:11434
```

Rebuild with `docker compose --profile ui up --build -d`, then restart the notebook
kernel. `/health` reports `mode: live` and `llm_provider: ollama`. Ollama runs on the
host; the API and notebook stay in Docker. On Linux, the host Ollama listener must
be reachable from the Docker gateway; alternatively use native Python with
`OLLAMA_URL=http://localhost:11434`.

Run the three real-model scenarios explicitly:

```sh
docker compose exec -e RUN_LIVE_LLM=1 -e LLM_PROVIDER=ollama api \
  python -m pytest tests/test_scenarios.py::test_live_model -v
```

[Qwen3 4B](https://ollama.com/library/qwen3:4b) has an Apache 2.0 license; its Ollama download is about 2.5 GB.
Local inference uses your machine's memory and compute, with no per-request API fee.
The tests check required domains, expected sources, completion and token usage;
they do not prove that every generated statement is correct.
The notebook also has an optional local live-test cell: set `RUN_LOCAL_LIVE_TEST = True`
there to run the same three scenarios while keeping the rest of the demo in mock mode.

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

The first suite uses test doubles; the second includes MiniLM. Live tests are
opt-in (`RUN_LIVE_LLM=1`) and use `LLM_PROVIDER` (OpenAI needs a key; Ollama does not).
Native equivalents use the same
`python -m ...` commands. Run `python -m ruff check .` and
`python -m ruff format --check .` for Python style; `npm run build` checks React.

## Scope

The corpus contains 18 short synthetic English documents. Documents, vectors,
feedback and metrics live in memory; restarting resets them. Notebook and API have
independent state. Use one API worker. This local application has no authentication
or conversational memory. Generated answers still need review against their sources.

See the [code and concepts guide (Bulgarian)](docs/code_walkthrough.bg.md) for the
execution flow, Python examples, evaluation limits and steps toward production.
