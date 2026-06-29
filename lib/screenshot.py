"""Screenshot capture for the trade desk — the "AI photos" pipeline.

Runs on YOUR Mac (uses macOS `screencapture`). Captures the chart / flow /
gauge / chain straight off your screen into data/shots/, then prints the
path so Claude Code can Read the image and analyze it — no manual paste.

  python lib/screenshot.py chart            # capture a named region from config
  python lib/screenshot.py --window         # click a window to capture it
  python lib/screenshot.py --full           # whole main display
  python lib/screenshot.py --all            # every named region in config

Region coordinates live in config.yaml under `screenshots.regions` as
[x, y, width, height]. Calibrate once (see README), then it's one command.

NOTE: this is macOS-only by design (your trading Mac). It cannot run in the
remote/web container — that environment is headless with no display.
"""
from __future__ import annotations

import argparse
import platform
import subprocess
import sys
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SHOTS = ROOT / "data" / "shots"


def _load_regions():
    cfg = ROOT / "config.yaml"
    if not cfg.exists():
        return {}
    try:
        import yaml
        data = yaml.safe_load(cfg.read_text()) or {}
        return (data.get("screenshots", {}) or {}).get("regions", {}) or {}
    except Exception:
        return {}


def _out_path(label: str) -> Path:
    SHOTS.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    return SHOTS / f"{label}_{stamp}.png"


def _require_macos():
    if platform.system() != "Darwin":
        sys.exit("screenshot.py needs macOS `screencapture`. Run it on your "
                 "trading Mac, not in the remote container (headless, no display).")


def capture_region(label: str, region) -> Path:
    """region = [x, y, w, h]."""
    _require_macos()
    out = _out_path(label)
    x, y, w, h = region
    subprocess.run(["screencapture", "-x", f"-R{x},{y},{w},{h}", str(out)], check=True)
    return out


def capture_full(label: str = "full") -> Path:
    _require_macos()
    out = _out_path(label)
    subprocess.run(["screencapture", "-x", str(out)], check=True)
    return out


def capture_window(label: str = "window") -> Path:
    """Interactive: cursor becomes a camera; click the window to grab."""
    _require_macos()
    out = _out_path(label)
    subprocess.run(["screencapture", "-w", "-o", str(out)], check=True)
    return out


def main():
    ap = argparse.ArgumentParser(description="Capture trade-desk screenshots.")
    ap.add_argument("label", nargs="?", help="named region from config.yaml")
    ap.add_argument("--window", action="store_true", help="click a window to capture")
    ap.add_argument("--full", action="store_true", help="capture whole main display")
    ap.add_argument("--all", action="store_true", help="capture every named region")
    args = ap.parse_args()

    regions = _load_regions()

    if args.full:
        print(capture_full()); return
    if args.window:
        print(capture_window()); return
    if args.all:
        if not regions:
            sys.exit("No regions in config.yaml under screenshots.regions.")
        for name, region in regions.items():
            print(capture_region(name, region))
        return
    if args.label:
        if args.label not in regions:
            sys.exit(f"Region '{args.label}' not in config.yaml. "
                     f"Known: {', '.join(regions) or '(none)'}. "
                     f"Or use --window / --full.")
        print(capture_region(args.label, regions[args.label])); return

    ap.print_help()


if __name__ == "__main__":
    main()
