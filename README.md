# 2026 MLB Statcast League Data — 棒球數據黑客松專案

本專案收錄自 [Baseball Savant League (2026)](https://baseballsavant.mlb.com/league) 擷取的完整 **2026 MLB 球季數據**，供黑客松團隊共同開發與分析使用。

## 1. 專案目錄結構

```text
mlb-statcast-2026-hackathon/
├── data/
│   ├── processed/          # 2026 MLB 聯盟與球隊彙總 CSV / JSON（30 隊打擊、投球、逐日紀錄）
│   ├── force_3b/           # 「一二壘有人：封殺三壘決策」專題整合資料集、RE24/BEP 表與 2026 跑速/臂力榜
│   │   ├── leaderboards/   # 2026 Sprint Speed, 90ft Splits, Arm Strength, Catcher Pop Time
│   │   └── DATA_DICTIONARY.md
│   ├── raw/                # 從 Baseball Savant League 頁面擷取的原始 JSON 備份
│   └── large/              # [Git 忽略] 存放巨量原始逐球檔（如 15MB RISP 原檔），不推上 GitHub
├── scripts/
│   ├── load_data.py              # 載入 2026 聯盟彙總表
│   ├── load_force_3b_data.py     # 載入「一二壘有人封殺三壘」專題所有資料表
│   └── build_force_3b_datasets.py# 從原始 Statcast 檔重建並串接封殺三壘特徵表
├── .gitignore
├── requirements.txt
└── README.md
```

## 2. 專題數據：「一二壘有人封殺三壘決策」(`data/force_3b/`)

詳細欄位定義請參閱 [`data/force_3b/DATA_DICTIONARY.md`](data/force_3b/DATA_DICTIONARY.md)：
- **`mlb_2026_1b2b_groundballs_bunts.csv`**（**2,375 筆**）：2026 MLB 整季所有精確「一二壘有人（無三壘跑者）、0 或 1 出局」的滾地球與短打，已轉換球場英尺座標 (`field_x_ft`, `field_y_ft`, `dist_to_3b_ft`) 並串接二壘跑者衝刺速度（配對率 99.3%）與野手傳球臂力（配對率 86.1%）。
- **`mlb_2026_1b2b_bunts_only.csv`**（**325 筆**）：一二壘有人短打專題子表。
- **`force_3b_bep_scenarios.csv` & `re24_matrix_reference.csv`**：MLB 與 CPBL (Rebas 基準) 的 RE24 矩陣與封殺三壘損益兩平點（BEP）門檻表（0 出局傳三壘 vs 傳一壘 BEP ≈ `65.1%`；1 出局高達 `86.4%`）。
- **`leaderboards/`**：2026 全聯盟跑速 (`sprint_speed_2026.csv`)、每 5 英尺 90ft 分段秒數 (`running_splits_90ft_2026.csv`)、內野臂力 (`arm_strength_2026.csv`) 與捕手轉傳時間 (`catcher_poptime_2026.csv`)。

## 3. 2026 MLB 聯盟彙總數據集 (`data/processed/`)

所有球隊統計表均包含 **30 支 MLB 球隊 + 1 列 `MLB` 全聯盟總計（共 31 列）**，並已附上 `Team_ID`、`Team_Abbr`（如 `NYY`, `LAD`）與 `Team` 名稱：

| 檔案名稱 (`.csv` / `.json`) | 內容說明 | 規模 | 核心欄位 |
| :--- | :--- | :--- | :--- |
| `league_standings_2026` | 2026 美聯/國聯 6 大分區排名與勝差 | 30 列 × 9 欄 | `League`, `Division`, `Division_Rank`, `Team_ID`, `Team_Abbr`, `Team`, `Games_Back` |
| `statcast_hitting_2026` | 團隊打擊與預期進階數據 (Statcast Hitting) | 31 列 × 28 欄 | `PA`, `AB`, `H`, `2B`, `3B`, `HR`, `BB`, `SO`, `BA`, `OBP`, `SLG`, `wOBA`, `wOBAcon`, `Pitches`, `Batted Balls`, `Barrels`, `Barrel %`, `Hard Hit %`, `Exit Velocity`, `Launch Angle`, `xBA`, `xSLG`, `xwOBA`, `xwOBAcon` |
| `statcast_batting_discipline_2026` | 團隊打擊本壘板紀律 (Plate Discipline - Batting) | 31 列 × 16 欄 | `Pitches`, `Zone %`, `Zone Swing %`, `Zone Contact %`, `Chase %`, `Chase Contact %`, `Edge %`, `1st Pitch Swing %`, `Swing %`, `Whiff %`, `Meatball %`, `Meatball Swing %` |
| `statcast_batting_batted_ball_2026` | 團隊擊球型態分佈 (Batted Ball Profile - Batting) | 31 列 × 19 欄 | `BBE`, `GB %`, `FB %`, `LD %`, `PU %`, `Pull %`, `Straight %`, `Oppo %`, `Weak %`, `Topped %`, `Under %`, `Flare/Burner %`, `Solid %`, `Launch Angle Sweet-Spot %`, `Barrel %` |
| `statcast_pitching_2026` | 團隊投球壓制與預期數據 (Statcast Pitching) | 31 列 × 28 欄 | 同打擊 Statcast 26 項指標（視角為投手被擊球表現） |
| `statcast_pitching_discipline_2026` | 團隊投球好球帶紀律 (Plate Discipline - Pitching) | 31 列 × 16 欄 | 同本壘板紀律指標（首球為 `1st Pitch Strike %`） |
| `statcast_pitching_batted_ball_2026` | 團隊投球被擊球型態 (Batted Ball Profile - Pitching) | 31 列 × 19 欄 | 同擊球型態 17 項指標（視角為投手被擊球分佈） |
| `statcast_game_logs_2026` | 2026 全聯盟逐日比賽彙總 (Game Logs: `2026-03-25` ~ `2026-10-28`) | 207 列 × 26 欄 | `Game Date`, `Games` 及當日全聯盟 24 項 Statcast 指標 |
| `mlb_statcast_2026_complete.json` | 上述所有 2026 表格的單一整合 JSON 檔 | 整合包 | 適合前端視覺化或 API 直接讀取 |

## 3. 快速開始

```bash
pip install -r requirements.txt
python3 scripts/load_data.py
```
