import requests
import time
import psycopg2
import pandas as pd
import os
from datetime import datetime
from requests.adapters import HTTPAdapter, Retry

# Load secrets
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
    "euw1": 1,
    "na1": 2,
    "kr": 3,
    "eun1": 4,
}

tier_map = {
    "GOLD": 1,
    "PLATINUM": 2,
    "EMERALD": 3,
    "DIAMOND": 4,
}

# Setup session with retries
session = requests.Session()
retries = Retry(
    total=5,
    backoff_factor=1,
    status_forcelist=[429, 500, 502, 503, 504],
    allowed_methods=["GET"]
)
adapter = HTTPAdapter(max_retries=retries)
session.mount("https://", adapter)


def get_summoners(region, tier, divisions, max_count=20):
    base_url = f"https://{region}.api.riotgames.com"
    summoner_entries = []
    seen_ids = set()
    for division in divisions:
        for page in range(1, 6):
            url = f"{base_url}/lol/league/v4/entries/RANKED_SOLO_5x5/{tier}/{division}?page={page}"
            try:
                resp = session.get(url, headers=headers, timeout=10)
                resp.raise_for_status()
            except requests.exceptions.RequestException as e:
                print(f"Request failed for {url} → {e}")
                time.sleep(5)
                continue

            entries = resp.json()
            for entry in entries:
                summoner_id = entry.get("summonerId")
                summoner_name = entry.get("summonerName")
                if summoner_id and summoner_name and summoner_id not in seen_ids:
                    summoner_entries.append({
                        "region": region,
                        "tier": tier,
                        "division": division,
                        "summonerId": summoner_id,
                        "summonerName": summoner_name
                    })
                    seen_ids.add(summoner_id)
                if len(seen_ids) >= max_count:
                    break
            if len(seen_ids) >= max_count:
                break
            time.sleep(1.2)
    return summoner_entries


def get_puuid_and_name(region, summoner_id):
    url = f"https://{region}.api.riotgames.com/lol/summoner/v4/summoners/{summoner_id}"
    try:
        resp = session.get(url, headers=headers, timeout=10)
        resp.raise_for_status()
        data = resp.json()
        return data["puuid"], data["name"]
    except requests.exceptions.RequestException as e:
        print(f"Failed to get PUUID for {summoner_id} in {region} → {e}")
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


def clear_summoners_table(cursor):
    cursor.execute("TRUNCATE TABLE summoners;")


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
    print("Starting summoner fetch...")
    for region in regions:
        for tier in tiers:
            print(f"Fetching summoners for {region} - {tier}")
            summoners = get_summoners(region, tier, divisions, max_count=20)
            all_summoners.extend(summoners)

    print(f"Fetched {len(all_summoners)} summoners. Fetching PUUIDs...")

    for summoner in all_summoners:
        puuid, latest_name = get_puuid_and_name(summoner["region"], summoner["summonerId"])
        if puuid:
            summoner["puuid"] = puuid
            summoner["summonerName"] = latest_name
        time.sleep(1.3)

    now = datetime.now()
    date_str = now.strftime("%-d-%B-%Y").lower().replace(" ", "")
    os.makedirs("data", exist_ok=True)
    csv_filename = f"data/summoners_{date_str}.csv"

    df = pd.DataFrame(all_summoners)
    df.to_csv(csv_filename, index=False)
    print(f"Saved summoners to {csv_filename}")

    conn = connect_db()
    cursor = conn.cursor()
    print("Clearing summoners table...")
    clear_summoners_table(cursor)

    print("Inserting summoners into database...")
    for summoner in all_summoners:
        if "puuid" in summoner:
            upsert_summoner(cursor, summoner)

    conn.commit()
    cursor.close()
    conn.close()
    print("Database update complete.")


if __name__ == "__main__":
    main()
