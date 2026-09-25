import logging

from config import NOTIFY_ON_REJECT
from telegram_client import extract_fragment, send_message, get_file_path, download_file
from transcribe import transcribe_voice
from triage import triage_fragment
from news_context import find_news_angle
from draft import draft_post
from history import recent_categories, record_draft

log = logging.getLogger("pipeline")

VERDICT_LABELS = {
    "hold_needs_fresher_angle": "not developing this one as-is - needs a fresher angle",
    "hold_needs_verification": "holding this one - needs verification/redaction before it's safe to draft",
    "archive": "archiving this one - not enough here to build on",
}


def process_update(update: dict):
    fragment = extract_fragment(update)
    if fragment is None:
        return

    chat_id = fragment["chat_id"]

    # Sent before anything else, unconditionally - triage/news/draft can
    # each take 10-40s combined, and previously gave no sign of life until
    # (if) a verdict came back, which was indistinguishable from the
    # webhook never firing at all. This confirms receipt immediately.
    send_message(chat_id, "Got it - reading this now.")

    if fragment["kind"] == "voice":
        file_path = get_file_path(fragment["file_id"])
        audio_bytes = download_file(file_path)
        text = transcribe_voice(audio_bytes)
    else:
        text = fragment["text"]

    if not text or not text.strip():
        return

    log.info("Fragment %s: %s", fragment["fragment_id"], text[:80])

    recent = recent_categories(limit=2)
    triage = triage_fragment(text, recent_categories=recent)
    log.info("Triage verdict: %s (weighted_score=%s)", triage.get("verdict"), triage.get("weighted_score"))

    verdict = triage.get("verdict")

    if verdict != "draft_now":
        if NOTIFY_ON_REJECT:
            label = VERDICT_LABELS.get(verdict, "not developing this one")
            reason = triage.get("gate_reason") or triage.get("reasoning") or ""
            send_message(chat_id, f"{label}{(' - ' + reason) if reason else ''}")
        return

    news = find_news_angle(text, triage.get("category"))
    draft = draft_post(
        text,
        triage.get("category", ""),
        news.get("item"),
        triage_reasoning=triage.get("reasoning", ""),
    )

    message = format_draft_message(triage, draft)
    send_message(chat_id, message)

    record_draft(fragment["fragment_id"], draft.get("category_tag") or triage.get("category", ""))


def format_draft_message(triage: dict, draft: dict) -> str:
    lines = [
        "DRAFT - REVIEW NEEDED",
        "",
        draft.get("post_text", "").strip(),
        "",
        "---",
        f"Category: {draft.get('category_tag') or triage.get('category')} | Weighted score: {triage.get('weighted_score')}/5.0",
    ]
    ref = draft.get("current_reference_used")
    if ref:
        lines.append(f"Source used: {ref}")
    notes = draft.get("review_notes")
    if notes:
        lines.append(f"Review notes: {notes}")
    return "\n".join(lines)
