"""
CryptoMind AI - Configuration Module
Loads settings from .env file and defines trading parameters.
"""

import os
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

# === API Keys ===
GROQ_API_KEY = os.getenv("GROQ_API_KEY", "")
TRADING_MODE = os.getenv("TRADING_MODE", "paper")  # "paper" or "live"

# === Groq AI Settings ===
GROQ_MODEL = "llama-3.3-70b-versatile"  # Free model on Groq
GROQ_API_URL = "https://api.groq.com/openai/v1/chat/completions"
GROQ_MAX_TOKENS = 500
GROQ_TEMPERATURE = 0.3  # Lower = more consistent decisions

# === Trading Pairs ===
# Kraken uses special pair names:
# BTC/USD = XXBTZUSD, ETH/USD = XETHZUSD, SOL/USD = SOLUSD
TRADING_PAIRS = ["XXBTZUSD", "XETHZUSD", "SOLUSD"]

# Human-readable names for display
PAIR_NAMES = {
    "XXBTZUSD": "BTC/USD",
    "XETHZUSD": "ETH/USD",
    "SOLUSD": "SOL/USD"
}

# === Trading Parameters ===
TRADE_INTERVAL_SECONDS = 900      # 15 minutes between each trading cycle
MAX_TRADE_SIZE_USD = 5.0          # Maximum $5 per trade (conservative)
MAX_TOTAL_INVESTMENT_USD = 20.0   # Never invest more than $20 total
MAX_OPEN_POSITIONS = 3            # Maximum 3 positions at once

# === Risk Management ===
STOP_LOSS_PCT = 3.0       # Close if position drops 3%
TAKE_PROFIT_PCT = 5.0     # Close if position gains 5%
MAX_DAILY_LOSS_PCT = 10.0 # Stop trading if daily loss exceeds 10%
TRADE_COOLDOWN_SECONDS = 1800  # 30 minutes between trades on same pair
MAX_RISK_PER_TRADE_PCT = 5.0   # Never risk more than 5% of portfolio

# === Technical Indicator Settings ===
RSI_PERIOD = 14
SMA_SHORT_PERIOD = 20
SMA_LONG_PERIOD = 50
EMA_SHORT_PERIOD = 12
EMA_LONG_PERIOD = 26
BOLLINGER_PERIOD = 20
BOLLINGER_STD = 2

# === OHLC Candle Settings ===
OHLC_INTERVAL = 60  # 60 minutes (1 hour candles)
OHLC_CANDLE_COUNT = 100  # Number of candles to fetch

# === File Paths ===
TRADES_FILE = "trades_history.json"
LOG_FILE = "logs/cryptomind.log"

# === Display Settings ===
def print_config():
    """Print current configuration for verification."""
    print("=" * 50)
    print("  CryptoMind AI - Configuration")
    print("=" * 50)
    print(f"  Trading Mode  : {TRADING_MODE}")
    print(f"  Groq Model    : {GROQ_MODEL}")
    print(f"  Trading Pairs : {', '.join(PAIR_NAMES.values())}")
    print(f"  Trade Interval: {TRADE_INTERVAL_SECONDS // 60} minutes")
    print(f"  Max Trade Size: ${MAX_TRADE_SIZE_USD}")
    print(f"  Stop Loss     : {STOP_LOSS_PCT}%")
    print(f"  Take Profit   : {TAKE_PROFIT_PCT}%")
    print(f"  Groq API Key  : {'SET' if GROQ_API_KEY else 'NOT SET'}")
    print("=" * 50)


if __name__ == "__main__":
    print_config()
