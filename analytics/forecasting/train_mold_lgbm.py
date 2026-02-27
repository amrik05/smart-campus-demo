import argparse
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.metrics import mean_absolute_error

try:
    import lightgbm as lgb
except Exception as exc:  # pragma: no cover
    raise SystemExit("LightGBM not installed. Install requirements-ml.txt") from exc


def time_split(df: pd.DataFrame, train_frac: float = 0.7, val_frac: float = 0.15):
    n = len(df)
    train_end = int(n * train_frac)
    val_end = int(n * (train_frac + val_frac))
    return df.iloc[:train_end], df.iloc[train_end:val_end], df.iloc[val_end:]


def build_xy(df: pd.DataFrame):
    drop_cols = {"ts", "scenario", "target_idx_mold_h"}
    X = df.drop(columns=[c for c in df.columns if c in drop_cols])
    y = df["target_idx_mold_h"].values
    return X, y


def main() -> None:
    parser = argparse.ArgumentParser(description="Train LightGBM mold forecaster")
    parser.add_argument("--data", default="/home/amrik/code/smart-campus/data/mold_dataset.csv")
    parser.add_argument("--out-model", default="/home/amrik/code/smart-campus/models/mold_lgbm.txt")
    args = parser.parse_args()

    df = pd.read_csv(args.data, parse_dates=["ts"])
    df = df.sort_values("ts")

    train_df, val_df, test_df = time_split(df)
    X_train, y_train = build_xy(train_df)
    X_val, y_val = build_xy(val_df)
    X_test, y_test = build_xy(test_df)

    params = {
        "objective": "regression",
        "metric": "mae",
        "learning_rate": 0.05,
        "num_leaves": 31,
        "feature_fraction": 0.9,
        "seed": 42,
    }

    dtrain = lgb.Dataset(X_train, label=y_train)
    dval = lgb.Dataset(X_val, label=y_val, reference=dtrain)

    model = lgb.train(
        params,
        dtrain,
        valid_sets=[dval],
        num_boost_round=200,
        early_stopping_rounds=20,
        verbose_eval=False,
    )

    preds = model.predict(X_test)
    mae = mean_absolute_error(y_test, preds)
    print(f"Test MAE: {mae:.4f}")

    Path(args.out_model).parent.mkdir(parents=True, exist_ok=True)
    model.save_model(args.out_model)
    print(f"Saved model to {args.out_model}")

    # Feature importance
    imp = pd.DataFrame({"feature": X_train.columns, "importance": model.feature_importance()})
    imp = imp.sort_values("importance", ascending=False)
    print("Top features:")
    print(imp.head(10).to_string(index=False))


if __name__ == "__main__":
    main()
