"""
一二壘有人：封殺三壘決策判斷 — 核心分析模型與模擬器資料匯出引擎
對齊 2026 野革盃 (REBAS Hackathon) sf-bep 雙階段架構：
  STEP 1: RE24 (1~6局) 與 WPA 勝率矩陣 (7~9局/延長) 損益兩平點 BEP 計算
  STEP 2: 時間差邏輯斯模型 (Time-Margin Logistic Model) 計算內野各落點封殺三壘成功率
  STEP 3: 匯出 2026 MLB 實戰散點、球員預設檔與矩陣至 web/data/force_3b_model_data.json
"""
from pathlib import Path
import csv
import json
import math

BASE_DIR = Path(__file__).resolve().parent.parent
FORCE_3B_DIR = BASE_DIR / "data" / "force_3b"
LB_DIR = FORCE_3B_DIR / "leaderboards"
WEB_DATA_DIR = BASE_DIR / "web" / "data"

# 三壘壘包座標 (英尺)：本壘 (0,0), 一壘 (63.64, 63.64), 二壘 (0, 127.28), 三壘 (-63.64, 63.64)
THIRD_BASE_X = -63.6396
THIRD_BASE_Y = 63.6396

# 各守位預設接球轉傳時間 (秒，含轉身調整步伐) 與預設傳球球速 (mph)
DEFAULT_POS_PARAMS = {
    "P": {"label": "投手 (P)", "exchange_sec": 0.96, "arm_mph": 78.0, "x": 0.0, "y": 60.5},
    "C": {"label": "捕手 (C)", "exchange_sec": 0.84, "arm_mph": 82.0, "x": 0.0, "y": 4.0},
    "1B": {"label": "一壘手 (1B)", "exchange_sec": 1.04, "arm_mph": 76.0, "x": 58.0, "y": 78.0},
    "3B": {"label": "三壘手 (3B)", "exchange_sec": 0.78, "arm_mph": 83.5, "x": -56.0, "y": 82.0},
    "SS": {"label": "游擊手 (SS)", "exchange_sec": 0.85, "arm_mph": 84.5, "x": -34.0, "y": 122.0},
}


def load_re24_matrix():
    """載入 MLB 與 CPBL RE24 矩陣。"""
    matrix = {}
    with open(FORCE_3B_DIR / "re24_matrix_reference.csv", encoding="utf-8") as f:
        for row in csv.DictReader(f):
            lg = row["league"]
            bs = row["base_state"]
            matrix.setdefault(lg, {})[bs] = [
                float(row["re_0_out"]),
                float(row["re_1_out"]),
                float(row["re_2_out"]),
            ]
    return matrix


def compute_re24_bep(re24: dict, outs: int, comparison: str = "vs_1b") -> dict:
    """
    計算 1~6 局 (RE24) 封殺三壘最低成功率門檻 (BEP)。
    comparison:
      - 'vs_1b': 傳三壘 vs 穩傳一壘 (安全選項 -> outs+1, 2B_3B)
      - 'vs_2b': 傳三壘 vs 穩抓二壘單殺 (安全選項 -> outs+1, 1B_3B)
    """
    safe_state = "2B_3B" if comparison == "vs_1b" else "1B_3B"
    re_safe = re24[safe_state][outs + 1]
    re_succ = re24["1B_2B"][outs + 1]
    re_fail = re24["1B_2B_3B"][outs]
    bep = (re_fail - re_safe) / (re_fail - re_succ)
    return {
        "mode": "RE24",
        "safe_state": f"{outs + 1} 出局 {'二三壘' if comparison == 'vs_1b' else '一三壘'}",
        "succ_state": f"{outs + 1} 出局 一二壘",
        "fail_state": f"{outs} 出局 滿壘",
        "val_safe": round(re_safe, 3),
        "val_succ": round(re_succ, 3),
        "val_fail": round(re_fail, 3),
        "bep": round(max(0.0, min(1.0, bep)), 4),
    }


