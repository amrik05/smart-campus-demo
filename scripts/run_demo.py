import argparse
import os
import signal
import subprocess
import sys
import threading
import time

# Used for API readiness polling
import requests

# Ensure repo root is on sys.path when running as a script
REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if REPO_ROOT not in sys.path:
    sys.path.insert(0, REPO_ROOT)

import uvicorn

from analytics.synthetic.scenario_generator import run_generator, run_sequence


def _start_api(host: str, port: int) -> threading.Thread:
    config = uvicorn.Config("cloud.ingest_api.app.main:app", host=host, port=port, log_level="info")
    server = uvicorn.Server(config=config)

    thread = threading.Thread(target=server.run, daemon=True)
    thread.start()
    return thread


def _start_streamlit(api_url: str, port: int) -> subprocess.Popen:
    env = os.environ.copy()
    env["API_URL"] = api_url
    cmd = [
        sys.executable,
        "-m",
        "streamlit",
        "run",
        "app/dashboard_streamlit/app.py",
        "--server.port",
        str(port),
        "--server.headless",
        "true",
    ]
    return subprocess.Popen(cmd, env=env)


def _wait_for_api(api_url: str, timeout_s: float = 15.0) -> None:
    deadline = time.time() + timeout_s
    while time.time() < deadline:
        try:
            resp = requests.get(f"{api_url}/latest", timeout=1)
            if resp.status_code == 200:
                return
        except Exception:
            time.sleep(0.2)
    raise RuntimeError("API did not become ready in time")


def main() -> None:
    parser = argparse.ArgumentParser(description="Run full Smart Campus demo (API + Streamlit + generator)")
    parser.add_argument("--api-host", default="127.0.0.1")
    parser.add_argument("--api-port", type=int, default=8000)
    parser.add_argument("--streamlit-port", type=int, default=8501)
    parser.add_argument("--rate-sec", type=float, default=1.0)
    parser.add_argument("--sequence", default="NORMAL:60,MOLD_EPISODE:120")
    parser.add_argument("--scenario", default="")
    parser.add_argument("--episode-id", default=None)
    parser.add_argument("--no-streamlit", action="store_true")
    parser.add_argument("--model", default="baseline", choices=["baseline", "lgbm"])
    parser.add_argument("--model-path", default="models/mold_lgbm.txt")
    parser.add_argument("--keep-alive", action="store_true")
    args = parser.parse_args()

    api_url = f"http://{args.api_host}:{args.api_port}"

    os.environ["MODEL_MODE"] = args.model
    os.environ["MODEL_PATH"] = args.model_path
    if args.model == "lgbm" and "FORECAST_HORIZON_MIN" not in os.environ:
        os.environ["FORECAST_HORIZON_MIN"] = "60"

    api_thread = _start_api(args.api_host, args.api_port)
    streamlit_proc = None
    if not args.no_streamlit:
        streamlit_proc = _start_streamlit(api_url, args.streamlit_port)

    _wait_for_api(api_url, timeout_s=15.0)

    try:
        if args.scenario:
            run_generator(
                api_url,
                args.scenario.upper(),
                args.rate_sec,
                0,
                42,
                args.episode_id,
                "SIM-001",
                "WATER-001",
                "RUTGERS-ENG-1",
                "RUTGERS",
                "ENG-1-BASEMENT",
            )
        else:
            parts = []
            for chunk in args.sequence.split(","):
                name, dur = chunk.split(":")
                parts.append((name.upper(), int(dur)))
            run_sequence(
                api_url,
                parts,
                args.rate_sec,
                42,
                "SIM-001",
                "WATER-001",
                "RUTGERS-ENG-1",
                "RUTGERS",
                "ENG-1-BASEMENT",
            )

        if args.keep_alive:
            while True:
                time.sleep(1.0)
    except KeyboardInterrupt:
        pass
    finally:
        if streamlit_proc:
            streamlit_proc.send_signal(signal.SIGINT)
            streamlit_proc.wait(timeout=5)


if __name__ == "__main__":
    main()
