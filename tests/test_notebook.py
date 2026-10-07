"""Exercise the actual notebook cells that select the mode and display failures."""

import json

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
    namespace = {}
    exec(code_cell("import json"), namespace)
    assert namespace["system"].llm.provider == provider


def test_notebook_reports_planner_error_instead_of_crashing_on_missing_plan(system):
    def fail(*args):
        raise LLMError("plan: simulated provider unavailable")

    system.llm.generate = fail
    with pytest.raises(AssertionError, match="plan: simulated provider unavailable"):
        exec(code_cell("queries = ["), {"system": system})
