# Multi-agent RAG

A small assistant that answers technical, business and compliance questions using
synthetic documents and citations. Includes a Jupyter notebook, FastAPI service
and optional React chat UI.

## Run with Docker

Start Docker Desktop, then run from the project folder. Create `.env` only if you
don't already have one:

```sh
cp .env.example .env
docker compose --profile ui up --build -d
```

- **Chat:** http://localhost:5173
- **API / Swagger:** http://localhost:8000/docs — try `POST /query`.
- **Notebook:** run `docker compose logs notebook`, open the
  `http://127.0.0.1:8888/lab?token=...` link and select `notebooks/demo.ipynb`.
  Choose **Kernel → Restart Kernel and Run All Cells**. If asked for a password,
  use the token from the logs.

Try: “What business approvals are needed for a new data processing workflow?”

The first start downloads dependencies and the embedding model. Omit `--profile ui`
if you only need the API and notebook. Rerun the start command after code changes.
Stop with `docker compose --profile ui down`.

## Choose mock or Ollama

Set `LLM_PROVIDER` in `.env`:

| Value | Answers |
| --- | --- |
| `mock` (default) | Rule-based responses; no LLM server needed. |
| `ollama` | Real local generation with `qwen3:4b`. |

Both use local MiniLM embeddings for vector search. No API key is required.

For Ollama, install and start [Ollama](https://ollama.com/download) on your machine
(use `ollama serve` if the app isn't running), then download the model:

```sh
ollama pull qwen3:4b
```

Set `LLM_PROVIDER=ollama` in `.env`, then apply the configuration:

```sh
docker compose up -d api notebook
```

Restart the notebook kernel and run all cells. Keep Ollama running; a full notebook
run can take several minutes. Compose connects to `host.docker.internal:11434`.
On Linux, Ollama must listen on an address reachable from Docker. Use `OLLAMA_URL`
or `OLLAMA_MODEL` in `.env` only to override the defaults.

## Tests

With the containers running:

```sh
# Fast tests with test doubles
docker compose exec api python -m pytest -q

# Include real MiniLM embeddings
docker compose exec -e RUN_SEMANTIC=1 api python -m pytest -q

# Real generation — requires Ollama and the model above
docker compose exec -e RUN_LIVE_LLM=1 api python -m pytest -m live -v
```

## Code overview

[`bootstrap.py`](rag_system/bootstrap.py) builds the shared core.
[`Orchestrator._query()`](rag_system/orchestrator.py) coordinates the flow:

**Question → plan → retrieve documents → resolve conflicts → domain answers → final answer with citations.**

[`domain_agents.py`](rag_system/domain_agents.py) handles the three domains,
[`vector_store.py`](rag_system/vector_store.py) handles retrieval, and
[`models.py`](rag_system/models.py) defines the data passed between components.

The corpus lives in `data/knowledge.json`. Documents, vectors, feedback and metrics
are held in memory and reset on restart. API and notebook have separate state.
Agents run sequentially; use one API worker. This local demo has no authentication
or conversation memory.
