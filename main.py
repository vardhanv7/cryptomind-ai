"""
CryptoMind AI -- Autonomous AI-Powered Crypto Trading Agent
============================================================
Built for the lablab.ai AI Trading Agents Hackathon (March-April 2026)

This is the main entry point.  Run with:
    python main.py              -- paper trading (default, safe)
    python main.py --mode live  -- live trading (real money!)

Architecture:
    market_data  -> fetch live prices + OHLC candles (Kraken CLI)
    indicators   -> RSI, MACD, Bollinger, SMA/EMA
    ai_brain     -> Groq LLaMA 3.3-70B trade decision
    trader       -> execute trade via Kraken CLI
    portfolio    -> record trade, track PnL, stop-loss / take-profit
    main (this)  -> orchestrate the loop, never crash
"""

import argparse
import json
import signal
import sys
import time
from datetime import date, datetime

# Force UTF-8 output on Windows (Kraken CLI uses box-drawing chars)
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

from config import (
    PAIR_NAMES, STOP_LOSS_PCT, TAKE_PROFIT_PCT,
    MAX_OPEN_POSITIONS, TRADES_FILE,
)
from logger import get_logger, setup_logger
import market_data
import indicators as ind
import ai_brain
import trader
import portfolio

# ---------------------------------------------------------------------------
# Top-level configuration (override via --mode argument)
# ---------------------------------------------------------------------------
TRADING_PAIRS  = ["XXBTZUSD", "XETHZUSD", "SOLUSD"]
TRADE_INTERVAL = 900   # seconds between full cycles (15 minutes)
TRADE_AMOUNT   = {     # base-asset amount per trade
    "XXBTZUSD": 0.001,   # ~$66  at $66k BTC
    "XETHZUSD": 0.01,    # ~$35  at $3.5k ETH
    "SOLUSD":   0.1,     # ~$14  at $140 SOL
}
MODE = "paper"  # reassigned after argparse

# ---------------------------------------------------------------------------
# Session state (in-memory, reset each run)
# ---------------------------------------------------------------------------
_last_trade_time: dict[str, float] = {}   # {pair: unix timestamp}
_running = True                           # set False by SIGINT handler


# ---------------------------------------------------------------------------
# Signal handler for graceful Ctrl+C shutdown
# ---------------------------------------------------------------------------
def _handle_sigint(sig, frame):
    global _running
    logger = get_logger()
    print("\n\n[Main] Ctrl+C received -- finishing current operation then stopping...")
    logger.info("Shutdown signal received (SIGINT)")
    _running = False


# ---------------------------------------------------------------------------
# Small helpers (avoid importing private symbols from other modules)
# ---------------------------------------------------------------------------

