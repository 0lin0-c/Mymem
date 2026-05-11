import json
from pathlib import Path


QUESTIONS = [
    "When did Caroline go to the LGBTQ support group?",
    "When did Caroline meet up with her friends, family, and mentors?",
    "How long has Caroline had her current group of friends for?",
    "Who supports Caroline when she has a negative experience?",
    "What workshop did Caroline attend recently?",
]

FILES = {
    "baseline": Path("test_results/converted_data/legacy/mymem_test_results_20260421_173554.json"),
    "tuned": Path("test_results/converted_data/legacy/mymem_test_results_20260422_010054.json"),
}


def load_results(path: Path) -> dict[str, dict]:
    data = json.loads(path.read_text(encoding="utf-8"))
    sample = data["samples"][0]
    out = {}
    for item in sample["qa_results"]:
        q = item["question"]
        if q in QUESTIONS:
            out[q] = item
    return out


def main() -> None:
    all_results = {name: load_results(path) for name, path in FILES.items()}
    for question in QUESTIONS:
        print(f"## {question}")
        for label in ("baseline", "tuned"):
            item = all_results[label].get(question)
            if not item:
                print(f"[{label}] missing")
                continue
            trace = item.get("trace_summary") or {}
            print(
                f"[{label}] "
                f"is_correct={item.get('is_correct')} "
                f"storage_hit={item.get('storage_hit')} "
                f"retrieval_hit={item.get('retrieval_hit')} "
                f"rank={item.get('rank_position')} "
                f"layer={trace.get('resolved_layer')} "
                f"failure_type={item.get('failure_type')}"
            )
            top_contexts = trace.get("top_contexts") or []
            if top_contexts:
                print(f"[{label}] top1={top_contexts[0]}")
            print(f"[{label}] answer={item.get('generated_answer')}")
        print()


if __name__ == "__main__":
    main()
