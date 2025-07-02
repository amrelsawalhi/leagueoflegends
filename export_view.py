import pandas as pd
from sqlalchemy import create_engine
import os

# Load credentials from GitHub Actions secrets
DB_HOST = os.environ["PGHOST"]
DB_PORT = os.environ["PGPORT"]
DB_NAME = os.environ["PGDATABASE"]
DB_USER = os.environ["PGUSER"]
DB_PASS = os.environ["PGPASSWORD"]

# Build connection
uri = f"postgresql+psycopg2://{DB_USER}:{DB_PASS}@{DB_HOST}:{DB_PORT}/{DB_NAME}"
engine = create_engine(uri)

# Query the view
query = "SELECT * FROM fact_champion_stats;"
df = pd.read_sql(query, engine)

# Save the CSV
df.to_csv("data/fact_champion_stats.csv", index=False)
print("✅ Export complete")
