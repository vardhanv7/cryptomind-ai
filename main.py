"""
CryptoMind AI — Autonomous AI-Powered Crypto Trading Agent
Built for lablab.ai AI Trading Agents Hackathon (March 30 – April 12, 2026)

This is the main entry point. Run this to start the trading agent.
The full trading loop will be built in Phase 4 (Day 8).
"""

from config import print_config
from logger import setup_logger, get_logger


def main():
    """Main entry point for CryptoMind AI."""
    
    # Set up logging
    logger = setup_logger()
    
    print("\n")
    print("╔══════════════════════════════════════════╗")
    print("║       CryptoMind AI Trading Agent        ║")
    print("║   lablab.ai AI Trading Agents Hackathon  ║")
    print("╚══════════════════════════════════════════╝")
    print()
    
    # Show current config
    print_config()
    
    logger.info("CryptoMind AI started")
    
    # Quick test: fetch BTC price
    print("\nQuick Test — Fetching live BTC price...")
    from market_data import get_ticker
    btc = get_ticker("XXBTZUSD")
    
    if btc:
        print(f"  BTC/USD: ${btc['last']:,.2f} ({btc['change_24h_pct']:+.2f}%)")
        print("  Kraken CLI connection: OK")
    else:
        print("  ERROR: Could not fetch BTC price. Check Kraken CLI.")
    
    # TODO: Full trading loop will be added in Phase 4
    print("\n  Trading loop not yet implemented (Phase 4, Day 8)")
    print("  For now, test individual modules:")
    print("    python market_data.py   — Test market data fetching")
    print("    python indicators.py    — Test technical indicators")
    print("    python ai_brain.py      — Test AI decisions (Phase 3)")
    
    logger.info("CryptoMind AI stopped")


if __name__ == "__main__":
    main()
