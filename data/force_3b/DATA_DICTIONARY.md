# 一二壘有人：封殺三壘決策分析 — 數據字典 (Data Dictionary)

本資料夾 (`data/force_3b/`) 收錄專為 **「一二壘有人（0 或 1 出局）：內野滾地球與短打是否封殺三壘」** 決策模型與互動模擬器所整理好的 **2026 MLB 實戰數據** 與 **RE24 / BEP 基準表**。

---

## 1. 核心檔案總覽

| 檔案路徑 | 資料筆數 | 用途說明 |
| :--- | :--- | :--- |
| `mlb_2026_1b2b_groundballs_bunts.csv` | **2,375 筆** | **主分析表**：2026 MLB 整季所有精確「一二壘有人（無三壘跑者）、0 或 1 出局」的滾地球與短打逐球資料，已自動轉換球場座標並串接二壘跑者速度與接球野手臂力 |
| `mlb_2026_1b2b_bunts_only.csv` | **325 筆** | **短打專題子表**：上述資料中所有「觸擊短打 (`is_bunt == True`)」事件（最常面臨「傳三壘 vs 穩傳一壘」抉擇的經典情境） |
| `force_3b_bep_scenarios.csv` | **8 種情境** | **損益兩平點 (BEP) 基準表**：依 RE24 推導出的 MLB 與 CPBL 傳三壘最低成功率門檻 |
| `re24_matrix_reference.csv` | **16 列** | **RE24 得分期望值表**：MLB 現代基準與 CPBL (Rebas 參考基準) 24 種壘包出局狀態得分期望值 |
| `force_3b_empirical_summary_2026.csv` | **26 列** | **2026 實戰選擇彙總表**：依出局數 × 是否短打 × 實際守備選擇分組的出現次數與平均距三壘距離 |
| `leaderboards/sprint_speed_2026.csv` | **566 位球員** | 2026 MLB 全聯盟跑者衝刺速度 (`sprint_speed`, `hp_to_1b`) |
| `leaderboards/running_splits_90ft_2026.csv` | **545 位球員** | 2026 MLB 跑者每 5 英尺（`0 ft` ~ `90 ft`）精確衝刺秒數（可估算二壘離壘後跑 75~80 ft 抵達三壘的時間） |
| `leaderboards/arm_strength_2026.csv` | **387 位球員** | 2026 MLB 野手各守備位置傳球臂力 (`arm_1b`, `arm_2b`, `arm_3b`, `arm_ss`, `max_arm_strength`) |
| `leaderboards/catcher_poptime_2026.csv` | **71 位捕手** | 2026 MLB 捕手轉傳時間 (`exchange_2b_3b_sba`)、傳三壘 Pop Time (`pop_3b_sba`) 與臂力 |

> **本機巨量原始檔備份**：完整的 2026 RISP 擊球原始檔（17,194 筆，15 MB）已存放於 `data/large/statcast_2026_risp_all_bip_raw.csv`（已被 `.gitignore` 忽略不推上 GitHub），需要重跑前處理時可直接執行 `python3 scripts/build_force_3b_datasets.py`。

---

## 2. 主分析表 (`mlb_2026_1b2b_groundballs_bunts.csv`) 重點欄位說明

### A. 比賽與情境資訊
- `game_date`, `inning`, `inning_topbot`, `outs_when_up` (`0` 或 `1`), `bat_score`, `fld_score`, `bat_score_diff`
- `if_fielding_alignment`: 內野守備站位（如 `Standard`, `Infield shade`, `Strategic`）

### B. 擊球物理與標準化球場座標（已從 `hc_x`, `hc_y` 換算為英尺）
- `launch_speed_mph`: 擊球初速 (EV)
- `launch_angle_deg`: 擊球仰角
- `field_x_ft`, `field_y_ft`: **標準球場英尺座標**（本壘 `(0, 0)`、一壘 `(+63.64, +63.64)`、二壘 `(0, +127.28)`、三壘 `(-63.64, +63.64)`）
- `dist_from_hp_ft`: 落點距離本壘的距離 (ft)
- `dist_to_3b_ft`: **落點距離三壘壘包的直線距離 (ft)**（評估傳三壘時間的核心特徵）
- `spray_angle_deg`: 擊球噴射角（負值偏三壘側，正值偏一壘側，0 度為正中）

### C. 已串接的跑者與野手能力特徵（配對率：跑者 99.3%、野手 86.1%）
- `runner_2b_id`, `runner_2b_name`: 當時在二壘的跑者（即將衝向三壘的領先跑者）
- `runner_2b_sprint_speed_fts`: 二壘跑者衝刺速度 (`ft/s`)
- `runner_2b_75ft_sec`, `runner_2b_90ft_sec`: 二壘跑者跑 75 ft / 90 ft 的實測秒數（考量離壘約 10–15 ft 時可直接參考 `75ft` 秒數）
- `fielded_by_pos` (`P`, `C`, `1B`, `2B`, `3B`, `SS`), `fielder_name`, `fielder_arm_mph`, `fielder_max_arm_mph`

### D. 守備決策標籤 (`defensive_choice`) 與結果
- `is_bunt`: 是否為短打 (`True` / `False`)
- `out_at_3b`, `out_at_2b`, `out_at_1b`, `has_error`: 各壘包出局與失誤標記
- `defensive_choice`: 自動分類的實際守備決策結果：
  - `FORCE_3B_SUCCESS`: 傳/踩三壘成功封殺領先跑者（單殺）
  - `DP_WITH_3B_OUT`: 含封殺三壘的雙殺（如 5-3 / 5-4-3 / 1-5-3）
  - `OUT_1B_ONLY`: 穩傳一壘抓打者（跑者進佔二三壘）
  - `FORCE_2B_SINGLE_OUT`: 傳二壘單殺（跑者進佔一三壘）
  - `DP_2B_1B`: 6-4-3 / 4-6-3 / 1-6-3 傳統雙殺
  - `FC_ALL_SAFE_OR_ERROR`: 野手選擇 All Safe（如拚三壘失敗變成滿壘）或發生失誤
  - `BASE_HIT`: 穿越內野形成安打
- `delta_run_exp`, `home_win_exp`, `delta_home_win_exp`: Statcast 逐球得分與勝率變動值（注意：`delta_run_exp` 是相對於當下球數的變動，計算純壘包狀態 BEP 時請優先使用 `re24_matrix_reference.csv`）