def _half_inning_run_dist(re_val: float, max_runs: int = 8) -> list[float]:
    """
    以校正後的零膨脹幾何/負二項近似分佈模擬半局剩餘得分機率分佈 P(R = k)，
    並使期望值精確等於 RE24 值 re_val（用於快速且穩健地推算 7~9 局與延長賽 WPA）。
    """
    # P(R >= 1) 隨 RE 值遞增，符合 MLB/CPBL 實際得分機率曲線
    p_score = 1.0 - math.exp(-0.78 * re_val)
    p_score = max(0.02, min(0.92, p_score))
    # 條件於至少得 1 分，剩餘分數服從幾何分佈，使 E[R] = re_val
    cond_mean = max(1.02, re_val / p_score)
    q = 1.0 - (1.0 / cond_mean)
    probs = [1.0 - p_score]
    for k in range(1, max_runs):
        probs.append(p_score * ((1.0 - q) * (q ** (k - 1))))
    rem = max(0.0, 1.0 - sum(probs))
    probs.append(rem)
    return probs


def _future_win_prob(fld_lead: int, remaining_off_half: int, remaining_def_half: int, rpg_half: float = 0.49) -> float:
    """
    給定「目前半局結束後」守備方領先分數 fld_lead 與後續剩餘攻守半局數，
    計算守備方最終獲勝機率（含延長賽平手 50% / 主隊略高 52%）。
    """
    if remaining_off_half <= 0 and remaining_def_half <= 0:
        if fld_lead > 0:
            return 1.0
        if fld_lead < 0:
            return 0.0
        return 0.50

    # 用常態近似剩餘半局的淨得分差 (均值 = (def - off) * rpg_half, 變異數 ≈ (def + off) * 1.12)
    mean_diff = fld_lead + (remaining_def_half - remaining_off_half) * rpg_half
    std_diff = math.sqrt(max(0.25, (remaining_def_half + remaining_off_half) * 1.15))
    # 連續性校正
    z_win = (0.5 - mean_diff) / std_diff
    z_tie = (-0.5 - mean_diff) / std_diff
    cdf = lambda z: 0.5 * (1.0 + math.erf(z / math.sqrt(2.0)))
    p_win_reg = 1.0 - cdf(z_win)
    p_tie_reg = max(0.0, cdf(z_win) - cdf(z_tie))
    return p_win_reg + 0.50 * p_tie_reg


def compute_defense_win_expectancy(
    re_val: float, inning: int, half: str, fld_score_diff: int, rpg_half: float = 0.49
) -> float:
    """
    計算守備方在目前 (inning, half, fld_score_diff, state_re) 的勝率 (WE_defense)。
    half: 'top' (上半局，主隊守備，主隊還保有下半局進攻) 或 'bot' (下半局，客隊守備)
    fld_score_diff: 守備方比分 - 進攻方比分（正值代表守備方領先）
    """
    eff_inn = min(inning, 9)
    if half == "top":
        rem_off = max(0, 9 - eff_inn)
        rem_def = max(0, 9 - eff_inn) + 1  # 主隊還有本局下半可進攻
    else:
        rem_off = max(0, 9 - eff_inn)
        rem_def = max(0, 9 - eff_inn)

    run_dist = _half_inning_run_dist(re_val)
    we = 0.0
    for runs_allowed, prob in enumerate(run_dist):
        new_lead = fld_score_diff - runs_allowed
        # 若為 9 局下（或延長下）且進攻方已經超前 (new_lead < 0)，比賽立即再見結束 -> 守備方勝率 0
        if inning >= 9 and half == "bot" and new_lead < 0:
            we += prob * 0.0
        else:
            we += prob * _future_win_prob(new_lead, rem_off, rem_def, rpg_half)
    return we


