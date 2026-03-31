"""
CryptoMind AI - Technical Indicators Module
Calculates RSI, SMA, EMA, MACD, Bollinger Bands from OHLC data.
Uses the 'ta' library — same indicators as NSE/BSE analysis.
"""

import pandas as pd
import ta
from logger import get_logger


def calculate_indicators(df):
    """
    Calculate all technical indicators from OHLC candle data.
    
    Args:
        df: Pandas DataFrame with columns: timestamp, open, high, low, close, volume
            Needs at least 50 rows for all indicators to work properly.
    
    Returns:
        Dictionary with all indicator values, or None if error.
    """
    logger = get_logger()
    
    if df is None or len(df) < 50:
        logger.warning(f"Not enough data for indicators (got {len(df) if df is not None else 0} candles, need 50+)")
        return None
    
    try:
        close = df["close"]
        high = df["high"]
        low = df["low"]
        volume = df["volume"]
        current_price = close.iloc[-1]
        
        # === RSI (Relative Strength Index) — 14 period ===
        # Same as you use for NSE stocks
        # Below 30 = oversold (potential buy), Above 70 = overbought (potential sell)
        rsi = ta.momentum.RSIIndicator(close, window=14)
        rsi_value = round(rsi.rsi().iloc[-1], 2)
        
        # === SMA (Simple Moving Average) — 20 and 50 period ===
        # Price above both SMAs = bullish, below both = bearish
        sma_20 = round(ta.trend.SMAIndicator(close, window=20).sma_indicator().iloc[-1], 2)
        sma_50 = round(ta.trend.SMAIndicator(close, window=50).sma_indicator().iloc[-1], 2)
        
        # === EMA (Exponential Moving Average) — 12 and 26 period ===
        # Faster than SMA, reacts quicker to price changes
        ema_12 = round(ta.trend.EMAIndicator(close, window=12).ema_indicator().iloc[-1], 2)
        ema_26 = round(ta.trend.EMAIndicator(close, window=26).ema_indicator().iloc[-1], 2)
        
        # === MACD (Moving Average Convergence Divergence) ===
        # MACD above signal line = bullish, below = bearish
        macd_indicator = ta.trend.MACD(close, window_slow=26, window_fast=12, window_sign=9)
        macd_value = round(macd_indicator.macd().iloc[-1], 2)
        macd_signal = round(macd_indicator.macd_signal().iloc[-1], 2)
        macd_histogram = round(macd_indicator.macd_diff().iloc[-1], 2)
        
        # === Bollinger Bands — 20 period, 2 standard deviations ===
        # Price near upper band = overbought, near lower band = oversold
        bollinger = ta.volatility.BollingerBands(close, window=20, window_dev=2)
        bb_upper = round(bollinger.bollinger_hband().iloc[-1], 2)
        bb_middle = round(bollinger.bollinger_mavg().iloc[-1], 2)
        bb_lower = round(bollinger.bollinger_lband().iloc[-1], 2)
        
        # === Volume Analysis ===
        # Compare current volume to 20-period average
        avg_volume = volume.rolling(window=20).mean().iloc[-1]
        current_volume = volume.iloc[-1]
        volume_trend = "above_average" if current_volume > avg_volume else "below_average"
        volume_ratio = round(current_volume / avg_volume, 2) if avg_volume > 0 else 0
        
        # === Price Position ===
        # Where is price relative to moving averages?
        if current_price > sma_20 and current_price > sma_50:
            price_vs_sma = "above_both"
        elif current_price < sma_20 and current_price < sma_50:
            price_vs_sma = "below_both"
        else:
            price_vs_sma = "between"
        
        # === Overall Trend ===
        # Simple trend determination based on multiple signals
        bullish_signals = 0
        bearish_signals = 0
        
        if rsi_value > 50: bullish_signals += 1
        else: bearish_signals += 1
        
        if current_price > sma_20: bullish_signals += 1
        else: bearish_signals += 1
        
        if current_price > sma_50: bullish_signals += 1
        else: bearish_signals += 1
        
        if macd_value > macd_signal: bullish_signals += 1
        else: bearish_signals += 1
        
        if ema_12 > ema_26: bullish_signals += 1
        else: bearish_signals += 1
        
        if bullish_signals >= 4:
            trend = "bullish"
        elif bearish_signals >= 4:
            trend = "bearish"
        else:
            trend = "neutral"
        
        # === Build result dictionary ===
        result = {
            "current_price": current_price,
            "rsi": rsi_value,
            "sma_20": sma_20,
            "sma_50": sma_50,
            "ema_12": ema_12,
            "ema_26": ema_26,
            "macd": macd_value,
            "macd_signal": macd_signal,
            "macd_histogram": macd_histogram,
            "bollinger_upper": bb_upper,
            "bollinger_middle": bb_middle,
            "bollinger_lower": bb_lower,
            "volume_trend": volume_trend,
            "volume_ratio": volume_ratio,
            "price_vs_sma": price_vs_sma,
            "bullish_signals": bullish_signals,
            "bearish_signals": bearish_signals,
            "trend": trend
        }
        
        logger.info(f"Indicators calculated: RSI={rsi_value}, MACD={macd_value}, Trend={trend}")
        return result
        
    except Exception as e:
        logger.error(f"Error calculating indicators: {e}")
        return None


