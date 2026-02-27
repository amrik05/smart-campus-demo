import argparse

import pandas as pd
from sklearn.metrics import mean_absolute_error

try:
    import lightgbm as lgb
except Exception as exc:  # pragma: no cover
    raise SystemExit("LightGBM not installed. Install requirements-ml.txt") from exc


def main() -> None:
    parser = argparse.ArgumentParser(description="Evaluate mold model and export plots data")
    parser.add_argument("--data", default="/home/amrik/code/smart-campus/data/mold_dataset.csv")
    parser.add_argument("--model", default="/home/amrik/code/smart-campus/models/mold_lgbm.txt")
    parser.add_argument("--out", default="/home/amrik/code/smart-campus/data/mold_eval.csv")
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

    out = df[["ts", "scenario", "target_idx_mold_h"]].copy()
    out["pred_idx_mold_h"] = preds
    out.to_csv(args.out, index=False)
    print(f"Wrote eval data to {args.out}")


if __name__ == "__main__":
    main()