def compute_wpa_bep(
    re24: dict,
    inning: int,
    half: str,
    fld_score_diff: int,
    outs: int,
    comparison: str = "vs_1b",
    rpg_half: float = 0.49,
) -> dict:
    """
    計算 7~9 局與延長賽 (WPA) 封殺三壘最低成功率門檻 (BEP)。
    守備方目標：最大化守備方勝率 WE_defense。
      p * WE(succ) + (1 - p) * WE(fail) > WE(safe)
      => p > (WE(safe) - WE(fail)) / (WE(succ) - WE(fail))
    """
    safe_state = "2B_3B" if comparison == "vs_1b" else "1B_3B"
    we_safe = compute_defense_win_expectancy(re24[safe_state][outs + 1], inning, half, fld_score_diff, rpg_half)
    we_succ = compute_defense_win_expectancy(re24["1B_2B"][outs + 1], inning, half, fld_score_diff, rpg_half)
    we_fail = compute_defense_win_expectancy(re24["1B_2B_3B"][outs], inning, half, fld_score_diff, rpg_half)

    denom = we_succ - we_fail
    bep = (we_safe - we_fail) / denom if denom > 1e-6 else 0.5
    return {
        "mode": "WPA",
        "safe_state": f"{outs + 1} 出局 {'二三壘' if comparison == 'vs_1b' else '一三壘'}",
        "succ_state": f"{outs + 1} 出局 一二壘",
        "fail_state": f"{outs} 出局 滿壘",
        "val_safe": round(we_safe, 4),
        "val_succ": round(we_succ, 4),
        "val_fail": round(we_fail, 4),
        "bep": round(max(0.0, min(1.0, bep)), 4),
    }


def predict_force_3b_prob(
    field_x_ft: float,
    field_y_ft: float,
    exit_vel_mph: float = 55.0,
    is_bunt: bool = True,
    runner_90ft_sec: float = 3.95,
    secondary_lead_ft: float = 12.0,
    exchange_sec: float = 0.72,
    arm_mph: float = 82.0,
    sigma_sec: float = 0.18,
) -> dict:
    """
    時間差邏輯斯模型 (Time-Margin Logistic Model)：
    計算球在 (field_x_ft, field_y_ft) 被接球後傳往三壘的封殺成功率。
    """
    dist_hp = math.hypot(field_x_ft, field_y_ft)
    dist_3b = math.hypot(field_x_ft - THIRD_BASE_X, field_y_ft - THIRD_BASE_Y)

    # 1. 球滾動至野手時間 (秒)
    ev_fts = max(20.0, exit_vel_mph * 1.46667)
    if is_bunt:
        # 觸擊短打草皮減速明顯，有效均速約為初速的 38%
        v_roll = max(16.0, ev_fts * 0.38)
    else:
        # 一般內野滾地球有效均速約為初速的 56%
        v_roll = max(28.0, ev_fts * 0.56)
    t_roll = dist_hp / v_roll

    # 2. 傳球飛行時間 (秒) - 若落點在三壘壘包 8 ft 內視為三壘手自踩壘包
    if dist_3b <= 8.0:
        t_exchange = 0.28
        t_throw = dist_3b / 22.0
    else:
        t_exchange = exchange_sec
        v_throw_fts = max(60.0, arm_mph * 1.46667 * 0.90)  # 空氣阻力修正 0.90
        t_throw = dist_3b / v_throw_fts

    t_catch_3b = 0.08  # 封殺只需接球踩包，無需觸殺 (Tag)
    t_ball = t_roll + t_exchange + t_throw + t_catch_3b

    # 3. 二壘跑者衝向三壘時間 (秒，扣除打擊區揮棒啟動時間 0.55s，反映二壘動態離壘加速)
    eff_speed_fts = 90.0 / max(2.8, runner_90ft_sec - 0.55)
    run_dist_ft = max(62.0, 90.0 - secondary_lead_ft)
    # 短打時跑者隨投球提前起跑（動態優勢 -0.15s）；滾地球需短暫判斷平飛球風險（+0.22s）
    start_offset = -0.15 if is_bunt else 0.22
    t_runner = (run_dist_ft / eff_speed_fts) + start_offset

    time_margin = t_runner - t_ball  # > 0 代表球比跑者早到三壘
    z = max(-20.0, min(20.0, time_margin / sigma_sec))
    prob = 1.0 / (1.0 + math.exp(-z))

    return {
        "dist_hp_ft": round(dist_hp, 1),
        "dist_3b_ft": round(dist_3b, 1),
        "t_roll": round(t_roll, 2),
        "t_exchange": round(t_exchange, 2),
        "t_throw": round(t_throw, 2),
        "t_ball": round(t_ball, 2),
        "t_runner": round(t_runner, 2),
        "time_margin": round(time_margin, 2),
        "prob": round(prob, 4),
    }


