"""Remove wall-clock fields and rebuild hashes for a public live-session artifact."""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from wormbrain.live import sanitize_public_recording


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    value = sanitize_public_recording(json.loads(args.input.read_text(encoding="utf-8")))
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(value, indent=2, allow_nan=False) + "\n", encoding="utf-8")
    print(json.dumps({"status": "public-recording-ready", "frames": len(value["frames"]),
                      "model_hash": value["model"]["network_sha256"], "audit_root": value["audit_root"]}))


if __name__ == "__main__":
    main()
