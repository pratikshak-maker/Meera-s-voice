"""Local sanity check for the Flask webhook route, using Flask's test client
(no real HTTP server, no deployment needed). Uses a fake chat_id so the
pipeline runs for real (triage/news/draft) but the final Telegram send fails
loudly in the logs instead of actually delivering anywhere - that's fine,
delivery itself was already proven by the live polling tests.

Run: python test_webhook.py
"""

import sys

for stream in (sys.stdout, sys.stderr):
    if hasattr(stream, "reconfigure"):
        stream.reconfigure(encoding="utf-8", errors="replace")

from config import WEBHOOK_SECRET
from app import app

FAKE_UPDATE = {
    "update_id": 999999001,
    "message": {
        "message_id": 1,
        "date": 1234567890,
        "chat": {"id": -999999, "type": "private"},
        "text": (
            "Had a customer email today saying our serum stung when she used it "
            "after her new AHA toner. I checked - her toner's pH is around 3, ours "
            "is 5.5-5.8. When you stack a low-pH exfoliant straight under a "
            "higher-pH serum, the mixing zone on skin sits somewhere in between "
            "for a few minutes, and that transition is when stinging shows up, "
            "especially on already-sensitized skin."
        ),
    },
}


def main():
    client = app.test_client()

    print("--- GET / (health check) ---")
    resp = client.get("/")
    print(resp.status_code, resp.get_data(as_text=True))

    print("\n--- POST /webhook without secret header (should 401 if WEBHOOK_SECRET is set) ---")
    resp = client.post("/webhook", json=FAKE_UPDATE)
    print(resp.status_code, resp.get_json())

    print("\n--- POST /webhook with correct secret header ---")
    headers = {"X-Telegram-Bot-Api-Secret-Token": WEBHOOK_SECRET} if WEBHOOK_SECRET else {}
    resp = client.post("/webhook", json=FAKE_UPDATE, headers=headers)
    print(resp.status_code, resp.get_json())
    print("\n(check the logging output above for the triage/draft run - the final")
    print("sendMessage call is expected to fail since chat_id -999999 doesn't exist)")


if __name__ == "__main__":
    main()