def print_indicators(indicators, pair_name=""):
    """Print a formatted summary of all indicators."""
    if indicators is None:
        print("  No indicator data available.")
        return
    
    title = f"TECHNICAL ANALYSIS — {pair_name}" if pair_name else "TECHNICAL ANALYSIS"
    
    print("\n" + "=" * 55)
    print(f"  {title}")
    print("=" * 55)
    print(f"  Current Price : ${indicators['current_price']:>12,.2f}")
    print("-" * 55)
    print(f"  RSI (14)      : {indicators['rsi']:>8.2f}  ", end="")
    if indicators['rsi'] > 70:
        print("[OVERBOUGHT]")
    elif indicators['rsi'] < 30:
        print("[OVERSOLD]")
    else:
        print("[NEUTRAL]")
    print(f"  SMA (20)      : ${indicators['sma_20']:>12,.2f}")
    print(f"  SMA (50)      : ${indicators['sma_50']:>12,.2f}")
    print(f"  EMA (12)      : ${indicators['ema_12']:>12,.2f}")
    print(f"  EMA (26)      : ${indicators['ema_26']:>12,.2f}")
    print("-" * 55)
    print(f"  MACD          : {indicators['macd']:>12,.2f}")
    print(f"  MACD Signal   : {indicators['macd_signal']:>12,.2f}")
    print(f"  MACD Histogram: {indicators['macd_histogram']:>12,.2f}")
    print("-" * 55)
    print(f"  Bollinger Upper: ${indicators['bollinger_upper']:>11,.2f}")
    print(f"  Bollinger Mid  : ${indicators['bollinger_middle']:>11,.2f}")
    print(f"  Bollinger Lower: ${indicators['bollinger_lower']:>11,.2f}")
    print("-" * 55)
    print(f"  Volume Trend  : {indicators['volume_trend']} (x{indicators['volume_ratio']})")
    print(f"  Price vs SMA  : {indicators['price_vs_sma']}")
    print(f"  Signals       : {indicators['bullish_signals']} bullish / {indicators['bearish_signals']} bearish")
    print(f"  Overall Trend : {indicators['trend'].upper()}")
    print("=" * 55 + "\n")


# === Test this module ===
if __name__ == "__main__":
    from logger import setup_logger
    from market_data import get_ohlc
    
    setup_logger()
    
    print("Testing Technical Indicators Module...")
    print("-" * 40)
    
    # Fetch OHLC data for BTC
    print("\nFetching BTC/USD candle data...")
    df = get_ohlc("XXBTZUSD", interval=60)
    
    if df is not None:
        print(f"Got {len(df)} candles")
        
        # Calculate indicators
        print("\nCalculating indicators...")
        indicators = calculate_indicators(df)
        
        # Print formatted results
        print_indicators(indicators, "BTC/USD")
    else:
        print("Failed to fetch candle data. Check Kraken CLI.")
    
    print("\nIndicators Module test complete!")
