import streamlit as st
import folium
from streamlit_folium import st_folium
import random
import pandas as pd
import requests

# --- KAGGLE CONFIG ---
KAGGLE_USERNAME = "moussaabbensalmi"
KAGGLE_API_KEY = "89232e615193c010f3158af8813f4811"

# --- METRIC NOTES ---
# MAE:  lower is better  → troops = (1 - score/threshold) * max
# RMSE: lower is better  → troops = (1 - score/threshold) * max
# CER:  lower is better  → troops = (1 - score/threshold) * max
# F1:   higher is better → troops = (score/threshold) * max  (threshold = 1.0 max)

# --- COMPETITION CONFIG ---
STAGE_COMPETITIONS = {
    "Algeria": {
        "competition": "uuuuuu",
        "metric": "MAE",
        "max_troops": 50000,
        "mae_threshold": 1000,
        "unlock_threshold": 1000,
    },
    "Sudan": {
        "competition": "Sudan_2",
        "metric": "CER",
        "max_troops": 50000,
        "mae_threshold": 1.0,       # CER is 0-1
        "unlock_threshold": 1.0,
    },
    "Egypt": {
        "competition": "Egypte",
        "metric": "F1",
        "max_troops": 50000,
        "mae_threshold": 1.0,       # F1 is 0-1
        "unlock_threshold": 0.5,    # unlock when F1 > 0.5
    },
    "Saudi Arabia": {
        "competition": "bike-demande-competition",
        "metric": "MAE",
        "max_troops": 50000,
        "mae_threshold": 1000,
        "unlock_threshold": 1000,
    },
    "Palestine": {
        "competition": "palestine",
        "metric": "MAE",
        "max_troops": 50000,
        "mae_threshold": 1000,
        "unlock_threshold": 1000,
    },
}

# --- ASSET & GAME CONFIGURATION ---
CUSTOM_LOGOS = {
    "Fighter Jet": "https://i.imgur.com/ywf0aun.png",
    "Missile Truck": "https://i.imgur.com/uGvCdKp.png",
    "Tank": "https://i.imgur.com/TGHMPxV.png",
    "Helicopter": "https://i.imgur.com/EcCleHZ.png",
    "Submarine": "https://i.imgur.com/zXC7TnD.png"
}

STAGES = ["Algeria", "Sudan", "Egypt", "Saudi Arabia", "Palestine"]
COORDS = {
    "Algeria": [28.03, 1.66], "Sudan": [12.86, 30.22], "Egypt": [26.82, 30.80],
    "Saudi Arabia": [23.88, 45.07], "Palestine": [31.95, 35.23],
    "Iraq": [33.22, 43.68], "Libya": [26.33, 17.22], "Syria": [34.80, 38.99],
    "Yemen": [15.55, 48.51]
}

SIDE_QUESTS = {
    "Iraq":  {"ability": "Freeze ❄️",   "desc": "Stop a rival team's submissions.", "competition": "NeuralX Side Mission: Rise of Nations", "metric": "MAE",  "threshold": 500.0},
    "Libya": {"ability": "Shield 🛡️",   "desc": "Protect from sabotage.",           "competition": "libya",  "metric": "MAE",  "threshold": 500.0},
    "Syria": {"ability": "Intel 👁️",    "desc": "Reveal rival submissions.",        "competition": "SYRIA-3","metric": "RMSE", "threshold": 500.0},
    "Yemen": {"ability": "Sabotage 💣", "desc": "Reduce rival troop count.",        "competition": "yemen_", "metric": "F1",   "threshold": 0.5},
}

if 'teams' not in st.session_state:
    st.session_state.teams = {}

if 'admin_unlocked' not in st.session_state:
    st.session_state.admin_unlocked = False

if 'side_quests_config' not in st.session_state:
    st.session_state.side_quests_config = {
        loc: {"active": False}
        for loc in SIDE_QUESTS.keys()
    }

# --- METRIC FUNCTIONS ---

def score_to_troops(score, metric, threshold, max_troops):
    """
    Convert a raw competition score to troop count based on metric type.
    Lower-is-better (MAE, RMSE, CER): troops = (1 - score/threshold) * max_troops
    Higher-is-better (F1):            troops = (score / threshold)   * max_troops
    """
    if score is None:
        return 0
    metric = metric.upper()
    if metric in ("MAE", "RMSE", "CER"):
        return int(max(0.0, (1.0 - score / threshold) * max_troops))
    elif metric == "F1":
        return int(max(0.0, min(1.0, score / threshold) * max_troops))
    else:
        # Default: lower is better
        return int(max(0.0, (1.0 - score / threshold) * max_troops))


