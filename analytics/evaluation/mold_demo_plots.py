import argparse
from pathlib import Path

import matplotlib.pyplot as plt
import pandas as pd


def main() -> None:
    parser = argparse.ArgumentParser(description="Generate mold demo plots")
    parser.add_argument("--eval", default="/home/amrik/code/smart-campus/data/mold_eval.csv")
    parser.add_argument("--out-dir", default="/home/amrik/code/smart-campus/data/plots")
    args = parser.parse_args()

    df = pd.read_csv(args.eval, parse_dates=["ts"])
    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    # Scatter: predicted vs actual
    plt.figure(figsize=(6, 6))
    plt.scatter(df["target_idx_mold_h"], df["pred_idx_mold_h"], s=8, alpha=0.6)
    plt.xlabel("Actual idx_mold(t+H)")
    plt.ylabel("Predicted idx_mold(t+H)")
    plt.title("Mold Forecast: Predicted vs Actual")
    plt.grid(True, alpha=0.2)
    plt.tight_layout()
    plt.savefig(out_dir / "mold_scatter.png", dpi=150)
    plt.close()

    # Timeline example (MOLD_EPISODE)
    mold = df[df["scenario"] == "MOLD_EPISODE"].copy()
    if not mold.empty:
        mold = mold.sort_values("ts").head(240)
        plt.figure(figsize=(10, 4))
        plt.plot(mold["ts"], mold["target_idx_mold_h"], label="Actual idx_mold(t+H)")
        plt.plot(mold["ts"], mold["pred_idx_mold_h"], label="Predicted idx_mold(t+H)")
        plt.axhline(0.6, color="red", linestyle="--", linewidth=1, label="Threshold 0.6")
        plt.title("Example MOLD_EPISODE Timeline")
        plt.xlabel("Time")
        plt.ylabel("Index")
        plt.legend()
        plt.tight_layout()
        plt.savefig(out_dir / "mold_timeline.png", dpi=150)
        plt.close()


if __name__ == "__main__":
    main()
