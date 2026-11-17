# 2026 MLB Statcast League Data — 棒球數據黑客松專案

本專案收錄自 [Baseball Savant League (2026)](https://baseballsavant.mlb.com/league) 擷取的完整 **2026 MLB 球季數據**，供黑客松團隊共同開發與分析使用。

## 1. 專案目錄結構

```text
mlb-statcast-2026-hackathon/
├── data/
│   ├── processed/          # 已清理並加上 Team_ID / Team_Abbr 的 CSV 與 JSON（直接進入 Git 供團隊共用）
│   ├── raw/                # 從 Baseball Savant 頁面擷取的原始 JSON 備份
│   └── large/              # [Git 忽略] 存放巨量資料（如 71 萬筆逐球 Parquet/CSV），不推上 GitHub
├── scripts/
│   └── load_data.py        # 一鍵載入所有 2026 數據表為 Pandas DataFrame 的工具腳本
├── .gitignore
├── requirements.txt
└── README.md
```

## 2. 已收錄的 2026 數據集一覽 (`data/processed/`)

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
