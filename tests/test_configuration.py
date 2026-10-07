"""Configuration is shared by API and notebook, without mutating process environment."""

import pytest

from rag_system import bootstrap


@pytest.fixture
def config_file(tmp_path, monkeypatch):
    (tmp_path / "data").mkdir()
    (tmp_path / "data" / "knowledge.json").write_text(
        (bootstrap.ROOT / "data" / "knowledge.json").read_text()
    )
    monkeypatch.setattr(bootstrap, "ROOT", tmp_path)
    for key in ("LLM_PROVIDER", "OLLAMA_URL", "OLLAMA_MODEL"):
        monkeypatch.delenv(key, raising=False)
    return tmp_path / ".env"


def test_defaults_and_reloading_dotenv(config_file):
    assert bootstrap.build_system(embedding_backend="lexical").llm.provider == "mock"
    config_file.write_text('LLM_PROVIDER=ollama\nOLLAMA_MODEL="qwen3:4b"\n')
    llm = bootstrap.build_system(embedding_backend="lexical").llm
    assert llm.provider == "ollama"
    assert llm.base_url == "http://localhost:11434"
    config_file.write_text("LLM_PROVIDER=mock\n")
    assert bootstrap.build_system(embedding_backend="lexical").llm.provider == "mock"


def test_environment_and_explicit_arguments_override_dotenv(config_file, monkeypatch):
    config_file.write_text("LLM_PROVIDER=mock\nOLLAMA_URL=http://localhost:11434\n")
    monkeypatch.setenv("LLM_PROVIDER", "ollama")
    monkeypatch.setenv("OLLAMA_URL", "http://host.docker.internal:11434")
    llm = bootstrap.build_system(embedding_backend="lexical").llm
    assert llm.provider == "ollama"
    assert llm.base_url == "http://host.docker.internal:11434"
    assert bootstrap.build_system("mock", "lexical").llm.provider == "mock"


def test_invalid_provider_does_not_silently_use_mock(config_file):
    config_file.write_text("LLM_PROVIDER=typo\n")
    with pytest.raises(ValueError, match="mock or ollama"):
        bootstrap.build_system(embedding_backend="lexical")
