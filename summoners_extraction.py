import requests
import time
import psycopg2
import pandas as pd
import os
import logging
from datetime import datetime
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

regions = ["euw1", "na1", "kr", "eun1"]
tiers = ["GOLD", "PLATINUM", "EMERALD", "DIAMOND"]
divisions = ["I", "II", "III", "IV"]

region_map = {"euw1": 3, "na1": 8, "kr": 5, "eun1": 2}
tier_map = {"GOLD": 4, "PLATINUM": 5, "EMERALD": 6, "DIAMOND": 7}

# Rate limit enforcement: 20/sec and 100/2min
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
    recent = [t for t in api_calls if now - t < 1]
    if len(recent) >= 20:
        logging.warning("⏳ Hit 20/sec limit, sleeping 1s")
        time.sleep(1)
        return enforce_rate_limits()
    api_calls.append(now)

def get_summoners(region, tier, divisions, max_count=20):
    base_url = f"https://{region}.api.riotgames.com"
    summoner_entries = []
    seen_ids = set()

    for division in divisions:
        for page in range(1, 6):
            url = f"{base_url}/lol/league/v4/entries/RANKED_SOLO_5x5/{tier}/{division}?page={page}"
            enforce_rate_limits()

            try:
                resp = requests.get(url, headers=HEADERS, timeout=10)
                logging.info(f"[{region} - {tier} {division} p{page}] → {resp.status_code}")
                entries = resp.json()

                if not isinstance(entries, list):
                    logging.warning(f"Unexpected response: {entries}")
                    continue

                for entry in entries:
                    sid = entry.get("summonerId")
                    if sid and sid not in seen_ids:
                        # Fetch puuid using summoner-v4 API
                        summoner_url = f"{base_url}/lol/summoner/v4/summoners/{sid}"
                        enforce_rate_limits()
                        try:
                            summoner_resp = requests.get(summoner_url, headers=HEADERS, timeout=10)
                            if summoner_resp.status_code == 200:
                                summoner_data = summoner_resp.json()
                                puuid = summoner_data.get("puuid")
                                if puuid:
                                    summoner_entries.append({
                                        "region": region,
                                        "tier": tier,
                                        "division": division,
                                        "summonerId": sid,
                                        "puuid": puuid
                                    })
                                    seen_ids.add(sid)
                                    if len(seen_ids) >= max_count:
                                        break
                        except Exception as e:
                            logging.error(f"❌ Failed to fetch summoner details for {sid}: {e}")
                if len(seen_ids) >= max_count:
                    break
            except Exception as e:
                logging.error(f"❌ Request failed for {url}: {e}")
                time.sleep(5)

    logging.info(f"✅ {len(summoner_entries)} summoners fetched from {region} {tier}")
    return summoner_entries

def connect_db():
    return psycopg2.connect(
        host=SUPABASE_DB_HOST,
        dbname=SUPABASE_DB_NAME,
        user=SUPABASE_DB_USER,
        password=SUPABASE_DB_PASSWORD,
        port=SUPABASE_DB_PORT,
        sslmode='require'
    )

def upsert_summoner(cursor, summoner):
    insert_sql = """
    INSERT INTO summoners (region_id, tier_id, division, summoner_id, puuid)
    VALUES (%s, %s, %s, %s, %s)
    ON CONFLICT (summoner_id) DO UPDATE
    SET puuid = EXCLUDED.puuid,
        division = EXCLUDED.division,
        region_id = EXCLUDED.region_id,
        tier_id = EXCLUDED.tier_id;
    """
    cursor.execute(insert_sql, (
        region_map[summoner["region"]],
        tier_map[summoner["tier"]],
        summoner["division"],
        summoner["summonerId"],
        summoner["puuid"]
    ))

def main():
    all_summoners = []
    logging.info("🚀 Starting summoner fetch...")

    for region in regions:
        for tier in tiers:
            logging.info(f"📡 Fetching: {region} - {tier}")
            summoners = get_summoners(region, tier, divisions, max_count=20)
            all_summoners.extend(summoners)

    logging.info(f"🔍 Total summoners fetched: {len(all_summoners)}")

    # DB insert
    conn = connect_db()
    cursor = conn.cursor()

    logging.info("🧹 Truncating summoners table...")
    cursor.execute("TRUNCATE TABLE summoners")

    logging.info("🛠️ Inserting into database...")
    inserted = 0
    for summoner in all_summoners:
        upsert_summoner(cursor, summoner)
        inserted += 1
    conn.commit()
    cursor.close()
    conn.close()
    logging.info(f"✅ DB update complete — {inserted} rows inserted")


if __name__ == "__main__":
    main()
