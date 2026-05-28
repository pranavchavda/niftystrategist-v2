"""Manual smoke test for the trading snapshot builder."""
import asyncio
import sys

from services.trading_snapshot import build_trading_snapshot


async def main():
    user_id = int(sys.argv[1]) if len(sys.argv) > 1 else 1
    live_scan = "--no-scan" not in sys.argv
    thread_id = next((a.split("=", 1)[1] for a in sys.argv if a.startswith("--thread=")), None)
    res = await build_trading_snapshot(
        user_id, thread_id=thread_id, run_live_scan=live_scan, scan_universe="nifty50"
    )
    print("=" * 70)
    print(f"ok={res.ok}  scan_source={res.scan_source}  error={res.error}")
    print("=" * 70)
    print(res.text)
    print("=" * 70)
    print("ALERTS:", res.alerts)


if __name__ == "__main__":
    asyncio.run(main())
