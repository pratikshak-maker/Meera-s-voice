"""Validate Stage 1 against the 5 seed notes and the expected verdicts from
the rubric doc. Run: python test_triage.py

Only needs GEMINI_API_KEY - no Telegram or Claude required.
"""

import json
import sys
from pathlib import Path

for stream in (sys.stdout, sys.stderr):
    if hasattr(stream, "reconfigure"):
        stream.reconfigure(encoding="utf-8", errors="replace")

from triage import triage_fragment

NOTES_PATH = Path(__file__).parent / "test_notes" / "notes.json"


def main():
    notes = json.loads(NOTES_PATH.read_text(encoding="utf-8"))

    print(f"{'note':<10} {'expected':<10} {'got':<10} {'exp_verdict':<26} {'got_verdict':<26} match")
    print("-" * 100)

    for note in notes:
        result = triage_fragment(note["text"])
        got_score = result.get("weighted_score")
        got_verdict = result.get("verdict")
        exp_score = note["expected_weighted_score"]
        exp_verdict = note["expected_verdict"]

        score_close = abs(got_score - exp_score) <= 0.6
        verdict_match = got_verdict == exp_verdict
        match = "OK" if (score_close and verdict_match) else "CHECK"

        print(
            f"{note['id']:<10} {exp_score:<10} {got_score:<10} {exp_verdict:<26} {got_verdict:<26} {match}"
        )
        if match == "CHECK":
            print(f"  reasoning: {result.get('reasoning')}")
            print(f"  scores: {result.get('scores')}")
            print(f"  gate: {result.get('gate')} ({result.get('gate_reason')})")


if __name__ == "__main__":
    main()
