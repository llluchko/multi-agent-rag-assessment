# Implementation plan

1. Scaffold the repository and pin dependencies.
2. Add synthetic knowledge, typed contracts, local embeddings and vector retrieval.
3. Implement mock/live LLM adapters, routing, domain agents and orchestration.
4. Demonstrate dynamic retrieval, conflicts, citation tracking, updates and feedback.
5. Expose the common core through FastAPI.
6. Add contract tests, separate retrieval evaluation and an executable notebook.
7. Package with Docker and write setup, trade-offs and verification results.
8. Add a small optional React client only after the core passes.

Scope: short English synthetic documents, one process, CPU embeddings, one LLM
provider. The mock mode is explicit. No autonomous loops, message broker, external
vector database or production deployment. Changes are committed incrementally.

Adapted from LLM Zoomcamp: grounded retrieval, vector search, evaluation separated
by stage, and observable execution. Hybrid search and reranking need measured
justification before being added.

References:
- https://datatalks.club/blog/llm-zoomcamp.html
- https://developers.openai.com/api/docs/guides/structured-outputs
