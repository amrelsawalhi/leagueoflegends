import requests
import time
import psycopg2
import logging
from collections import deque
import os

# Setup logging
logging.basicConfig(
    format="%(asctime)s - %(levelname)s - %(message)s",
    level=logging.INFO
)

# Load environment variables
API_KEY = os.getenv("RIOT_API_KEY")
SUPABASE_DB_HOST = os.getenv("SUPABASE_DB_HOST")
SUPABASE_DB_NAME = os.getenv("SUPABASE_DB_NAME")
SUPABASE_DB_USER = os.getenv("SUPABASE_DB_USER")
SUPABASE_DB_PASSWORD = os.getenv("SUPABASE_DB_PASSWORD")
SUPABASE_DB_PORT = os.getenv("SUPABASE_DB_PORT", 5432)

HEADERS = {"X-Riot-Token": API_KEY}

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

def connect_db():
    return psycopg2.connect(
        host=SUPABASE_DB_HOST,
        dbname=SUPABASE_DB_NAME,
        user=SUPABASE_DB_USER,
        password=SUPABASE_DB_PASSWORD,
        port=SUPABASE_DB_PORT,
        sslmode='require'
    )

def fetch_unprocessed_match_ids(limit=50):
    conn = connect_db()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT match_id, region_id FROM match_ids
        WHERE processed = FALSE
        LIMIT %s
    """, (limit,))
    rows = cursor.fetchall()
    cursor.close()
    conn.close()
    return rows

def get_remaining_matches_count():
    conn = connect_db()
    cursor = conn.cursor()
    cursor.execute("SELECT COUNT(*) FROM match_ids WHERE processed = FALSE")
    count = cursor.fetchone()[0]
    cursor.close()
    conn.close()
    return count

def mark_match_processed(match_id):
    conn = connect_db()
    cursor = conn.cursor()
    cursor.execute("UPDATE match_ids SET processed = TRUE WHERE match_id = %s", (match_id,))
    conn.commit()
    cursor.close()
    conn.close()

def insert_match_data(conn, match_data, region_id):
    cursor = conn.cursor()
    match_info = {
        "match_id": match_data["metadata"]["matchId"],
        "game_duration": match_data["info"]["gameDuration"],
        "game_creation": match_data["info"]["gameCreation"],
        "game_mode": match_data["info"]["gameMode"],
        "game_type": match_data["info"]["gameType"],
        "map_id": match_data["info"]["mapId"],
        "region_id": region_id,
        "queue_id": match_data["info"]["queueId"],
        "game_version": match_data["info"]["gameVersion"]
    }

    cursor.execute("""
        INSERT INTO matches (match_id, game_duration, game_creation, game_mode, game_type, map_id, region_id, queue_id, game_version)
        VALUES (%s, %s, to_timestamp(%s / 1000), %s, %s, %s, %s, %s, %s)
        ON CONFLICT (match_id) DO NOTHING
    """, (
        match_info["match_id"],
        match_info["game_duration"],
        match_info["game_creation"],
        match_info["game_mode"],
        match_info["game_type"],
        match_info["map_id"],
        match_info["region_id"],
        match_info["queue_id"],
        match_info["game_version"]
    ))

    game_duration_minutes = match_info["game_duration"] / 60 if match_info["game_duration"] > 0 else 1

    participant_rows = []
    for p in match_data["info"]["participants"]:
        total_damage = p.get("totalDamageDealtToChampions", 0)
        gold_earned = p.get("goldEarned", 0)
        total_minions = p.get("totalMinionsKilled", 0) + p.get("neutralMinionsKilled", 0)

        damage_per_minute = total_damage / game_duration_minutes
        gold_per_minute = gold_earned / game_duration_minutes
        cs_per_minute = total_minions / game_duration_minutes

        participant_rows.append((
            match_info["match_id"],
            p["puuid"],
            p["participantId"],
            p["teamId"],
            p.get("championId", None),
            p.get("championName", None),
            p.get("summonerName", None),
            p.get("kills", 0),
            p.get("deaths", 0),
            p.get("assists", 0),
            total_damage,
            p.get("visionScore", 0),
            gold_earned,
            total_minions,
            p.get("champLevel", 0),
            p.get("win", False),
            p.get("lane", None),
            p.get("individualPosition", None),
            damage_per_minute,
            gold_per_minute,
            cs_per_minute
        ))

    cursor.executemany("""
        INSERT INTO match_participants (
            match_id, puuid, participant_id, team_id, champion_id,
            champion_name, summoner_name, kills, deaths, assists,
            damage_dealt, vision_score, gold_earned, total_minions_killed,
            champ_level, win, lane, position, damage_per_minute, gold_per_minute, cs_per_minute
        ) VALUES (
            %s, %s, %s, %s, %s,
            %s, %s, %s, %s, %s,
            %s, %s, %s, %s,
            %s, %s, %s, %s, %s, %s, %s
        )
        ON CONFLICT DO NOTHING
    """, participant_rows)

    ban_rows = []
    for team in match_data["info"].get("teams", []):
        team_id = team["teamId"]
        for ban in team.get("bans", []):
            ban_rows.append((
                match_info["match_id"],
                team_id,
                ban["championId"]
            ))

    cursor.executemany("""
        INSERT INTO match_bans (match_id, team_id, champion_id)
        VALUES (%s, %s, %s)
        ON CONFLICT DO NOTHING
    """, ban_rows)

    conn.commit()
    cursor.close()

def fetch_match(region_id, match_id):
    region_map = {
        2: "europe",
        3: "europe",
        5: "asia",
        8: "americas"
    }
    platform = region_map.get(region_id, "europe")
    url = f"https://{platform}.api.riotgames.com/lol/match/v5/matches/{match_id}"
    enforce_rate_limits()
    try:
        resp = requests.get(url, headers=HEADERS, timeout=10)
        if resp.status_code == 200:
            return resp.json()
        elif resp.status_code == 429:
            retry_after = int(resp.headers.get("Retry-After", 1))
            logging.warning(f"Rate limited. Sleeping {retry_after}s")
            time.sleep(retry_after)
            return fetch_match(region_id, match_id)
        else:
            logging.error(f"Failed to fetch match {match_id}: {resp.status_code} {resp.text}")
            return None
    except Exception as e:
        logging.error(f"Exception fetching match {match_id}: {e}")
        return None

def main():
    logging.info("🚀 Starting match data extraction...")

    conn = connect_db()

    while True:
        remaining = get_remaining_matches_count()
        logging.info(f"🧮 Remaining unprocessed matches: {remaining}")
        if remaining == 0:
            break

        batch = fetch_unprocessed_match_ids(limit=50)
        if not batch:
            break

        for match_id, region_id in batch:
            logging.info(f"Processing match {match_id}")
            match_data = fetch_match(region_id, match_id)
            if match_data:
                try:
                    insert_match_data(conn, match_data, region_id)
                    mark_match_processed(match_id)
                    logging.info(f"✅ Match {match_id} processed.")
                except Exception as e:
                    logging.error(f"❌ DB insert error for match {match_id}: {e}")
                    conn.rollback()
            else:
                logging.warning(f"⚠️ Skipping match {match_id} due to fetch failure.")

    conn.close()
    logging.info("🏁 Finished all processing.")

if __name__ == "__main__":
    main()
