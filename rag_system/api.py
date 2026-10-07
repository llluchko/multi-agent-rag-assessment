"""A thin OpenAPI boundary around the same application used by the notebook."""

from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException, Request

from .bootstrap import build_system
from .models import Answer, Document, Feedback, Query


def create_app(system=None) -> FastAPI:
    @asynccontextmanager
    async def lifespan(app):
        app.state.system = system or build_system()
        yield

    app = FastAPI(title="Multi-agent RAG", version="0.1.0", lifespan=lifespan)

    @app.get("/health")
    def health(request: Request):
        s = request.app.state.system
        return {
            "status": "ready",
            "mode": s.llm.mode,
            "llm_provider": s.llm.provider,
            "embedding_backend": s.store.embedder.name,
        }

    @app.post(
        "/query",
        response_model=Answer,
        responses={502: {"model": Answer, "description": "Model failure with trace"}},
    )
    def query(body: Query, request: Request):
        # Business-level partial/no-evidence outcomes use 200 and explicit status.
        answer = request.app.state.system.query(body.text)
        if answer.status == "failed":
            from fastapi.responses import JSONResponse

            return JSONResponse(status_code=502, content=answer.model_dump(mode="json"))
        return answer

    @app.put("/documents/{document_id}")
    def upsert(document_id: str, body: Document, request: Request):
        if document_id != body.id:
            raise HTTPException(422, "Path and document ID must match")
        try:
            changed = request.app.state.system.upsert(body)
        except ValueError as exc:
            raise HTTPException(409, str(exc)) from exc
        return {"changed": changed, "source_id": body.source_id}

    @app.post("/feedback")
    def feedback(body: Feedback, request: Request):
        try:
            weight = request.app.state.system.submit_feedback(body)
        except ValueError as exc:
            raise HTTPException(409, str(exc)) from exc
        return {"source_id": body.source_id, "weight": weight}

    @app.get("/metrics")
    def metrics(request: Request):
        return request.app.state.system.metrics()

    return app


app = create_app()
