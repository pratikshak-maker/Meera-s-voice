"""Full end-to-end dry run over the 5 seed notes: triage -> news -> draft.
No Telegram needed - just prints what would be sent back to Meera.

Run: python test_pipeline.py
"""

import json
import sys
from pathlib import Path

for stream in (sys.stdout, sys.stderr):
    if hasattr(stream, "reconfigure"):
        stream.reconfigure(encoding="utf-8", errors="replace")

from triage import triage_fragment
from news_context import find_news_angle
from draft import draft_post
from pipeline import format_draft_message, VERDICT_LABELS

NOTES_PATH = Path(__file__).parent / "test_notes" / "notes.json"


def main():
    notes = json.loads(NOTES_PATH.read_text(encoding="utf-8"))
    recent = []

    for note in notes:
        print("=" * 100)
        print(f"NOTE: {note['id']}")
        print("=" * 100)

        triage = triage_fragment(note["text"], recent_categories=recent)
        print(f"Triage verdict: {triage['verdict']} (weighted_score={triage['weighted_score']})")
        print(f"Category: {triage.get('category')}")
        print(f"Reasoning: {triage.get('reasoning')}")

        if triage["verdict"] != "draft_now":
            label = VERDICT_LABELS.get(triage["verdict"], "not developing this one")
            reason = triage.get("gate_reason") or triage.get("reasoning") or ""
            print(f"\n[Would send to Telegram]: {label}{(' - ' + reason) if reason else ''}")
            continue

        news = find_news_angle(note["text"], triage.get("category"))
        print(f"\nNews query used: {news['query']}")
        item = news.get("item")
        if item:
            print(f"Top result: {item['title']} ({item.get('source', '')}, {item.get('date', '')})")
            print(f"  Summary: {item.get('summary', '')}")
        else:
            print("Top result: none found")

        draft = draft_post(
            note["text"],
            triage.get("category", ""),
            item,
            triage_reasoning=triage.get("reasoning", ""),
        )

        message = format_draft_message(triage, draft)
        print("\n[Would send to Telegram]:\n")
        print(message)

        if triage.get("category"):
            recent.insert(0, draft.get("category_tag") or triage["category"])
            recent = recent[:2]

        print()


if __name__ == "__main__":
    main()
