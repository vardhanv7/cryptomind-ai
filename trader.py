"""
CryptoMind AI - Trader Module
==============================
Executes trades via Kraken CLI using subprocess.
Supports paper trading (safe default) and live trading.

Think of it like this:
- ai_brain.py   = decides WHAT to trade (BUY/SELL/HOLD)
- trader.py     = actually EXECUTES the trade via Kraken CLI
- portfolio.py  = tracks performance over time

Always defaults to paper mode — never risks real money unless explicitly set.
"""

import json
import re
import subprocess
import sys
import time
from datetime import datetime

# Windows terminals default to cp1252 which can't print many CLI outputs.
# Force UTF-8 so Kraken CLI responses display correctly.
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

from config import PAIR_NAMES, TRADES_FILE
from logger import get_logger, setup_logger


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _run_trade_command(command):
    """
    Run a Kraken CLI command and return (success, stdout, stderr).

    Args:
        command: list of strings, e.g. ["kraken", "paper", "buy", "XXBTZUSD", "0.001"]

    Returns:
        (success: bool, stdout: str, stderr: str)
    """
    logger = get_logger()
    try:
        result = subprocess.run(
            command,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=30
        )
        stdout = result.stdout.strip()
        stderr = result.stderr.strip()

        if result.returncode != 0:
            logger.error(f"Kraken CLI error (rc={result.returncode}): {stderr or stdout}")
            return False, stdout, stderr

        return True, stdout, stderr

    except subprocess.TimeoutExpired:
        logger.error(f"Kraken CLI timed out: {' '.join(command)}")
        return False, "", "Command timed out after 30s"
    except FileNotFoundError:
        logger.error("Kraken CLI not found. Make sure it is installed and in PATH.")
        return False, "", "kraken CLI not found in PATH"
    except Exception as e:
        logger.error(f"Unexpected error running Kraken CLI: {e}")
        return False, "", str(e)


def _parse_trade_output(output):
    """
    Parse Kraken CLI trade output into a normalised dict.
    Tries JSON first, then falls back to regex on plain text.

    Returns:
        dict with keys: price (float|None), order_id (str|None), status (str)
    """
    parsed = {"price": None, "order_id": None, "status": "unknown"}

    if not output:
        return parsed

    # --- Try JSON ---
    try:
        data = json.loads(output)
        raw_price = (
            data.get("price")
            or data.get("avg_price")
            or data.get("cost")
        )
        parsed["price"] = float(raw_price) if raw_price else None
        parsed["order_id"] = (
            data.get("txid")
            or data.get("order_id")
            or data.get("id")
        )
        parsed["status"] = data.get("status", "executed")
        return parsed
    except (json.JSONDecodeError, ValueError, TypeError):
        pass

    # --- Plain-text fallback ---
    # Match patterns like "at $84,600.00", "@ 84600", "price: 84600"
    price_match = re.search(
        r'(?:at|price|@)\s*\$?([\d,]+\.?\d*)', output, re.IGNORECASE
    )
    if price_match:
        parsed["price"] = float(price_match.group(1).replace(",", ""))

    # Match order/txid patterns like "txid: O12345" or "order_id=ABC-123"
    id_match = re.search(
        r'(?:txid|order.?id|id)[\s:=]+([A-Z0-9-]+)', output, re.IGNORECASE
    )
    if id_match:
        parsed["order_id"] = id_match.group(1)

    parsed["status"] = "executed"
    return parsed


