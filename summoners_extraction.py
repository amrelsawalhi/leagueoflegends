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

# Load secrets from environment variables
API_KEY = os.getenv("RIOT_API_KEY")
SUPABASE_DB_HOST = os.getenv("SUPABASE_DB_HOST")
SUPABASE_DB_NAME = os.getenv("SUPABASE_DB_NAME")
SUPABASE_DB_USER = os.getenv("SUPABASE_DB_USER")
SUPABASE_DB_PASSWORD = os.getenv("SUPABASE_DB_PASSWORD")
SUPABASE_DB_PORT = os.getenv("SUPABASE_DB_PORT", 5432)

headers = {"X-Riot-Token": API_KEY}

regions = ["euw1", "na1", "kr", "eun1"]
tiers = ["GOLD", "PLATINUM", "EMERALD", "DIAMOND"]
divisions = ["I", "II", "III", "IV"]

region_map = {
    "euw1": 3,
    "na1": 8,
    "kr": 5,
    "eun1": 2,
}

tier_map = {
    "GOLD": 4,
    "PLATINUM": 5,
    "EMERALD": 6,
    "DIAMOND": 7,
}

# API rate limit tracking
api_calls = deque()

def enforce_rate_limits():
    now = time.time()

    # Clean calls older than 120 seconds
    while api_calls and now - api_calls[0] > 120:
        api_calls.popleft()

    # Check long-term limit
    if len(api_calls) >= 100:
        wait = 120 - (now - api_calls[0])
        logging.warning(f"Rate limit 100/2min hit, sleeping for {wait:.2f}s")
        time.sleep(wait)
        return enforce_rate_limits()

    # Check short-term limit
    recent = [t for t in api_calls if now - t < 1]
    if len(recent) >= 20:
        logging.warning("Rate limit 20/sec hit, sleeping for 1s")
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
                resp = requests.get(url, headers=headers, timeout=10)
                logging.info(f"[{region} - {tier} {division} p{page}] → {resp.status_code}")
                if resp.status_code != 200:
                    logging.warning(f"Failed request: {resp.status_code} → {resp.text[:200]}")
                    continue

                entries = resp.json()
                for entry in entries:
                    sid = entry.get("summonerId")
                    sname = entry.get("summonerName")
                    if sid and sname and sid not in seen_ids:
                        summoner_entries.append({
                            "region": region,
                            "tier": tier,
                            "division": division,
                            "summonerId": sid,
                            "summonerName": sname
                        })
                        seen_ids.add(sid)

                    if len(seen_ids) >= max_count:
                        break

                if len(seen_ids) >= max_count:
                    break
                time.sleep(1.2)

            except requests.exceptions.RequestException as e:
                logging.error(f"Exception on {url}: {e}")
                time.sleep(5)

    logging.info(f"✅ {len(summoner_entries)} summoners fetched from {region} {tier}")
    return summoner_entries

def get_puuid_and_name(region, summoner_id):
    url = f"https://{region}.api.riotgames.com/lol/summoner/v4/summoners/{summoner_id}"
    enforce_rate_limits()

    try:
        resp = requests.get(url, headers=headers, timeout=10)
        logging.info(f"PUUID GET {region} {summoner_id} → {resp.status_code}")
        if resp.status_code == 200:
            data = resp.json()
            return data["puuid"], data["name"]
        else:
            logging.warning(f"Failed to fetch PUUID for {summoner_id}: {resp.status_code}")
            return None, None
    except Exception as e:
        logging.error(f"Exception getting PUUID for {summoner_id}: {e}")
        return None, None

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
    INSERT INTO summoners (region_id, tier_id, division, summoner_id, puuid, summoner_name)
    VALUES (%s, %s, %s, %s, %s, %s)
    ON CONFLICT (summoner_id) DO UPDATE
    SET puuid = EXCLUDED.puuid,
        summoner_name = EXCLUDED.summoner_name,
        division = EXCLUDED.division,
        region_id = EXCLUDED.region_id,
        tier_id = EXCLUDED.tier_id;
    """
    cursor.execute(insert_sql, (
        region_map[summoner["region"]],
        tier_map[summoner["tier"]],
        summoner["division"],
        summoner["summonerId"],
        summoner["puuid"],
        summoner["summonerName"],
    ))

def main():
    all_summoners = []
    logging.info("🚀 Starting summoner fetch")
    for region in regions:
        for tier in tiers:
            logging.info(f"📡 Fetching: {region} - {tier}")
            summoners = get_summoners(region, tier, divisions, max_count=20)
            all_summoners.extend(summoners)

    logging.info(f"🔍 Total summoners before PUUIDs: {len(all_summoners)}")

    for summoner in all_summoners:
        puuid, latest_name = get_puuid_and_name(summoner["region"], summoner["summonerId"])
        if puuid:
            summoner["puuid"] = puuid
            summoner["summonerName"] = latest_name
        time.sleep(1.3)

    now = datetime.now()
    date_str = now.strftime("%-d-%B-%Y").lower()
    csv_filename = f"summoners_{date_str}.csv"

    df = pd.DataFrame(all_summoners)
    df.to_csv(csv_filename, index=False)
    logging.info(f"📁 Saved to {csv_filename}")

    conn = connect_db()
    cursor = conn.cursor()

    logging.info("🛠️ Inserting into database...")
    inserted = 0
    for summoner in all_summoners:
        if "puuid" in summoner:
            upsert_summoner(cursor, summoner)
            inserted += 1
    conn.commit()
    cursor.close()
    conn.close()
    logging.info(f"✅ Database update complete — {inserted} inserted.")

if __name__ == "__main__":
    main()
