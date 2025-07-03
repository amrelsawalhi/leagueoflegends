import streamlit as st
import pandas as pd

# Page config
st.set_page_config(page_title="League of Legends Dashboard", layout="wide")
st.markdown(
    """
    <style>
    .stApp {
        background-image: url("https://raw.githubusercontent.com/amrelsawalhi/leagueoflegends/main/streamlit/background.png");
        background-size: cover;
        background-position: center;
        background-repeat: no-repeat;
        background-attachment: fixed;
    }
    </style>
    """,
    unsafe_allow_html=True
)

# Load data and lookup table
@st.cache_data
def load_data():
    stats_url = "https://raw.githubusercontent.com/amrelsawalhi/leagueoflegends/main/data/fact_champion_stats.csv"
    champs_url = "https://raw.githubusercontent.com/amrelsawalhi/leagueoflegends/main/data/champions.csv"
    portraits_url = "https://raw.githubusercontent.com/amrelsawalhi/leagueoflegends/main/data/champion_portraits.csv"

    df = pd.read_csv(stats_url)
    champs = pd.read_csv(champs_url).rename(columns={"name": "champion_name"})
    portraits = pd.read_csv(portraits_url).rename(columns={"Champion": "champion_name", "PortraitURL": "img_url"})

    df = df.merge(champs[["champion_id", "champion_name"]], on="champion_id", how="left")
    df = df.merge(portraits, on="champion_name", how="left")

    return df

df = load_data()

# --- Sidebar Filters ---
st.sidebar.header("📊 Filters")

regions = sorted(df["region"].unique())
tiers = sorted(df["tier"].unique())
champ_names = sorted(df["champion_name"].dropna().unique())

selected_region = st.sidebar.selectbox("Select Region", ["All"] + regions)
selected_tier = st.sidebar.selectbox("Select Tier", ["All"] + tiers)
selected_champ = st.sidebar.selectbox("Select Champion", ["All"] + champ_names)

if selected_champ != "All":
    champ_img_url = df[df["champion_name"] == selected_champ]["img_url"].dropna().values
    if len(champ_img_url) > 0:
        st.sidebar.image(champ_img_url[0], caption=selected_champ, use_container_width=True)

    
# --- Apply Filters ---
filtered = df.copy()

if selected_region != "All":
    filtered = filtered[filtered["region"] == selected_region]

if selected_tier != "All":
    filtered = filtered[filtered["tier"] == selected_tier]

if selected_champ != "All":
    filtered = filtered[filtered["champion_name"] == selected_champ]

# --- Dashboard Header ---
st.title("🏆 League of Legends Champion Stats Dashboard")

# --- KPIs ---
if selected_champ != "All":
    avg_kda = round(filtered["avg_kda"].mean(), 2)
    avg_cs = round(filtered["avg_cs"].mean(), 2)
    avg_gold = round(filtered["avg_gold_earned"].mean() / 1000, 2)
    avg_damage = round(filtered["avg_damage_dealt"].mean() / 1000, 2)
    avg_vision = round(filtered["avg_vision_score"].mean(), 2)
    avg_win_rate = round(filtered['win_rate'].mean() * 100, 2)
    avg_pick_rate = round(filtered['pick_rate'].mean() * 100, 2)
    avg_ban_rate = round(filtered['win_rate'].mean() * 100, 2)

    col6, col7, col8 = st.columns(3)
    col1, col2, col3 = st.columns(3)
    col4, col5, _ = st.columns(3)

    col1.metric("Average KDA", avg_kda)
    col2.metric("Average CS", avg_cs)
    col3.metric("Avg Gold Earned", f"{avg_gold}K")
    col4.metric("Avg Damage Dealt", f"{avg_damage}K")
    col5.metric("Avg Vision Score", avg_vision)
    col6.metric("Win Rate", f"{avg_win_rate}%")
    col7.metric("Pick Rate", f"{avg_pick_rate}%")
    col8.metric("Ban Rate", f"{avg_ban_rate}%")
else:
    st.info("Select a champion to view their performance metrics.")


# --- Raw Data Table ---
st.subheader("🔎 Raw Data")
st.dataframe(filtered)

# --- Disclaimer ---
st.markdown("---")
st.markdown(
    "<small>⚠️ **Disclaimer:** These metrics are based on a limited dataset and are intended for demonstration purposes only. Interpret results with caution.</small>",
    unsafe_allow_html=True
)