def qualifies_unlock(score, metric, unlock_threshold):
    """
    Check if a score crosses the unlock threshold.
    Lower-is-better: score < threshold
    Higher-is-better (F1): score >= threshold
    """
    if score is None:
        return False
    metric = metric.upper()
    if metric == "F1":
        return score >= unlock_threshold
    else:
        return score < unlock_threshold


# --- KAGGLE INTEGRATION FUNCTIONS ---

def fetch_leaderboard_for(competition):
    """Fetch leaderboard from Kaggle API for a given competition slug"""
    endpoints = [
        f"https://www.kaggle.com/api/v1/competitions/{competition}/leaderboard/view",
        f"https://www.kaggle.com/api/v1/competitions/{competition}/leaderboard/download",
    ]
    auth_formats = [
        {"auth": (KAGGLE_USERNAME, KAGGLE_API_KEY)},
        {"headers": {"Authorization": f"Bearer {KAGGLE_API_KEY}"}},
        {"headers": {
            "Authorization": "Basic " + __import__('base64').b64encode(
                f"{KAGGLE_USERNAME}:{KAGGLE_API_KEY}".encode()
            ).decode()
        }},
    ]
    try:
        for endpoint in endpoints:
            for auth in auth_formats:
                response = requests.get(endpoint, timeout=10, **auth)
                if response.status_code == 200:
                    if "download" in endpoint:
                        import io
                        df = pd.read_csv(io.StringIO(response.text))
                        df.columns = [c.lower() for c in df.columns]
                        col_team  = next((c for c in df.columns if "team" in c), df.columns[0])
                        col_score = next((c for c in df.columns if "score" in c), df.columns[1])
                        col_rank  = next((c for c in df.columns if "rank" in c), None)
                        records = []
                        for _, row in df.iterrows():
                            records.append({
                                "teamName": str(row[col_team]),
                                "score": row[col_score],
                                "rank": row[col_rank] if col_rank else None
                            })
                        return records
                    else:
                        raw = response.json()
                        if isinstance(raw, dict):
                            return raw.get("submissions", raw.get("leaderboard", []))
                        return raw
        return None
    except Exception:
        return None


def parse_entries(raw_list):
    """Normalize Kaggle API response to list of {teamName, score, rank}"""
    entries = []
    for i, entry in enumerate(raw_list):
        team_name = (
            entry.get("teamName") or entry.get("team_name") or
            entry.get("TeamName") or entry.get("name") or "Unknown"
        )
        raw_score = entry.get("score", entry.get("Score", None))
        raw_rank  = entry.get("rank",  entry.get("Rank",  i + 1))
        try:
            score = float(raw_score) if raw_score is not None else None
            rank  = int(raw_rank)
        except (ValueError, TypeError):
            score = None
            rank  = i + 1
        entries.append({"teamName": team_name, "score": score, "rank": rank})
    return entries


def evaluate_side_quests(sq_lookups):
    """Auto-grant/remove abilities based on each side quest's own leaderboard"""
    for team_name, team in st.session_state.teams.items():
        for loc, info in SIDE_QUESTS.items():
            cfg = st.session_state.side_quests_config[loc]

            if not cfg["active"]:
                team["abilities"].pop(loc, None)
                team["ability_offsets"].pop(loc, None)
                continue

            lookup = sq_lookups.get(loc, {})
            entry  = lookup.get(team_name)
            score  = entry["score"] if entry else None

            qualifies = qualifies_unlock(score, info["metric"], info["threshold"])

            if qualifies and loc not in team["abilities"]:
                team["abilities"][loc]       = {"size": 40, "circle_size": 10.0, "rotation": 0}
                team["ability_offsets"][loc] = [0.0, 0.0]
            elif not qualifies and loc in team["abilities"]:
                team["abilities"].pop(loc, None)
                team["ability_offsets"].pop(loc, None)


