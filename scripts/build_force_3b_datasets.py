"""
建置「一二壘有人：封殺三壘決策分析」所需之整合數據集：
1. 從 2026 MLB Statcast RISP 擊球資料篩選精確「一二壘有人（無三壘跑者）、0或1出局、滾地球與短打」事件
2. 轉換 Statcast 座標 (hc_x, hc_y) 為真實球場英尺座標 (field_x_ft, field_y_ft) 與距離三壘壘包距離 (dist_to_3b_ft)
3. 串接二壘跑者速度 (Sprint Speed / 90ft Splits) 與接球野手臂力 (Arm Strength / Pop Time)
4. 依據文字紀錄 (des) 與事件類型 (events) 標記守備實際傳球選擇與是否封殺三壘成功
5. 產出 RE24 基準表與「封殺三壘 BEP 損益兩平點」參考表
"""
from pathlib import Path
import csv
import math
import re
from collections import Counter

BASE_DIR = Path(__file__).resolve().parent.parent
LARGE_DIR = BASE_DIR / "data" / "large"
OUT_DIR = BASE_DIR / "data" / "force_3b"
LB_DIR = OUT_DIR / "leaderboards"

POS_MAP = {
    "1": ("P", "pitcher", "arm_overall"),
    "2": ("C", "fielder_2", "arm_overall"),
    "3": ("1B", "fielder_3", "arm_1b"),
    "4": ("2B", "fielder_4", "arm_2b"),
    "5": ("3B", "fielder_5", "arm_3b"),
    "6": ("SS", "fielder_6", "arm_ss"),
    "7": ("LF", "fielder_7", "arm_lf"),
    "8": ("CF", "fielder_8", "arm_cf"),
    "9": ("RF", "fielder_9", "arm_rf"),
}


def to_float(val):
    if val is None:
        return None
    s = str(val).strip()
    if not s or s.upper() == "NA":
        return None
    try:
        return float(s)
    except ValueError:
        return None


def load_lookup_tables():
    sprint = {}
    with open(LB_DIR / "sprint_speed_2026.csv", encoding="utf-8-sig") as f:
        for row in csv.DictReader(f):
            pid = row.get("player_id", "").strip()
            if pid:
                sprint[pid] = {
                    "name": row.get("last_name, first_name", "").strip(),
                    "sprint_speed": to_float(row.get("sprint_speed")),
                    "hp_to_1b": to_float(row.get("hp_to_1b")),
                }

    splits = {}
    with open(LB_DIR / "running_splits_90ft_2026.csv", encoding="utf-8-sig") as f:
        for row in csv.DictReader(f):
            pid = row.get("player_id", "").strip()
            if pid:
                splits[pid] = {
                    "name": row.get("last_name, first_name", "").strip(),
                    "sec_75ft": to_float(row.get("seconds_since_hit_075")),
                    "sec_80ft": to_float(row.get("seconds_since_hit_080")),
                    "sec_90ft": to_float(row.get("seconds_since_hit_090")),
                }

    arms = {}
    with open(LB_DIR / "arm_strength_2026.csv", encoding="utf-8-sig") as f:
        for row in csv.DictReader(f):
            pid = row.get("player_id", "").strip()
            if pid:
                arms[pid] = {
                    "name": row.get("fielder_name", "").strip(),
                    "max_arm": to_float(row.get("max_arm_strength")),
                    "arm_overall": to_float(row.get("arm_overall")),
                    "arm_inf": to_float(row.get("arm_inf")),
                    "arm_1b": to_float(row.get("arm_1b")),
                    "arm_2b": to_float(row.get("arm_2b")),
                    "arm_3b": to_float(row.get("arm_3b")),
                    "arm_ss": to_float(row.get("arm_ss")),
                }

    poptime = {}
    with open(LB_DIR / "catcher_poptime_2026.csv", encoding="utf-8-sig") as f:
        for row in csv.DictReader(f):
            pid = row.get("entity_id", "").strip()
            if pid:
                poptime[pid] = {
                    "name": row.get("entity_name", "").strip(),
                    "arm_c": to_float(row.get("maxeff_arm_2b_3b_sba")),
                    "exchange_c": to_float(row.get("exchange_2b_3b_sba")),
                    "pop_3b": to_float(row.get("pop_3b_sba")),
                }

    return sprint, splits, arms, poptime


