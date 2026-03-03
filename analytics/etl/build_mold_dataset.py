import argparse
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Dict, List, Tuple

import numpy as np
import pandas as pd

from analytics.indices.mold_index import mold_risk_index
from analytics.indices.physics import dew_point_c


@dataclass
class EpisodeConfig:
    scenario: str
    hours: int
    seed: int
    episode_id: int


def _rng(seed: int) -> np.random.Generator:
    return np.random.default_rng(seed)


def _quantize(values: np.ndarray, step: float) -> np.ndarray:
    return np.round(values / step) * step


def _clip(values: np.ndarray, lo: float, hi: float) -> np.ndarray:
    return np.clip(values, lo, hi)


def _sensor_profiles(
    steps: int,
    scenario: str,
    rng: np.random.Generator,
) -> Dict[str, np.ndarray]:
    # Baseline indoor ranges (cheap sensors)
    air_temp = 22.0 + rng.normal(0.0, 0.25, steps)
    air_rh = 45.0 + rng.normal(0.0, 2.0, steps)
    air_co2 = 600.0 + rng.normal(0.0, 30.0, steps)
    air_pm25 = 8.0 + rng.normal(0.0, 2.0, steps)
    air_tvoc = 150.0 + rng.normal(0.0, 20.0, steps)
    air_surface_temp = air_temp - 0.6 + rng.normal(0.0, 0.1, steps)
    air_material_moisture = 0.08 + rng.normal(0.0, 0.01, steps)
    outdoor_temp = 10.0 + 5.0 * np.sin(np.arange(steps) / 30.0) + rng.normal(0.0, 0.5, steps)
    outdoor_rh = 65.0 + 10.0 * np.cos(np.arange(steps) / 40.0) + rng.normal(0.0, 1.5, steps)

    if scenario == "MOLD_EPISODE":
        # Delayed ramp + plateau to create predictive lead at horizon
        t = np.arange(steps)
        ramp = np.clip((t - steps * 0.2) / (steps * 0.6), 0.0, 1.0)
        air_rh = 65.0 + 30.0 * ramp + rng.normal(0.0, 0.8, steps)
        air_temp = 23.0 + rng.normal(0.0, 0.2, steps)
        air_surface_temp = air_temp - (0.7 + 0.3 * ramp) + rng.normal(0.0, 0.08, steps)
        air_material_moisture = 0.10 + 0.10 * ramp + rng.normal(0.0, 0.01, steps)

    # Quantize to mimic low-cost sensors
    air_temp = _quantize(air_temp, 0.1)
    air_rh = _quantize(air_rh, 0.1)
    air_co2 = _quantize(air_co2, 1.0)
    air_pm25 = _quantize(air_pm25, 1.0)
    air_tvoc = _quantize(air_tvoc, 1.0)
    air_surface_temp = _quantize(air_surface_temp, 0.1)
    air_material_moisture = _quantize(air_material_moisture, 0.01)
    outdoor_temp = _quantize(outdoor_temp, 0.1)
    outdoor_rh = _quantize(outdoor_rh, 0.1)

    # Clip to plausible ranges
    air_temp = _clip(air_temp, 15.0, 30.0)
    air_rh = _clip(air_rh, 20.0, 98.0)
    air_co2 = _clip(air_co2, 400.0, 2000.0)
    air_pm25 = _clip(air_pm25, 0.0, 150.0)
    air_tvoc = _clip(air_tvoc, 0.0, 2000.0)
    air_material_moisture = _clip(air_material_moisture, 0.01, 0.6)
    outdoor_rh = _clip(outdoor_rh, 20.0, 100.0)

    return {
        "air_temp_c": air_temp,
        "air_rh_pct": air_rh,
        "air_co2_ppm": air_co2,
        "air_pm25_ugm3": air_pm25,
        "air_tvoc": air_tvoc,
        "air_surface_temp_c": air_surface_temp,
        "air_material_moisture": air_material_moisture,
        "outdoor_temp_c": outdoor_temp,
        "outdoor_rh_pct": outdoor_rh,
    }


