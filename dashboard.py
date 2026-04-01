"""
CryptoMind AI -- Live Monitoring Dashboard
==========================================
Run in a separate terminal while the agent runs in another:
    python dashboard.py

Refreshes every 60 seconds automatically.
No external libraries required.
"""

import json
import os
import re
import subprocess
import sys
import time
from datetime import datetime

# Windows UTF-8 safety (Kraken CLI uses box-drawing chars)
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------
TRADES_FILE      = "trades_history.json"
REFRESH_INTERVAL = 60          # seconds between full redraws
WIDTH            = 64          # terminal column width

WATCH_PAIRS = ["XXBTZUSD", "XETHZUSD", "SOLUSD"]
PAIR_NAMES  = {
    "XXBTZUSD": "BTC/USD",
    "XETHZUSD": "ETH/USD",
    "SOLUSD":   "SOL/USD",
}


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def clear_screen():
    os.system("cls" if os.name == "nt" else "clear")


def bar(char="="):
    return char * WIDTH


def section(title):
    return f"\n  {title}\n  " + "-" * (WIDTH - 2)


def load_history() -> list:
    try:
        with open(TRADES_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return []


def fetch_ticker(pair: str) -> dict | None:
    """
    Call 'kraken ticker PAIR -o json' and return a small dict with
    last price and today's change %.  Returns None on any failure.
    """
    try:
        result = subprocess.run(
            ["kraken", "ticker", pair, "-o", "json"],
            capture_output=True, text=True,
            encoding="utf-8", errors="replace",
            timeout=10
        )
        if result.returncode != 0 or not result.stdout.strip():
            return None
        data = json.loads(result.stdout.strip())
        if pair not in data:
            return None
        t          = data[pair]
        last       = float(t["c"][0])
        open_today = float(t["o"])
        change_pct = ((last - open_today) / open_today * 100) if open_today else 0.0
        return {"last": last, "change_pct": change_pct}
    except Exception:
        return None


def price_from_raw(raw_output: str) -> float | None:
    """
    Extract the fill price from Kraken CLI table output.
    The table contains a row like:  │ Price  ┆ 68580.50  │
    """
    if not raw_output:
        return None
    # ┆ is U+2506 (box-drawing light triple dash vertical)
    m = re.search(r"Price\s+[\u2506|]\s+([\d,.]+)", raw_output)
    if m:
        try:
            return float(m.group(1).replace(",", ""))
        except ValueError:
            pass
    return None


def resolve_entry_price(pos: dict, history: list) -> float | None:
    """
    Find the fill price for a portfolio position (TRD-xxxx record).
    Strategy:
      1. pos['price'] field directly
      2. pos['raw_output'] (unlikely but check)
      3. Match a raw trader record by same pair + BUY + timestamp prefix
    """
    if pos.get("price") is not None:
        return float(pos["price"])

    if pos.get("raw_output"):
        p = price_from_raw(pos["raw_output"])
        if p:
            return p

    # Match raw record: same pair, BUY, timestamp within the same second
    pos_ts = str(pos.get("timestamp", ""))[:19]
    for t in history:
        if (not t.get("trade_id")
                and t.get("pair") == pos.get("pair")
                and t.get("action") == "BUY"
                and t.get("success")
                and str(t.get("timestamp", ""))[:19] == pos_ts):
            p = price_from_raw(t.get("raw_output", ""))
            if p:
                return p

    return None


# ---------------------------------------------------------------------------
# Stats computation
# ---------------------------------------------------------------------------

def compute_stats(history: list) -> dict:
    # Portfolio records have trade_id; raw trader records don't
    portfolio = [t for t in history if t.get("trade_id")]
    raw       = [t for t in history if not t.get("trade_id")]

    buy_signals  = [t for t in portfolio if t.get("action") == "BUY"]
    sell_signals = [t for t in portfolio if t.get("action") == "SELL"]
    failed_raw   = [t for t in raw if not t.get("success", True)]

    open_pos   = [t for t in buy_signals if t.get("status") == "open"]
    closed_pos = [
        t for t in buy_signals
        if t.get("status") == "closed" and t.get("pnl") is not None
    ]

    wins   = [t for t in closed_pos if (t.get("pnl") or 0) > 0]
    losses = [t for t in closed_pos if (t.get("pnl") or 0) <= 0]
    win_rate     = (len(wins) / len(closed_pos) * 100) if closed_pos else 0.0
    realized_pnl = sum(t.get("pnl", 0) or 0 for t in closed_pos)

    best  = max(closed_pos, key=lambda t: t.get("pnl", 0) or 0, default=None)
    worst = min(closed_pos, key=lambda t: t.get("pnl", 0) or 0, default=None)

    return {
        "buy_count":    len(buy_signals),
        "sell_count":   len(sell_signals),
        "failed_count": len(failed_raw),
        "open_pos":     open_pos,
        "closed_pos":   closed_pos,
        "win_rate":     win_rate,
        "wins":         len(wins),
        "losses":       len(losses),
        "realized_pnl": realized_pnl,
        "best":         best,
        "worst":        worst,
        "portfolio":    portfolio,
    }


# ---------------------------------------------------------------------------
# Rendering
# ---------------------------------------------------------------------------

def render(prices: dict, history: list, stats: dict) -> str:
    now = datetime.now().strftime("%Y-%m-%d  %H:%M:%S")
    L   = []   # lines list

    # ---- Header ----
    L.append(bar("="))
    L.append("  CRYPTOMIND AI  --  LIVE MONITORING DASHBOARD")
    L.append(f"  Updated: {now}   |   Refresh: every {REFRESH_INTERVAL}s")
    L.append(bar("="))

    # ---- Live prices ----
    L.append(section("LIVE MARKET PRICES"))
    for pair in WATCH_PAIRS:
        name = PAIR_NAMES.get(pair, pair)
        p    = prices.get(pair)
        if p:
            sign  = "+" if p["change_pct"] >= 0 else ""
            trend = "^" if p["change_pct"] >= 0 else "v"
            L.append(
                f"  {trend} {name:8s}:  ${p['last']:>12,.2f}"
                f"    ({sign}{p['change_pct']:.2f}% today)"
            )
        else:
            L.append(f"    {name:8s}:  -- unavailable --")

    # ---- Portfolio stats ----
    L.append(section("PORTFOLIO STATS"))
    total_signals = stats["buy_count"] + stats["sell_count"]
    L.append(
        f"  Total Signals     :  {total_signals}"
        f"  ({stats['buy_count']} BUY  |  {stats['sell_count']} SELL"
        f"  |  {stats['failed_count']} failed)"
    )
    L.append(f"  Open Positions    :  {len(stats['open_pos'])}")
    L.append(f"  Closed Positions  :  {len(stats['closed_pos'])}")
    L.append(
        f"  Win Rate          :  {stats['win_rate']:.1f}%"
        f"  ({stats['wins']}W / {stats['losses']}L)"
    )
    L.append(f"  Realized PnL      :  ${stats['realized_pnl']:>+.4f}")

    def trade_label(t):
        if t is None:
            return "(no closed trades yet)"
        name = PAIR_NAMES.get(t.get("pair", ""), t.get("pair", "?"))
        return f"{t.get('trade_id','?')}  {name}  ${t.get('pnl', 0) or 0:>+.4f}"

    L.append(f"  Best Trade        :  {trade_label(stats['best'])}")
    L.append(f"  Worst Trade       :  {trade_label(stats['worst'])}")

    # ---- Open positions ----
    L.append(section("OPEN POSITIONS"))
    if not stats["open_pos"]:
        L.append("  (none)")
    else:
        for pos in stats["open_pos"]:
            pair      = pos.get("pair", "")
            name      = PAIR_NAMES.get(pair, pair)
            tid       = pos.get("trade_id", "?")
            ts        = str(pos.get("timestamp", ""))[:16].replace("T", " ")
            entry     = resolve_entry_price(pos, history)
            amount    = float(pos.get("amount") or 0)
            live_info = prices.get(pair)
            now_price = live_info["last"] if live_info else None

            L.append(f"  [{tid}]  {name}  |  opened {ts}")
            if entry and now_price:
                unreal   = (now_price - entry) * amount
                pct      = (now_price - entry) / entry * 100
                sign     = "+" if unreal >= 0 else ""
                L.append(
                    f"    Entry ${entry:>10,.2f}  ->  "
                    f"Now ${now_price:>10,.2f}  |  "
                    f"PnL {sign}${unreal:.4f} ({pct:>+.2f}%)"
                )
            elif entry:
                L.append(f"    Entry ${entry:>10,.2f}  ->  live price unavailable")
            else:
                L.append(f"    Entry price not recorded by Kraken CLI (table format)")
                if now_price:
                    L.append(f"    Current price: ${now_price:>10,.2f}")

    # ---- Last 10 signals ----
    L.append(section("LAST 10 TRADE SIGNALS"))
    col = f"  {'Timestamp':16s}  {'Pair':7s}  {'Act':4s}  {'Conf':4s}  Result"
    L.append(col)
    L.append("  " + "-" * (WIDTH - 4))

    signals = sorted(
        stats["portfolio"],
        key=lambda t: t.get("timestamp", ""),
        reverse=True
    )[:10]

    if not signals:
        L.append("  (no signals recorded yet)")
    else:
        for t in signals:
            ts     = str(t.get("timestamp", ""))[:16].replace("T", " ")
            name   = PAIR_NAMES.get(t.get("pair", ""), t.get("pair", "?"))
            action = t.get("action", "?")
            conf   = t.get("ai_confidence")
            conf_s = f"{conf:.0%}" if conf is not None else " N/A"
            tid    = t.get("trade_id", "?")
            status = t.get("status", "?")
            pnl    = t.get("pnl") or 0

            # Determine result label
            if action == "BUY" and status == "open":
                result = f"OPEN     ({tid})"
            elif action == "BUY" and status == "closed":
                result = f"CLOSED   PnL=${pnl:>+.4f}"
            elif action == "SELL" and status == "closed":
                result = f"SOLD     PnL=${pnl:>+.4f}"
            else:
                result = status

            L.append(
                f"  {ts:16s}  {name:7s}  {action:4s}  {conf_s:4s}  {result}"
            )

    # ---- Footer ----
    L.append("")
    L.append(bar("="))
    L.append(
        f"  File: {TRADES_FILE}"
        f"{'':>{WIDTH - 8 - len(TRADES_FILE)}}Ctrl+C to exit"
    )
    L.append(bar("="))

    return "\n".join(L)


# ---------------------------------------------------------------------------
# Main loop
# ---------------------------------------------------------------------------

def run():
    print("CryptoMind AI Dashboard starting...")
    print("Fetching prices and reading trade history...")

    while True:
        try:
            # Load data
            history = load_history()
            stats   = compute_stats(history)

            # Fetch all live prices (parallel-ish: sequential but fast)
            prices = {pair: fetch_ticker(pair) for pair in WATCH_PAIRS}

            # Draw
            clear_screen()
            print(render(prices, history, stats))

        except KeyboardInterrupt:
            print("\n\nDashboard stopped.  Goodbye!")
            sys.exit(0)
        except Exception as exc:
            print(f"\n[Dashboard] Render error: {exc}")

        # Live countdown until next refresh
        try:
            for remaining in range(REFRESH_INTERVAL, 0, -1):
                print(
                    f"\r  Next refresh in {remaining:3d}s"
                    f"  |  Ctrl+C to exit   ",
                    end="",
                    flush=True,
                )
                time.sleep(1)
            print()  # newline before next clear
        except KeyboardInterrupt:
            print("\n\nDashboard stopped.  Goodbye!")
            sys.exit(0)


if __name__ == "__main__":
    run()
