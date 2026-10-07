# Multi-agent RAG assessment

An inspectable assistant for questions spanning **technical, business and compliance**
knowledge. A planner decomposes a question, domain agents retrieve their own evidence,
and an orchestrator resolves conflicts and synthesizes a cited answer.

**One Python core, an executable notebook, a FastAPI/OpenAPI service, and an optional React chat.**
This repository implements the **Technical Task**. The separate Systems Design task
is still a separate deliverable and is not represented as completed here.

## Quick start with Docker

Prerequisite: Docker with Compose. From the repository root:

```sh
cp .env.example .env
docker compose up --build
```

- API documentation: <http://localhost:8000/docs>
- OpenAPI schema: <http://localhost:8000/openapi.json>
- Jupyter: open the localhost URL with its generated token from the notebook service logs.
  If needed: `docker compose logs notebook`. Open `notebooks/demo.ipynb` and **Restart Kernel → Run All**.
- Optional chat: `docker compose --profile ui up --build`, then <http://localhost:5173>.

Default mode uses **real local MiniLM embeddings and mock text generation**. No API key
or GPU is required. Initial image builds and the roughly 90 MB embedding download need
internet. A named volume caches the model. Later cached runs can use `HF_HUB_OFFLINE=1`
when running natively. The two Python services share the model cache, not application state.

Docker images were built and the API, notebook and optional UI were started with Docker
Desktop. The semantic test suite and all ten notebook cells also passed inside containers.
See [validation](docs/validation.md) for exact evidence and limits.

## Native setup

Use Python **3.13**. Commands below are for macOS/Linux; on Windows activate the virtual
environment using `.venv\Scripts\Activate.ps1`. Docker provides the common runtime.

```sh
python3.13 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt -c constraints.txt
python -m jupyterlab
```

In Jupyter select this environment's Python kernel, then **Restart Kernel → Run All**.
For VS Code, open the repository and select `.venv` as the notebook kernel.
The notebook initializes its own application and needs no API process.

To start the API in another terminal with the same environment active:

```sh
python -m uvicorn rag_system.api:app --host 127.0.0.1 --port 8000
```

For the optional React client, use Node **22.12+** (Node 24 was tested):

```sh
cd frontend
npm ci
npm run dev
```

Open <http://localhost:5173>. The dev server proxies `/api` to port 8000, so there is no
browser API key or permissive CORS configuration. `npm run build` type-checks and builds
static assets. The Docker UI uses a local Vite server, intended only for this demo.

## Real LLM mode

The live adapter calls **OpenAI Responses** with strict JSON Schema. The default model
is `gpt-4.1-mini-2025-04-14`; `OPENAI_MODEL` can select another compatible model available
to your account. The model/provider is configured in one place.

For Docker, edit the untracked `.env`:

```dotenv
RAG_MODE=live
OPENAI_API_KEY=your-own-key
```

Restart the services. For native execution, set these variables in the terminal before
starting Jupyter or the API. Native Python does not automatically load `.env`.
Live calls require internet and incur provider usage. Prompts and retrieved synthetic
passages are sent to OpenAI. Requests set `store=false`.

**Live mode never silently falls back to mock.** Missing credentials fail at startup;
provider failures are returned with an explicit failed/partial status. No real API
calls were tested during initial implementation because no key was available.

| Mode | Embeddings | Planner and answers | Purpose |
| --- | --- | --- | --- |
| Default `RAG_MODE=mock` | MiniLM, CPU | Lexical routing and extractive simulation | Reproducible demonstration without a key |
| `RAG_MODE=live` | MiniLM, CPU | Real structured LLM output | Real model demonstration and quality review |
| `EMBEDDING_BACKEND=lexical` | Hashed word vectors, explicitly labelled | Either configured mode | Download-free contract tests; not semantic retrieval |

## What the demo proves

The ten notebook code cells inspect retrieval, execute the three assignment queries,
resolve an annotated contradiction, update a document, demonstrate feedback changing
ranking, withhold an ambiguous conflict, simulate a domain failure, evaluate 24 cases,
and call the OpenAPI boundary.

Mock routing is intentionally simple and mock synthesis is extractive. It can retrieve
generic advice for an unanswerable question containing familiar vocabulary; evaluation
includes such a failing case. Mock success does not measure LLM answer quality.

