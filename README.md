# League of Legends Data Pipeline & Dashboard

## 🌐 Streamlit Dashboard
![Streamlit App](https://raw.githubusercontent.com/amrelsawalhi/leagueoflegends/cd84d8711c5501c629053eb7072b6d26ad4920b1/streamlit/streamlit_sc.png)

## 📊 Power BI Dashboard
![Dashboard](https://github.com/amrelsawalhi/leagueoflegends/blob/62282077134094093ff5ed2954b59369fdb3c17b/dashboard.png)



## 📌 Project Summary

This end-to-end data engineering project automates the collection, transformation, and visualization of League of Legends ranked match data using the Riot Games API. It demonstrates:

- Data extraction from a third-party API with rate-limiting and error-handling.
- Modeling and managing a structured PostgreSQL database.
- Building a dimensional schema to support analytics.
- Automating workflows via GitHub Actions.
- Power BI dashboard design for insight delivery.
- Full pipeline and infrastructure are entirely cloud-based — no local setup required.

---

## 🛠 Tech Stack

- **Python**: ETL scripting and automation.
- **PostgreSQL**: Central data warehouse.
- **GitHub Actions**: Workflow scheduling and automation.
- **Pandas / psycopg2 / requests**: Data processing and API communication.
- **Power BI**: Data visualization and dashboarding.

---

## 🧩 Project Architecture

**1. Data Extraction Scripts**
- `summoner_extraction.py`: Retrieves high-ELO summoner information.
- `matchids_extraction.py`: Pulls match IDs for each summoner.
- `main_matches_script.py`: Downloads detailed match data (participants, bans, metadata).

**2. Dimensional Modeling**
- Modeled as a snowflake schema with:
  - `summoners`, `champions`, `tiers`, `regions` (dimensions)
  - `matches`, `match_participants`, `match_bans` (facts)
  ![Database Schema](https://github.com/amrelsawalhi/leagueoflegends/blob/55c5faefd70260391cd147f47d894f2e1329197c/database_schema.png)

**3. Aggregation & Export**
- `export_view.py`: Creates and exports a fact view (`fact_champion_stats.csv`) for Power BI.
- View includes champion-level metrics like:
  - Win rate
  - Ban rate
  - Pick rate
  - Gold per minute, damage per minute, and more.

**4. Automation via GitHub Actions**
- `summoner_extraction.yml`: Weekly refresh of summoner list.
- `matchid.yml`: Triggered after summoner update; pulls latest match IDs.
- `matches_details.yml`: Fetches detailed match data every 6 hours until all are processed.
- `export_view.yml`: Exports view as CSV when match ingestion completes.

---

## 📊 Power BI Dashboard

The dashboard showcases:
- Champion performance metrics.
- Champion popularity (pick_rate)
- Tier, Server and Champion slicers.
- Time-based trends in ranked meta (to be added later).
- Role popularity and performance (to be added later).

📎 Download it here: [lol_dashboard.pbix](https://github.com/amrelsawalhi/leagueoflegends/blob/62282077134094093ff5ed2954b59369fdb3c17b/lol_dashboard.pbix)

---

## 🌐 Live Web App (Streamlit)

You can explore the champion stats interactively on a live dashboard powered by **Streamlit**:

👉 [lol-stats.streamlit.app](https://lol-stats.streamlit.app/)

---

## 🚧 Challenges Faced

- **Rate Limiting**: Handled via recursive backoff and deque tracking.
- **Data Duplication**: Solved with proper DB constraints and conflict resolution.
- **Workflow Resilience**: Designed jobs to be idempotent and fault-tolerant across executions.
- **Power BI Refresh**: Integrated with GitHub-hosted CSVs for low-friction updating.

---

## 🔮 Future Improvements

- Add **role-duo synergy** analytics (e.g. jungle+mid, bot+support).
- Analyze **rune and item builds** per champion and correlate with win rate.
- Deploy dashboard via **Streamlit** for public, interactive access.
- Implement **real-time tracking** of new matches using webhook-style polling.

---

## 📁 Repository Structure

```
.github/workflows/
    summoner_extraction.yml
    matchid.yml
    matches_details.yml
    export_view.yml
data/
    champion_portraits.csv
    champions.csv
    fact_champion_stats.csv
    regions.csv
    tiers.csv
    summoners_<date>.csv
streamlit/
    background.png
    streamlit_app.py

pull_dimensions.py
summoner_extraction.py
matchids_extraction.py
main_matches_script.py
export_view.py
lol_dashboard.pbix
database_schema.png
dashboard.png
README.md
```