def _load_trade_history() -> list:
    """Read trades_history.json safely.  Returns [] on any error."""
    try:
        with open(TRADES_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return []


def _get_open_position_count() -> int:
    """Count currently open BUY positions in the trade history."""
    return sum(
        1 for t in _load_trade_history()
        if t.get("action") == "BUY" and t.get("status") == "open"
    )


def _get_daily_pnl() -> float:
    """Sum today's realized PnL from closed BUY positions."""
    today = date.today().isoformat()
    return sum(
        t.get("pnl", 0) or 0
        for t in _load_trade_history()
        if t.get("action") == "BUY"
        and t.get("status") == "closed"
        and str(t.get("timestamp", "")).startswith(today)
    )


def _get_portfolio_value(mode: str) -> float:
    """
    Fetch total portfolio value from Kraken paper/live status.
    Falls back to $10,000 if the CLI call fails.
    """
    try:
        status = trader.get_portfolio_status(mode)
        if status["success"] and status.get("total_value"):
            return float(status["total_value"])
    except Exception:
        pass
    return 10_000.0


# ---------------------------------------------------------------------------
# Core: one full trading cycle
# ---------------------------------------------------------------------------

def run_trading_cycle(mode: str) -> int:
    """
    Run one complete pass over all trading pairs.

    For each pair:
        a. Fetch latest price
        b. Fetch OHLC candles
        c. Calculate technical indicators
        d. Ask AI brain for trade decision
        e. Risk-management check (should_trade)
        f. Execute trade if approved
        g. Record trade in portfolio

    After all pairs:
        - Update open positions for stop-loss / take-profit
        - Print a brief status summary

    Returns the number of trades executed this cycle.
    Never raises -- all exceptions are caught and logged.
    """
    logger      = get_logger()
    cycle_ts    = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    current_prices: dict[str, float] = {}
    trades_done = 0

    print("\n" + "=" * 62)
    print(f"  TRADING CYCLE  |  {cycle_ts}  |  MODE: {mode.upper()}")
    print("=" * 62)
    logger.info(f"Trading cycle started [{mode.upper()}]")

    # Pre-fetch portfolio value once (avoids repeated slow CLI calls)
    portfolio_value = _get_portfolio_value(mode)
    logger.debug(f"Portfolio value: ${portfolio_value:,.2f}")

    for pair in TRADING_PAIRS:
        pair_name = PAIR_NAMES.get(pair, pair)
        print(f"\n  [{pair_name}]")

        try:
            # ------------------------------------------------------------------
            # a. Latest price
            # ------------------------------------------------------------------
            ticker = market_data.get_ticker(pair)
            if not ticker:
                logger.warning(f"{pair_name}: could not fetch ticker -- skipping")
                print(f"    [SKIP] Could not fetch price")
                continue

            current_price = ticker["last"]
            current_prices[pair] = current_price
            print(
                f"    Price  : ${current_price:>12,.2f}  "
                f"({ticker['change_24h_pct']:+.2f}% 24h)"
            )

            # ------------------------------------------------------------------
            # b. OHLC candles (1-hour interval, need 50+ for indicators)
            # ------------------------------------------------------------------
            df = market_data.get_ohlc(pair, interval=60)
            candle_count = len(df) if df is not None else 0
            if df is None or candle_count < 50:
                logger.warning(
                    f"{pair_name}: only {candle_count} candles available "
                    f"(need 50+) -- skipping"
                )
                print(f"    [SKIP] Not enough candle data ({candle_count}/50 required)")
                continue

            # ------------------------------------------------------------------
            # c. Technical indicators
            # ------------------------------------------------------------------
            ind_data = ind.calculate_indicators(df)
            if not ind_data:
                logger.warning(f"{pair_name}: indicator calculation failed -- skipping")
                print(f"    [SKIP] Indicator calculation failed")
                continue

            print(
                f"    RSI    : {ind_data['rsi']:>6.1f}  |  "
                f"Trend: {ind_data['trend']:8s}  |  "
                f"MACD: {ind_data['macd']:>8.2f}"
            )

            # ------------------------------------------------------------------
            # d. AI trade signal
            # ------------------------------------------------------------------
            recent_prices = df["close"].tolist()
            signal = ai_brain.get_trade_signal(
                ind_data, recent_prices, current_price, pair_name
            )
            if not signal:
                logger.warning(f"{pair_name}: no AI signal received -- skipping")
                print(f"    [SKIP] AI signal unavailable")
                continue

            # ------------------------------------------------------------------
            # e. Risk management
            # ------------------------------------------------------------------
            open_pos       = _get_open_position_count()
            daily_pnl      = _get_daily_pnl()
            last_trade_ts  = _last_trade_time.get(pair, 0)

            approved, reason = ai_brain.should_trade(
                signal,
                portfolio_value  = portfolio_value,
                open_positions   = open_pos,
                last_trade_time  = last_trade_ts,
                daily_pnl        = daily_pnl,
            )

            action_str = signal.get("action", "HOLD")
            conf_str   = f"{signal.get('confidence', 0):.0%}"
            print(
                f"    Signal : {action_str:4s}  confidence={conf_str}  |  "
                f"approved={approved}"
            )
            print(f"    Reason : {reason}")
            logger.info(
                f"{pair_name}: action={action_str}, conf={conf_str}, "
                f"approved={approved} -- {reason}"
            )

            if not approved:
                continue

            # ------------------------------------------------------------------
            # f. Execute trade
            # ------------------------------------------------------------------
            amount       = TRADE_AMOUNT.get(pair, 0.001)
            trade_result = trader.execute_trade(action_str, pair, amount, mode)

            if not trade_result or not trade_result.get("success"):
                err = (trade_result or {}).get("error", "unknown error")
                logger.error(f"{pair_name}: trade execution failed -- {err}")
                print(f"    [FAIL] Trade execution failed: {err}")
                continue

            _last_trade_time[pair] = time.time()
            trades_done += 1

            # ------------------------------------------------------------------
            # g. Record in portfolio
            # ------------------------------------------------------------------
            enriched = {
                **trade_result,
                "ai_confidence":   signal.get("confidence"),
                "ai_reason":       signal.get("reason"),
                "stop_loss_pct":   signal.get("stop_loss_pct",   STOP_LOSS_PCT),
                "take_profit_pct": signal.get("take_profit_pct", TAKE_PROFIT_PCT),
            }
            portfolio.record_trade(enriched)

        except Exception as exc:
            logger.error(
                f"{pair_name}: unexpected error in trading cycle: {exc}",
                exc_info=True,
            )
            print(f"    [ERROR] {pair_name}: {exc}")
            # Never crash -- always continue to the next pair

    # --------------------------------------------------------------------------
    # Post-cycle: stop-loss / take-profit sweep
    # --------------------------------------------------------------------------
    if current_prices:
        print("\n  [Position check]  stop-loss / take-profit sweep...")
        try:
            # Build alias dict so update_positions can find prices
            # (it accepts both "BTCUSD" and "XXBTZUSD" style keys)
            result = portfolio.update_positions(current_prices)
            if result["auto_closed"]:
                print(f"    Auto-closed: {result['auto_closed']}")
                logger.info(f"Auto-closed positions: {result['auto_closed']}")
            else:
                print("    No auto-closes triggered")
        except Exception as exc:
            logger.error(f"update_positions error: {exc}", exc_info=True)

    # --------------------------------------------------------------------------
    # Cycle summary
    # --------------------------------------------------------------------------
    print("\n" + "-" * 62)
    print(portfolio.get_portfolio_summary())
    logger.info(f"Trading cycle complete -- {trades_done} trade(s) executed")
    return trades_done


# ---------------------------------------------------------------------------
# Countdown between cycles (sleeps in 60-second chunks for Ctrl+C response)
# ---------------------------------------------------------------------------

def _countdown(seconds: int) -> None:
    """
    Wait `seconds` total, printing a live countdown.
    Exits early (and cleanly) if _running becomes False.
    """
    elapsed = 0
    while elapsed < seconds and _running:
        remaining  = seconds - elapsed
        chunk      = min(60, remaining)
        mins, secs = divmod(remaining, 60)
        print(
            f"\r[Main] Next cycle in: {mins:02d}:{secs:02d}  "
            f"(Ctrl+C to stop)   ",
            end="",
            flush=True,
        )
        time.sleep(chunk)
        elapsed += chunk
    print()  # newline after the \r countdown line


# ---------------------------------------------------------------------------
# Startup banner
# ---------------------------------------------------------------------------

def _print_banner(mode: str) -> None:
    print()
    print("=" * 62)
    print("  CryptoMind AI  --  Autonomous Crypto Trading Agent")
    print("  lablab.ai AI Trading Agents Hackathon 2026")
    print("=" * 62)
    print(f"  Mode      : {mode.upper()}")
    print(f"  Pairs     : {', '.join(PAIR_NAMES.get(p, p) for p in TRADING_PAIRS)}")
    print(f"  Interval  : {TRADE_INTERVAL // 60} minutes between cycles")
    amounts = ", ".join(
        f"{PAIR_NAMES.get(p, p)}={v}" for p, v in TRADE_AMOUNT.items()
    )
    print(f"  Amounts   : {amounts}")
    print(f"  Started   : {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 62)

    if mode == "live":
        print()
        print("  *** LIVE TRADING MODE -- REAL MONEY AT RISK ***")
        print("  Ctrl+C within 5 seconds to abort...")
        for i in range(5, 0, -1):
            print(f"  Starting in {i}...", end="\r", flush=True)
            time.sleep(1)
        print()


# ---------------------------------------------------------------------------
# Startup health-check: verify Kraken CLI is reachable
# ---------------------------------------------------------------------------

def _verify_kraken_cli() -> bool:
    """
    Fetch BTC ticker as a quick smoke-test for the Kraken CLI.
    Returns True if it works, False otherwise.
    """
    logger = get_logger()
    print("\n[Startup] Verifying Kraken CLI connection...")
    logger.info("Verifying Kraken CLI connection")

    try:
        test_ticker = market_data.get_ticker("XXBTZUSD")
        if test_ticker:
            print(
                f"[Startup] Kraken CLI OK -- "
                f"BTC/USD: ${test_ticker['last']:>10,.2f}  "
                f"({test_ticker['change_24h_pct']:+.2f}% 24h)"
            )
            logger.info(
                f"Kraken CLI verified -- BTC/USD: ${test_ticker['last']:,.2f}"
            )
            return True
        else:
            print("[Startup] ERROR: Kraken CLI returned no data.")
            logger.error("Kraken CLI verification failed -- no ticker data")
            return False
    except Exception as exc:
        print(f"[Startup] ERROR: Kraken CLI exception: {exc}")
        logger.error(f"Kraken CLI exception: {exc}", exc_info=True)
        return False


# ---------------------------------------------------------------------------
# Shutdown: print final report
# ---------------------------------------------------------------------------

def _shutdown(cycle_count: int) -> None:
    logger = get_logger()
    print("\n" + "=" * 62)
    print("  CryptoMind AI  --  Shutting Down")
    print("=" * 62)
    print("\n[Shutdown] Final performance report:")
    try:
        print(portfolio.get_performance_report())
    except Exception as exc:
        logger.error(f"Could not generate final report: {exc}", exc_info=True)
        print(f"[Shutdown] Could not generate report: {exc}")

    logger.info(f"CryptoMind AI stopped cleanly after {cycle_count} cycle(s)")
    print(f"\n[Shutdown] Completed {cycle_count} cycle(s).  Goodbye!")


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def main() -> None:
    global MODE, _running

    # --- Parse CLI arguments ---
    parser = argparse.ArgumentParser(
        description="CryptoMind AI -- Autonomous crypto trading agent"
    )
    parser.add_argument(
        "--mode",
        choices=["paper", "live"],
        default="paper",
        help="Trading mode: 'paper' (simulated, default) or 'live' (real money)",
    )
    args   = parser.parse_args()
    MODE   = args.mode

    # --- Logger + signal handler ---
    logger = setup_logger()
    signal.signal(signal.SIGINT, _handle_sigint)

    # --- Banner ---
    _print_banner(MODE)

    # --- Verify Kraken CLI ---
    if not _verify_kraken_cli():
        print("[Startup] Cannot proceed without Kraken CLI.  Exiting.")
        sys.exit(1)

    logger.info(f"CryptoMind AI started in {MODE.upper()} mode")
    print(
        f"\n[Startup] Trading loop started "
        f"(cycle every {TRADE_INTERVAL // 60} min).  "
        f"Press Ctrl+C to stop gracefully.\n"
    )

    cycle_count = 0

    while _running:
        cycle_count += 1
        logger.info(f"=== Cycle #{cycle_count} ===")

        try:
            run_trading_cycle(MODE)
        except Exception as exc:
            # Last-resort catch -- the cycle itself shouldn't raise, but just in case
            logger.error(
                f"Cycle #{cycle_count} raised unexpectedly: {exc}",
                exc_info=True,
            )
            print(f"\n[Main] Cycle #{cycle_count} failed: {exc} -- continuing")

        if not _running:
            break

        print(
            f"\n[Main] Cycle #{cycle_count} done.  "
            f"Next cycle in {TRADE_INTERVAL // 60} min."
        )
        _countdown(TRADE_INTERVAL)

    _shutdown(cycle_count)


if __name__ == "__main__":
    main()
