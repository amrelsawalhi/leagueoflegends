import requests
import psycopg2
import os
import time

API_KEY = os.getenv("RIOT_API_KEY")
SUPABASE_DB_HOST = os.getenv("SUPABASE_DB_HOST")
SUPABASE_DB_NAME = os.getenv("SUPABASE_DB_NAME")
SUPABASE_DB_USER = os.getenv("SUPABASE_DB_USER")
SUPABASE_DB_PASSWORD = os.getenv("SUPABASE_DB_PASSWORD")
SUPABASE_DB_PORT = os.getenv("SUPABASE_DB_PORT", 5432)

headers = {"X-Riot-Token": API_KEY}

def connect_db():
    return psycopg2.connect(
        host=SUPABASE_DB_HOST,
        dbname=SUPABASE_DB_NAME,
        user=SUPABASE_DB_USER,
        password=SUPABASE_DB_PASSWORD,
        port=SUPABASE_DB_PORT,
        sslmode='require'
    )

def get_all_summoners():
    conn = connect_db()
    cursor = conn.cursor()
    cursor.execute("SELECT puuid, region_id FROM summoners;")
    summoners = cursor.fetchall()
    cursor.close()
    conn.close()
    return summoners

def region_code(region_id):
    return {1: "europe", 2: "americas", 3: "asia", 4: "europe"}.get(region_id, "europe")

def fetch_match_ids(puuid, platform_region):
    url = f"https://{platform_region}.api.riotgames.com/lol/match/v5/matches/by-puuid/{puuid}/ids"
    params = {"start": 0, "count": 50, "queue": 420}
    resp = requests.get(url, headers=headers, params=params)
    if resp.status_code == 200:
        return resp.json()
    print(f"[{puuid}] Error fetching match IDs: {resp.status_code} - {resp.text}")
    return []

def fetch_queue_id(match_id, platform_region):
    url = f"https://{platform_region}.api.riotgames.com/lol/match/v5/matches/{match_id}"
    resp = requests.get(url, headers=headers)
    if resp.status_code == 200:
        return resp.json().get("info", {}).get("queueId")
    print(f"[{match_id}] Error fetching match info: {resp.status_code} - {resp.text}")
    return None

def main():
    conn = connect_db()
    cursor = conn.cursor()
    cursor.execute("TRUNCATE TABLE match_ids;")

    summoners = get_all_summoners()
    print(f"Found {len(summoners)} summoners.")

    for puuid, region_id in summoners:
        platform_region = region_code(region_id)
        match_ids = fetch_match_ids(puuid, platform_region)

        for match_id in match_ids:
            queue_id = fetch_queue_id(match_id, platform_region)
            if queue_id == 420:
                cursor.execute("""
                    INSERT INTO match_ids (match_id, puuid, region_id, queue_id)
                    VALUES (%s, %s, %s, %s)
                    ON CONFLICT (match_id) DO NOTHING;
                """, (match_id, puuid, region_id, queue_id))
            time.sleep(1.2)

    conn.commit()
    cursor.close()
    conn.close()
    print("Done.")

if __name__ == "__main__":
    main()