def sync_from_kaggle():
    """Sync all stage leaderboards, create/update teams"""
    cfgs = {s: STAGE_COMPETITIONS[s] for s in STAGES}

    # Fetch Algeria (required)
    raw_algeria = fetch_leaderboard_for(cfgs["Algeria"]["competition"])
    if raw_algeria is None:
        st.error("❌ Could not fetch Algeria leaderboard.")
        return
    if not raw_algeria:
        st.warning("⚠️ Algeria leaderboard is empty.")
        return

    algeria_entries = parse_entries(raw_algeria)

    # Fetch all other stages
    raws = {s: fetch_leaderboard_for(cfgs[s]["competition"]) for s in STAGES[1:]}
    lookups = {
        s: {e["teamName"]: e for e in parse_entries(raws[s])} if raws[s] else {}
        for s in STAGES[1:]
    }

    created, updated = 0, 0

    for entry in algeria_entries:
        team_name   = entry["teamName"]
        algeria_cfg = cfgs["Algeria"]
        algeria_score  = entry["score"]
        algeria_troops = score_to_troops(algeria_score, algeria_cfg["metric"], algeria_cfg["mae_threshold"], algeria_cfg["max_troops"])

        # Build unlock chain and scores for each stage
        scores  = {"Algeria": algeria_score}
        troops  = {"Algeria": algeria_troops}
        unlocked = {"Algeria": True}

        prev_stage = "Algeria"
        for stage in STAGES[1:]:
            cfg = cfgs[stage]
            prev_cfg = cfgs[prev_stage]
            prev_unlocked = unlocked[prev_stage]
            prev_score    = scores[prev_stage]

            # Unlock this stage if previous was unlocked AND previous score crosses threshold
            unlock = prev_unlocked and qualifies_unlock(prev_score, prev_cfg["metric"], prev_cfg["unlock_threshold"])
            unlocked[stage] = unlock

            if unlock and team_name in lookups[stage]:
                s = lookups[stage][team_name]["score"]
                scores[stage]  = s
                troops[stage]  = score_to_troops(s, cfg["metric"], cfg["mae_threshold"], cfg["max_troops"])
            else:
                scores[stage]  = None
                troops[stage]  = 0

            prev_stage = stage

        # Current stage = furthest unlocked
        current_stage_idx = max(
            (i for i, s in enumerate(STAGES) if unlocked[s]),
            default=0
        )

        if team_name not in st.session_state.teams:
            # CREATE
            logo_key = random.choice(list(CUSTOM_LOGOS.keys()))
            team = {
                "current_idx": current_stage_idx,
                "history":  {"Algeria": algeria_troops},
                "color":    f"#{random.randint(100,255):02x}{random.randint(100,255):02x}{random.randint(100,255):02x}",
                "logo_url": CUSTOM_LOGOS[logo_key],
                "offsets":  {"Algeria": [0.0, 0.0]},
                "rotation": {"Algeria": 0},
                "size":     {"Algeria": 50},
                "abilities": {},
                "ability_offsets": {},
            }
            # Store scores and add unlocked stages
            for stage in STAGES:
                team[f"{stage.lower().replace(' ', '_')}_score"] = scores[stage]
            for stage in STAGES[1:]:
                if unlocked[stage]:
                    team["history"][stage]  = troops[stage]
                    team["offsets"][stage]  = [0.0, 0.0]
                    team["rotation"][stage] = 0
                    team["size"][stage]     = 50
            st.session_state.teams[team_name] = team
            created += 1

        else:
            # UPDATE
            team = st.session_state.teams[team_name]
            team["history"]["Algeria"] = algeria_troops
            for stage in STAGES:
                team[f"{stage.lower().replace(' ', '_')}_score"] = scores[stage]
            for stage in STAGES[1:]:
                if unlocked[stage]:
                    if stage not in team["history"]:
                        team["history"][stage]  = 0
                        team["offsets"][stage]  = [0.0, 0.0]
                        team["rotation"][stage] = 0
                        team["size"][stage]     = 50
                    team["history"][stage] = troops[stage]
            if current_stage_idx > team["current_idx"]:
                team["current_idx"] = current_stage_idx
            updated += 1

    # Side quest leaderboards
    sq_lookups = {}
    for loc, info in SIDE_QUESTS.items():
        raw = fetch_leaderboard_for(info["competition"])
        sq_lookups[loc] = {e["teamName"]: e for e in parse_entries(raw)} if raw else {}

    evaluate_side_quests(sq_lookups)
    st.success(f"✅ Synced — {created} new teams created, {updated} updated.")
    st.rerun()


