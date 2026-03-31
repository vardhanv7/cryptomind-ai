"""
CryptoMind AI - Market Data Module
Fetches live price data and OHLC candles using Kraken CLI.
Uses subprocess to call Kraken CLI commands and parse JSON output.
"""

import subprocess
import json
import pandas as pd
from datetime import datetime
from logger import get_logger


def run_kraken_command(command):
    """
    Run a Kraken CLI command and return the output.
    
    Args:
        command: List of command parts, e.g. ["kraken", "ticker", "XXBTZUSD", "-o", "json"]
    
    Returns:
        Parsed JSON output from the command, or None if error.
    """
    logger = get_logger()
    
    try:
        # Run the command and capture output
        result = subprocess.run(
            command,
            capture_output=True,  # Capture stdout and stderr
            text=True,            # Return as string, not bytes
            timeout=30            # Timeout after 30 seconds
        )
        
        # Check if command was successful
        if result.returncode != 0:
            logger.error(f"Kraken CLI error: {result.stderr.strip()}")
            return None
        
        # Parse JSON output
        output = result.stdout.strip()
        if output:
            return json.loads(output)
        else:
            logger.warning("Kraken CLI returned empty output")
            return None
            
    except subprocess.TimeoutExpired:
        logger.error(f"Kraken CLI command timed out: {' '.join(command)}")
        return None
    except json.JSONDecodeError as e:
        logger.error(f"Failed to parse Kraken CLI JSON output: {e}")
        return None
    except FileNotFoundError:
        logger.error("Kraken CLI not found! Make sure it's installed and in PATH.")
        return None
    except Exception as e:
        logger.error(f"Unexpected error running Kraken CLI: {e}")
        return None


def get_ticker(pair):
    """
    Get the current price for a trading pair.
    
    Args:
        pair: Kraken pair name, e.g. "XXBTZUSD"
    
    Returns:
        Dictionary with price info, or None if error.
        Example: {"ask": 67500.0, "bid": 67499.0, "last": 67500.0}
    """
    logger = get_logger()
    logger.debug(f"Fetching ticker for {pair}")
    
    data = run_kraken_command(["kraken", "ticker", pair, "-o", "json"])
    
    if data is None or pair not in data:
        logger.error(f"Failed to get ticker for {pair}")
        return None
    
    ticker = data[pair]
    
    # Parse the ticker data
    # Kraken ticker format:
    # a = ask [price, whole_lot_volume, lot_volume]
    # b = bid [price, whole_lot_volume, lot_volume]
    # c = last trade [price, lot_volume]
    # h = high [today, last_24h]
    # l = low [today, last_24h]
    # v = volume [today, last_24h]
    # o = opening price today
    
    result = {
        "pair": pair,
        "ask": float(ticker["a"][0]),       # Current ask price
        "bid": float(ticker["b"][0]),       # Current bid price
        "last": float(ticker["c"][0]),      # Last trade price
        "high_24h": float(ticker["h"][1]),  # 24h high
        "low_24h": float(ticker["l"][1]),   # 24h low
        "volume_24h": float(ticker["v"][1]),# 24h volume
        "open_today": float(ticker["o"]),   # Opening price today
        "timestamp": datetime.now().isoformat()
    }
    
    # Calculate 24h change percentage
    if result["open_today"] > 0:
        result["change_24h_pct"] = round(
            ((result["last"] - result["open_today"]) / result["open_today"]) * 100, 2
        )
    else:
        result["change_24h_pct"] = 0.0
    
    logger.info(f"{pair}: ${result['last']:,.2f} ({result['change_24h_pct']:+.2f}%)")
    return result


