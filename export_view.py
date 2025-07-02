import psycopg2
import pandas as pd
import os

# Load from GitHub secrets (must be set in Actions → Secrets)
DB_HOST = os.environ["SUPABASE_DB_HOST"]
DB_PORT = os.environ.get("SUPABASE_DB_PORT", "5432")  # default to 5432
DB_NAME = os.environ["SUPABASE_DB_NAME"]
DB_USER = os.environ["SUPABASE_DB_USER"]
DB_PASS = os.environ["SUPABASE_DB_PASSWORD"]

# Connect using psycopg2
conn = psycopg2.connect(
    host=DB_HOST,
    port=DB_PORT,
    dbname=DB_NAME,
    user=DB_USER,
    password=DB_PASS
)

# Query the view
query = "SELECT * FROM fact_champion_stats;"
df = pd.read_sql_query(query, conn)

# Save as CSV
output_path = "data/fact_champion_stats.csv"
df.to_csv(output_path, index=False)

print(f"✅ Exported to {output_path}")

conn.close()
