import streamlit as st
import folium
from streamlit_folium import st_folium
import random
import pandas as pd
import numpy as np
import requests

# --- KAGGLE CONFIG ---
KAGGLE_USERNAME = st.secrets["kaggle_username"]
KAGGLE_API_KEY  = st.secrets["kaggle_api_key"]

# --- COMPETITION CONFIG ---
# All thresholds are loaded from st.secrets — never hardcoded her
STAGE_COMPETITIONS = {
    "Algeria": {
        "competition":      st.secrets["first"],   
        "metric":           "WMAE",
        "max_troops":       50000,
        "unlock_threshold": st.secrets["unlock_algeria"],
    },
    "Sudan": {
        "competition":      st.secrets["secod"],
        "metric":           "F1",
        "max_troops":       50000,
        "unlock_threshold": st.secrets["unlock_sudan"],
    },
    "Egypt": {
        "competition":      st.secrets["third"],
        "metric":           "CER",
        "max_troops":       50000,
        "unlock_threshold": st.secrets["unlock_egypt"],
    },
    "Saudi Arabia": {
        "competition":      st.secrets["forth"],
        "metric":           "RMSE",
        "max_troops":       50000,
        "unlock_threshold": st.secrets["unlock_saudi"],
    },
    "Palestine": {
        "competition":      "palestine",
        "metric":           "??",
        "max_troops":       50000,
        "unlock_threshold": st.secrets["unlock_palestine"],
    },
}

CUSTOM_LOGOS = {
    "Fighter Jet":  "https://i.imgur.com/ywf0aun.png",
    "Missile Truck":"https://i.imgur.com/uGvCdKp.png",
    "Tank":         "https://i.imgur.com/TGHMPxV.png",
    "Helicopter":   "https://i.imgur.com/EcCleHZ.png",
    "Submarine":    "https://i.imgur.com/zXC7TnD.png",
    "Drone": "https://i.imgur.com/X0UfGoB.png",
    "Tank2": "https://i.imgur.com/pS5yX8Z.png",

    "56" : "https://i.imgur.com/us8kcra.png",

    "45" : "https://i.imgur.com/69RB0tH.png",

    "ee": "https://i.imgur.com/KLkBDCn.png",

    "tt" : "https://i.imgur.com/Yb0XuFf.png",

    "rtr": "https://i.imgur.com/E5kFxhE.png"
}

STAGES = ["Algeria", "Sudan", "Egypt", "Saudi Arabia", "Palestine"]
COORDS = {
    "Algeria":      [28.03,  1.66],
    "Sudan":        [12.86, 30.22],
    "Egypt":        [26.82, 30.80],
    "Saudi Arabia": [23.88, 45.07],
    "Palestine":    [31.95, 35.23],
    "Iraq":         [33.22, 43.68],
    "Libya":        [26.33, 17.22],
    "Syria":        [34.80, 38.99],
    "Yemen":        [15.55, 48.51],
}

SIDE_QUESTS = {
    "Iraq":  {"ability": "Key 🔑",   "desc": "Unlock the next challenge.", "competition": "NeuralX Side Mission: Rise of Nations", "metric": "RMSE", "threshold": st.secrets["sq_iraq"]},
    "Libya": {"ability": "Extra 🚀",   "desc": "Add 5 submissions in any challenge.","competition": "tests",   "metric": "RMSE", "threshold": st.secrets["sq_libya"]},
    "Syria": {"ability": "IntelSabotage 💣",    "desc": "Reduce rival troop count.",        "competition": "SYRIA-3", "metric": "RMSE", "threshold": st.secrets["sq_syria"]},
    "Yemen": {"ability": "Intel 👁️", "desc": "Reveal 2 private score.",        "competition": "yemen_",  "metric": "MAE",   "threshold": st.secrets["sq_yemen"]},
}


import json
import os

# --- PERSISTENT MEMORY ---
DB_FILE = "game_state.json"

def save_game_state():
    with open(DB_FILE, "w") as f:
        json.dump(st.session_state.teams, f)

