import pytest

from rag_system.bootstrap import build_system


@pytest.fixture
def system():
    return build_system("mock", "lexical")