# ─────────────────────────────────────────────
# SIDEBAR
# ─────────────────────────────────────────────
with st.sidebar:
    st.header("🎮 Field Marshal Console")

    # --- ADMIN LOGIN ---
    if not st.session_state.admin_unlocked:
        pwd = st.text_input("🔐 Admin Password", type="password", key="pwd_input")
        if st.button("Unlock", use_container_width=True):
            if pwd == "yahiasinwar":
                st.session_state.admin_unlocked = True
                st.rerun()
            else:
                st.error("Wrong password.")
        st.info("👁️ Viewing in read-only mode.")

    else:
        st.success("🔓 Admin mode active")
        if st.button("🔒 Lock", use_container_width=True):
            st.session_state.admin_unlocked = False
            st.rerun()
        st.divider()

        if st.button("🔄 Sync from Kaggle Leaderboard", use_container_width=True, type="primary"):
            with st.spinner("Fetching leaderboards..."):
                sync_from_kaggle()

        st.divider()

        with st.expander("➕ Deploy New Piece"):
            new_name = st.text_input("Army Name")
            selected_logo = st.selectbox("Assign Piece Type", list(CUSTOM_LOGOS.keys()))
            if st.button("Deploy to Map"):
                if new_name and new_name not in st.session_state.teams:
                    team = {
                        "current_idx": 0,
                        "history":  {"Algeria": 500},
                        "color":    f"#{random.randint(100, 255):02x}{random.randint(100, 255):02x}{random.randint(100, 255):02x}",
                        "logo_url": CUSTOM_LOGOS[selected_logo],
                        "offsets":  {"Algeria": [0.0, 0.0]},
                        "rotation": {"Algeria": 0},
                        "size":     {"Algeria": 50},
                        "abilities": {},
                        "ability_offsets": {},
                    }
                    for stage in STAGES:
                        team[f"{stage.lower().replace(' ', '_')}_score"] = None
                    st.session_state.teams[new_name] = team
                    st.rerun()

        # --- SIDE QUEST MANAGEMENT ---
        st.divider()
        with st.expander("⚔️ Side Quest Control Panel"):
            st.caption("Activate a quest. Teams whose score crosses the threshold auto-get the ability on sync.")
            for loc, info in SIDE_QUESTS.items():
                cfg = st.session_state.side_quests_config[loc]
                col_tog, col_info = st.columns([1, 3])
                cfg["active"] = col_tog.checkbox("Open", value=cfg["active"], key=f"sq_active_{loc}")
                col_info.markdown(f"**{loc}** — {info['ability']}")
                col_info.caption(f"`{info['metric']}` threshold: `{info['threshold']}` | `{info['competition']}`")
                st.divider()

            if st.button("🔁 Re-evaluate Side Quests", use_container_width=True):
                with st.spinner("Fetching side quest leaderboards..."):
                    sq_lookups = {}
                    for loc, info in SIDE_QUESTS.items():
                        raw = fetch_leaderboard_for(info["competition"])
                        sq_lookups[loc] = {e["teamName"]: e for e in parse_entries(raw)} if raw else {}
                    evaluate_side_quests(sq_lookups)
                st.success("Side quests re-evaluated!")
                st.rerun()

        if st.session_state.teams:
            st.divider()
            t_name = st.selectbox("Select Team", list(st.session_state.teams.keys()))
            team_data = st.session_state.teams[t_name]

            # Score info per stage
            for stage in STAGES:
                key = f"{stage.lower().replace(' ', '_')}_score"
                cfg = STAGE_COMPETITIONS[stage]
                score = team_data.get(key)
                if score is not None:
                    t = team_data["history"].get(stage, 0)
                    st.caption(f"{stage} {cfg['metric']}: `{score:.4f}` → {t:,} troops")

            if st.button("🗑️ DISMISS TEAM", use_container_width=True):
                del st.session_state.teams[t_name]
                st.rerun()

            # --- ABILITY MANAGEMENT ---
            st.divider()
            st.subheader("🌟 Manage Abilities")
            selected_aq = st.selectbox("Choose Quest Location", list(SIDE_QUESTS.keys()))

            col_add, col_rem = st.columns(2)
            if col_add.button("Grant Ability"):
                team_data["abilities"][selected_aq] = {"size": 40, "circle_size": 10.0, "rotation": 0}
                team_data["ability_offsets"][selected_aq] = [0.0, 0.0]
                st.rerun()

            if col_rem.button("Remove Ability"):
                if selected_aq in team_data["abilities"]:
                    del team_data["abilities"][selected_aq]
                    st.rerun()

            if selected_aq in team_data["abilities"]:
                st.caption(f"Transforming {selected_aq} Ability Icon")
                aq_rot = st.slider(f"Rotate {selected_aq} Logo", 0, 360, int(team_data["abilities"][selected_aq].get("rotation", 0)))
                team_data["abilities"][selected_aq]["rotation"] = aq_rot

                aq_size = st.slider(f"Size {selected_aq}", 10, 150, int(team_data["abilities"][selected_aq]["size"]))
                team_data["abilities"][selected_aq]["size"] = aq_size

                aq_circ = st.slider(f"Zone Radius {selected_aq}", 1.0, 50.0, float(team_data["abilities"][selected_aq]["circle_size"]), step=1.0)
                team_data["abilities"][selected_aq]["circle_size"] = aq_circ

                off = team_data["ability_offsets"][selected_aq]
                aq_ny = st.slider("Ability Nudge Y", -5.0, 5.0, float(off[0]), step=0.1)
                aq_nx = st.slider("Ability Nudge X", -5.0, 5.0, float(off[1]), step=0.1)
                team_data["ability_offsets"][selected_aq] = [aq_ny, aq_nx]

            # --- CORE PIECE MANAGEMENT ---
            st.divider()
            st.subheader("📍 Core Path Adjustment")
            target_loc = st.selectbox("Select Visited Location:", list(team_data["history"].keys()))

            main_rot = st.slider("Rotate Main Piece", 0, 360, int(team_data["rotation"].get(target_loc, 0)))
            team_data["rotation"][target_loc] = main_rot

            main_size = st.slider("Scale Main Piece", 20, 150, int(team_data["size"].get(target_loc, 50)))
            team_data["size"][target_loc] = main_size

            core_off = team_data["offsets"].get(target_loc, [0.0, 0.0])
            main_ny = st.slider("Main Nudge Y", -5.0, 5.0, float(core_off[0]), step=0.1)
            main_nx = st.slider("Main Nudge X", -5.0, 5.0, float(core_off[1]), step=0.1)
            team_data["offsets"][target_loc] = [main_ny, main_nx]

            team_data["history"][target_loc] = st.number_input(
                "Troops", value=team_data["history"][target_loc], step=50
            )

            col_fwd, col_bck = st.columns(2)

            if team_data["current_idx"] < len(STAGES) - 1:
                if col_fwd.button(f"⏩ {STAGES[team_data['current_idx'] + 1]}", use_container_width=True):
                    team_data["current_idx"] += 1
                    new_loc = STAGES[team_data["current_idx"]]
                    team_data["history"][new_loc] = 0
                    team_data["offsets"][new_loc]  = [0.0, 0.0]
                    team_data["rotation"][new_loc] = 0
                    team_data["size"][new_loc]     = 50
                    st.rerun()

            if team_data["current_idx"] > 0:
                if col_bck.button(f"⏪ {STAGES[team_data['current_idx'] - 1]}", use_container_width=True):
                    current_loc = STAGES[team_data["current_idx"]]
                    team_data["history"].pop(current_loc, None)
                    team_data["offsets"].pop(current_loc, None)
                    team_data["rotation"].pop(current_loc, None)
                    team_data["size"].pop(current_loc, None)
                    team_data["current_idx"] -= 1
                    st.rerun()

