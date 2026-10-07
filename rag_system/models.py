"""Validated messages passed between the planner, agents, API and notebook."""

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

Domain = Literal["technical", "business", "compliance"]
DOMAINS: tuple[Domain, ...] = ("technical", "business", "compliance")


class Message(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)


class Document(Message):
    """A short, atomic synthetic passage; fact_key plus scope defines a comparable fact."""

    id: str = Field(pattern=r"^[a-z0-9_-]{1,64}$")
    domain: Domain
    title: str = Field(min_length=1, max_length=200)
    text: str = Field(min_length=1, max_length=3000)
    fact_key: str = Field(min_length=1, max_length=100)
    scope: str = Field(min_length=1, max_length=100)
    value: str = Field(min_length=1, max_length=200)
    authority: float = Field(ge=0, le=1)
    version: int = Field(default=1, ge=1)

    @property
    def source_id(self) -> str:
        return f"{self.id}@v{self.version}#0"

    @property
    def fact(self) -> tuple[str, str]:
        return self.fact_key, self.scope


class Query(Message):
    text: str = Field(min_length=3, max_length=2000)

    @field_validator("text")
    @classmethod
    def has_words(cls, value: str) -> str:
        if not any(c.isalpha() for c in value):
            raise ValueError("Query must contain words")
        return value


class Task(Message):
    domain: Domain
    subquery: str = Field(min_length=3, max_length=2000)


class Plan(Message):
    tasks: list[Task] = Field(max_length=3)
    complexity: Literal["simple", "complex"]
    reason: str = Field(min_length=1, max_length=500)

    @model_validator(mode="after")
    def unique_domains(self):
        if len({t.domain for t in self.tasks}) != len(self.tasks):
            raise ValueError("Only one task per domain is allowed")
        return self


class Claim(Message):
    text: str = Field(min_length=1, max_length=2000)
    source_ids: list[str] = Field(min_length=1, max_length=10)


class Draft(Message):
    claims: list[Claim] = Field(max_length=12)


class Evidence(Message):
    document: Document
    similarity: float
    confidence: float
    feedback_weight: float


class Conflict(Message):
    fact_key: str
    scope: str
    candidates: list[Evidence]
    selected_source_id: str | None
    reason: str


class AgentResult(Message):
    task: Task
    top_k: int
    min_similarity: float
    retrieved: list[Evidence] = Field(default_factory=list)
    evidence: list[Evidence] = Field(default_factory=list)
    claims: list[Claim] = Field(default_factory=list)
    elapsed_ms: float = 0
    error: str | None = None


class Answer(Message):
    request_id: str
    mode: Literal["mock", "live"]
    embedding_backend: str
    status: Literal["answered", "partial", "no_evidence", "failed"]
    answer: str
    plan: Plan | None
    results: list[AgentResult]
    citations: list[Evidence]
    conflicts: list[Conflict]
    timings_ms: dict[str, float]
    llm_calls: int
    input_tokens: int
    output_tokens: int
    error: str | None = None


class Feedback(Message):
    request_id: str
    source_id: str
    helpful: bool
