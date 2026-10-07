# Architecture

The application answers technical, business and compliance questions over a small
synthetic corpus. One Python core serves the notebook and API; the React UI calls
the API. Setup instructions are in the [README](../README.md).

## Components

```mermaid
flowchart TD
    UI[React UI] --> API[FastAPI]
    API --> O[Orchestrator]
    N[Jupyter notebook] --> ON[Separate Orchestrator instance]
    O --> P[QueryClassifier]
    O --> A[DomainAgent: technical, business, compliance]
    A --> V[VectorStoreManager]
    V --> E[Local MiniLM embeddings]
    P --> L[MockLLM or OllamaLLM]
    A --> L
    O --> L
    L -->|Ollama only: HTTP| S[Ollama server / Qwen3]
```

[`build_system()`](../rag_system/bootstrap.py) reads configuration, loads
`data/knowledge.json`, embeds the documents and creates the store, LLM adapter and
orchestrator. Each notebook/API instance owns its own state. The notebook instance
uses the same components shown for the API.

The three agents are configurations of one
[`DomainAgent`](../rag_system/domain_agents.py) class. They share a store but filter
initial retrieval by domain. They run sequentially inside the Python process.

## A question from input to answer

[`Orchestrator._query()`](../rag_system/orchestrator.py) makes the stages explicit:

1. **Plan:** `QueryClassifier` returns a `Plan` with up to one `Task` per domain.
   Each task contains a domain and a self-contained subquery.
2. **Retrieve:** each selected agent embeds its subquery and searches its domain.
   Normalized vectors make the dot product equivalent to cosine similarity.
   Results below the similarity threshold are excluded; the rest are ranked by
   `similarity × feedback_weight` and limited to `top_k`.
3. **Resolve conflicts:** inspect all documents with the same annotated
   `(fact_key, scope)`, including ones outside the initial retrieval. Conflicting
   values are resolved by source authority, then heuristic confidence. Close
   equal-authority conflicts are withheld. This is metadata-based conflict
   detection, not general contradiction detection over arbitrary text.
4. **Answer per domain:** each agent receives the approved evidence and returns
   claims referencing source IDs. Code checks that those references exist in the
   supplied evidence.
5. **Synthesize:** combine domain claims, validate references again, then return
   an `Answer` containing the text, citations, plan, agent results, conflicts and
   timings. Status is `answered`, `partial`, `no_evidence` or `failed`.

`top_k` is 2 for technical/business and 3 for compliance, with 2 added for a complex
plan. It limits initial retrieval, not the final citation count. These small
budgets and confidence scores are heuristics, not calibrated correctness measures.

## How agents share context

Agents communicate through the orchestrator using the Pydantic models in
[`models.py`](../rag_system/models.py); there is no message broker or direct
agent-to-agent messaging.

| Object | Purpose |
| --- | --- |
| `Plan` / `Task` | Selected domains, subqueries and retrieval complexity. |
| `Evidence` | Document snapshot, similarity, confidence and feedback weight. |
| `AgentResult` | Task, raw retrieval, approved evidence, claims, timing and error. |
| `Draft` / `Claim` | Generated statements and their supporting source IDs. |
| `Answer` | Final response and the execution trace. |

The orchestrator replaces raw retrieval with approved evidence before generation
and passes domain claims into synthesis. Source IDs such as `biz-approvals@v1#0`
identify the document, version and passage. Each short document is one passage.

## Mock and Ollama

Both adapters implement `generate(stage, instructions, payload, schema)` in
[`llm.py`](../rag_system/llm.py). Retrieval and orchestration are shared.

| Stage | Mock | Ollama |
| --- | --- | --- |
| Planning | Keyword rules and templated subqueries; multiple domains mean complex. | Model selects domains, subqueries and complexity from instructions. |
| Domain answers | Copies supplied source text into claims. | Generates claims from supplied evidence. |
| Synthesis | Deduplicates claims and keeps up to 12. | Generates a combined answer from domain claims and sources. |

`OllamaLLM` is an HTTP adapter; constructing it does not load Qwen or contact the
server. Each `generate()` calls Ollama's `/api/chat` with instructions, input and a
JSON schema, then validates the response with Pydantic. Ollama runs separately and
executes the model. Failures are reported without an automatic mock fallback.
`/health` reports application readiness and configuration, not model availability.

## State and design choices

- **In-memory NumPy store:** exact search is sufficient for the 18-document seed
  corpus; no database service is required. MiniLM embeddings are real in both
  modes. A lexical test double supports fast offline tests.
- **Controlled feedback:** one vote per retained request/source changes its
  retrieval weight by ±0.05, bounded to 0.8–1.2. This adjusts ranking, not model
  parameters. Unrelated or obsolete source versions are rejected.
- **Versioned updates:** new documents are embedded before replacing store state.
  Changed documents require a higher version; identical updates are no-ops.
- **Simple concurrency:** an `RLock` serializes queries, feedback and updates.
  Use one API worker. State resets on restart; history retains up to 256 answers.
- **Observable results:** responses expose stage timings and model call/token
  counts. `/metrics` aggregates outcomes. Citation validity and completion status
  do not establish factual correctness.

Tests cover routing, retrieval, conflicts, citations, feedback, updates and failure
handling, with opt-in MiniLM and Ollama integration tests. The notebook demonstrates
the complete flow; test commands are in the README.

The current scope is a local demo without authentication, persistence or chat
memory. A production version would need durable state, access control and broader
answer-quality evaluation before scaling concurrency or changing the vector store.
