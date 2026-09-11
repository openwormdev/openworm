from __future__ import annotations
import argparse
import json
from pathlib import Path

from .core import SCENARIOS


def main():
    parser = argparse.ArgumentParser(description="WormStreet — paper-only c302 laboratory")
    sub = parser.add_subparsers(dest="command", required=True)
    replay = sub.add_parser("replay", help="Run a real c302 reference replay")
    replay.add_argument("--scenario", choices=SCENARIOS, default="reversal")
    replay.add_argument("--input", type=Path, help="Optional validated observation JSON; never published automatically")
    replay.add_argument("--output", type=Path, default=Path("runs/report.json"))
    sub.add_parser("serve", help="Serve the dashboard and bounded worker on loopback")
    sub.add_parser("doctor", help="Check runtime versions without printing identity or secrets")
    args = parser.parse_args()
    if args.command == "serve":
        import uvicorn
        uvicorn.run("wormstreet.api:app", host="127.0.0.1", port=8000, access_log=False, proxy_headers=False)
    elif args.command == "doctor":
        import importlib.metadata
        import shutil
        print(json.dumps({"java_available": bool(shutil.which("java")), "compiler_available":all(shutil.which(x) for x in ("gcc", "g++", "make")), "live_execution": False,
                          "versions": {x: importlib.metadata.version(x) for x in ("c302", "cect", "pyNeuroML", "neuron", "fastapi")}}, indent=2))
    else:
        from .replay import run_replay
        ticks = json.loads(args.input.read_text()) if args.input else None
        report = run_replay(args.scenario, ticks=ticks)
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(json.dumps(report, indent=2, allow_nan=False) + "\n")
        print(json.dumps({"status": "complete", "neurons": report["model"]["neurons"],
                          "ticks": len(report["rows"]), "paper_fills": sum(bool(x["fill"]) for x in report["rows"]),
                          "report_hash": report["report_hash"]}))


if __name__ == "__main__":
    main()
