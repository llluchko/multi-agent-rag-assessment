"""Exercise the actual notebook cells that select the mode and display failures."""

import json

import httpx
import pytest

from rag_system.bootstrap import ROOT
from rag_system.llm import LLMError


def code_cell(prefix):
    notebook = json.loads((ROOT / "notebooks" / "demo.ipynb").read_text())
    return next(
        "".join(cell["source"])
        for cell in notebook["cells"]
        if cell["cell_type"] == "code" and "".join(cell["source"]).startswith(prefix)
    )


@pytest.mark.parametrize("provider", ["mock", "ollama"])
def test_notebook_uses_the_same_provider_configuration_as_the_api(monkeypatch, provider):
    monkeypatch.chdir(ROOT)
    monkeypatch.setenv("LLM_PROVIDER", provider)
    monkeypatch.setenv("EMBEDDING_BACKEND", "lexical")
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    monkeypatch.setenv("OLLAMA_URL", "http://ollama.test:11434")
    calls = []

    def available(url, **kwargs):
        calls.append(url)
        return httpx.Response(200, request=httpx.Request("GET", url))

    monkeypatch.setattr(httpx, "get", available)
    namespace = {}
    exec(code_cell("import json"), namespace)
    assert namespace["system"].llm.provider == provider
    assert calls == (["http://ollama.test:11434/api/tags"] if provider == "ollama" else [])


def test_notebook_explains_how_to_recover_when_ollama_is_unavailable(monkeypatch):
    monkeypatch.chdir(ROOT)
    monkeypatch.setenv("LLM_PROVIDER", "ollama")
    monkeypatch.setenv("EMBEDDING_BACKEND", "lexical")

    def unavailable(*args, **kwargs):
        raise httpx.ConnectError("Connection refused")

    monkeypatch.setattr(httpx, "get", unavailable)
    with pytest.raises(RuntimeError, match="Start the Ollama app") as error:
        exec(code_cell("import json"), {})
    assert "docker compose up -d api notebook" in str(error.value)


def test_notebook_does_not_repeat_executable_cells():
    notebook = json.loads((ROOT / "notebooks" / "demo.ipynb").read_text())
    sources = [
        "".join(cell["source"]).strip()
        for cell in notebook["cells"]
        if cell["cell_type"] == "code" and "".join(cell["source"]).strip()
    ]
    assert len(sources) == len(set(sources)), "Repeated cells can reset demo state"


def test_notebook_reports_planner_error_instead_of_crashing_on_missing_plan(system):
    def fail(*args):
        raise LLMError("plan: simulated provider unavailable")

    system.llm.generate = fail
    with pytest.raises(AssertionError, match="plan: simulated provider unavailable"):
        exec(code_cell("queries = ["), {"system": system})
