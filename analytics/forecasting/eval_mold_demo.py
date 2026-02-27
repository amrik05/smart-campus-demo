import argparse
import json
from pathlib import Path
from typing import Dict

import numpy as np
import pandas as pd
from sklearn.metrics import mean_absolute_error, precision_recall_fscore_support

try:
    import lightgbm as lgb
except Exception as exc:  # pragma: no cover
    raise SystemExit("LightGBM not installed. Install requirements-ml.txt") from exc


def threshold_metrics(y_true: np.ndarray, y_pred: np.ndarray, threshold: float) -> Dict[str, float]:
    y_true_bin = (y_true >= threshold).astype(int)
    y_pred_bin = (y_pred >= threshold).astype(int)
    precision, recall, f1, _ = precision_recall_fscore_support(
        y_true_bin, y_pred_bin, average="binary", zero_division=0
    )
    acc = float((y_true_bin == y_pred_bin).mean())
    return {
        "threshold": threshold,
        "accuracy": acc,
        "precision": float(precision),
        "recall": float(recall),
        "f1": float(f1),
    }


def average_lead_time(df: pd.DataFrame, threshold: float) -> float:
    lead_times = []
    for _, group in df.groupby("episode_id"):
        g = group.sort_values("ts")
        actual_idx = g.index[g["target_idx_mold_h"] >= threshold]
        pred_idx = g.index[g["pred_idx_mold_h"] >= threshold]
        if len(actual_idx) == 0 or len(pred_idx) == 0:
            continue
        actual_ts = g.loc[actual_idx[0], "ts"]
        pred_ts = g.loc[pred_idx[0], "ts"]
        lead_min = (actual_ts - pred_ts).total_seconds() / 60.0
        lead_times.append(lead_min)
    if not lead_times:
        return 0.0
    return float(np.mean(lead_times))


def main() -> None:
    parser = argparse.ArgumentParser(description="Evaluate mold model and export plots data")
    parser.add_argument("--data", default="/home/amrik/code/smart-campus/data/mold_dataset.csv")
    parser.add_argument("--model", default="/home/amrik/code/smart-campus/models/mold_lgbm.txt")
    parser.add_argument("--out", default="/home/amrik/code/smart-campus/data/mold_eval.csv")
    parser.add_argument("--threshold", type=float, default=0.6)
    parser.add_argument("--out-metrics", default="/home/amrik/code/smart-campus/data/mold_metrics.json")
    args = parser.parse_args()

    df = pd.read_csv(args.data, parse_dates=["ts"])
    df = df.sort_values("ts")

    drop_cols = {"ts", "scenario", "target_idx_mold_h"}
    X = df.drop(columns=[c for c in df.columns if c in drop_cols])
    y = df["target_idx_mold_h"].values

    model = lgb.Booster(model_file=args.model)
    preds = model.predict(X)

    mae = mean_absolute_error(y, preds)
    print(f"Eval MAE: {mae:.4f}")

    metrics = threshold_metrics(y, preds, args.threshold)
    print("Threshold metrics:")
    print(metrics)

    out = df[["ts", "scenario", "target_idx_mold_h"]].copy()
    out["pred_idx_mold_h"] = preds
    out.to_csv(args.out, index=False)
    print(f"Wrote eval data to {args.out}")

    # Lead time (episode-based)
    lead_min = 0.0
    if "episode_id" in df.columns:
        df_out = df[["ts", "episode_id", "target_idx_mold_h"]].copy()
        df_out["pred_idx_mold_h"] = preds
        lead_min = average_lead_time(df_out, args.threshold)
        print(f"Average lead time (min): {lead_min:.1f}")

    metrics_out = {
        "mae": float(mae),
        "threshold_metrics": metrics,
        "average_lead_time_min": float(lead_min),
    }
    Path(args.out_metrics).parent.mkdir(parents=True, exist_ok=True)
    Path(args.out_metrics).write_text(json.dumps(metrics_out, indent=2))
    print(f"Wrote metrics to {args.out_metrics}")


if __name__ == "__main__":
    main()
