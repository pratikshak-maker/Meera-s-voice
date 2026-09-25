"""Stage 3 - Draft Generation. Uses Gemini (same provider as triage/transcribe,
no separate API key needed).

Quality is enforced two ways: a strong system prompt grounded in the full
voice skill + published corpus, and a deterministic post-generation check
against the voice skill's hard, checkable rules (banned words, emoji,
hashtags, exclamation points) with one automatic retry if violated - LLMs
follow "no hype words" instructions well but not perfectly, and this is
cheap insurance that doesn't depend on the model re-reading its own output
carefully.
"""

from __future__ import annotations

import json
import re
from google import genai
from google.genai import types
from config import GEMINI_API_KEY, GEMINI_DRAFT_MODEL, GROUNDING_DIR

client = genai.Client(api_key=GEMINI_API_KEY)

VOICE_SKILL = (GROUNDING_DIR / "voice_skill.txt").read_text(encoding="utf-8")
PUBLISHED_PIECES = (GROUNDING_DIR / "published_pieces.md").read_text(encoding="utf-8")

PERSONA_FACTS = """
PERSONA FACTS:
- Meera Pillai, founder of Skinstinct (D2C skincare, Mumbai, ~18 months old).
- Background: 2 years in pharmaceutical formulation before starting the brand.
  Not a dermatologist, no medical degree. Authority = formulation/documentation
  literacy, not clinical credentials.
- Products: currently sells one serum (pH 5.5-5.8, fragrance-free). Does NOT
  currently sell a Vitamin C product, a peptide product, or a sunscreen.
""".strip()

SYSTEM_INSTRUCTION = f"""
You are drafting a LinkedIn post for Meera Pillai (Skinstinct) from an
approved fragment, in her voice. This is a DRAFT for her review - it will
not be posted automatically. Never claim otherwise in your output.

{PERSONA_FACTS}

VOICE SKILL (the only ground truth for how she writes - match it specifically,
not a generic "confident founder" voice):
{VOICE_SKILL}

PUBLISHED PIECES (for calibration - do not repeat their content or reuse
their specific anecdotes):
{PUBLISHED_PIECES}

Follow the structure and rules in the voice skill exactly:
- Destabilizing opener (state the assumed claim, undercut it immediately)
- One concrete anchor (the fragment itself, or the current news angle, or both)
- Technical unpacking, ideally as a triad of factors
- At least one explicit hedge ("I'm not saying X, I'm saying Y")
- At least one short punch sentence directly after a longer one
- A direct, actionable instruction to the reader near the end
- If Skinstinct is mentioned, an explicit disclaimer that this isn't a pitch
- Plain sign-off, no CTA language, no hashtags, no emojis, no exclamation
  points, no hype vocabulary (banned list is in the voice skill)

If a news item is provided: if it is genuinely relevant, use it to make the
post timely. If it doesn't fit naturally, ignore it. Only cite it named and
dated, and only as far as it actually supports - do not force in a weak or
tangential reference, and do not fabricate any statistic, study, or quote
that isn't in the fragment or the news item.

Length: roughly 250-450 words.

Output valid JSON only, matching this schema:
{{
  "post_text": "the full draft post",
  "current_reference_used": "string or null - what was cited, if anything",
  "category_tag": "string",
  "needs_human_review": true | false,
  "review_notes": "anything Meera should verify before publishing"
}}
""".strip()

# TODO: placeholder text - replace with the exact required wording once confirmed.
NEWS_VERIFY_FLAG = "VERIFY SOURCE BEFORE PUBLISHING - this draft cites an external news item; confirm it's accurate and current."

BANNED_PHRASES = [
    "game-changing", "game changing", "revolutionary", "unlock", "supercharge",
    "must-have", "must have", "obsessed", "love this", "exciting news",
]
EMOJI_PATTERN = re.compile(
    "["
    "\U0001F300-\U0001FAFF"
    "\U00002600-\U000027BF"
    "\U0001F1E6-\U0001F1FF"
    "]+"
)


def _find_violations(post_text: str) -> list:
    violations = []
    lower = post_text.lower()

    for phrase in BANNED_PHRASES:
        if phrase in lower:
            violations.append(f'banned hype phrase "{phrase}"')

    if "!" in post_text:
        violations.append("contains an exclamation point")

    if re.search(r"(?<!\w)#\w+", post_text):
        violations.append("contains a hashtag")

    if EMOJI_PATTERN.search(post_text):
        violations.append("contains an emoji")

    return violations


def _generate(prompt: str) -> dict:
    response = client.models.generate_content(
        model=GEMINI_DRAFT_MODEL,
        contents=prompt,
        config=types.GenerateContentConfig(
            system_instruction=SYSTEM_INSTRUCTION,
            response_mime_type="application/json",
            temperature=0.6,
        ),
    )
    return json.loads(response.text)


def draft_post(fragment_text: str, category: str, news_item: dict | None, triage_reasoning: str = "") -> dict:
    if news_item:
        news_block = (
            f"- {news_item['title']} ({news_item.get('source', '')}, {news_item.get('date', '')})\n"
            f"  Summary: {news_item.get('summary', '')}\n"
            f"  Link: {news_item.get('link', '')}"
        )
    else:
        news_block = "(no news item found)"

    prompt = f"""
Fragment:
{fragment_text}

Category (from triage): {category}
Triage reasoning (why this fragment was picked): {triage_reasoning}

News item (judge relevance yourself, may not be relevant):
{news_block}
""".strip()

    try:
        result = _generate(prompt)
    except json.JSONDecodeError:
        return {
            "post_text": "",
            "current_reference_used": None,
            "category_tag": category,
            "needs_human_review": True,
            "review_notes": "Model did not return valid JSON.",
        }

    violations = _find_violations(result.get("post_text", ""))

    if violations:
        retry_prompt = f"""
{prompt}

Your previous draft violated these hard rules from the voice skill:
{chr(10).join(f"- {v}" for v in violations)}

Rewrite the post from scratch, fixing these specifically, while keeping
everything else about the structure and content. Same output schema.
""".strip()
        try:
            retried = _generate(retry_prompt)
            retry_violations = _find_violations(retried.get("post_text", ""))
            if len(retry_violations) < len(violations):
                result = retried
                violations = retry_violations
        except json.JSONDecodeError:
            pass

    if violations:
        note = f"Automated style check still found: {'; '.join(violations)} - please edit before publishing."
        result["review_notes"] = f"{result.get('review_notes', '') or ''} {note}".strip()
        result["needs_human_review"] = True

    # Enforced deterministically rather than trusted to the model - a draft
    # that cites a news item must carry this flag every time, not "usually."
    if result.get("current_reference_used"):
        post_text = result.get("post_text", "")
        if NEWS_VERIFY_FLAG not in post_text:
            result["post_text"] = f"{post_text.rstrip()}\n\n{NEWS_VERIFY_FLAG}"
        result["needs_human_review"] = True

    return result
