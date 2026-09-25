"""Single lazy Gemini client shared by triage/transcribe/draft/news_context.

Constructed on first use, not at import time. Four modules used to each call
genai.Client(api_key=...) at module load, which meant a missing/bad
GEMINI_API_KEY crashed the entire app on import - including routes that
don't need Gemini at all, like the Vercel health check. Now a missing key
only fails the specific request that actually needs the client.
"""

from __future__ import annotations

from google import genai
from config import GEMINI_API_KEY

_client: genai.Client | None = None


def get_client() -> genai.Client:
    global _client
    if _client is None:
        _client = genai.Client(api_key=GEMINI_API_KEY)
    return _client
