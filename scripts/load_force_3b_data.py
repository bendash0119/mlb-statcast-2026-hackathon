"""
一鍵載入「一二壘有人：封殺三壘決策分析」所有整理好的數據集
"""
from pathlib import Path
import pandas as pd

BASE_DIR = Path(__file__).resolve().parent.parent
FORCE_3B_DIR = BASE_DIR / "data" / "force_3b"
LB_DIR = FORCE_3B_DIR / "leaderboards"


def load_force_3b_bundle() -> dict[str, pd.DataFrame]:
    return {
        "plays_1b2b": pd.read_csv(FORCE_3B_DIR / "mlb_2026_1b2b_groundballs_bunts.csv"),
        "bunts_1b2b": pd.read_csv(FORCE_3B_DIR / "mlb_2026_1b2b_bunts_only.csv"),
        "bep_scenarios": pd.read_csv(FORCE_3B_DIR / "force_3b_bep_scenarios.csv"),
        "re24_matrix": pd.read_csv(FORCE_3B_DIR / "re24_matrix_reference.csv"),
        "empirical_summary": pd.read_csv(FORCE_3B_DIR / "force_3b_empirical_summary_2026.csv"),
        "sprint_speed": pd.read_csv(LB_DIR / "sprint_speed_2026.csv"),
        "running_splits": pd.read_csv(LB_DIR / "running_splits_90ft_2026.csv"),
        "arm_strength": pd.read_csv(LB_DIR / "arm_strength_2026.csv"),
        "catcher_poptime": pd.read_csv(LB_DIR / "catcher_poptime_2026.csv"),
    }


if __name__ == "__main__":
    bundle = load_force_3b_bundle()
    print("=== 一二壘有人封殺三壘專案數據集載入成功 ===")
    for name, df in bundle.items():
        print(f"- {name:20s}: {df.shape[0]:5d} 列 x {df.shape[1]:2d} 欄")