# ─────────────────────────────────────────────
# MAP RENDERING
# ─────────────────────────────────────────────
st.title("🛡️ Tactical Deployment Board")
m = folium.Map(location=[24.0, 25.0], zoom_start=4, tiles="CartoDB dark_matter")

for loc in SIDE_QUESTS.keys():
    folium.Marker(
        location=COORDS[loc],
        icon=folium.Icon(color="gray", icon="star", prefix="fa"),
        tooltip=f"Side Quest: {loc}"
    ).add_to(m)

for name, data in st.session_state.teams.items():
    history_locs = list(data["history"].keys())

    path_coords = [
        [COORDS[l][0] + data["offsets"].get(l, [0, 0])[0],
         COORDS[l][1] + data["offsets"].get(l, [0, 0])[1]]
        for l in history_locs
    ]
    if len(path_coords) > 1:
        folium.PolyLine(path_coords, color=data["color"], weight=3, opacity=0.4, dash_array='10, 5').add_to(m)

    for loc in history_locs:
        off       = data["offsets"].get(loc, [0.0, 0.0])
        rot       = data["rotation"].get(loc, 0)
        size      = data["size"].get(loc, 50)
        troops    = data["history"][loc]
        final_pos = [COORDS[loc][0] + off[0], COORDS[loc][1] + off[1]]

        folium.Circle(
            location=final_pos, radius=troops * 12,
            color=data["color"], fill=True, fill_opacity=0.15
        ).add_to(m)

        icon_html = (
            f'<div style="transform: rotate({rot}deg); width: {size}px; height: {size}px; '
            f'filter: drop-shadow(2px 4px 6px black);">'
            f'<img src="{data["logo_url"]}" style="width: 100%; height: 100%;"></div>'
        )
        folium.Marker(
            location=final_pos,
            icon=folium.DivIcon(html=icon_html, icon_size=(size, size), icon_anchor=(size / 2, size / 2)),
            tooltip=f"<b>{name}</b><br>Troops: {troops:,}"
        ).add_to(m)

    for aq_loc, aq_data in data["abilities"].items():
        off    = data["ability_offsets"].get(aq_loc, [0.0, 0.0])
        rot    = aq_data.get("rotation", 0)
        aq_pos = [COORDS[aq_loc][0] + off[0], COORDS[aq_loc][1] + off[1]]

        folium.Circle(
            location=aq_pos, radius=aq_data["circle_size"] * 10000,
            color=data["color"], fill=True, fill_opacity=0.2, weight=1
        ).add_to(m)

        aq_size = aq_data["size"]
        aq_html = (
            f'<div style="transform: rotate({rot}deg); width: {aq_size}px; height: {aq_size}px; '
            f'filter: drop-shadow(2px 2px 4px {data["color"]});">'
            f'<img src="{data["logo_url"]}" style="width: 100%; height: 100%;"></div>'
        )
        folium.Marker(
            location=aq_pos,
            icon=folium.DivIcon(html=aq_html, icon_size=(aq_size, aq_size), icon_anchor=(aq_size / 2, aq_size / 2)),
            tooltip=f"{name} controls {aq_loc}"
        ).add_to(m)