def _build_episode(cfg: EpisodeConfig, freq_min: int = 1) -> pd.DataFrame:
    steps = int(cfg.hours * 60 / freq_min)
    start = datetime(2026, 2, 27, 12, 0, tzinfo=timezone.utc) + timedelta(
        hours=cfg.episode_id * (cfg.hours + 1)
    )
    ts = [start + timedelta(minutes=i * freq_min) for i in range(steps)]

    rng = _rng(cfg.seed)
    sensors = _sensor_profiles(steps, cfg.scenario, rng)

    df = pd.DataFrame({"ts": ts, **sensors})

    df["dew_point_c"] = df.apply(lambda r: dew_point_c(r["air_temp_c"], r["air_rh_pct"]), axis=1)
    df["dew_margin_c"] = df["air_surface_temp_c"] - df["dew_point_c"]
    df["outdoor_dew_point_c"] = df["outdoor_temp_c"] - (100.0 - df["outdoor_rh_pct"]) / 5.0
    df["tod_sin"] = np.sin(2.0 * np.pi * df["ts"].dt.hour * 60.0 / (24 * 60))
    df["tod_cos"] = np.cos(2.0 * np.pi * df["ts"].dt.hour * 60.0 / (24 * 60))
    df["dow_sin"] = np.sin(2.0 * np.pi * df["ts"].dt.weekday / 7.0)
    df["dow_cos"] = np.cos(2.0 * np.pi * df["ts"].dt.weekday / 7.0)
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
    # Keep only engineered features here to avoid duplicate columns
    feats["rh_mean_w"] = df["air_rh_pct"].rolling(window).mean()
    feats["rh_std_w"] = df["air_rh_pct"].rolling(window).std()
    feats["rh_slope_w"] = df["air_rh_pct"].diff(window)
    feats["temp_slope_w"] = df["air_temp_c"].diff(window)
    feats["dew_point_slope_w"] = df["dew_point_c"].diff(window)
    feats["dew_margin_slope_w"] = df["dew_margin_c"].diff(window)
    feats["rh_time_above_70_w"] = (df["air_rh_pct"] >= 70.0).rolling(window).mean()
    feats["dew_margin_time_below_0_w"] = (df["dew_margin_c"] <= 0.0).rolling(window).mean()
    feats["air_rh_pct_t_minus_1"] = df["air_rh_pct"].shift(1)
    feats["air_rh_pct_t_minus_5"] = df["air_rh_pct"].shift(5)
    feats["dew_margin_c_t_minus_5"] = df["dew_margin_c"].shift(5)
    feats["idx_mold_now_t_minus_5"] = df["idx_mold_now"].shift(5)
    return feats


def _inject_missing(df: pd.DataFrame, missing_rate: float, rng: np.random.Generator) -> pd.DataFrame:
    if missing_rate <= 0.0:
        return df
    cols = [
        "air_temp_c",
        "air_rh_pct",
        "dew_point_c",
        "air_co2_ppm",
        "air_pm25_ugm3",
        "air_tvoc",
        "air_surface_temp_c",
        "air_material_moisture",
    ]
    for col in cols:
        mask = rng.random(len(df)) < missing_rate
        df.loc[mask, col] = np.nan
    return df


def _impute(df: pd.DataFrame, window: int) -> pd.DataFrame:
    # Demo imputation: forward fill, then rolling mean, then global mean
    df = df.copy()
    df = df.fillna(method="ffill")
    for col in df.columns:
        if col == "ts":
            continue
        if df[col].isna().any():
            df[col] = df[col].fillna(df[col].rolling(window, min_periods=1).mean())
    df = df.fillna(df.mean(numeric_only=True))
    return df


def _build_dataset(
    scenarios: List[str],
    hours: int,
    horizon_min: int,
    window_min: int,
    seed: int,
    episodes_per_scenario: int,
    missing_rate: float,
) -> pd.DataFrame:
    frames = []
    rng = _rng(seed)
    for i, scenario in enumerate(scenarios):
        for e in range(episodes_per_scenario):
            cfg = EpisodeConfig(
                scenario=scenario,
                hours=hours,
                seed=seed + i * 13 + e * 31,
                episode_id=i * episodes_per_scenario + e,
            )
            df = _build_episode(cfg)
            df["idx_mold_now"] = _compute_idx(df, window=window_min)
            feats = _build_features(df, window=window_min)

            df = pd.concat([df, feats], axis=1)
            df = _inject_missing(df, missing_rate, rng)
            df = _impute(df, window=window_min)
            df["target_idx_mold_h"] = df["idx_mold_now"].shift(-horizon_min)
            df["scenario"] = scenario
            df["episode_id"] = cfg.episode_id
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
    parser.add_argument("--episodes-per-scenario", type=int, default=3)
    parser.add_argument("--missing-rate", type=float, default=0.0)
    args = parser.parse_args()

    scenarios = ["NORMAL", "MOLD_EPISODE"]
    df = _build_dataset(
        scenarios,
        args.hours,
        args.horizon_min,
        args.window_min,
        args.seed,
        args.episodes_per_scenario,
        args.missing_rate,
    )
    df.to_csv(args.out, index=False)
    print(f"Wrote dataset to {args.out} (rows={len(df)})")


if __name__ == "__main__":
    main()
