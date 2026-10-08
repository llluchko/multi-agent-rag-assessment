# Multi-agent RAG

An assistant for technical, business and compliance questions, with cited answers,
a demo notebook, FastAPI service and React chat UI.

## 1. Prepare the project

Use **Docker Desktop** for the API and chat UI. For the notebook, install
**Python 3.13** and **VS Code** with Microsoft's **Python** and **Jupyter** extensions.
The notebook runs locally in `.venv`.

Clone the repository if you don't already have it:

```sh
git clone https://github.com/llluchko/multi-agent-rag-assessment.git
cd multi-agent-rag-assessment
```

Open the project folder in VS Code. Whenever a step below includes a terminal
command, run it from the project root using VS Code's integrated terminal.

## 2. Choose Ollama or mock

Copy `.env.example` to `.env` using VS Code, keeping an existing `.env` if present.
The example selects real local generation:

```dotenv
LLM_PROVIDER=ollama
OLLAMA_MODEL=qwen3:4b
EMBEDDING_BACKEND=fastembed
```

For a quick demo **without Ollama**, change only `LLM_PROVIDER=mock` and skip step 3.
Mock returns retrieved passages instead of generating text. Both modes use real
MiniLM embeddings for search; neither requires an API key.

## 3. Start Ollama (skip for mock)

Install [Ollama](https://ollama.com/download) on your computer and open the app.
If running it from the terminal instead, keep `ollama serve` running in another
terminal. Download the model once:

```sh
ollama pull qwen3:4b
```

Open http://localhost:11434/api/tags and confirm that `qwen3:4b` appears.
Keep Ollama running while using the project. The local notebook uses
`localhost:11434`; Docker uses `host.docker.internal:11434`. Both are configured
automatically, so leave `OLLAMA_URL` unset for this setup.

On Linux, the Ollama listener must be reachable from Docker; see the
[Ollama network configuration](https://docs.ollama.com/faq#how-do-i-configure-ollama-server).

## 4. Start the API and chat UI with Docker

Start Docker Desktop, then run (skip this step if you only need the notebook):

```sh
docker compose up --build -d api ui
```

The first start downloads dependencies and MiniLM. Then open:

- **Chat:** http://localhost:5173
- **API / Swagger:** http://localhost:8000/docs
- **Current provider:** http://localhost:8000/health — check `llm_provider`.

Try: “What business approvals are needed for a new data processing workflow?”

## 5. Run the notebook in VS Code

Create the local environment and install dependencies once. On macOS/Linux:

```sh
python3.13 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt -c constraints.txt
```

On Windows PowerShell, create it with `py -3.13 -m venv .venv`, activate with
`.venv\Scripts\Activate.ps1`, then run the same pip command above.
If `.venv` is already prepared, go straight to kernel selection.

1. Open `notebooks/demo.ipynb` in VS Code.
2. Click **Select Kernel → Select Another Kernel → Python Environments** and
   choose the project's **`.venv` (Python 3.13)**. If already selected, keep it.
3. Select **Restart Kernel**, then **Run All**. The first cell prints the provider.

The notebook reads the project's `.env` automatically. No server URL or token is
needed. The first local run downloads MiniLM; Ollama generation can take several
minutes. See [VS Code kernel selection](https://code.visualstudio.com/docs/datascience/jupyter-kernel-management#_python-environments)
if `.venv` is missing from the picker.

## Changing settings and stopping

After changing `.env`, restart the notebook kernel and run all cells. To also
apply the change to the Docker API:

```sh
docker compose up -d api
```

Docker Desktop **Restart** alone does not reload `.env`. Rerun the command from
step 4 after changing application code; restart the local kernel for Python changes.

Stop the application, including the optional UI service:

```sh
docker compose --profile ui down
```

## Optional checks

```sh
# Fast tests; no Ollama required
docker compose exec api python -m pytest -q

# Three live scenarios; requires running Ollama with qwen3:4b
docker compose exec -e RUN_LIVE_LLM=1 api python -m pytest -m live -v
```

The demo uses synthetic data and in-memory state. API and notebook have separate
state, reset on restart. See [Architecture](docs/architecture.md) for the design.
