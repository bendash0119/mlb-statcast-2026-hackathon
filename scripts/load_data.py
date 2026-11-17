"""
2026 MLB Baseball Savant (Statcast) 聯盟數據載入與逐球巨量資料下載工具
"""
from pathlib import Path
import json
import pandas as pd

BASE_DIR = Path(__file__).resolve().parent.parent
PROCESSED_DIR = BASE_DIR / "data" / "processed"
LARGE_DIR = BASE_DIR / "data" / "large"

DATASETS = [
    "league_standings_2026",
    "statcast_hitting_2026",
    "statcast_batting_discipline_2026",
    "statcast_batting_batted_ball_2026",
    "statcast_pitching_2026",
    "statcast_pitching_discipline_2026",
    "statcast_pitching_batted_ball_2026",
    "statcast_game_logs_2026",
]


def load_all_tables() -> dict[str, pd.DataFrame]:
    """載入 data/processed/ 下所有 2026 Baseball Savant League CSV 表格為 DataFrame 字典。"""
    tables = {}
    for name in DATASETS:
        csv_path = PROCESSED_DIR / f"{name}.csv"
        if csv_path.exists():
            tables[name] = pd.read_csv(csv_path)
    return tables


def load_complete_json() -> dict:
    """載入合併後的完整 JSON 檔案。"""
    json_path = PROCESSED_DIR / "mlb_statcast_2026_complete.json"
    with open(json_path, "r", encoding="utf-8") as f:
        return json.load(f)


if __name__ == "__main__":
    dfs = load_all_tables()
    print("=== 2026 MLB Baseball Savant 數據集載入成功 ===")
    for name, df in dfs.items():
        print(f"- {name}: {df.shape[0]} 列 x {df.shape[1]} 欄")
