"""Vercel entrypoint. Telegram pushes each update here via webhook instead of
this process polling getUpdates - required because Vercel functions are
short-lived request handlers, not long-running processes (main.py's polling
loop can't run there at all).

All pipeline logic (triage -> news -> draft -> reply) is unchanged and lives
in pipeline.py; this file only swaps how an update arrives.
"""

from __future__ import annotations

import logging

from flask import Flask, jsonify, request

from config import WEBHOOK_SECRET
from pipeline import process_update

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger("app")

app = Flask(__name__)


@app.get("/")
def health():
    return "Skinstinct content pipeline is running.", 200


@app.post("/webhook")
def webhook():
    if WEBHOOK_SECRET:
        header = request.headers.get("X-Telegram-Bot-Api-Secret-Token", "")
        if header != WEBHOOK_SECRET:
            log.warning("Rejected webhook call with bad/missing secret token")
            return jsonify({"ok": False}), 401

    update = request.get_json(silent=True)
    if not update:
        return jsonify({"ok": False, "error": "no JSON body"}), 400

    try:
        process_update(update)
    except Exception:
        # Always 200 back to Telegram regardless of our own failure - a
        # non-200 makes Telegram retry the same update repeatedly, which
        # would re-run (and re-bill) the Gemini calls for no benefit.
        log.exception("Failed to process update %s", update.get("update_id"))

    return jsonify({"ok": True}), 200
