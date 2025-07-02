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
query1 = "SELECT * FROM tiers;"
query2 = "SELECT * FROM regions;"
query3 = "SELECT * FROM champions;"

df1 = pd.read_sql_query(query1, conn)
output_path1 = "data/tiers.csv"
df1.to_csv(output_path1, index=False)
print(f"✅ Exported to {output_path1}")

df2 = pd.read_sql_query(query2, conn)
output_path2 = "data/regions.csv"
df2.to_csv(output_path2, index=False)
print(f"✅ Exported to {output_path2}")

df3 = pd.read_sql_query(query3, conn)
output_path3 = "data/champions.csv"
df3.to_csv(output_path3, index=False)
print(f"✅ Exported to {output_path3}")

conn.close()