## API

| Method and path | Contract |
| --- | --- |
| `GET /health` | Ready state and active mode/backend; not a live-provider availability probe |
| `POST /query` | `{ "text": "..." }` → answer, tasks, evidence, citations, conflicts and timings |
| `PUT /documents/{id}` | Full document; changed content requires a higher version; equal retries are idempotent |
| `POST /feedback` | `{ "request_id": "...", "source_id": "doc@v1#0", "helpful": true }` |
| `GET /metrics` | Completion rate, explicit feedback success rate and per-agent timings/errors |

Queries return `answered`, `partial`, `no_evidence` or `failed`. A model failure returns
HTTP 502 with the trace; empty input returns 422; invalid/stale/duplicate feedback and
stale document updates return 409. `no_evidence` and `partial` are valid business outcomes,
not HTTP failures. API schemas and examples can be inspected through `/docs`.

```sh
curl -s http://localhost:8000/query \
  -H 'Content-Type: application/json' \
  -d '{"text":"What is the process for deploying a microservice and what compliance checks are needed?"}'
```

## Tests and evaluation

```sh
python -m pytest -q                             # contract tests, no download or key
RUN_SEMANTIC=1 python -m pytest -q               # add real local embeddings
RUN_LIVE_LLM=1 python -m pytest -q -m live       # explicit paid live check
python -m scripts.evaluate                     # report in .cache/evaluation.json
python scripts/execute_notebook.py              # executes and saves notebook outputs
python -m ruff check .
python -m ruff format --check .
```

`requirements.txt` pins direct dependencies; `constraints.txt` pins the tested transitive
resolution. The embedding model is pinned to a Hugging Face revision. The frontend has a
lockfile. Docker base images use version tags rather than immutable digests: this is a
repeatable demo setup, not a claim of byte-for-byte reproducibility on all platforms.

Evaluation separates routing, **raw retrieval recall at the selected k**, expected-source
recall in the final answer, and abstention. Its diagnostic success rate is not semantic
correctness. The cases are development examples, not an independent holdout. Use the
[manual quality rubric](docs/validation.md#manual-live-quality-review) for actual live outputs.

## Scope and trade-offs

- Eighteen short synthetic English passages, one chunk per document. `#0` identifies that
  atomic chunk. No general file ingestion. MiniLM truncates long inputs; keep added
  documents and subqueries short (within its 256-token window).
- Exact cosine search is adequate here. A production vector database, hybrid search and
  reranking are follow-up experiments motivated by scale or measured quality gaps.
- Multi-agent means distinct roles, domain-filtered knowledge and typed messages in one
  explicit workflow. Agents share the model and implementation; no autonomous loops.
- Conflicts use annotated `fact_key`, `scope` and canonical `value`. This is deliberately
  a controlled simulation, not general contradiction detection.
- Source authority precedes a confidence heuristic. Similarity/confidence are not truth
  probabilities. Citation membership is checked; semantic support still needs review.
- Simulated feedback adjusts per-source ranking weights in [0.8, 1.2]. It does not train
  the LLM and cannot override source authority.
- All knowledge updates, feedback and metrics are **in memory**. Restart resets to the
  committed seed corpus. Answers retain source snapshots. History is bounded to 256 requests.
- Use one API worker. A lock serializes queries and updates for consistent snapshots.
  This sacrifices throughput for clarity. Notebook and API have independent state.
- Chat history is visual only; every question is independent. No auth, file upload,
  conversational memory, streaming, or public deployment is included.

See [architecture and requirement mapping](docs/architecture.md), [validation](docs/validation.md),
and [implementation plan](docs/plan.md). Start with the [Bulgarian code walkthrough](docs/code_walkthrough.bg.md)
to follow a question through the classes. Development used incremental local Git commits;
this new repository has not been published to GitHub.

## References

- [LLM Zoomcamp](https://datatalks.club/blog/llm-zoomcamp.html): grounded RAG, evaluation and monitoring.
- [OpenAI structured outputs](https://developers.openai.com/api/docs/guides/structured-outputs): strict response schemas.
- [FastAPI](https://fastapi.tiangolo.com/features/): validation and OpenAPI documentation.
- [FastEmbed](https://github.com/qdrant/fastembed): local ONNX embeddings.
