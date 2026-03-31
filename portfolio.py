"""
CryptoMind AI - Portfolio Module
==================================
Tracks all trades, calculates PnL, and generates performance reports.

Think of it like this:
- trader.py     = executes the trade (the broker)
- portfolio.py  = tracks performance (the accountant)

Trades are stored in trades_history.json. Each BUY opens a position;
a matching SELL closes it and locks in the realized PnL.
"""

import json
import sys
from datetime import datetime

from config import PAIR_NAMES, STOP_LOSS_PCT, TAKE_PROFIT_PCT, TRADES_FILE
from logger import get_logger, setup_logger

# Windows console safety
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

# Maps Kraken pair names to the key aliases callers might use in current_prices
_PAIR_PRICE_ALIASES = {
    "XXBTZUSD": ["BTCUSD", "XXBTZUSD", "BTC/USD", "XBTUSD"],
    "XETHZUSD": ["ETHUSD", "XETHZUSD", "ETH/USD"],
    "SOLUSD":   ["SOLUSD", "SOL/USD"],
}


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _load_history():
    """Load trades_history.json. Returns [] if missing or corrupt."""
    try:
        with open(TRADES_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return []


def _save_history(history):
    """Write the trades list back to trades_history.json."""
    logger = get_logger()
    try:
        with open(TRADES_FILE, "w", encoding="utf-8") as f:
            json.dump(history, f, indent=2, default=str)
    except Exception as e:
        logger.error(f"Could not save trade history: {e}")


def _lookup_price(pair, current_prices):
    """
    Find the current price for a Kraken pair from a prices dict.
    Tries several common key formats so callers don't need to know Kraken
    pair names (e.g. accepts "BTCUSD" for "XXBTZUSD").
    Returns float or None.
    """
    candidates = _PAIR_PRICE_ALIASES.get(pair, [pair])
    for key in candidates:
        if key in current_prices:
            return float(current_prices[key])
    # Last-resort: case-insensitive scan
    pair_upper = pair.upper()
    for k, v in current_prices.items():
        if k.upper() == pair_upper:
            return float(v)
    return None


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def record_trade(trade_details):
    """
    Append an enriched trade record to trades_history.json.

    Accepts the raw dict from execute_trade() (or any dict with the same
    keys), plus optional AI signal fields. Normalises everything into a
    consistent portfolio record and — for SELL trades — matches to the
    oldest open BUY on the same pair (FIFO) and locks in realized PnL.

    Args:
        trade_details: dict — required keys:
            pair, action, amount, timestamp, mode
            Optional keys (from AI signal or execute_trade):
            price, order_id, ai_confidence, ai_reason,
            stop_loss_pct, take_profit_pct

    Returns:
        The saved record dict, or None on error.
    """
    logger = get_logger()

    try:
        history  = _load_history()
        trade_id = f"TRD-{len(history) + 1:04d}"

        action = trade_details.get("action", "").upper()
        amount = float(trade_details.get("amount", 0))
        price  = trade_details.get("price")
        pair   = trade_details.get("pair", "")

        record = {
            "trade_id":        trade_id,
            "timestamp":       trade_details.get("timestamp", datetime.now().isoformat()),
            "pair":            pair,
            "action":          action,
            "amount":          amount,
            "price":           float(price) if price is not None else None,
            "cost_usd":        round(float(price) * amount, 4) if price else None,
            "ai_confidence":   trade_details.get("ai_confidence"),
            "ai_reason":       trade_details.get("ai_reason"),
            "stop_loss_pct":   trade_details.get("stop_loss_pct",   STOP_LOSS_PCT),
            "take_profit_pct": trade_details.get("take_profit_pct", TAKE_PROFIT_PCT),
            "status":          "open" if action == "BUY" else "closed",
            "pnl":             0.0,
            "unrealized_pnl":  None,
            "mode":            trade_details.get("mode", "paper"),
            "order_id":        trade_details.get("order_id"),
        }

        # SELL: match to oldest open BUY on the same pair (FIFO) and book PnL
        if action == "SELL" and price is not None:
            exit_price = float(price)
            for t in history:                          # oldest first = FIFO
                if (t.get("pair") == pair
                        and t.get("action") == "BUY"
                        and t.get("status") == "open"
                        and t.get("price") is not None):
                    entry_price = float(t["price"])
                    pnl         = round((exit_price - entry_price) * amount, 4)
                    t["status"]       = "closed"
                    t["closed_at"]    = record["timestamp"]
                    t["close_price"]  = exit_price
                    t["pnl"]          = pnl
                    t["unrealized_pnl"] = None
                    record["pnl"]           = pnl
                    record["matched_buy_id"] = t["trade_id"]
                    logger.info(
                        f"Closed {pair} [{t['trade_id']}]: "
                        f"entry=${entry_price:,.2f}, exit=${exit_price:,.2f}, "
                        f"PnL=${pnl:+.4f}"
                    )
                    break

        history.append(record)
        _save_history(history)

        pair_name  = PAIR_NAMES.get(pair, pair)
        price_disp = f"${float(price):,.2f}" if price is not None else "N/A"
        logger.info(
            f"Trade recorded [{trade_id}]: {action} {amount} {pair_name} "
            f"@ {price_disp} | status={record['status']} | PnL=${record['pnl']:+.4f}"
        )
        return record

    except Exception as e:
        logger.error(f"Failed to record trade: {e}")
        return None


def update_positions(current_prices):
    """
    Recalculate unrealized PnL for every open BUY position.
    Auto-close positions that have hit their stop-loss or take-profit level.

    Args:
        current_prices: dict — pair name -> price.
            Accepts Kraken names or common aliases, e.g.:
            {"BTCUSD": 66000, "ETHUSD": 3500}
            {"XXBTZUSD": 66000}

    Returns:
        dict:
            updated    : list of (trade_id, unrealized_pnl) for each open position
            auto_closed: list of trade_ids that were automatically closed
    """
    logger     = get_logger()
    history    = _load_history()
    updated    = []
    auto_closed = []
    changed    = False

    for trade in history:
        if trade.get("status") != "open" or trade.get("action") != "BUY":
            continue

        pair        = trade.get("pair", "")
        entry_price = trade.get("price")
        amount      = float(trade.get("amount", 0))
        sl_pct      = float(trade.get("stop_loss_pct",   STOP_LOSS_PCT))
        tp_pct      = float(trade.get("take_profit_pct", TAKE_PROFIT_PCT))

        if entry_price is None:
            continue  # No entry price recorded — skip

        entry_price = float(entry_price)
        current     = _lookup_price(pair, current_prices)

        if current is None:
            logger.debug(f"No price found for {pair} in current_prices — skipping")
            continue

        unrealized_pnl = round((current - entry_price) * amount, 4)
        pct_change     = round(((current - entry_price) / entry_price) * 100, 4)

        trade["unrealized_pnl"] = unrealized_pnl
        trade["current_price"]  = current
        trade["pct_change"]     = pct_change
        updated.append((trade["trade_id"], unrealized_pnl))
        changed = True

        pair_name = PAIR_NAMES.get(pair, pair)
        logger.debug(
            f"{pair_name} [{trade['trade_id']}]: entry=${entry_price:,.2f}, "
            f"now=${current:,.2f}, unrealized=${unrealized_pnl:+.4f} ({pct_change:+.2f}%)"
        )

        # Auto-close: stop-loss
        if pct_change <= -sl_pct:
            logger.warning(
                f"STOP-LOSS triggered [{trade['trade_id']}] {pair_name}: "
                f"{pct_change:.2f}% <= -{sl_pct}%"
            )
            print(
                f"[Portfolio] STOP-LOSS hit: {pair_name} {pct_change:+.2f}% "
                f"(limit: -{sl_pct}%) — auto-closing position"
            )
            trade["status"]       = "closed"
            trade["closed_at"]    = datetime.now().isoformat()
            trade["close_price"]  = current
            trade["pnl"]          = unrealized_pnl
            trade["close_reason"] = "stop_loss"
            trade["unrealized_pnl"] = None
            auto_closed.append(trade["trade_id"])

        # Auto-close: take-profit
        elif pct_change >= tp_pct:
            logger.info(
                f"TAKE-PROFIT triggered [{trade['trade_id']}] {pair_name}: "
                f"{pct_change:.2f}% >= {tp_pct}%"
            )
            print(
                f"[Portfolio] TAKE-PROFIT hit: {pair_name} {pct_change:+.2f}% "
                f"(target: {tp_pct}%) — auto-closing position"
            )
            trade["status"]       = "closed"
            trade["closed_at"]    = datetime.now().isoformat()
            trade["close_price"]  = current
            trade["pnl"]          = unrealized_pnl
            trade["close_reason"] = "take_profit"
            trade["unrealized_pnl"] = None
            auto_closed.append(trade["trade_id"])

    if changed:
        _save_history(history)
        logger.info(
            f"update_positions: {len(updated)} checked, "
            f"{len(auto_closed)} auto-closed"
        )

    return {"updated": updated, "auto_closed": auto_closed}


def get_portfolio_summary():
    """
    Calculate metrics and return a formatted portfolio summary string.

    Metrics:
        - Total PnL (realized + unrealized)
        - Win rate (% of closed positions that were profitable)
        - Total trades / open positions / closed positions
        - Average profit per winning trade
        - Average loss per losing trade
        - Maximum drawdown (peak-to-trough of cumulative realized PnL)

    Returns:
        str — formatted multi-line summary
    """
    logger   = get_logger()
    history  = _load_history()

    # Only BUY records carry PnL (SELL records are for audit only)
    buy_trades    = [t for t in history if t.get("action") == "BUY"]
    open_trades   = [t for t in buy_trades if t.get("status") == "open"]
    closed_trades = [
        t for t in buy_trades
        if t.get("status") == "closed" and t.get("pnl") is not None
    ]

    realized_pnl   = sum(t.get("pnl", 0)             for t in closed_trades)
    unrealized_pnl = sum(t.get("unrealized_pnl") or 0 for t in open_trades)
    total_pnl      = realized_pnl + unrealized_pnl

    wins   = [t for t in closed_trades if t.get("pnl", 0) > 0]
    losses = [t for t in closed_trades if t.get("pnl", 0) <= 0]

    win_rate = (len(wins) / len(closed_trades) * 100) if closed_trades else 0.0
    avg_win  = (sum(t["pnl"] for t in wins)   / len(wins))   if wins   else 0.0
    avg_loss = (sum(t["pnl"] for t in losses) / len(losses)) if losses else 0.0

    # Maximum drawdown: largest peak-to-trough drop in cumulative realized PnL
    max_drawdown = 0.0
    if closed_trades:
        cumulative = 0.0
        peak       = 0.0
        for t in sorted(closed_trades, key=lambda x: x.get("timestamp", "")):
            cumulative += t.get("pnl", 0)
            if cumulative > peak:
                peak = cumulative
            drawdown = peak - cumulative
            if drawdown > max_drawdown:
                max_drawdown = drawdown

    lines = [
        "=" * 55,
        "  CRYPTOMIND AI  --  PORTFOLIO SUMMARY",
        "=" * 55,
        f"  Total PnL         :  ${total_pnl:>+10.4f}",
        f"    Realized        :  ${realized_pnl:>+10.4f}",
        f"    Unrealized      :  ${unrealized_pnl:>+10.4f}",
        "-" * 55,
        f"  Total Trades      :  {len(buy_trades)}",
        f"  Open Positions    :  {len(open_trades)}",
        f"  Closed Positions  :  {len(closed_trades)}",
        "-" * 55,
        f"  Win Rate          :  {win_rate:>7.1f}%  "
        f"({len(wins)} wins / {len(losses)} losses)",
        f"  Avg Win           :  ${avg_win:>+10.4f}",
        f"  Avg Loss          :  ${avg_loss:>+10.4f}",
        f"  Max Drawdown      :  ${max_drawdown:>10.4f}",
        "=" * 55,
    ]

    summary = "\n".join(lines)
    logger.info(
        f"Portfolio summary: PnL=${total_pnl:+.4f}, "
        f"win_rate={win_rate:.1f}%, trades={len(buy_trades)}, "
        f"open={len(open_trades)}"
    )
    return summary


def get_performance_report():
    """
    Generate a detailed performance report for the hackathon submission.

    Sections:
        1. Portfolio summary (all key metrics)
        2. AI signal metrics (avg confidence, trades with AI data)
        3. Performance breakdown by pair
        4. Trade-by-trade table

    Returns:
        str — the full formatted report
    """
    logger       = get_logger()
    history      = _load_history()
    generated_at = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    # --- Summary ---
    summary = get_portfolio_summary()

    # --- AI metrics ---
    trades_with_ai = [t for t in history if t.get("ai_confidence") is not None]
    avg_ai_conf    = (
        sum(float(t["ai_confidence"]) for t in trades_with_ai) / len(trades_with_ai)
        if trades_with_ai else 0.0
    )

    # --- Per-pair breakdown (BUY side only) ---
    pair_stats = {}
    for t in history:
        if t.get("action") != "BUY":
            continue
        pair = PAIR_NAMES.get(t.get("pair", ""), t.get("pair", "Unknown"))
        if pair not in pair_stats:
            pair_stats[pair] = {"trades": 0, "pnl": 0.0, "wins": 0}
        pair_stats[pair]["trades"] += 1
        pnl = t.get("pnl") or t.get("unrealized_pnl") or 0.0
        pair_stats[pair]["pnl"] += pnl
        if pnl > 0:
            pair_stats[pair]["wins"] += 1

    pair_lines = []
    for pair, s in pair_stats.items():
        wr = (s["wins"] / s["trades"] * 100) if s["trades"] else 0
        pair_lines.append(
            f"  {pair:8s}:  {s['trades']:3d} trade(s), "
            f"PnL = ${s['pnl']:>+9.4f},  win rate = {wr:.0f}%"
        )

    # --- Trade-by-trade table ---
    buy_trades = [t for t in history if t.get("action") == "BUY"]
    col_header = (
        "  Trade ID   | Timestamp        | Pair    "
        "| Entry Price  | PnL        | Conf | Status"
    )
    col_sep = "  " + "-" * 77

    rows = []
    for t in buy_trades:
        price_str = f"${float(t['price']):>10,.2f}" if t.get("price") else "         N/A"
        pnl_val   = t.get("pnl") or t.get("unrealized_pnl") or 0.0
        pnl_tag   = "(unreal)" if t.get("status") == "open" else "        "
        pnl_str   = f"${pnl_val:>+8.4f} {pnl_tag}"
        conf_str  = f"{float(t['ai_confidence']):.0%}" if t.get("ai_confidence") else " N/A"
        pair_name = PAIR_NAMES.get(t.get("pair", ""), t.get("pair", "?"))
        ts        = t.get("timestamp", "")[:16].replace("T", " ")
        rows.append(
            f"  {t.get('trade_id', '?'):10s} | {ts} | {pair_name:7s} "
            f"| {price_str} | {pnl_str} | {conf_str:>4s} | {t.get('status', '?')}"
        )

    report_lines = [
        "=" * 65,
        "  CRYPTOMIND AI  --  PERFORMANCE REPORT",
        f"  Generated : {generated_at}",
        "=" * 65,
        "",
        summary,
        "",
        "=" * 65,
        "  AI SIGNAL METRICS",
        "=" * 65,
        f"  Trades with AI signals  :  {len(trades_with_ai)}",
        f"  Average AI confidence   :  {avg_ai_conf:.0%}",
        "",
        "=" * 65,
        "  PERFORMANCE BY PAIR",
        "=" * 65,
    ] + (pair_lines if pair_lines else ["  (no trades recorded yet)"]) + [
        "",
        "=" * 65,
        "  TRADE-BY-TRADE BREAKDOWN  (BUY positions only)",
        "=" * 65,
        col_header,
        col_sep,
    ] + (rows if rows else ["  (no trades recorded yet)"]) + [
        col_sep,
        "",
        "=" * 65,
        "  END OF REPORT",
        "=" * 65,
    ]

    report = "\n".join(report_lines)
    logger.info(
        f"Performance report generated: {len(buy_trades)} BUY trades, "
        f"{len(pair_stats)} pair(s)"
    )
    return report


# ---------------------------------------------------------------------------
# TEST: python portfolio.py
# ---------------------------------------------------------------------------
if __name__ == "__main__":
    setup_logger()

    print("=" * 60)
    print("  CryptoMind AI -- Portfolio Module Test")
    print("=" * 60)
    print("  Note: sample trades are APPENDED to trades_history.json")
    print("=" * 60)

    # Five sample trades: 2 closed (1 win, 1 loss) + 1 open
    sample_trades = [
        {   # Win: BTC long opened and closed at profit
            "pair": "XXBTZUSD", "action": "BUY", "amount": 0.001,
            "price": 64000.0, "timestamp": "2026-03-28T10:00:00",
            "mode": "paper", "order_id": "SAMPLE-001",
            "ai_confidence": 0.78,
            "ai_reason": "RSI oversold + MACD bullish crossover",
            "stop_loss_pct": 3.0, "take_profit_pct": 5.0,
        },
        {
            "pair": "XXBTZUSD", "action": "SELL", "amount": 0.001,
            "price": 67200.0, "timestamp": "2026-03-29T08:00:00",
            "mode": "paper", "order_id": "SAMPLE-002",
            "ai_confidence": 0.82,
            "ai_reason": "RSI overbought, take-profit target reached",
        },
        {   # Loss: ETH long opened and closed at a loss
            "pair": "XETHZUSD", "action": "BUY", "amount": 0.05,
            "price": 3500.0, "timestamp": "2026-03-29T12:00:00",
            "mode": "paper", "order_id": "SAMPLE-003",
            "ai_confidence": 0.61,
            "ai_reason": "Bollinger lower band bounce",
            "stop_loss_pct": 3.0, "take_profit_pct": 5.0,
        },
        {
            "pair": "XETHZUSD", "action": "SELL", "amount": 0.05,
            "price": 3290.0, "timestamp": "2026-03-30T09:00:00",
            "mode": "paper", "order_id": "SAMPLE-004",
            "ai_confidence": 0.70,
            "ai_reason": "Support broken, stop-loss triggered",
        },
        {   # Open SOL position — unrealized PnL updated in Step 2
            "pair": "SOLUSD", "action": "BUY", "amount": 1.0,
            "price": 140.0, "timestamp": "2026-03-31T07:00:00",
            "mode": "paper", "order_id": "SAMPLE-005",
            "ai_confidence": 0.65,
            "ai_reason": "Bullish trend continuation signal",
            "stop_loss_pct": 3.0, "take_profit_pct": 5.0,
        },
    ]

    print("\n[Step 1] Recording 5 sample trades...")
    for td in sample_trades:
        rec = record_trade(td)
        if rec:
            p = f"${rec['price']:>9,.2f}" if rec["price"] else "       N/A"
            print(
                f"  [{rec['trade_id']}] {rec['action']:4s} {rec['pair']:9s} "
                f"@ {p} | status={rec['status']:6s} | PnL=${rec['pnl']:+.4f}"
            )

    print("\n[Step 2] Updating open positions with current market prices...")
    result = update_positions({
        "BTCUSD": 66000.0,   # BTC already closed — no effect
        "ETHUSD": 3400.0,    # ETH already closed — no effect
        "SOLUSD": 146.50,    # SOL open: +$6.50 unrealized gain
    })
    print(f"  Positions updated  : {len(result['updated'])}")
    print(f"  Auto-closed        : {len(result['auto_closed'])}")
    for tid, upnl in result["updated"]:
        print(f"  {tid}: unrealized PnL = ${upnl:+.4f}")

    print("\n[Step 3] Portfolio Summary:")
    print(get_portfolio_summary())

    print("\n[Step 4] Full Performance Report:")
    print(get_performance_report())