def export_web_bundle():
    """將 RE24、WPA 預計算表、2026 球員預設與實戰散點輸出給互動模擬器使用。"""
    WEB_DATA_DIR.mkdir(parents=True, exist_ok=True)
    re24 = load_re24_matrix()

    # 1. 整理 2026 實戰散點 (聚焦內野範圍內，方便疊加在紅綠燈熱區圖上)
    empirical_plays = []
    with open(FORCE_3B_DIR / "mlb_2026_1b2b_groundballs_bunts.csv", encoding="utf-8") as f:
        for row in csv.DictReader(f):
            if not row["field_x_ft"] or not row["field_y_ft"]:
                continue
            fx = float(row["field_x_ft"])
            fy = float(row["field_y_ft"])
            if fy < -5 or fy > 175 or abs(fx) > 135:
                continue
            choice = row["defensive_choice"]
            if choice not in (
                "FORCE_3B_SUCCESS",
                "DP_WITH_3B_OUT",
                "OUT_1B_ONLY",
                "FORCE_2B_SINGLE_OUT",
                "DP_2B_1B",
                "FC_ALL_SAFE_OR_ERROR",
            ):
                continue
            empirical_plays.append({
                "x": round(fx, 1),
                "y": round(fy, 1),
                "d3b": round(float(row["dist_to_3b_ft"]), 1),
                "ev": round(float(row["launch_speed_mph"]), 1) if row["launch_speed_mph"] else None,
                "bunt": row["is_bunt"] == "True",
                "outs": int(row["outs_when_up"]),
                "pos": row["fielded_by_pos"],
                "choice": choice,
                "r2": row["runner_2b_name"],
                "r2_spd": float(row["runner_2b_sprint_speed_fts"]) if row["runner_2b_sprint_speed_fts"] else None,
                "fld": row["fielder_name"],
                "arm": float(row["fielder_arm_mph"]) if row["fielder_arm_mph"] else None,
                "date": row["game_date"],
                "des": row["des"],
            })

    # 2. 整理 2026 代表性跑者預設 (從快、中、慢各抽代表球員供戰術表使用)
    splits_list = []
    with open(LB_DIR / "running_splits_90ft_2026.csv", encoding="utf-8-sig") as f:
        for row in csv.DictReader(f):
            s90 = row.get("seconds_since_hit_090", "").strip()
            if s90:
                splits_list.append({
                    "name": row["last_name, first_name"].strip(),
                    "team": row["name_abbrev"].strip(),
                    "pos": row["position_name"].strip(),
                    "sec_90ft": float(s90),
                    "sec_75ft": float(row["seconds_since_hit_075"]),
                })
    splits_list.sort(key=lambda r: r["sec_90ft"])
    n_sp = len(splits_list)
    sample_indices = [0, int(n_sp * 0.08), int(n_sp * 0.25), int(n_sp * 0.45), int(n_sp * 0.65), int(n_sp * 0.85), n_sp - 1]
    runner_presets = []
    tier_labels = ["頂尖快腿 (PR99)", "快腿 (PR92)", "中上腳程 (PR75)", "聯盟平均 (PR55)", "中下腳程 (PR35)", "偏慢重砲 (PR15)", "極慢捕手/DH (PR1)"]
    for idx, tier in zip(sample_indices, tier_labels):
        p = splits_list[idx]
        runner_presets.append({
            "tier": tier,
            "name": f"{p['name']} ({p['team']})",
            "sec_90ft": p["sec_90ft"],
            "sec_75ft": p["sec_75ft"],
        })

    # 3. 整理 2026 各內野守位平均臂力基準
    pos_arm_buckets = {"1B": [], "2B": [], "3B": [], "SS": []}
    with open(LB_DIR / "arm_strength_2026.csv", encoding="utf-8-sig") as f:
        for row in csv.DictReader(f):
            for p_code, col in [("1B", "arm_1b"), ("2B", "arm_2b"), ("3B", "arm_3b"), ("SS", "arm_ss")]:
                v = row.get(col, "").strip()
                if v:
                    pos_arm_buckets[p_code].append(float(v))
    c_arms = []
    c_exchanges = []
    with open(LB_DIR / "catcher_poptime_2026.csv", encoding="utf-8-sig") as f:
        for row in csv.DictReader(f):
            if row.get("maxeff_arm_2b_3b_sba"):
                c_arms.append(float(row["maxeff_arm_2b_3b_sba"]))
            if row.get("exchange_2b_3b_sba"):
                c_exchanges.append(float(row["exchange_2b_3b_sba"]))

    pos_benchmarks = {}
    for p_code, cfg in DEFAULT_POS_PARAMS.items():
        avg_arm = cfg["arm_mph"]
        avg_ex = cfg["exchange_sec"]
        if p_code in pos_arm_buckets and pos_arm_buckets[p_code]:
            avg_arm = round(sum(pos_arm_buckets[p_code]) / len(pos_arm_buckets[p_code]), 1)
        elif p_code == "C" and c_arms:
            avg_arm = round(sum(c_arms) / len(c_arms), 1)
            avg_ex = round(sum(c_exchanges) / len(c_exchanges), 2)
        pos_benchmarks[p_code] = {**cfg, "arm_mph": avg_arm, "exchange_sec": avg_ex}

    # 4. 預先計算所有 7~9 局與延長賽 WPA BEP 查詢表 (供前端零延遲即時切換)
    wpa_lookup = {}
    for lg in ["CPBL_Rebas_Ref", "MLB_Modern"]:
        rpg_half = 0.50 if lg == "CPBL_Rebas_Ref" else 0.481
        wpa_lookup[lg] = {}
        for inn in [7, 8, 9, 10]:
            for half in ["top", "bot"]:
                for diff in range(-3, 4):  # 守備方領先分差 -3 ~ +3
                    for outs in [0, 1]:
                        for comp in ["vs_1b", "vs_2b"]:
                            key = f"{inn}_{half}_{diff}_{outs}_{comp}"
                            wpa_lookup[lg][key] = compute_wpa_bep(
                                re24[lg], inn, half, diff, outs, comp, rpg_half
                            )

    re24_lookup = {}
    for lg in ["CPBL_Rebas_Ref", "MLB_Modern"]:
        re24_lookup[lg] = {}
        for outs in [0, 1]:
            for comp in ["vs_1b", "vs_2b"]:
                re24_lookup[lg][f"{outs}_{comp}"] = compute_re24_bep(re24[lg], outs, comp)

    bundle = {
        "meta": {
            "title": "一二壘有人：封殺三壘決策模擬器 (Force-3B BEP Simulator)",
            "season": 2026,
            "total_infield_plays": len(empirical_plays),
        },
        "re24_bep": re24_lookup,
        "wpa_bep": wpa_lookup,
        "pos_benchmarks": pos_benchmarks,
        "runner_presets": runner_presets,
        "empirical_plays": empirical_plays,
    }

    out_path = WEB_DATA_DIR / "force_3b_model_data.json"
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(bundle, f, ensure_ascii=False)

    print(f"Exported web model bundle to {out_path} ({out_path.stat().st_size / 1024:.1f} KB)")
    print(f"  - Empirical infield plays: {len(empirical_plays)}")
    print(f"  - Runner presets: {len(runner_presets)}")
    print(f"  - Position benchmarks: { {k: v['arm_mph'] for k, v in pos_benchmarks.items()} }")


if __name__ == "__main__":
    export_web_bundle()