st_folium(m, width=1200, height=650)

# ─────────────────────────────────────────────
# STATISTICS DASHBOARD
# ─────────────────────────────────────────────
st.divider()
st.header("📊 Military Intelligence Dashboard")

if st.session_state.teams:
    stats_data = []
    for name, data in st.session_state.teams.items():
        row = {
            "Army":           name,
            "Current Front":  STAGES[data["current_idx"]],
            "Total Soldiers": sum(data["history"].values()),
        }
        for stage in STAGES:
            cfg   = STAGE_COMPETITIONS[stage]
            key   = f"{stage.lower().replace(' ', '_')}_score"
            score = data.get(key)
            row[f"{stage} {cfg['metric']}"]   = f"{score:.4f}" if score is not None else "—"
            row[f"{stage} Troops"] = f"{data['history'].get(stage, 0):,}"
        row["Abilities"] = ", ".join(data["abilities"].keys()) if data["abilities"] else "None"
        stats_data.append(row)

    df = pd.DataFrame(stats_data)

    c1, c2, c3 = st.columns(3)
    top_team = df.loc[df["Total Soldiers"].idxmax()]
    c1.metric("Global Leader",  top_team["Army"], f"{top_team['Total Soldiers']:,} troops")
    c2.metric("Active Armies",  len(st.session_state.teams))
    c3.metric("Most Advanced",  df.iloc[df["Current Front"].map(lambda x: STAGES.index(x)).idxmax()]["Army"])

    st.dataframe(df, use_container_width=True)
else:
    st.info("No armies deployed yet. Use the sidebar to start the crusade.")

# ─────────────────────────────────────────────
# SIDE QUEST CODEX
# ─────────────────────────────────────────────
st.divider()
st.header("📜 Side Quest Codex")
cols = st.columns(len(SIDE_QUESTS))
for i, (loc, info) in enumerate(SIDE_QUESTS.items()):
    with cols[i]:
        st.subheader(loc)
        st.write(f"**{info['ability']}**")
        st.caption(info['desc'])
        st.caption(f"Metric: `{info['metric']}` | Threshold: `{info['threshold']}`")