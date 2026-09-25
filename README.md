# Skinstinct Content Pipeline

Telegram -> Gemini (triage) -> Google News (context) -> Gemini (draft) -> back to
Telegram, tagged "DRAFT - REVIEW NEEDED". Nothing is ever posted automatically; Meera
reviews and publishes herself.

Single-provider by design: Gemini handles transcription, triage, and drafting, so the
whole pipeline runs off one API key.

## Architecture

```
Meera (Telegram)  --voice/text-->  bot
  bot transcribes voice via Gemini (if needed)
  Gemini scores the fragment against the 6-metric rubric (triage.py)
    -> verdict: draft_now | hold_needs_fresher_angle | hold_needs_verification | archive
  if draft_now:
    Google News RSS fetches candidate context (news_context.py, no API key)
    Gemini drafts the post in Meera's voice (draft.py), judging news relevance itself
    bot sends the draft back to the same Telegram chat, tagged for review
  else:
    bot sends a short one-line note on why it's not being developed (optional)
```

This is a real-time, per-message pipeline (one fragment in, one decision out), not the
batched/cron version described in `gemini-content-pipeline-prompts.md` - simpler, and it
matches the swimlane diagram you sketched. No dedupe-against-processed-IDs step is
needed because there's no batching; `history.py` keeps a small rolling log of recent
categories purely for the rubric's "calendar balance" metric.

## Setup

1. `python -m venv .venv` then activate it, then `pip install -r requirements.txt`
2. Copy `.env.example` to `.env` if you don't already have one, and fill in the keys
   (see table below).
3. **Add the bot as an admin of the Telegram channel/group Meera posts fragments into.**
   Bots cannot see channel posts unless they are an admin, even with the right token -
   this is a Telegram platform restriction, not something the code can work around.
4. `python test_triage.py` - sanity-checks Stage 1 against the 5 seed notes and your
   Gemini key, no Telegram needed.
5. `python main.py` - starts the live polling loop.

## Keys

| Env var | Where to get it | Notes |
|---|---|---|
| `TELEGRAM_BOT_TOKEN` | [@BotFather](https://t.me/BotFather) on Telegram | |
| `TELEGRAM_CHAT_ID` | `getChat` / forward a message to `@userinfobot` | Must be a chat/channel/group the bot is a member (and, for channels, an *admin*) of |
| `GEMINI_API_KEY` | [aistudio.google.com/apikey](https://aistudio.google.com/apikey) | Used for everything AI-side: triage (`triage.py`), voice transcription (`transcribe.py`), and drafting (`draft.py`) |

Google News needs no key - `news_context.py` hits the public RSS search endpoint
(`news.google.com/rss/search`).

## Files

- `config.py` - env loading, required-key check
- `telegram_client.py` - getUpdates / sendMessage / file download
- `transcribe.py` - Gemini audio transcription for voice notes
- `triage.py` - Stage 1, the 6-metric weighted rubric
- `news_context.py` - Stage 2, free Google News RSS search
- `draft.py` - Stage 3, Gemini drafts in Meera's voice (`GEMINI_DRAFT_MODEL`, defaults
  to the same model as triage - point it at a stronger tier independently if voice
  quality needs it)
- `history.py` - rolling log of recently-drafted categories (rubric metric 5)
- `pipeline.py` - orchestrates one fragment end to end
- `main.py` - polling loop entrypoint
- `grounding/voice_skill.txt`, `grounding/published_pieces.md` - the only ground truth
  for Meera's voice and what's already been published; attached to every AI call
- `test_notes/`, `test_triage.py` - the 5 seed notes and a harness to validate Stage 1
  against the expected scores/verdicts in the rubric doc

## Tuning

- Triage thresholds (`draft_now` >= 3.5, `hold` >= 2.5, else `archive`) and metric
  weights live in the system instruction in `triage.py` - the rubric doc is the source
  of truth, edit both together if you change it.
- `NOTIFY_ON_REJECT=false` in `.env` silences the "not developing this one" pings and
  just logs locally instead.
