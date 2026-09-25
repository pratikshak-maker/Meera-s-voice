import logging
import sys
import time

from config import check_required, OFFSET_FILE
from telegram_client import get_updates
from pipeline import process_update

# Windows consoles default to cp1252, which can't encode characters that
# show up routinely in real fragments (em-dashes, degree signs, <=/>=). Left
# unfixed, logging one of those crashes this long-running process outright.
for stream in (sys.stdout, sys.stderr):
    if hasattr(stream, "reconfigure"):
        stream.reconfigure(encoding="utf-8", errors="replace")

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger("main")


def load_offset():
    if OFFSET_FILE.exists():
        return int(OFFSET_FILE.read_text().strip())
    return None


def save_offset(offset):
    OFFSET_FILE.write_text(str(offset))


def main():
    check_required()
    offset = load_offset()
    log.info("Skinstinct content pipeline started. Polling Telegram...")

    while True:
        try:
            updates = get_updates(offset=offset)
        except Exception:
            log.exception("getUpdates failed, retrying in 10s")
            time.sleep(10)
            continue

        for update in updates:
            offset = update["update_id"] + 1
            try:
                process_update(update)
            except Exception:
                log.exception("Failed to process update %s", update.get("update_id"))
            finally:
                save_offset(offset)

        time.sleep(2)


if __name__ == "__main__":
    main()
