import requests
import time
import psycopg2
import os
import logging
from collections import deque

# Setup logging
logging.basicConfig(
    format="%(asctime)s - %(levelname)s - %(message)s",
    level=logging.INFO
)

# Load secrets
API_KEY = os.getenv("RIOT_API_KEY")
SUPABASE_DB_HOST = os.getenv("SUPABASE_DB_HOST")
SUPABASE_DB_NAME = os.getenv("SUPABASE_DB_NAME")
SUPABASE_DB_USER = os.getenv("SUPABASE_DB_USER")
SUPABASE_DB_PASSWORD = os.getenv("SUPABASE_DB_PASSWORD")
SUPABASE_DB_PORT = os.getenv("SUPABASE_DB_PORT", 5432)

HEADERS = {"X-Riot-Token": API_KEY}
QUEUE_ID = 420

routing_map = {
    2: "europe",
    3: "europe",
    5: "asia",
    8: "americas"
}

api_calls = deque()

def enforce_rate_limits():
    now = time.time()
    while api_calls and now - api_calls[0] > 120:
        api_calls.popleft()
    if len(api_calls) >= 100:
        wait = 120 - (now - api_calls[0])
        logging.warning(f"⏳ Hit 100/2min limit, sleeping {wait:.2f}s")
        time.sleep(wait)
        return enforce_rate_limits()
    if len([t for t in api_calls if now - t < 1]) >= 20:
        logging.warning("⏳ Hit 20/sec limit, sleeping 1s")
        time.sleep(1)
        return enforce_rate_limits()
    api_calls.append(now)

def connect_db():
    return psycopg2.connect(
        host=SUPABASE_DB_HOST,
        dbname=SUPABASE_DB_NAME,
        user=SUPABASE_DB_USER,
        password=SUPABASE_DB_PASSWORD,
        port=SUPABASE_DB_PORT,
        sslmode='require'
    )

def fetch_all_summoners():
    conn = connect_db()
    cursor = conn.cursor()
    cursor.execute("SELECT puuid, region_id FROM summoners;")
    summoners = cursor.fetchall()
    cursor.close()
    conn.close()
    return summoners

def fetch_match_ids(puuid, region):
    enforce_rate_limits()
    url = f"https://{region}.api.riotgames.com/lol/match/v5/matches/by-puuid/{puuid}/ids"
    params = {"start": 0, "count": 50, "queue": QUEUE_ID}
    try:
        resp = requests.get(url, headers=HEADERS, params=params, timeout=10)
        logging.info(f"[{puuid}] → {resp.status_code}")
        if resp.status_code == 200:
            return resp.json()
        elif resp.status_code == 429:
            retry = int(resp.headers.get("Retry-After", 10))
            logging.warning(f"Rate limited fetching match IDs: sleeping {retry}s")
            time.sleep(retry)
            return fetch_match_ids(puuid, region)
        else:
            logging.warning(f"Unexpected response: {resp.text}")
    except Exception as e:
        logging.error(f"❌ Match ID fetch failed: {e}")
    return []

def main():
    logging.info("🚀 Starting match ID fetch...")

    summoners = fetch_all_summoners()
    logging.info(f"🔍 Total summoners: {len(summoners)}")

    conn = connect_db()
    cursor = conn.cursor()
    cursor.execute("TRUNCATE TABLE match_ids;")

    inserted = 0
    for puuid, region_id in summoners:
        region = routing_map.get(region_id, "europe")
        match_ids = fetch_match_ids(puuid, region)

        for match_id in match_ids:
            cursor.execute("""
                INSERT INTO match_ids (match_id, puuid, region_id, queue_id)
                VALUES (%s, %s, %s, %s)
                ON CONFLICT (match_id) DO NOTHING;
            """, (match_id, puuid, region_id, QUEUE_ID))
            inserted += 1

    conn.commit()
    cursor.close()
    conn.close()
    logging.info(f"✅ DB update complete — {inserted} matches inserted")

if __name__ == "__main__":
    main()
