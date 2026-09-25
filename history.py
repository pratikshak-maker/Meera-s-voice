"""Tiny local log of recently-drafted categories, for triage metric 5
(Category & Calendar Balance) and for dedupe context over time. A JSON file
is enough here - this pipeline processes one fragment per Telegram message,
so there's no batch dedupe step to replicate from the original spec.
"""

import json
from datetime import datetime, timezone
from config import HISTORY_FILE

MAX_RECENT = 10


def _load() -> list:
    if not HISTORY_FILE.exists():
        return []
    try:
        return json.loads(HISTORY_FILE.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return []


def recent_categories(limit: int = 2) -> list:
    entries = _load()
    return [e["category"] for e in entries[-limit:] if e.get("category")][::-1]


def record_draft(fragment_id: str, category: str):
    entries = _load()
    entries.append(
        {
            "fragment_id": fragment_id,
            "category": category,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
    )
    entries = entries[-MAX_RECENT:]
    HISTORY_FILE.write_text(json.dumps(entries, indent=2), encoding="utf-8")