def classify_play(events: str, des: str):
    d = des.lower()
    is_bunt = (events == "sac_bunt") or ("bunt" in d)
    out_3b = ("out at 3rd" in d) or ("out at third" in d)
    out_2b = ("out at 2nd" in d) or ("out at second" in d)
    out_1b = (
        ("out at 1st" in d)
        or ("grounds out" in d)
        or ("sacrifice bunt" in d and "out on a sacrifice bunt" in d)
    )
    has_error = ("error" in d) or (events == "field_error")

    if events in ("single", "double", "triple", "home_run"):
        choice = "BASE_HIT"
    elif events == "triple_play":
        choice = "TRIPLE_PLAY"
    elif events in ("grounded_into_double_play", "double_play"):
        if out_3b:
            choice = "DP_WITH_3B_OUT"
        elif out_2b and out_1b:
            choice = "DP_2B_1B"
        else:
            choice = "DP_OTHER"
    elif events in ("force_out", "fielders_choice_out"):
        if out_3b:
            choice = "FORCE_3B_SUCCESS"
        elif out_2b:
            choice = "FORCE_2B_SINGLE_OUT"
        else:
            choice = "FORCE_OTHER"
    elif events in ("field_out", "sac_bunt"):
        if out_3b:
            choice = "FORCE_3B_SUCCESS"
        elif out_1b:
            choice = "OUT_1B_ONLY"
        else:
            choice = "FIELD_OUT_OTHER"
    elif events in ("fielders_choice", "field_error"):
        choice = "FC_ALL_SAFE_OR_ERROR"
    else:
        choice = "OTHER"

    return is_bunt, out_3b, out_2b, out_1b, has_error, choice


def convert_coords(hc_x, hc_y):
    """
    將 Baseball Savant Statcast (hc_x, hc_y) 轉為標準球場英尺座標：
    本壘 = (0, 0)
    一壘 = (+63.64, +63.64)
    二壘 = (0, +127.28)
    三壘 = (-63.64, +63.64)
    """
    if hc_x is None or hc_y is None:
        return None, None, None, None, None
    fx = 2.495671 * (hc_x - 125.42)
    fy = 2.495671 * (198.27 - hc_y)
    dist_hp = math.hypot(fx, fy)
    dist_3b = math.hypot(fx - (-63.6396), fy - 63.6396)
    spray_deg = math.degrees(math.atan2(fx, fy)) if (fx != 0 or fy != 0) else 0.0
    return (
        round(fx, 2),
        round(fy, 2),
        round(dist_hp, 2),
        round(dist_3b, 2),
        round(spray_deg, 2),
    )


