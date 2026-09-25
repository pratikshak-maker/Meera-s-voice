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

There are two ways to run this - pick one, don't run both at once (Telegram doesn't
allow polling and a webhook to be active on the same bot simultaneously):

- **Local polling** (`main.py`) - simplest for development, no public URL needed.
- **Vercel webhook** (`app.py`) - for a real deployment. Vercel functions are
  short-lived request handlers, not long-running processes, so `main.py`'s `while True`
  polling loop cannot run there at all - Telegram has to push each update to us instead.

## Setup (local polling)

1. `python -m venv .venv` then activate it, then `pip install -r requirements.txt`
2. Copy `.env.example` to `.env` if you don't already have one, and fill in the keys
   (see table below).
3. **Add the bot as an admin of the Telegram channel/group Meera posts fragments into.**
   Bots cannot see channel posts unless they are an admin, even with the right token -
   this is a Telegram platform restriction, not something the code can work around.
4. `python test_triage.py` - sanity-checks Stage 1 against the 5 seed notes and your
   Gemini key, no Telegram needed.
5. `python main.py` - starts the live polling loop.

## Deploying to Vercel (webhook)

1. Push to GitHub and import the repo in Vercel (or let an already-connected repo
   redeploy). Vercel auto-detects `app.py` as a Python/Flask function because it
   exports a top-level `app`.
2. In the Vercel project's Settings -> Environment Variables, set `TELEGRAM_BOT_TOKEN`,
   `GEMINI_API_KEY`, `WEBHOOK_SECRET` (any random string - generate one with
   `python -c "import secrets; print(secrets.token_hex(24))"`), and optionally
   `GEMINI_MODEL` / `GEMINI_DRAFT_MODEL`. These are **not** read
   from `.env` in production - `.env` is gitignored and never deployed.
3. Deploy. Note the resulting URL (e.g. `https://your-project.vercel.app`).
4. Register the webhook with Telegram (replace the placeholders):
   ```
   curl "https://api.telegram.org/bot<TELEGRAM_BOT_TOKEN>/setWebhook?url=https://your-project.vercel.app/webhook&secret_token=<WEBHOOK_SECRET>"
   ```
   From this point on Telegram pushes every message to that URL instead of anything
   polling for it - stop any local `python main.py` process first, or it and the
   webhook will both try to handle the same messages.
5. Sanity check: `curl https://your-project.vercel.app/` should return "Skinstinct
   content pipeline is running."

Two Vercel-specific things already handled in the code, carried over from lessons
learned deploying the sibling project on this same account:
- `.python-version` pins Python 3.12, and `from __future__ import annotations` guards
  every file using `X | None` style type hints, since an older interpreter parsing
  those directly has broken Vercel Python builds here before.
- `vercel.json` sets `maxDuration: 60` on `app.py` - the triage + news + draft chain
  can take 20-40s end to end (more with the draft.py retry), which exceeds Vercel's
  10s default.
- `history.py`'s state file lives in the OS temp dir (`/tmp` on Vercel), never in the
  project directory, which is read-only at runtime.

## Keys

| Env var | Where to get it | Notes |
|---|---|---|
| `TELEGRAM_BOT_TOKEN` | [@BotFather](https://t.me/BotFather) on Telegram | |
| `GEMINI_API_KEY` | [aistudio.google.com/apikey](https://aistudio.google.com/apikey) | Used for everything AI-side: triage (`triage.py`), voice transcription (`transcribe.py`), and drafting (`draft.py`) |
| `WEBHOOK_SECRET` | Generate your own (see step 2 above) | Only used by `app.py` - validates that webhook calls actually came from Telegram, not an open POST endpoint anyone can hit |

`TELEGRAM_CHAT_ID` is deliberately not a config value - each reply goes back to
whichever chat the incoming message came from, read from the update itself.

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
- `pipeline.py` - orchestrates one fragment end to end (shared by both entrypoints)
- `main.py` - local polling loop entrypoint
- `app.py` - Vercel/Flask webhook entrypoint
- `vercel.json`, `.python-version` - Vercel deployment config
- `grounding/voice_skill.txt`, `grounding/published_pieces.md` - the only ground truth
  for Meera's voice and what's already been published; attached to every AI call
- `test_notes/`, `test_triage.py` - the 5 seed notes and a harness to validate Stage 1
  against the expected scores/verdicts in the rubric doc

## Tuning

- Triage thresholds (`draft_now` >= 3.5, `hold` >= 2.5, else `archive`) and metric
  weights live in the system instruction in `triage.py` - the rubric doc is the source
  of truth, edit both together if you change it.
- Every incoming fragment always gets a reply - an immediate "Got it" acknowledgment,
  then either a draft or the full triage verdict/reasoning. This is intentionally not
  configurable: an env-var-gated version of this silently dropped replies in
  production with no visible error, so it was removed rather than debugged further.
