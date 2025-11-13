import time
import random
import logging
import requests
import os
from typing import List, Dict, Any

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")

# ---------- CONFIG ----------

TOKEN = os.getenv("DISCORD_TOKEN")
CHANNEL_ID = os.getenv("DISCORD_CHANNEL_ID")

if not TOKEN or not CHANNEL_ID:
    raise RuntimeError("Missing environment variables: DISCORD_TOKEN or DISCORD_CHANNEL_ID")

API_URL = "https://discordautomessage.vercel.app/api/discord/user-send-multiple"
REPEAT_COUNT = 1        # how many times to send each emoji per batch
INTRA_DELAY = 1         # seconds between repeats in a batch
INTERVAL = 60           # seconds between batches

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
EMOJI_FILE = os.path.join(BASE_DIR, "emojis.txt")
# ----------------------------------------------------

HEADERS = {
    "Accept": "*/*",
    "Accept-Language": "en-US,en;q=0.5",
    "Referer": "https://discordautomessage.vercel.app/",
    "Origin": "https://discordautomessage.vercel.app",
    "User-Agent": "Mozilla/5.0",
    "Cache-Control": "no-cache",
    "Content-Type": "application/json"
}

def load_emojis(filename: str) -> List[str]:
    """Load emojis from a file, ignoring empty lines."""
    with open(filename, "r", encoding="utf-8") as f:
        return [line.strip() for line in f if line.strip()]

def build_payload(token: str, message: str, channel: str) -> Dict[str, Any]:
    return {"token": token, "message": message, "targets": [{"type": "channel", "id": channel}]}

def post_payload(payload: Dict[str, Any]) -> requests.Response:
    return requests.post(API_URL, json=payload, headers=HEADERS, timeout=15)

def main():
    EMOJI_POOL = load_emojis(EMOJI_FILE)
    if not EMOJI_POOL:
        logging.error("Emoji pool is empty. Check %s", EMOJI_FILE)
        return

    last_two = []  # track last 2 emojis
    round_num = 0
    logging.info("Starting emoji sender — interval=%ss repeat=%d", INTERVAL, REPEAT_COUNT)

    try:
        while True:
            round_num += 1

            # pick emoji not in last_two
            choices = EMOJI_POOL.copy()
            for e in last_two:
                if e in choices and len(choices) > 1:
                    choices.remove(e)
            emoji = random.choice(choices)
            logging.info("Round %d — picked %s", round_num, emoji)

            # send emoji REPEAT_COUNT times
            for i in range(REPEAT_COUNT):
                payload = build_payload(TOKEN, emoji, CHANNEL_ID)
                try:
                    resp = post_payload(payload)
                    logging.info("Sent (%d/%d) status=%s", i+1, REPEAT_COUNT, resp.status_code)
                    if resp.status_code == 429:
                        logging.warning("Rate-limited (429). Response: %s", resp.text)
                        ra = resp.headers.get("Retry-After")
                        wait = float(ra) if ra else 5.0
                        logging.info("Waiting %.1fs due to rate-limit...", wait)
                        time.sleep(wait)
                except requests.RequestException as e:
                    logging.error("Network error during POST: %s", e)

                if i < REPEAT_COUNT - 1:
                    time.sleep(INTRA_DELAY)

            # update last_two
            last_two.append(emoji)
            if len(last_two) > 2:
                last_two.pop(0)

            logging.info("Batch complete. Sleeping exactly %s seconds...", INTERVAL)
            time.sleep(INTERVAL)

    except KeyboardInterrupt:
        logging.info("Interrupted by user — exiting cleanly.")

if __name__ == "__main__":
    main()
