from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from app.services.ai_model_evaluation import (  # noqa: E402
    load_evaluation_tasks,
    run_evaluation_sync,
    build_evaluation_report,
    write_results,
)


def main() -> int:
    parser = argparse.ArgumentParser(description="Run LexFlow legal AI model evaluation tasks.")
    parser.add_argument(
        "--providers",
        nargs="+",
        default=["gemini", "cohere", "openrouter", "ollama"],
        help="Provider names to evaluate. Uses existing environment config for each provider.",
    )
    parser.add_argument(
        "--tasks",
        default=str(BACKEND_ROOT / "app" / "evaluation" / "legal_model_tasks.json"),
        help="Path to evaluation task JSON file.",
    )
    parser.add_argument(
        "--output",
        default=str(BACKEND_ROOT / "evaluation_results" / "latest_model_eval.json"),
        help="Output JSON path for detailed results.",
    )
    args = parser.parse_args()

    tasks = load_evaluation_tasks(args.tasks)
    results = run_evaluation_sync(args.providers, tasks)
    write_results(args.output, results)

    report = build_evaluation_report(results)
    print(json.dumps({"results_path": args.output, **report}, ensure_ascii=False, indent=2))
    if not results:
        print("No active providers returned results. Check provider API keys/models in your .env.", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
