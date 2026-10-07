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

## Choose the LLM

Set one value in `.env`; API and notebook use the same setting:

```dotenv
LLM_PROVIDER=mock
```

Use `mock` for deterministic answers without an LLM server, or `ollama` for real
local Qwen3 4B generation. Both use real local MiniLM embeddings by default.
No API key is needed. Ollama failures are reported; there is no automatic mock fallback.

Native Python reads `.env` automatically. After changing it, restart the notebook
kernel and run all cells. With Docker, first run `docker compose up -d api notebook`
to apply the setting to both containers. No notebook code changes are needed.

### Start Ollama (only for `LLM_PROVIDER=ollama`)

Install [Ollama](https://ollama.com/download) on the host and start it (`ollama serve`
in another terminal if the app is not running). Download the model once:

```sh
ollama pull qwen3:4b
```

Check that Ollama is running by opening [the local model list](http://localhost:11434/api/tags)
in your browser, or running `curl http://localhost:11434/api/tags`. The JSON should
include `qwen3:4b`. If the connection fails, start Ollama; if the model is missing,
run the pull command above. Keep the `ollama serve` terminal open during the demo.

<details>
<summary>Reuse an existing cached Ollama installation on macOS</summary>

If you already have the runtime and model in
`~/Desktop/multi-agent-rag/.cache/ollama`, start them directly without reinstalling
or downloading the model again:

```sh
OLLAMA_MODELS="$HOME/Desktop/multi-agent-rag/.cache/ollama/models" \
OLLAMA_HOST=127.0.0.1:11434 \
"$HOME/Desktop/multi-agent-rag/.cache/ollama/bin/ollama" serve
```

Adjust the paths if your cache is elsewhere. This optional shortcut is specific to
an existing local installation; a fresh checkout uses the standard setup above.
Skip this command if Ollama is already running on port 11434.

</details>

Ollama runs on the host; the API and notebook can stay in Docker. The address is
selected automatically: native Python uses `localhost:11434`, while Compose uses
`host.docker.internal:11434`. Set `OLLAMA_URL` only for a custom server and
`OLLAMA_MODEL` only to override `qwen3:4b`. On Linux, the Ollama listener must be
reachable from the Docker gateway; otherwise use native Python.

The notebook's final cell checks the three answers already generated with Ollama.
In mock mode, it explicitly skips the real-model assertions. Feedback and failure
experiments, plus the 24-case diagnostic baseline, always use mock and are labelled.

[Qwen3 4B](https://ollama.com/library/qwen3:4b) has an Apache 2.0 license and a roughly
2.5 GB download. Inference uses your computer, with no per-request API fee.
A full notebook run takes several minutes with Ollama. Valid citations do not prove
that every generated statement is relevant or complete.

## Development without Docker

Use Python 3.13. On macOS/Linux:

```sh
python3.13 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt -c constraints.txt
python -m uvicorn rag_system.api:app --host 127.0.0.1 --port 8000
```

On Windows, activate with `.venv\Scripts\Activate.ps1`. The same `.env` is loaded
automatically. Explicit environment variables take precedence over the file.
Run `python -m jupyterlab` for the notebook. For React, use Node 22.12+ and run
`npm ci` then `npm run dev` inside `frontend`.

## Checks

```sh
docker compose exec api python -m pytest -q
docker compose exec -e RUN_SEMANTIC=1 api python -m pytest -q
docker compose exec api python -m scripts.evaluate
```

The first suite uses test doubles; the second includes MiniLM. To run the three
real Ollama scenarios separately from the notebook:

```sh
docker compose exec -e RUN_LIVE_LLM=1 api python -m pytest -m live -v
```

`RUN_LIVE_LLM` only opts into pytest's slower integration tests; it does not configure
the application or notebook. Native equivalents use the same
`python -m ...` commands. Run `python -m ruff check .` and
`python -m ruff format --check .` for Python style; `npm run build` checks React.

## Scope

The corpus contains 18 short synthetic English documents. Documents, vectors,
feedback and metrics live in memory; restarting resets them. Notebook and API have
independent state. Use one API worker. This local application has no authentication
or conversational memory. Generated answers still need review against their sources.

See the [code and concepts guide (Bulgarian)](docs/code_walkthrough.bg.md) for the
execution flow, Python examples, evaluation limits and steps toward production.