if 'teams' not in st.session_state:
    if os.path.exists(DB_FILE):
        with open(DB_FILE, "r") as f:
            st.session_state.teams = json.load(f)
    else:
        st.session_state.teams = {}

# --- HELPER: GET UNIQUE LOGO ---
def get_unique_logo():
    used_logos = [t["logo_url"] for t in st.session_state.teams.values()]
    available_logos = [url for url in CUSTOM_LOGOS.values() if url not in used_logos]
    if not available_logos:
        # If all 5 logos are used, just pick randomly again
        available_logos = list(CUSTOM_LOGOS.values()) 
    return random.choice(available_logos)

if 'admin_unlocked' not in st.session_state:
    st.session_state.admin_unlocked = False
if 'side_quests_config' not in st.session_state:
    st.session_state.side_quests_config = {
        loc: {"active": False} for loc in SIDE_QUESTS.keys()
    }

LOWER_IS_BETTER  = {"WMAE", "MAE", "RMSE", "CER"}
HIGHER_IS_BETTER = {"F1"}
BOTTOM_EXCLUDE   = 2


def compute_troops_for_stage(entries, metric, max_troops):
    metric = metric.upper()
    valid  = [(e["teamName"], e["score"]) for e in entries if e["score"] is not None]
    if not valid:
        return {}
    names      = [v[0] for v in valid]
    scores_arr = np.array([v[1] for v in valid], dtype=float)
    result     = {}

    if metric in HIGHER_IS_BETTER:
        for name, score in zip(names, scores_arr):
            result[name] = int(round(float(np.clip(score, 0.0, 1.0)) * max_troops))
    else:
        if len(scores_arr) == 1:
            result[names[0]] = max_troops
            return result
            
        if len(scores_arr) == 2:
            # --- THE FIX STARTS HERE ---
            if scores_arr[0] == scores_arr[1]:
                # It's a perfect tie! Give them both max troops.
                result[names[0]] = max_troops
                result[names[1]] = max_troops
            else:
                best_idx  = int(np.argmin(scores_arr))
                worst_idx = 1 - best_idx
                result[names[best_idx]]  = max_troops
                result[names[worst_idx]] = 0
            return result
            # --- THE FIX ENDS HERE ---

        sorted_scores = np.sort(scores_arr)

        trimmed = sorted_scores[:-BOTTOM_EXCLUDE] if len(sorted_scores) > BOTTOM_EXCLUDE else sorted_scores
        half        = max(1, len(trimmed) // 2)
        bottom_half = trimmed[-half:]
        baseline    = float(np.median(bottom_half))

        if baseline <= np.min(scores_arr):
            for name in names:
                result[name] = max_troops
            return result
        if baseline < 1e-9:
            baseline = float(np.max(scores_arr)) if np.max(scores_arr) > 1e-9 else 1.0

        for name, score in zip(names, scores_arr):
            score_norm = float(np.clip(score / baseline, 0.0, 1.0))
            result[name] = max(0, int(round((1.0 - score_norm) * max_troops)))

    return result


def qualifies_unlock(score, metric, unlock_threshold):
    if score is None:
        return False
    return score >= unlock_threshold if metric.upper() in HIGHER_IS_BETTER else score < unlock_threshold


def fetch_leaderboard_for(competition):
    endpoints = [
        f"https://www.kaggle.com/api/v1/competitions/{competition}/leaderboard/view",
        f"https://www.kaggle.com/api/v1/competitions/{competition}/leaderboard/download",
    ]
    auth_formats = [
        {"auth": (KAGGLE_USERNAME, KAGGLE_API_KEY)},
        {"headers": {"Authorization": f"Bearer {KAGGLE_API_KEY}"}},
        {"headers": {"Authorization": "Basic " + __import__('base64').b64encode(
            f"{KAGGLE_USERNAME}:{KAGGLE_API_KEY}".encode()).decode()}},
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
                        col_team  = next((c for c in df.columns if "team"  in c), df.columns[0])
                        col_score = next((c for c in df.columns if "score" in c), df.columns[1])
                        col_rank  = next((c for c in df.columns if "rank"  in c), None)
                        return [{"teamName": str(row[col_team]), "score": row[col_score],
                                 "rank": row[col_rank] if col_rank else None}
                                for _, row in df.iterrows()]
                    else:
                        raw = response.json()
                        if isinstance(raw, dict):
                            return raw.get("submissions", raw.get("leaderboard", []))
                        return raw
        return None
    except Exception:
        return None


def parse_entries(raw_list):
    entries = []
    for i, entry in enumerate(raw_list):
        team_name = (entry.get("teamName") or entry.get("team_name") or
                     entry.get("TeamName") or entry.get("name") or "Unknown")
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
    for team_name, team in st.session_state.teams.items():
        for loc, info in SIDE_QUESTS.items():
            cfg = st.session_state.side_quests_config[loc]
            if not cfg["active"]:
                team["abilities"].pop(loc, None)
                team["ability_offsets"].pop(loc, None)
                continue
            entry     = sq_lookups.get(loc, {}).get(team_name)
            score     = entry["score"] if entry else None
            qualifies = qualifies_unlock(score, info["metric"], info["threshold"])
            if qualifies and loc not in team["abilities"]:
                team["abilities"][loc]       = {"size": 40, "circle_size": 10.0, "rotation": 0}
                team["ability_offsets"][loc] = [0.0, 0.0]
            elif not qualifies and loc in team["abilities"]:
                team["abilities"].pop(loc, None)
                team["ability_offsets"].pop(loc, None)


def sync_from_kaggle():
    cfgs = {s: STAGE_COMPETITIONS[s] for s in STAGES}
    raw_stages = {s: fetch_leaderboard_for(cfgs[s]["competition"]) for s in STAGES}

    if raw_stages["Algeria"] is None:
        st.error("❌ Could not fetch Algeria leaderboard.")
        return
    if not raw_stages["Algeria"]:
        st.warning("⚠️ Algeria leaderboard is empty.")
        

    entries_by_stage = {s: parse_entries(raw_stages[s]) for s in STAGES if raw_stages[s]}
    lookup_by_stage  = {s: {e["teamName"]: e for e in entries_by_stage[s]} for s in entries_by_stage}
    troops_by_stage  = {
        s: compute_troops_for_stage(entries_by_stage[s], cfgs[s]["metric"], cfgs[s]["max_troops"])
        for s in STAGES if s in entries_by_stage
    }

    created, updated = 0, 0

    for entry in entries_by_stage.get("Algeria", []):
        team_name = entry["teamName"]
        scores    = {"Algeria": entry["score"]}
        troops    = {"Algeria": troops_by_stage.get("Algeria", {}).get(team_name, 0)}
        unlocked  = {"Algeria": True}

        prev_stage = "Algeria"
        for stage in STAGES[1:]:
            prev_cfg = cfgs[prev_stage]
            unlock   = unlocked[prev_stage] and qualifies_unlock(
                scores[prev_stage], prev_cfg["metric"], prev_cfg["unlock_threshold"]
            )
            unlocked[stage] = unlock
            if unlock and team_name in lookup_by_stage.get(stage, {}):
                s = lookup_by_stage[stage][team_name]["score"]
                scores[stage] = s
                troops[stage] = troops_by_stage.get(stage, {}).get(team_name, 0)
            else:
                scores[stage] = None
                troops[stage] = 0
            prev_stage = stage

        current_stage_idx = max(
            (i for i, s in enumerate(STAGES) if unlocked[s]), default=0
        )

        if team_name not in st.session_state.teams:
            logo_key = random.choice(list(CUSTOM_LOGOS.keys()))
            team = {
                "current_idx": current_stage_idx,
                "history":     {"Algeria": troops["Algeria"]},
                "casualties":  0,
                "color":       f"#{random.randint(100,255):02x}{random.randint(100,255):02x}{random.randint(100,255):02x}",
                "logo_url":    CUSTOM_LOGOS[logo_key],
                "offsets":     {"Algeria": [0.0, 0.0]},
                "rotation":    {"Algeria": 0},
                "size":        {"Algeria": 50},
                "abilities":   {},
                "ability_offsets": {},
            }
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
            team = st.session_state.teams[team_name]
            team["history"]["Algeria"] = troops["Algeria"]
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

    sq_lookups = {}
    for loc, info in SIDE_QUESTS.items():
        raw = fetch_leaderboard_for(info["competition"])
        sq_lookups[loc] = {e["teamName"]: e for e in parse_entries(raw)} if raw else {}
    # ── Automatic Purge of Ghost Teams ───────────────
    # If a team is in our memory but disappeared from the Kaggle Algeria leaderboard, delete them.
    current_kaggle_teams = set(lookup_by_stage.get("Algeria", {}).keys())
    ghost_teams = [t_name for t_name in st.session_state.teams.keys() if t_name not in current_kaggle_teams]
    
    for ghost in ghost_teams:
        del st.session_state.teams[ghost]
    evaluate_side_quests(sq_lookups)
    st.success(f"✅ Synced — {created} new teams created, {updated} updated.")
    st.rerun()


# ─────────────────────────────────────────────
# SIDEBAR
# ─────────────────────────────────────────────
# ─────────────────────────────────────────────
# SIDEBAR
# ─────────────────────────────────────────────
with st.sidebar:
    st.header("🎮 Field Marshal Console")

    # ==========================================
    # 🌍 PUBLIC / READ-ONLY TOOLS 
    # ==========================================
    st.caption("Available to all participants")
    
    # Public Sync Button
    if st.button("🔄 Sync Leaderboards from Kaggle", use_container_width=True, type="primary"):
        with st.spinner("Fetching latest leaderboards..."):
            sync_from_kaggle()

    # Public Army Evolution Inspector
    if st.session_state.teams:
        st.divider()
        st.subheader("📈 Army Evolution Tracker")
        public_t_name = st.selectbox("Inspect Army Record", list(st.session_state.teams.keys()))
        public_t_data = st.session_state.teams[public_t_name]

        for stage in STAGES:
            key   = f"{stage.lower().replace(' ', '_')}_score"
            cfg   = STAGE_COMPETITIONS[stage]
            score = public_t_data.get(key)
            if score is not None:
                t = public_t_data["history"].get(stage, 0)
                st.caption(f"**{stage}** {cfg['metric']}: `{score:.4f}` ➡️ {t:,} troops")

    st.divider()

    # ==========================================
    # ⚙️ ADMIN / GAME MASTER TOOLS
    # ==========================================
    if not st.session_state.admin_unlocked:
        st.subheader("⚙️ Game Master Tools")
        pwd = st.text_input("🔐 Admin Password", type="password", key="pwd_input")
        if st.button("Unlock Admin", use_container_width=True):
            if pwd == st.secrets["admin_password"]:
                st.session_state.admin_unlocked = True
                st.rerun()
            else:
                st.error("Wrong password.")
        st.info("👁️ Viewing in read-only mode.")

    else:
        st.success("🔓 Admin mode active")
        if st.button("🔒 Lock Admin", use_container_width=True):
            st.session_state.admin_unlocked = False
            st.rerun()
        st.divider()

        with st.expander("➕ Deploy New Piece"):
            new_name = st.text_input("Army Name")
            selected_logo = st.selectbox("Assign Piece Type", list(CUSTOM_LOGOS.keys()))
            if st.button("Deploy to Map"):
                if new_name and new_name not in st.session_state.teams:
                    team = {
                        "current_idx": 0,
                        "history":  {"Algeria": 500},
                        "casualties": 0,
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

        if st.session_state.teams:
            st.divider()
            t_name = st.selectbox("Select Team to Manage", list(st.session_state.teams.keys()), key="admin_team_select")
            team_data = st.session_state.teams[t_name]

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

            main_size = st.slider("Scale Main Piece", 0, 150, int(team_data["size"].get(target_loc, 50)))
            team_data["size"][target_loc] = main_size

            core_off = team_data["offsets"].get(target_loc, [0.0, 0.0])
            main_ny = st.slider("Main Nudge Y", -5.0, 5.0, float(core_off[0]), step=0.1)
            main_nx = st.slider("Main Nudge X", -5.0, 5.0, float(core_off[1]), step=0.1)
            team_data["offsets"][target_loc] = [main_ny, main_nx]

                        # --- THE NEW CIRCLE FIX STARTS HERE ---
            if "circle_mult" not in team_data:
                team_data["circle_mult"] = {}
                
            c_mult = team_data["circle_mult"].get(target_loc, 12.0)
            new_mult = st.slider("Troop Circle Radius", 1.0, 50.0, float(c_mult), step=1.0, key=f"circ_{t_name}_{target_loc}")
            
            if new_mult != c_mult:
                team_data["circle_mult"][target_loc] = new_mult
                save_game_state()
            # CASUALTIES CONTROLS (From earlier)
            st.divider()
            st.subheader("💣 Sabotage / Casualties")
            st.caption("Permanent troop deduction.")
            current_casualties = team_data.get("casualties", 0)
            new_casualties = st.number_input("Set Troop Casualties (-)", value=current_casualties, step=5000)
            team_data["casualties"] = new_casualties

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

        casualties = data.get("casualties", 0)

    for loc in history_locs:
        off       = data["offsets"].get(loc, [0.0, 0.0])
        rot       = data["rotation"].get(loc, 0)
        size      = data["size"].get(loc, 50)
        c_mult    = data.get("circle_mult", {}).get(loc, 12.0)
        troops    = max(0, data["history"][loc] - casualties)
        final_pos = [COORDS[loc][0] + off[0], COORDS[loc][1] + off[1]]

        folium.Circle(location=final_pos, radius=troops * c_mult,
                      color=data["color"], fill=True, fill_opacity=0.15).add_to(m)
        icon_html = (
            f'<div style="transform: rotate({rot}deg); width: {size}px; height: {size}px; '
            f'filter: drop-shadow(2px 4px 6px black);">'
            f'<img src="{data["logo_url"]}" style="width: 100%; height: 100%;"></div>'
        )
        folium.Marker(
            location=final_pos,
            icon=folium.DivIcon(html=icon_html, icon_size=(size, size), icon_anchor=(size/2, size/2)),
            tooltip=f"<b>{name}</b><br>Troops: {troops:,}"
        ).add_to(m)


    for aq_loc, aq_data in data["abilities"].items():
        off    = data["ability_offsets"].get(aq_loc, [0.0, 0.0])
        rot    = aq_data.get("rotation", 0)
        aq_pos = [COORDS[aq_loc][0] + off[0], COORDS[aq_loc][1] + off[1]]
        folium.Circle(location=aq_pos, radius=aq_data["circle_size"] * 10000,
                      color=data["color"], fill=True, fill_opacity=0.2, weight=1).add_to(m)
        aq_size = aq_data["size"]
        aq_html = (
            f'<div style="transform: rotate({rot}deg); width: {aq_size}px; height: {aq_size}px; '
            f'filter: drop-shadow(2px 2px 4px {data["color"]});">'
            f'<img src="{data["logo_url"]}" style="width: 100%; height: 100%;"></div>'
        )
        folium.Marker(
            location=aq_pos,
            icon=folium.DivIcon(html=aq_html, icon_size=(aq_size, aq_size), icon_anchor=(aq_size/2, aq_size/2)),
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
        base_troops = sum(data["history"].values())
        casualties  = data.get("casualties", 0)
        final_total = max(0, base_troops - casualties)
        row = {
            "Army":           name,
            "Current Front":  STAGES[data["current_idx"]],
            "Base Troops":    base_troops,
            "Casualties":     f"-{casualties:,}" if casualties > 0 else "0",
            "Total Soldiers": final_total,
        }
        for stage in STAGES:
            cfg   = STAGE_COMPETITIONS[stage]
            key   = f"{stage.lower().replace(' ', '_')}_score"
            score = data.get(key)
            row[f"{stage} {cfg['metric']}"] = f"{score:.4f}" if score is not None else "—"
            row[f"{stage} Troops"]          = f"{data['history'].get(stage, 0):,}"
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
        # Metric shown, threshold hidden
        st.caption(f"Metric: `{info['metric']}`")