def _save_trade_to_history(trade):
    """Append a trade record to trades_history.json."""
    logger = get_logger()
    try:
        history = []
        try:
            with open(TRADES_FILE, "r") as f:
                history = json.load(f)
        except (FileNotFoundError, json.JSONDecodeError):
            pass  # Start fresh if file is missing or corrupt

        history.append(trade)

        with open(TRADES_FILE, "w") as f:
            json.dump(history, f, indent=2, default=str)

        logger.debug(f"Trade saved to {TRADES_FILE} ({len(history)} total records)")
    except Exception as e:
        logger.warning(f"Could not save trade to history file: {e}")


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def execute_trade(action, pair, amount, mode="paper"):
    """
    Execute a BUY or SELL trade via Kraken CLI.

    Args:
        action: "BUY" or "SELL"
        pair:   Kraken pair name, e.g. "XXBTZUSD"
        amount: Amount of base asset to trade (e.g. 0.001 for 0.001 BTC)
        mode:   "paper" (default — safe) or "live" (real money!)

    Returns:
        dict with keys:
            pair, action, amount, price, order_id,
            timestamp, mode, success, error, raw_output
    """
    logger = get_logger()
    action = action.upper()
    pair_name = PAIR_NAMES.get(pair, pair)
    mode_tag = "[PAPER]" if mode == "paper" else "[LIVE] "

    # Validate action
    if action not in ("BUY", "SELL"):
        msg = f"Invalid action '{action}'. Must be BUY or SELL."
        logger.error(msg)
        return {
            "pair": pair, "action": action, "amount": amount,
            "price": None, "order_id": None, "mode": mode,
            "timestamp": datetime.now().isoformat(),
            "success": False, "error": msg, "raw_output": ""
        }

    # Build CLI command
    verb = action.lower()
    if mode == "paper":
        command = ["kraken", "paper", verb, pair, str(amount)]
    else:
        command = ["kraken", verb, pair, str(amount)]

    logger.info(f"{mode_tag} Executing {action} {amount} {pair_name} — command: {' '.join(command)}")
    print(f"\n[Trader] {mode_tag} {action} {amount} {pair_name}")
    print(f"[Trader] Running: {' '.join(command)}")

    success, output, error = _run_trade_command(command)
    timestamp = datetime.now().isoformat()
    parsed = _parse_trade_output(output)

    trade = {
        "pair": pair,
        "action": action,
        "amount": amount,
        "price": parsed["price"],
        "order_id": parsed["order_id"],
        "timestamp": timestamp,
        "mode": mode,
        "success": success,
        "error": error if not success else None,
        "raw_output": output
    }

    if success:
        price_str = f"${parsed['price']:,.2f}" if parsed["price"] else "price N/A"
        logger.info(
            f"{mode_tag} {action} confirmed: {amount} {pair_name} "
            f"@ {price_str} | order_id={parsed['order_id']}"
        )
        print(f"[Trader] [OK] {action} confirmed: {amount} {pair_name} @ {price_str}")
    else:
        logger.error(f"{mode_tag} {action} FAILED for {pair_name}: {error or output}")
        print(f"[Trader] [FAIL] {action} FAILED: {error or output}")

    _save_trade_to_history(trade)
    return trade


def get_portfolio_status(mode="paper"):
    """
    Fetch current portfolio holdings and balances via Kraken CLI.

    Args:
        mode: "paper" (default) or "live"

    Returns:
        dict with keys:
            positions (list), balances (dict), total_value (float),
            mode, timestamp, success, raw_output
    """
    logger = get_logger()
    mode_tag = "[PAPER]" if mode == "paper" else "[LIVE] "

    command = ["kraken", "paper", "status"] if mode == "paper" else ["kraken", "balance"]

    logger.info(f"{mode_tag} Fetching portfolio status — command: {' '.join(command)}")
    print(f"\n[Trader] {mode_tag} Fetching portfolio status...")

    success, output, error = _run_trade_command(command)
    timestamp = datetime.now().isoformat()

    result = {
        "mode": mode,
        "timestamp": timestamp,
        "success": success,
        "positions": [],
        "balances": {},
        "total_value": 0.0,
        "raw_output": output
    }

    if not success:
        logger.error(f"{mode_tag} Could not fetch portfolio status: {error or output}")
        print(f"[Trader] [FAIL] Could not fetch portfolio: {error or output}")
        return result

    # --- Try JSON parse ---
    try:
        data = json.loads(output)
        result["balances"] = (
            data.get("balances") or data.get("balance") or {}
        )
        result["positions"] = (
            data.get("positions") or data.get("open_orders") or []
        )
        raw_value = data.get("total_value") or data.get("equity") or 0
        result["total_value"] = float(raw_value)
    except (json.JSONDecodeError, ValueError, TypeError):
        # Store raw output — CLI may use plain text
        result["balances"] = {"raw": output}

    # --- Print summary ---
    print(f"[Trader] [OK] Portfolio status retrieved:")
    balances = result["balances"]
    if balances and "raw" not in balances:
        for asset, balance in balances.items():
            print(f"         {asset:6s}: {balance}")
    else:
        display = output if output else "(no output from CLI)"
        print(f"         {display}")
    if result["total_value"]:
        print(f"         Total value: ${result['total_value']:,.2f}")
    print(f"         Open positions: {len(result['positions'])}")

    logger.info(
        f"{mode_tag} Portfolio: {len(result['positions'])} positions, "
        f"total=${result['total_value']:,.2f}"
    )
    return result


