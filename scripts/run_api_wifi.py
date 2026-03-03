#!/usr/bin/env python
import argparse
import os
import sys

import uvicorn

# Ensure repo root is on sys.path when running as a script
REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if REPO_ROOT not in sys.path:
    sys.path.insert(0, REPO_ROOT)


def main() -> None:
    parser = argparse.ArgumentParser(description="Run Smart Campus FastAPI server for WiFi/ESP32 testing.")
    parser.add_argument("--host", default="0.0.0.0", help="Bind host. Use 0.0.0.0 for LAN access.")
    parser.add_argument("--port", type=int, default=8000)
    parser.add_argument("--model", default="baseline", choices=["baseline", "lgbm"])
    parser.add_argument("--model-path", default="models/mold_lgbm.txt")
    parser.add_argument("--horizon-min", type=int, default=60)
    parser.add_argument("--reload", action="store_true", help="Enable autoreload for local dev.")
    args = parser.parse_args()

    os.environ["MODEL_MODE"] = args.model
    os.environ["MODEL_PATH"] = args.model_path
    os.environ["FORECAST_HORIZON_MIN"] = str(args.horizon_min)

    uvicorn.run(
        "cloud.ingest_api.app.main:app",
        host=args.host,
        port=args.port,
        reload=args.reload,
        log_level="info",
    )


if __name__ == "__main__":
    main()