def build_datasets():
    sprint, splits, arms, poptime = load_lookup_tables()
    raw_path = LARGE_DIR / "statcast_2026_risp_all_bip_raw.csv"
    out_rows = []
    bunt_rows = []

    with open(raw_path, encoding="utf-8-sig") as f:
        for row in csv.DictReader(f):
            on1 = row.get("on_1b", "").strip()
            on2 = row.get("on_2b", "").strip()
            on3 = row.get("on_3b", "").strip()
            outs = row.get("outs_when_up", "").strip()
            if not (on1 and on2 and not on3 and outs in ("0", "1")):
                continue

            bb = row.get("bb_type", "").strip()
            ev = row.get("events", "").strip()
            des = row.get("des", "").strip()
            if not (bb == "ground_ball" or "bunt" in des.lower() or ev == "sac_bunt"):
                continue

            is_bunt, out_3b, out_2b, out_1b, has_error, choice = classify_play(ev, des)
            hc_x = to_float(row.get("hc_x"))
            hc_y = to_float(row.get("hc_y"))
            fx, fy, dist_hp, dist_3b, spray_deg = convert_coords(hc_x, hc_y)

            # Runner on 2nd base info
            r2_id = str(int(float(on2))) if on2 else ""
            r2_sp = sprint.get(r2_id, {})
            r2_sl = splits.get(r2_id, {})

            # Fielder info via hit_location
            hloc = row.get("hit_location", "").strip()
            if hloc.endswith(".0"):
                hloc = hloc[:-2]
            pos_abbr, f_col, arm_key = POS_MAP.get(hloc, ("UNK", "", ""))
            f_id = ""
            if f_col:
                raw_fid = row.get(f_col, "").strip()
                if raw_fid:
                    f_id = str(int(float(raw_fid)))

            f_name = ""
            f_arm = None
            f_max_arm = None
            if f_id in arms:
                f_name = arms[f_id]["name"]
                f_arm = arms[f_id].get(arm_key) or arms[f_id].get("arm_inf") or arms[f_id].get("arm_overall")
                f_max_arm = arms[f_id].get("max_arm")
            elif pos_abbr == "C" and f_id in poptime:
                f_name = poptime[f_id]["name"]
                f_arm = poptime[f_id].get("arm_c")
                f_max_arm = f_arm

            bat_sc = to_float(row.get("bat_score"))
            fld_sc = to_float(row.get("fld_score"))
            score_diff = int(bat_sc - fld_sc) if (bat_sc is not None and fld_sc is not None) else None

            rec = {
                "game_pk": row.get("game_pk", "").strip(),
                "game_date": row.get("game_date", "").strip(),
                "home_team": row.get("home_team", "").strip(),
                "away_team": row.get("away_team", "").strip(),
                "inning": row.get("inning", "").strip(),
                "inning_topbot": row.get("inning_topbot", "").strip(),
                "outs_when_up": int(outs),
                "bat_score": int(bat_sc) if bat_sc is not None else "",
                "fld_score": int(fld_sc) if fld_sc is not None else "",
                "bat_score_diff": score_diff if score_diff is not None else "",
                "batter_id": row.get("batter", "").strip(),
                "batter_name": row.get("player_name", "").strip(),
                "batter_stand": row.get("stand", "").strip(),
                "runner_1b_id": str(int(float(on1))) if on1 else "",
                "runner_2b_id": r2_id,
                "runner_2b_name": r2_sp.get("name") or r2_sl.get("name") or "",
                "runner_2b_sprint_speed_fts": r2_sp.get("sprint_speed") if r2_sp.get("sprint_speed") is not None else "",
                "runner_2b_hp_to_1b_sec": r2_sp.get("hp_to_1b") if r2_sp.get("hp_to_1b") is not None else "",
                "runner_2b_75ft_sec": r2_sl.get("sec_75ft") if r2_sl.get("sec_75ft") is not None else "",
                "runner_2b_90ft_sec": r2_sl.get("sec_90ft") if r2_sl.get("sec_90ft") is not None else "",
                "bb_type": bb,
                "is_bunt": is_bunt,
                "launch_speed_mph": to_float(row.get("launch_speed")) if to_float(row.get("launch_speed")) is not None else "",
                "launch_angle_deg": to_float(row.get("launch_angle")) if to_float(row.get("launch_angle")) is not None else "",
                "hc_x": hc_x if hc_x is not None else "",
                "hc_y": hc_y if hc_y is not None else "",
                "field_x_ft": fx if fx is not None else "",
                "field_y_ft": fy if fy is not None else "",
                "dist_from_hp_ft": dist_hp if dist_hp is not None else "",
                "dist_to_3b_ft": dist_3b if dist_3b is not None else "",
                "spray_angle_deg": spray_deg if spray_deg is not None else "",
                "hit_location": hloc,
                "fielded_by_pos": pos_abbr,
                "fielder_id": f_id,
                "fielder_name": f_name,
                "fielder_arm_mph": f_arm if f_arm is not None else "",
                "fielder_max_arm_mph": f_max_arm if f_max_arm is not None else "",
                "if_fielding_alignment": row.get("if_fielding_alignment", "").strip(),
                "events": ev,
                "out_at_3b": out_3b,
                "out_at_2b": out_2b,
                "out_at_1b": out_1b,
                "has_error": has_error,
                "defensive_choice": choice,
                "delta_run_exp": to_float(row.get("delta_run_exp")) if to_float(row.get("delta_run_exp")) is not None else "",
                "home_win_exp": to_float(row.get("home_win_exp")) if to_float(row.get("home_win_exp")) is not None else "",
                "delta_home_win_exp": to_float(row.get("delta_home_win_exp")) if to_float(row.get("delta_home_win_exp")) is not None else "",
                "des": des,
            }
            out_rows.append(rec)
            if is_bunt:
                bunt_rows.append(rec)

    fieldnames = list(out_rows[0].keys())
    with open(OUT_DIR / "mlb_2026_1b2b_groundballs_bunts.csv", "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=fieldnames)
        w.writeheader()
        w.writerows(out_rows)

    with open(OUT_DIR / "mlb_2026_1b2b_bunts_only.csv", "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=fieldnames)
        w.writeheader()
        w.writerows(bunt_rows)

    # Empirical summary by Outs x Defensive Choice
    stats = {}
    for r in out_rows:
        key = (r["outs_when_up"], r["is_bunt"], r["defensive_choice"])
        if key not in stats:
            stats[key] = {"count": 0, "dre_sum": 0.0, "dre_n": 0, "dist3b_sum": 0.0, "dist3b_n": 0}
        stats[key]["count"] += 1
        if r["delta_run_exp"] != "":
            stats[key]["dre_sum"] += float(r["delta_run_exp"])
            stats[key]["dre_n"] += 1
        if r["dist_to_3b_ft"] != "":
            stats[key]["dist3b_sum"] += float(r["dist_to_3b_ft"])
            stats[key]["dist3b_n"] += 1

    emp_rows = []
    for (outs_val, bunt_flag, choice_val), st in sorted(stats.items()):
        emp_rows.append({
            "outs_when_up": outs_val,
            "is_bunt": bunt_flag,
            "defensive_choice": choice_val,
            "play_count": st["count"],
            "avg_delta_run_exp": round(st["dre_sum"] / st["dre_n"], 4) if st["dre_n"] else "",
            "avg_dist_to_3b_ft": round(st["dist3b_sum"] / st["dist3b_n"], 2) if st["dist3b_n"] else "",
        })
    with open(OUT_DIR / "force_3b_empirical_summary_2026.csv", "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=list(emp_rows[0].keys()))
        w.writeheader()
        w.writerows(emp_rows)

    # RE24 Reference Matrix (MLB 2024-2026 Modern Era & CPBL Rebas Reference)
    # States: base_state -> (0_out, 1_out, 2_out)
    re24_rows = [
        # MLB modern run environment (~4.45 R/G)
        ("MLB_Modern", "Empty", 0.481, 0.254, 0.098),
        ("MLB_Modern", "1B", 0.859, 0.509, 0.224),
        ("MLB_Modern", "2B", 1.100, 0.664, 0.319),
        ("MLB_Modern", "3B", 1.350, 0.950, 0.353),
        ("MLB_Modern", "1B_2B", 1.437, 0.884, 0.429),
        ("MLB_Modern", "1B_3B", 1.784, 1.130, 0.478),
        ("MLB_Modern", "2B_3B", 1.964, 1.376, 0.580),
        ("MLB_Modern", "1B_2B_3B", 2.292, 1.541, 0.752),
        # CPBL reference (aligned with Rebas sf-bep run environment)
        ("CPBL_Rebas_Ref", "Empty", 0.500, 0.265, 0.099),
        ("CPBL_Rebas_Ref", "1B", 0.885, 0.525, 0.230),
        ("CPBL_Rebas_Ref", "2B", 1.135, 0.685, 0.325),
        ("CPBL_Rebas_Ref", "3B", 1.395, 0.960, 0.371),
        ("CPBL_Rebas_Ref", "1B_2B", 1.480, 0.915, 0.440),
        ("CPBL_Rebas_Ref", "1B_3B", 1.825, 1.160, 0.495),
        ("CPBL_Rebas_Ref", "2B_3B", 2.010, 1.410, 0.600),
        ("CPBL_Rebas_Ref", "1B_2B_3B", 2.340, 1.585, 0.775),
    ]
    with open(OUT_DIR / "re24_matrix_reference.csv", "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["league", "base_state", "re_0_out", "re_1_out", "re_2_out"])
        w.writerows(re24_rows)

    # Calculate Force-3B Break-Even Point (BEP) Scenarios from RE24
    re_map = {(lg, bs): (r0, r1, r2) for lg, bs, r0, r1, r2 in re24_rows}
    bep_rows = []
    for lg in ["MLB_Modern", "CPBL_Rebas_Ref"]:
        # 1) 0 Outs, 1B&2B: Throw 3B vs Throw 1B (Safe = 1 out 2B_3B; 3B Success = 1 out 1B_2B; 3B Fail = 0 out Loaded)
        re_hold = re_map[(lg, "2B_3B")][1]
        re_succ = re_map[(lg, "1B_2B")][1]
        re_fail = re_map[(lg, "1B_2B_3B")][0]
        bep = (re_fail - re_hold) / (re_fail - re_succ)
        bep_rows.append({
            "league": lg, "outs_when_up": 0, "comparison": "Force_3B_vs_Safe_1B",
            "re_if_safe_option": re_hold, "re_if_3b_success": re_succ, "re_if_3b_fail_loaded": re_fail,
            "bep_min_success_prob": round(bep, 4), "bep_pct": f"{bep*100:.1f}%",
            "notes": "0出局一二壘有人(如短打/軟弱滾地球)：傳三壘 vs 穩抓一壘"
        })

        # 2) 0 Outs, 1B&2B: Throw 3B vs Throw 2B Single Out (Safe = 1 out 1B_3B; 3B Success = 1 out 1B_2B; 3B Fail = 0 out Loaded)
        re_hold_2b = re_map[(lg, "1B_3B")][1]
        bep_2b = (re_fail - re_hold_2b) / (re_fail - re_succ)
        bep_rows.append({
            "league": lg, "outs_when_up": 0, "comparison": "Force_3B_vs_Force_2B_SingleOut",
            "re_if_safe_option": re_hold_2b, "re_if_3b_success": re_succ, "re_if_3b_fail_loaded": re_fail,
            "bep_min_success_prob": round(bep_2b, 4), "bep_pct": f"{bep_2b*100:.1f}%",
            "notes": "0出局一二壘有人(無法雙殺時)：傳三壘 vs 穩抓二壘單殺"
        })

        # 3) 1 Out, 1B&2B: Throw 3B vs Throw 1B (Safe = 2 out 2B_3B; 3B Success = 2 out 1B_2B; 3B Fail = 1 out Loaded)
        re_hold_1 = re_map[(lg, "2B_3B")][2]
        re_succ_1 = re_map[(lg, "1B_2B")][2]
        re_fail_1 = re_map[(lg, "1B_2B_3B")][1]
        bep_1 = (re_fail_1 - re_hold_1) / (re_fail_1 - re_succ_1)
        bep_rows.append({
            "league": lg, "outs_when_up": 1, "comparison": "Force_3B_vs_Safe_1B",
            "re_if_safe_option": re_hold_1, "re_if_3b_success": re_succ_1, "re_if_3b_fail_loaded": re_fail_1,
            "bep_min_success_prob": round(bep_1, 4), "bep_pct": f"{bep_1*100:.1f}%",
            "notes": "1出局一二壘有人：傳三壘 vs 穩抓一壘(2出局二三壘)"
        })

        # 4) 1 Out, 1B&2B: Throw 3B vs Throw 2B Single Out (Safe = 2 out 1B_3B; 3B Success = 2 out 1B_2B; 3B Fail = 1 out Loaded)
        re_hold_1_2b = re_map[(lg, "1B_3B")][2]
        bep_1_2b = (re_fail_1 - re_hold_1_2b) / (re_fail_1 - re_succ_1)
        bep_rows.append({
            "league": lg, "outs_when_up": 1, "comparison": "Force_3B_vs_Force_2B_SingleOut",
            "re_if_safe_option": re_hold_1_2b, "re_if_3b_success": re_succ_1, "re_if_3b_fail_loaded": re_fail_1,
            "bep_min_success_prob": round(bep_1_2b, 4), "bep_pct": f"{bep_1_2b*100:.1f}%",
            "notes": "1出局一二壘有人(無法雙殺時)：傳三壘 vs 穩抓二壘單殺(2出局一三壘)"
        })

    with open(OUT_DIR / "force_3b_bep_scenarios.csv", "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=list(bep_rows[0].keys()))
        w.writeheader()
        w.writerows(bep_rows)

    print(f"Total 2026 1B&2B groundballs+bunts saved: {len(out_rows)}")
    print(f"Total 2026 1B&2B bunts_only saved: {len(bunt_rows)}")
    print("Choice breakdown:", Counter(r["defensive_choice"] for r in out_rows))
    print("Runner 2B speed matched:", sum(1 for r in out_rows if r["runner_2b_sprint_speed_fts"] != ""), "/", len(out_rows))
    print("Fielder arm matched:", sum(1 for r in out_rows if r["fielder_arm_mph"] != ""), "/", len(out_rows))


if __name__ == "__main__":
    build_datasets()
