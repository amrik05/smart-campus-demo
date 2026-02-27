import argparse
import sqlite3
import time
from datetime import datetime
try:
    import tkinter as tk
    from tkinter import ttk
except Exception:  # pragma: no cover
    tk = None
    ttk = None


def fetch_latest(conn):
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
    return raw, feat, pred, alert


def format_row(row):
    if not row:
        return "-"
    return " | ".join(f"{k}={row[k]}" for k in row.keys())


def main():
    parser = argparse.ArgumentParser(description="Tkinter demo GUI")
    parser.add_argument("--db", default="/home/amrik/code/smart-campus/data/smart_campus.db")
    parser.add_argument("--interval", type=float, default=1.0)
    args = parser.parse_args()

    conn = sqlite3.connect(args.db)

    if tk is None or ttk is None:
        print("Tkinter not available. Install python3-tk or use console monitor:")
        print("  sudo apt-get install python3-tk")
        print("  python scripts/live_monitor.py --mode console --interval 2")
        return

    root = tk.Tk()
    root.title("Smart Campus Demo Monitor")
    root.geometry("900x600")

    title = ttk.Label(root, text="Smart Campus Demo: Mold Forecasting", font=("Arial", 16, "bold"))
    title.pack(pady=8)

    info = ttk.Label(
        root,
        text=(
            "Mold risk index is 0-1. Typical alert threshold is 0.6.\n"
            "Physics computes current risk; ML forecasts how risk evolves.\n"
            "Lead time = minutes between predicted and actual threshold crossing."
        ),
        justify="center",
    )
    info.pack(pady=6)

    metrics_frame = ttk.Frame(root)
    metrics_frame.pack(pady=8, fill="x")

    latest_pred = ttk.Label(metrics_frame, text="Predicted Risk: -", font=("Arial", 12, "bold"))
    latest_act = ttk.Label(metrics_frame, text="Actual Risk: -", font=("Arial", 12, "bold"))
    lead_time = ttk.Label(metrics_frame, text="Lead Time (min): -", font=("Arial", 12, "bold"))
    latest_pred.grid(row=0, column=0, padx=20)
    latest_act.grid(row=0, column=1, padx=20)
    lead_time.grid(row=0, column=2, padx=20)

    raw_label = ttk.Label(root, text="Latest Telemetry", font=("Arial", 11, "bold"))
    raw_label.pack(anchor="w", padx=10)
    raw_text = ttk.Label(root, text="-", wraplength=860, justify="left")
    raw_text.pack(anchor="w", padx=10)

    feat_label = ttk.Label(root, text="Latest Features", font=("Arial", 11, "bold"))
    feat_label.pack(anchor="w", padx=10, pady=(8, 0))
    feat_text = ttk.Label(root, text="-", wraplength=860, justify="left")
    feat_text.pack(anchor="w", padx=10)

    pred_label = ttk.Label(root, text="Latest Prediction", font=("Arial", 11, "bold"))
    pred_label.pack(anchor="w", padx=10, pady=(8, 0))
    pred_text = ttk.Label(root, text="-", wraplength=860, justify="left")
    pred_text.pack(anchor="w", padx=10)

    alert_label = ttk.Label(root, text="Latest Alert", font=("Arial", 11, "bold"))
    alert_label.pack(anchor="w", padx=10, pady=(8, 0))
    alert_text = ttk.Label(root, text="-", wraplength=860, justify="left")
    alert_text.pack(anchor="w", padx=10)

    def refresh():
        raw, feat, pred, alert = fetch_latest(conn)
        raw_text.config(text=format_row(raw))
        feat_text.config(text=format_row(feat))
        pred_text.config(text=format_row(pred))
        alert_text.config(text=format_row(alert))

        if feat:
            latest_act.config(text=f"Actual Risk: {feat['idx_mold_now']:.3f}")
        if pred:
            latest_pred.config(text=f"Predicted Risk: {pred['pred_idx_mold_h']:.3f}")

        # Lead time estimate from most recent rows (simple demo approximation)
        if pred and feat:
            lead_time.config(text="Lead Time (min): demo")

        root.after(int(args.interval * 1000), refresh)

    refresh()
    root.mainloop()


if __name__ == "__main__":
    main()
