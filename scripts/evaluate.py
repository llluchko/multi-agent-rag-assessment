"""Run from the repository root: python -m scripts.evaluate."""

import json

from rag_system.bootstrap import ROOT, build_system
from rag_system.evaluation import evaluate

if __name__ == "__main__":
    report = evaluate(build_system())
    output = ROOT / ".cache" / "evaluation.json"
    output.parent.mkdir(exist_ok=True)
    output.write_text(json.dumps(report, indent=2) + "\n")
    print(json.dumps({k: v for k, v in report.items() if k != "rows"}, indent=2))
    print(f"Details: {output}")
