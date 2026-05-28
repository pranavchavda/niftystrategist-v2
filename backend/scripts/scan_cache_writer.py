"""Subprocess entry point for the scan-cache cron.

Run as an isolated process (not in-process) so the pandas-heavy scan's memory
is fully freed each cycle — prod is a small, already-swapping box. The
scheduler spawns this every ~3 min during market hours.

  python scripts/scan_cache_writer.py [universe]
"""
import asyncio
import os
import sys

_backend = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _backend not in sys.path:
    sys.path.insert(0, _backend)

from services.scan_cache import run_and_store  # noqa: E402


def main():
    universe = sys.argv[1] if len(sys.argv) > 1 else "nifty500"
    result = asyncio.run(run_and_store(universe=universe))
    print(result)


if __name__ == "__main__":
    main()
