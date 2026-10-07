# Validation record

Validated on **7 October 2026**, native macOS x86-64, Python 3.13, Node 24.14.0.
The new repository has its own `.venv` and frontend dependencies. The embedding model
is cached locally and pinned to revision `d13954661f83248295ba75c1ed411eef3b7b936e`.

## Executed checks

| Check | Result |
| --- | --- |
| `RUN_SEMANTIC=1 python -m pytest -q` | **27 passed, 1 skipped** |
| Skipped live test | No API key; explicitly requires `RUN_LIVE_LLM=1` |
| Notebook from a fresh kernel | **All 10 code cells passed**, mock LLM + actual MiniLM |
| Ruff lint and format | Passed |
| React TypeScript check and Vite build | Passed |
| Browser end-to-end check | Simplified question form → Docker API → visible answer and source/agent controls |
| Native API | Started on localhost; health, OpenAPI and query response verified |
| Compose file | Parsed as YAML; services and optional UI profile checked |
| Docker image/build/runtime | Docker Desktop: images built, API healthy, notebook and UI started |
| Tests inside Docker before the orchestration refactor | **27 passed, 1 skipped**, actual MiniLM with offline model cache |
| Notebook inside Docker before the orchestration refactor | **All 10 code cells passed** from a fresh kernel; saved user outputs left unchanged |
| OpenAI provider contract | HTTP request/response tests with mock transport; **no real model call** |

After extracting named orchestration steps, the native suite again passed **27 tests**
(one live test skipped), all **10 notebook code cells** passed from a fresh kernel,
and Ruff plus the TypeScript/Vite build passed. Notebook validation did not overwrite
the user's saved outputs. Docker runtime checks above precede the Python refactor;
rebuild containers to load the updated source.

The test suite emits a Starlette deprecation notice for its httpx test client; tests
still pass. Notebook kernel transport emitted a local TCP warning from Jupyter.
Neither message was hidden or treated as a test failure.

## Evaluation results

See the committed [mock evaluation report](evaluation_mock.json). These are 24
hand-authored development cases, including the three assignment examples. They are
not an independent holdout and must not be presented as a general accuracy benchmark.

- Mock routing exact-domain accuracy: **24/24**.
- Mean raw retrieval recall at the dynamic budget, over 21 answerable cases: **1.0**.
- Diagnostic success: **23/24 (95.8%)**.
- All three assignment examples passed.

Diagnostic success means correct routed domains, expected status and expected source
coverage. It does **not** check semantic entailment, completeness, style or correctness
of a live generated answer. High recall does not imply high retrieval precision; mock
answers can include more context than necessary.

### Known failing case

`unknown-tech`: “How do I repair the quantum database flux capacitor API?”

Expected: no evidence. Actual: generic API troubleshooting evidence is returned and
extracted by the mock generator. Familiar vocabulary can pass the similarity threshold
even though the question is unanswerable. A real model is instructed to abstain, but
that behavior is unverified until live evaluation is run. We keep the failing case
visible instead of hard-coding a special answer or increasing a threshold to fit it.

## Manual live quality review

After supplying a key, execute the notebook and evaluation in live mode. For each
assignment example, an unknown-domain question, the in-domain unanswerable question,
and both conflict cases, inspect:

1. Did routing select the necessary domains without unrelated work?
2. Did the subqueries preserve the original constraints?
3. Do the cited passages actually support each generated claim, including units and exceptions?
4. Does the answer cover all requested parts without extraneous advice?
5. Does it abstain when evidence is missing and expose unresolved contradictions?
6. Are partial failures clearly marked rather than presented as complete answers?

Record qualitative findings and actual provider/model usage separately from mock
metrics. A valid source ID and an HTTP 200 response do not establish answer correctness.

## Remaining verification before interview submission

- Repeat Docker startup on a clean checkout if the submission machine differs from this host.
- Run the real LLM mode with an available API key and review answer quality using the rubric.
- Complete the separate Systems Design task if submitting the full assignment.
- Publish this local repository to GitHub when ready; it has no configured remote.

No production deployment, durable shared state, authenticated access or cross-platform
runtime test is claimed by this first version.
