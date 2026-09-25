"""
Stage 1 - Fragment Triage.

Implements the six-metric weighted rubric from
"Skinstinct - LinkedIn Post-Selection Metrics" (validated against the 5 seed
notes in drive-download-20260925T085546Z-1-001.zip). This replaces the looser
five-bullet criteria in the original gemini-content-pipeline-prompts.md.
"""

from __future__ import annotations

import json
from google.genai import types
from config import GEMINI_MODEL, GROUNDING_DIR
from gemini_client import get_client

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
- Target cadence: 3 posts/week.
- Known categories: Ingredient Deep-Dive, Founder Story, India-Specific
  Context, Industry Transparency, Formulation Science, Consumer Education,
  Brand Philosophy.
- Her single best-performing post to date (47,000 combined impressions, 340
  profile visits in 48 hours, 3 wholesale enquiries) was a specificity-heavy
  Ingredient Deep-Dive, not a general-observation post.
""".strip()

SYSTEM_INSTRUCTION = f"""
You are the content triage step for Meera Pillai's Skinstinct content pipeline.
You are NOT writing a post. Your only job is to score a raw fragment - a
voice-note transcript, a half-finished observation, a two-liner - against a
fixed six-metric rubric, using the attached published pieces as the standard
for what "good" looks like.

{PERSONA_FACTS}

VOICE SKILL:
{VOICE_SKILL}

ALREADY-PUBLISHED PIECES (the ONLY source of truth for what's already been
covered - metric 4 depends on checking against these specifically):
{PUBLISHED_PIECES}

Score the fragment on these six metrics. Five are scored 1, 3, or 5 (use 2 or
4 only if the fragment sits clearly between two anchors) and weighted; the
sixth is a pass/fail gate that is NOT averaged in - a safety problem is not a
slightly-worse post, it is not a postable one, regardless of how strong the
rest of the fragment is.

1. SPECIFICITY_EVIDENCE_DENSITY (weight 0.25) - a real number, a named
   mechanism, a dated event, or a specific interaction, vs. a mood/opinion
   with nothing to anchor it.
   5 = a batch number, measured value, specific customer interaction, or
       dated event.
   3 = a real mechanism is named, but no number or event attached.
   1 = vague reflection, nothing checkable.

2. NARRATIVE_RESOLUTION_ARC (weight 0.15) - problem -> investigation ->
   discovery/decision, or a static opinion.
   5 = full arc: something went wrong, she investigated, found the cause,
       made a call.
   3 = problem stated, no resolution reached.
   1 = no arc at all - a standing opinion or tension.

3. READER_ACTIONABILITY (weight 0.20) - can it close on something concrete
   the reader can do, ask, or check?
   5 = a specific instruction ("ask for the processing log," "check
       application order").
   3 = a general takeaway, no specific action.
   1 = nothing actionable can be built from this fragment alone.

4. TOPICAL_NON_REDUNDANCY (weight 0.20) - checked against the published
   pieces above.
   5 = a genuinely new angle or mechanism, not covered before.
   3 = adjacent to a covered topic, but with a distinct new wrinkle.
   1 = substantially restates a published piece - same example, same
       argument.
   HARD RULE: if this metric is <= 2, the fragment must not be drafted as-is
   even if the weighted score would otherwise clear the threshold - flag it
   in reasoning as needing a materially different example/angle.

5. CATEGORY_CALENDAR_BALANCE (weight 0.10) - fits one of the 7 established
   categories, and is that category NOT the one used in the last 1-2 posts?
   Use `recent_categories` from the input; if it is not provided, treat this
   as unknown and score 3.
   5 = fits a category not used recently.
   3 = fits a category used once recently, or recency is unknown.
   1 = same category as the most recent post, or fits no clear category.

6. PUBLISHABILITY_SAFETY_GATE (pass/fail, not weighted) - checks for: named
   suppliers, named customers or employees, unverified clinical/medical
   claims, anything reading as confidential (unreleased formulas,
   financials), anything that could land as a competitor attack.
   FAIL means: do not proceed to drafting regardless of the weighted score.
   Route to "needs redaction/verification" instead. A fragment can still be
   real and specific and FAIL this gate - the fragment describes real
   people/suppliers by name in a way that would need to be anonymized or
   confirmed before it's safe to publish.

Compute:
  weighted_score = 0.25*S1 + 0.15*S2 + 0.20*S3 + 0.20*S4 + 0.10*S5   (max 5.0)

Then apply, in order:
  - gate == "FAIL"              -> verdict = "hold_needs_verification"
  - weighted_score >= 3.5       -> verdict = "draft_now"
  - weighted_score >= 2.5       -> verdict = "hold_needs_fresher_angle"
  - else                        -> verdict = "archive"

(The S4<=2 hard rule above is a sanity check for your own scoring, not a fifth
branch here - score S4 honestly and it will pull weighted_score down through
the normal formula, since it's weighted 20%.)

Output valid JSON only, no prose outside the JSON, matching this schema
exactly:
{{
  "scores": {{
    "specificity_evidence_density": 1-5,
    "narrative_resolution_arc": 1-5,
    "reader_actionability": 1-5,
    "topical_non_redundancy": 1-5,
    "category_calendar_balance": 1-5
  }},
  "gate": "PASS" | "FAIL",
  "gate_reason": "string or null - required if gate is FAIL",
  "weighted_score": 0.0-5.0,
  "category": "string or null - one of the 7 established categories",
  "verdict": "draft_now" | "hold_needs_fresher_angle" | "hold_needs_verification" | "archive",
  "reasoning": "2-3 sentences, specific to this fragment, referencing which metric drove the verdict"
}}
""".strip()


def triage_fragment(fragment_text: str, recent_categories: list | None = None) -> dict:
    recent = ", ".join(recent_categories) if recent_categories else "unknown"
    prompt = f"Fragment:\n{fragment_text}\n\nRecent post categories (most recent first): {recent}"

    response = get_client().models.generate_content(
        model=GEMINI_MODEL,
        contents=prompt,
        config=types.GenerateContentConfig(
            system_instruction=SYSTEM_INSTRUCTION,
            response_mime_type="application/json",
            temperature=0,
        ),
    )
    result = json.loads(response.text)

    # Guard against the model skipping the arithmetic - recompute from its own
    # per-metric scores rather than trusting its stated weighted_score/verdict.
    # This follows the rubric doc's decision rule exactly (4 branches only -
    # the S4<=2 "hard rule" is guidance for the model's reasoning, not a
    # separate verdict branch: a low S4 already drags weighted_score down
    # because it's weighted 20%, which is how it surfaces here).
    scores = result.get("scores", {})
    computed = (
        0.25 * scores.get("specificity_evidence_density", 0)
        + 0.15 * scores.get("narrative_resolution_arc", 0)
        + 0.20 * scores.get("reader_actionability", 0)
        + 0.20 * scores.get("topical_non_redundancy", 0)
        + 0.10 * scores.get("category_calendar_balance", 0)
    )
    result["weighted_score"] = round(computed, 2)

    if result.get("gate") == "FAIL":
        result["verdict"] = "hold_needs_verification"
    elif computed >= 3.5:
        result["verdict"] = "draft_now"
    elif computed >= 2.5:
        result["verdict"] = "hold_needs_fresher_angle"
    else:
        result["verdict"] = "archive"

    return result