def close_position(pair, amount, mode="paper"):
    """
    Close an open position by executing the opposite trade.

    Checks current portfolio to determine whether the open position is
    long (BUY) or short (SELL), then trades the other direction.
    Defaults to selling (closing a long) if position direction is unclear.

    Args:
        pair:   Kraken pair name, e.g. "XXBTZUSD"
        amount: Amount to close
        mode:   "paper" (default) or "live"

    Returns:
        dict — same shape as execute_trade() return value
    """
    logger = get_logger()
    pair_name = PAIR_NAMES.get(pair, pair)
    mode_tag = "[PAPER]" if mode == "paper" else "[LIVE] "

    logger.info(f"{mode_tag} Closing position: {amount} {pair_name}")
    print(f"\n[Trader] {mode_tag} Closing position: {amount} {pair_name}")

    # Default: sell to close a long position
    close_action = "SELL"

    # Check portfolio to detect if the position is short (then buy to close)
    status = get_portfolio_status(mode)
    if status["success"] and status["positions"]:
        for pos in status["positions"]:
            if not isinstance(pos, dict):
                continue
            pos_pair = pos.get("pair", "")
            pos_side = (pos.get("side") or pos.get("type") or "").upper()
            if pos_pair == pair and pos_side in ("BUY", "SELL"):
                close_action = "BUY" if pos_side == "SELL" else "SELL"
                logger.debug(
                    f"Detected {pos_side} position on {pair_name} — "
                    f"closing with {close_action}"
                )
                break

    logger.info(f"{mode_tag} Closing {pair_name} with {close_action} {amount}")
    trade = execute_trade(close_action, pair, amount, mode)

    if trade and trade["success"]:
        logger.info(f"{mode_tag} Position closed: {amount} {pair_name}")
        print(f"[Trader] [OK] Position closed successfully")
    else:
        logger.error(f"{mode_tag} Failed to close position for {pair_name}")
        print(f"[Trader] [FAIL] Could not close position")

    return trade


# ---------------------------------------------------------------------------
# TEST: python trader.py
# ---------------------------------------------------------------------------
if __name__ == "__main__":
    setup_logger()

    print("=" * 60)
    print("  CryptoMind AI — Trader Module Test")
    print("=" * 60)
    print("  Mode: PAPER TRADING (no real money used)")
    print("=" * 60)

    TEST_PAIR   = "XXBTZUSD"
    TEST_AMOUNT = 0.001  # ~$66 at $66k BTC

    # --- Step 1: Paper BUY ---
    print("\n[Step 1] Paper BUY 0.001 BTC...")
    buy = execute_trade("BUY", TEST_PAIR, TEST_AMOUNT, mode="paper")
    if buy:
        price_display = f"${buy['price']:,.2f}" if buy["price"] else "N/A"
        print(f"  Success : {buy['success']}")
        print(f"  Price   : {price_display}")
        print(f"  Order ID: {buy['order_id'] or 'N/A'}")
        print(f"  Time    : {buy['timestamp']}")
        if not buy["success"]:
            print(f"  Error   : {buy['error']}")

    # --- Step 2: Portfolio status after BUY ---
    print("\n[Step 2] Portfolio status after BUY...")
    status_after_buy = get_portfolio_status(mode="paper")
    print(f"  Fetch success  : {status_after_buy['success']}")
    print(f"  Open positions : {len(status_after_buy['positions'])}")

    # Small pause between trades
    time.sleep(1)

    # --- Step 3: Paper SELL (close the position) ---
    print("\n[Step 3] Paper SELL 0.001 BTC (close position)...")
    sell = execute_trade("SELL", TEST_PAIR, TEST_AMOUNT, mode="paper")
    if sell:
        price_display = f"${sell['price']:,.2f}" if sell["price"] else "N/A"
        print(f"  Success : {sell['success']}")
        print(f"  Price   : {price_display}")
        print(f"  Order ID: {sell['order_id'] or 'N/A'}")
        if not sell["success"]:
            print(f"  Error   : {sell['error']}")

    # --- Step 4: Final portfolio status ---
    print("\n[Step 4] Final portfolio status...")
    final_status = get_portfolio_status(mode="paper")
    print(f"  Fetch success  : {final_status['success']}")
    print(f"  Open positions : {len(final_status['positions'])}")

    print("\n" + "=" * 60)
    print("  Trader Module Test Complete!")
    print(f"  Trade history saved to: {TRADES_FILE}")
    print("=" * 60)