def get_ohlc(pair, interval=60):
    """
    Get OHLC (Open, High, Low, Close) candle data for a trading pair.
    
    Args:
        pair: Kraken pair name, e.g. "XXBTZUSD"
        interval: Candle interval in minutes (1, 5, 15, 30, 60, 240, 1440, 10080)
    
    Returns:
        Pandas DataFrame with columns: timestamp, open, high, low, close, volume
        Returns None if error.
    """
    logger = get_logger()
    logger.debug(f"Fetching OHLC data for {pair} (interval: {interval}min)")
    
    data = run_kraken_command([
        "kraken", "ohlc", pair,
        "--interval", str(interval),
        "-o", "json"
    ])
    
    if data is None:
        logger.error(f"Failed to get OHLC data for {pair}")
        return None
    
    # Find the pair data in the response
    # Kraken might return the pair with a different key
    pair_data = None
    for key in data:
        if key != "last":  # Skip the "last" timestamp field
            pair_data = data[key]
            break
    
    if pair_data is None or len(pair_data) == 0:
        logger.error(f"No OHLC data found for {pair}")
        return None
    
    # Convert to DataFrame
    # Kraken OHLC format: [time, open, high, low, close, vwap, volume, count]
    rows = []
    for candle in pair_data:
        rows.append({
            "timestamp": datetime.fromtimestamp(candle[0]),
            "open": float(candle[1]),
            "high": float(candle[2]),
            "low": float(candle[3]),
            "close": float(candle[4]),
            "vwap": float(candle[5]),
            "volume": float(candle[6]),
            "count": int(candle[7])
        })
    
    df = pd.DataFrame(rows)
    df = df.sort_values("timestamp").reset_index(drop=True)
    
    logger.info(f"Got {len(df)} candles for {pair} ({interval}min interval)")
    return df


def get_all_prices(pairs=None):
    """
    Get current prices for all trading pairs.
    
    Args:
        pairs: List of pair names. If None, uses default pairs from config.
    
    Returns:
        Dictionary mapping pair names to their ticker data.
    """
    from config import TRADING_PAIRS
    
    if pairs is None:
        pairs = TRADING_PAIRS
    
    prices = {}
    for pair in pairs:
        ticker = get_ticker(pair)
        if ticker:
            prices[pair] = ticker
    
    return prices


def print_market_summary(prices):
    """Print a formatted summary of current market prices."""
    print("\n" + "=" * 60)
    print("  MARKET SUMMARY")
    print("=" * 60)
    
    from config import PAIR_NAMES
    
    for pair, data in prices.items():
        name = PAIR_NAMES.get(pair, pair)
        print(f"  {name:10s} | ${data['last']:>12,.2f} | {data['change_24h_pct']:>+6.2f}%")
    
    print("=" * 60)
    print(f"  Updated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 60 + "\n")


# === Test this module ===
if __name__ == "__main__":
    from logger import setup_logger
    setup_logger()
    
    print("Testing Market Data Module...")
    print("-" * 40)
    
    # Test 1: Get ticker for BTC
    print("\n[Test 1] Fetching BTC/USD ticker...")
    btc_ticker = get_ticker("XXBTZUSD")
    if btc_ticker:
        print(f"  BTC Price: ${btc_ticker['last']:,.2f}")
        print(f"  24h High:  ${btc_ticker['high_24h']:,.2f}")
        print(f"  24h Low:   ${btc_ticker['low_24h']:,.2f}")
        print(f"  24h Change: {btc_ticker['change_24h_pct']:+.2f}%")
    
    # Test 2: Get OHLC candles for BTC
    print("\n[Test 2] Fetching BTC/USD OHLC candles (1hr)...")
    df = get_ohlc("XXBTZUSD", interval=60)
    if df is not None:
        print(f"  Got {len(df)} candles")
        print(f"  Latest candle: {df.iloc[-1]['timestamp']}")
        print(f"  Close: ${df.iloc[-1]['close']:,.2f}")
        print(f"  Volume: {df.iloc[-1]['volume']:.4f}")
    
    # Test 3: Get all prices
    print("\n[Test 3] Fetching all trading pairs...")
    prices = get_all_prices()
    if prices:
        print_market_summary(prices)
    
    print("\nMarket Data Module test complete!")
