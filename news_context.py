"""Stage 2 - Current Angle Finder.

1. Extract keywords - ask Gemini to pull 3-5 search terms from the approved
   fragment and return a short search phrase.
2. Fetch news - use that phrase to search Google News RSS (no account, no
   key). Pull the top result: headline, source, date, and a one-line summary.

Relevance judgement is deliberately NOT done here - it's passed to Gemini in
Stage 3 alongside the fragment and voice skill, with the instruction: use it
if it's genuinely relevant, ignore it if it doesn't fit naturally.
"""

from __future__ import annotations

import html
import json
import re
from urllib.parse import quote_plus

import feedparser
import requests
from google.genai import types
from config import GEMINI_MODEL
from gemini_client import get_client

KEYWORD_SYSTEM_INSTRUCTION = """
You extract search terms for a news lookup. Given a raw content fragment,
pull the 3-5 words/phrases that best capture what it's actually about (the
mechanism, ingredient, or specific event - not generic skincare filler
words), and combine them into one short search phrase suitable for a news
search engine - not a full sentence, no punctuation.

Output valid JSON only:
{"keywords": ["...", "..."], "query": "short search phrase"}
""".strip()


def _extract_query(fragment_text: str) -> str:
    response = get_client().models.generate_content(
        model=GEMINI_MODEL,
        contents=f"Fragment:\n{fragment_text}",
        config=types.GenerateContentConfig(
            system_instruction=KEYWORD_SYSTEM_INSTRUCTION,
            response_mime_type="application/json",
            temperature=0,
        ),
    )
    try:
        result = json.loads(response.text)
        query = result.get("query", "").strip()
        return query or fragment_text[:80]
    except json.JSONDecodeError:
        return fragment_text[:80]


def find_news_angle(fragment_text: str, category: str | None = None) -> dict:
    query = _extract_query(fragment_text)
    url = f"https://news.google.com/rss/search?q={quote_plus(query)}&hl=en-IN&gl=IN&ceid=IN:en"

    try:
        resp = requests.get(url, timeout=15)
        resp.raise_for_status()
    except requests.RequestException:
        return {"query": query, "item": None}

    feed = feedparser.parse(resp.content)
    if not feed.entries:
        return {"query": query, "item": None}

    entry = feed.entries[0]
    raw_summary = getattr(entry, "summary", "") or getattr(entry, "title", "")
    # Google News RSS summaries are an HTML anchor tag, not plain text.
    summary = html.unescape(re.sub(r"<[^>]+>", "", raw_summary)).strip()

    item = {
        "title": getattr(entry, "title", ""),
        "source": getattr(getattr(entry, "source", None), "title", "") or "",
        "date": getattr(entry, "published", ""),
        "summary": summary,
        "link": getattr(entry, "link", ""),
    }

    return {"query": query, "item": item}
