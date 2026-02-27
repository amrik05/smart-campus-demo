import argparse
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Dict, List

import numpy as np
import pandas as pd

from analytics.indices.mold_index import mold_risk_index
from analytics.indices.physics import dew_point_c


@dataclass
class EpisodeConfig:
    scenario: str
    hours: int
    seed: int


def _rng(seed: int) -> np.random.Generator:
    return np.random.default_rng(seed)


def _build_episode(cfg: EpisodeConfig, freq_min: int = 1) -> pd.DataFrame:
    steps = int(cfg.hours * 60 / freq_min)
    start = datetime(2026, 2, 27, 12, 0, tzinfo=timezone.utc)
    ts = [start + timedelta(minutes=i * freq_min) for i in range(steps)]

    rng = _rng(cfg.seed)
    air_temp = 22.0 + rng.normal(0.0, 0.3, steps)
    air_rh = 45.0 + rng.normal(0.0, 2.0, steps)

    if cfg.scenario == "MOLD_EPISODE":
        for i in range(steps):
            air_rh[i] = min(95.0, 70.0 + i * 0.3 + rng.normal(0.0, 1.0))
            air_temp[i] = 23.0 + rng.normal(0.0, 0.2)

    df = pd.DataFrame(
        {
            "ts": ts,
            "air_temp_c": air_temp,
            "air_rh_pct": air_rh,
        }
    )

    df["dew_point_c"] = df.apply(lambda r: dew_point_c(r["air_temp_c"], r["air_rh_pct"]), axis=1)
    return df


def _compute_idx(df: pd.DataFrame, window: int) -> pd.Series:
    idx_vals: List[float] = []
    history: List[tuple] = []
    for _, row in df.iterrows():
        history.append((row["air_temp_c"], row["air_rh_pct"]))
        history = history[-window:]
        idx_vals.append(mold_risk_index(row["air_temp_c"], row["air_rh_pct"], history))
    return pd.Series(idx_vals, index=df.index)


def _build_features(df: pd.DataFrame, window: int) -> pd.DataFrame:
    feats = pd.DataFrame(index=df.index)
    feats["air_temp_c"] = df["air_temp_c"]
    feats["air_rh_pct"] = df["air_rh_pct"]
    feats["dew_point_c"] = df["dew_point_c"]

    feats["rh_mean_w"] = df["air_rh_pct"].rolling(window).mean()
    feats["rh_slope_w"] = df["air_rh_pct"].diff(window)
    feats["temp_slope_w"] = df["air_temp_c"].diff(window)
    feats["dew_point_slope_w"] = df["dew_point_c"].diff(window)
    return feats


def _build_dataset(
    scenarios: List[str],
    hours: int,
    horizon_min: int,
    window_min: int,
    seed: int,
) -> pd.DataFrame:
    frames = []
    for i, scenario in enumerate(scenarios):
        cfg = EpisodeConfig(scenario=scenario, hours=hours, seed=seed + i * 13)
        df = _build_episode(cfg)
        df["idx_mold_now"] = _compute_idx(df, window=window_min)
        feats = _build_features(df, window=window_min)

        df = pd.concat([df, feats], axis=1)
        df["target_idx_mold_h"] = df["idx_mold_now"].shift(-horizon_min)
        df["scenario"] = scenario
        frames.append(df)

    full = pd.concat(frames, ignore_index=True)
    full = full.dropna().reset_index(drop=True)
    return full


def main() -> None:
    parser = argparse.ArgumentParser(description="Build mold model dataset")
    parser.add_argument("--out", default="/home/amrik/code/smart-campus/data/mold_dataset.csv")
    parser.add_argument("--hours", type=int, default=12)
    parser.add_argument("--horizon-min", type=int, default=60)
    parser.add_argument("--window-min", type=int, default=60)
    parser.add_argument("--seed", type=int, default=42)
    args = parser.parse_args()

    scenarios = ["NORMAL", "MOLD_EPISODE"]
    df = _build_dataset(scenarios, args.hours, args.horizon_min, args.window_min, args.seed)
    df.to_csv(args.out, index=False)
    print(f"Wrote dataset to {args.out} (rows={len(df)})")


if __name__ == "__main__":
    main()
