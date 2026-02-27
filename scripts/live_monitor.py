import argparse
import sqlite3
import time
from datetime import datetime


def fetch_latest(db_path: str):
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()

    cur.execute("SELECT * FROM raw_telemetry ORDER BY ts DESC LIMIT 1")
    raw = cur.fetchone()

    cur.execute("SELECT * FROM features ORDER BY ts DESC LIMIT 1")
    feat = cur.fetchone()

    cur.execute("SELECT * FROM predictions ORDER BY ts DESC LIMIT 1")
    pred = cur.fetchone()

    cur.execute("SELECT * FROM alerts ORDER BY ts DESC LIMIT 1")
    alert = cur.fetchone()

    conn.close()
    return raw, feat, pred, alert


def fetch_series(db_path: str, limit: int = 300):
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()
    cur.execute(
        """
        SELECT r.ts, r.air_rh_pct, f.idx_mold_now, p.pred_idx_mold_h
        FROM raw_telemetry r
        LEFT JOIN features f ON r.ts = f.ts
        LEFT JOIN predictions p ON r.ts = p.ts
        ORDER BY r.ts DESC
        LIMIT ?
        """,
        (limit,),
    )
    rows = cur.fetchall()
    conn.close()
    return list(reversed(rows))


def print_latest(raw, feat, pred, alert):
    print("\n=== Latest ===")
    if raw:
        print(f"ts={raw['ts']} RH={raw['air_rh_pct']} temp={raw['air_temp_c']}")
    if feat:
        print(f"idx_mold_now={feat['idx_mold_now']:.3f} health={feat['sensor_health_score']:.2f}")
    if pred:
        print(f"pred_idx_mold_h={pred['pred_idx_mold_h']:.3f} horizon={pred['horizon_min']}m")
    if alert:
        print(f"alert={alert['severity']} {alert['message']}")


def run_console(db_path: str, interval: float):
    while True:
        raw, feat, pred, alert = fetch_latest(db_path)
        print_latest(raw, feat, pred, alert)
        time.sleep(interval)


def run_plot(db_path: str, interval: float, limit: int):
    try:
        import matplotlib
        matplotlib.use("TkAgg")
        import matplotlib.pyplot as plt
    except Exception as exc:  # pragma: no cover
        raise SystemExit("matplotlib/TkAgg not available; pip install -r requirements-ml.txt") from exc

    plt.ion()
    fig, ax = plt.subplots(figsize=(10, 4))
    line_rh, = ax.plot([], [], label="air_rh_pct")
    line_mold, = ax.plot([], [], label="idx_mold_now")
    line_pred, = ax.plot([], [], label="pred_idx_mold_h")
    ax.set_ylim(0, 100)
    ax.set_title("Live Mold Monitoring")
    ax.set_xlabel("Time")
    ax.set_ylabel("Value")
    ax.legend()

    while True:
        rows = fetch_series(db_path, limit=limit)
        if rows:
            ts = [datetime.fromisoformat(r["ts"]) for r in rows]
            rh = [r["air_rh_pct"] or 0.0 for r in rows]
            mold = [r["idx_mold_now"] or 0.0 for r in rows]
            pred = [r["pred_idx_mold_h"] or 0.0 for r in rows]

            line_rh.set_data(ts, rh)
            line_mold.set_data(ts, mold)
            line_pred.set_data(ts, pred)
            ax.set_xlim(ts[0], ts[-1])
            ax.relim()
            ax.autoscale_view()
        fig.canvas.draw()
        fig.canvas.flush_events()
        plt.pause(0.001)
        time.sleep(interval)


def main() -> None:
    parser = argparse.ArgumentParser(description="Live monitor for ingest pipeline")
    parser.add_argument("--db", default="/home/amrik/code/smart-campus/data/smart_campus.db")
    parser.add_argument("--interval", type=float, default=2.0)
    parser.add_argument("--mode", choices=["console", "plot"], default="console")
    parser.add_argument("--limit", type=int, default=300)
    args = parser.parse_args()

    if args.mode == "plot":
        run_plot(args.db, args.interval, args.limit)
    else:
        run_console(args.db, args.interval)


if __name__ == "__main__":
    main()
