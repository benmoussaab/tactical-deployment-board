import statistics

# --- UPDATED COMPETITION CONFIG ---
STAGE_COMPETITIONS = {
    "Algeria": {
        "competition": "uuuuuu",
        "metric": "WMAE", # Updated
        "max_troops": 50000,
        "unlock_threshold": 1000,
    },
    "Sudan": {
        "competition": "Sudan_2",
        "metric": "CER", # Updated
        "max_troops": 50000,
        "unlock_threshold": 1.0,
    },
    "Egypt": {
        "competition": "Egypte",
        "metric": "F1 MACRO", # Updated
        "max_troops": 50000,
        "unlock_threshold": 0.5,
    },
    "Saudi Arabia": {
        "competition": "bike-demande-competition",
        "metric": "RMSE", # Updated
        "max_troops": 50000,
        "unlock_threshold": 1000,
    },
    "Palestine": {
        "competition": "palestine",
        "metric": "MAE",
        "max_troops": 50000,
        "unlock_threshold": 1000,
    },
}

# --- UPDATED SIDE QUESTS ---
SIDE_QUESTS = {
    "Iraq":  {"ability": "Freeze ❄️",   "desc": "Stop a rival team's submissions.", "competition": "NeuralX Side Mission: Rise of Nations", "metric": "RMSE",  "threshold": 0.1},
    "Libya": {"ability": "Shield 🛡️",   "desc": "Protect from sabotage.",           "competition": "libya",  "metric": "RMSE",  "threshold": 4.0},
    "Syria": {"ability": "Intel 👁️",    "desc": "Reveal rival submissions.",        "competition": "SYRIA-3","metric": "RMSE", "threshold": 7.0},
    "Yemen": {"ability": "Sabotage 💣", "desc": "Reduce rival troop count.",         "competition": "yemen_", "metric": "F1 MACRO",   "threshold": 0.90},
}

# --- NEW ROBUST CALCULATION LOGIC ---

def calculate_robust_troops_distribution(scores_dict, metric, max_troops):
    """
    Calculates troops for a group of scores using trimming to ignore noise (0 scores)
    and robust statistics (MAD) to allow infinite scaling for 1st place.
    """
    valid_teams = {k: v for k, v in scores_dict.items() if v is not None}
    if len(valid_teams) < 2:
        return {k: (int(max_troops * 0.5) if v is not None else 0) for k, v in scores_dict.items()}

    all_scores = sorted(list(valid_teams.values()))
    
    # 1. Trimming: Ignore bottom 10% (noise) and top 10% (outliers) to find the 'standard'
    lower_idx = max(0, int(len(all_scores) * 0.1))
    upper_idx = max(1, int(len(all_scores) * 0.9))
    trimmed_scores = all_scores[lower_idx:upper_idx]
    
    if not trimmed_scores or len(set(trimmed_scores)) == 1:
        trimmed_scores = all_scores

    # 2. Robust Stats
    median_val = statistics.median(trimmed_scores)
    mad = statistics.median([abs(s - median_val) for s in trimmed_scores])
    robust_stdev = mad * 1.4826
    
    if robust_stdev == 0:
        robust_stdev = statistics.stdev(all_scores) if len(all_scores) > 1 else 1.0

    is_higher_better = metric.upper() in ("F1", "F1 MACRO", "ACCURACY", "R2")

    distribution = {}
    for team, score in scores_dict.items():
        if score is None:
            distribution[team] = 0
            continue

        # Calculate Z-score relative to the 'Serious Pack'
        z = (score - median_val) / robust_stdev
        if not is_higher_better:
            z = -z

        # Linear Scaling: Median gets 50% max_troops. Each Z gets +20%.
        # This allows scores to go WAY above max_troops if they are outliers.
        final_troops = (max_troops * 0.5) + (z * (max_troops * 0.2))
        
        # Floor: 5% of max_troops minimum for anyone who submitted
        distribution[team] = int(max(max_troops * 0.05, final_troops))

    return distribution

# --- MODIFIED SYNC FUNCTION ---

def sync_from_kaggle():
    """Sync all stage leaderboards and calculate troops using Robust Distribution"""
    cfgs = {s: STAGE_COMPETITIONS[s] for s in STAGES}
    
    # 1. Fetch all raw data first
    stage_data = {}
    for stage in STAGES:
        raw = fetch_leaderboard_for(cfgs[stage]["competition"])
        stage_data[stage] = {e["teamName"]: e["score"] for e in parse_entries(raw)} if raw else {}

    # Algeria defines the team list
    if not stage_data["Algeria"]:
        st.error("❌ Could not fetch Algeria leaderboard.")
        return

    # 2. Pre-calculate the Robust Troop Distributions for every stage
    # This considers all players on Kaggle to define the "scale"
    stage_troop_maps = {}
    for stage in STAGES:
        stage_troop_maps[stage] = calculate_robust_troops_distribution(
            stage_data[stage], 
            cfgs[stage]["metric"], 
            cfgs[stage]["max_troops"]
        )

    # 3. Process Team Updates
    created, updated = 0, 0
    for team_name, algeria_score in stage_data["Algeria"].items():
        unlocked = {"Algeria": True}
        scores = {"Algeria": algeria_score}
        
        # Determine unlock chain
        prev_stage = "Algeria"
        for stage in STAGES[1:]:
            prev_cfg = cfgs[prev_stage]
            can_unlock = unlocked[prev_stage] and qualifies_unlock(scores[prev_stage], prev_cfg["metric"], prev_cfg["unlock_threshold"])
            unlocked[stage] = can_unlock
            scores[stage] = stage_data[stage].get(team_name) if can_unlock else None
            prev_stage = stage

        current_idx = max((i for i, s in enumerate(STAGES) if unlocked[s]), default=0)

        # Build History dict
        history = {}
        for stage in STAGES:
            if unlocked[stage]:
                history[stage] = stage_troop_maps[stage].get(team_name, 0)

        if team_name not in st.session_state.teams:
            logo_key = random.choice(list(CUSTOM_LOGOS.keys()))
            st.session_state.teams[team_name] = {
                "current_idx": current_idx,
                "history": history,
                "color": f"#{random.randint(100,255):02x}{random.randint(100,255):02x}{random.randint(100,255):02x}",
                "logo_url": CUSTOM_LOGOS[logo_key],
                "offsets": {s: [0.0, 0.0] for s in history},
                "rotation": {s: 0 for s in history},
                "size": {s: 50 for s in history},
                "abilities": {},
                "ability_offsets": {},
            }
            created += 1
        else:
            team = st.session_state.teams[team_name]
            team["history"] = history
            team["current_idx"] = current_idx
            # Ensure new stages have default UI configs
            for s in history:
                if s not in team["offsets"]:
                    team["offsets"][s] = [0.0, 0.0]
                    team["rotation"][s] = 0
                    team["size"][s] = 50
            updated += 1
            
        # Store raw scores for the dashboard
        for stage in STAGES:
            st.session_state.teams[team_name][f"{stage.lower().replace(' ', '_')}_score"] = scores[stage]

    # Side quest sync
    sq_lookups = {}
    for loc, info in SIDE_QUESTS.items():
        raw = fetch_leaderboard_for(info["competition"])
        sq_lookups[loc] = {e["teamName"]: e for e in parse_entries(raw)} if raw else {}
    evaluate_side_quests(sq_lookups)

    st.success(f"✅ Synced: {created} new, {updated} updated.")
    st.rerun()