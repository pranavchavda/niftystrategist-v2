"""Subprocess entry point for the sector-flow cache cron.

Run as an isolated process (not in-process) so each cycle's fetch buffers are
fully freed on the small prod box, and a rate-limit stall can't wedge the main
loop. The scheduler spawns this every ~5 min during market hours.

  python scripts/sector_flow_cache_writer.py [universe]
"""
import asyncio
import os
import sys

_backend = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
for _p in (_backend, os.path.join(_backend, "cli-tools")):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from services.sector_flow_cache import run_and_store  # noqa: E402


def main():
    universe = sys.argv[1] if len(sys.argv) > 1 else "nifty500"
    result = asyncio.run(run_and_store(universe=universe))
    print(result)


if __name__ == "__main__":
    main()
