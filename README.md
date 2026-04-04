# CryptoMind AI

**Autonomous AI-Powered Crypto Trading Agent**

[![MIT License](https://img.shields.io/badge/license-MIT-blue.svg)](LICENSE)
[![Python](https://img.shields.io/badge/python-3.10%2B-blue.svg)](https://www.python.org/)
[![Groq](https://img.shields.io/badge/AI-Groq%20LLaMA%203.3%2070B-orange.svg)](https://groq.com/)
[![Hackathon](https://img.shields.io/badge/lablab.ai-AI%20Trading%20Agents%202026-green.svg)](https://lablab.ai/)

Built for the **lablab.ai AI Trading Agents Hackathon** (March 30 – April 12, 2026).

CryptoMind AI combines live technical analysis with a Groq-powered LLaMA 3.3 70B brain to make autonomous BUY / SELL / HOLD decisions across BTC, ETH, and SOL — with full risk management and a real-time terminal dashboard.

---

## Results — 48-Hour Paper Trading Test

| Metric | Result |
|---|---|
| Total trade signals | 50 (25 BUY / 25 SELL) |
| Closed trades | 24 |
| Win rate | **58.3%** (14 wins / 10 losses) |
| Realized PnL | **+$0.6166** |
| Operation | Fully autonomous, zero crashes |
| Uptime | 48 hours continuous |

---

## How It Works

Each 15-minute cycle:

1. **Market data** — fetch live price + 720 OHLC candles via Kraken CLI
2. **Indicators** — calculate RSI, MACD, Bollinger Bands, SMA/EMA, volume trend
3. **AI decision** — send indicators + market regime to Groq LLaMA 3.3 70B; receive BUY / SELL / HOLD with confidence score and suggested stop-loss / take-profit
4. **Risk check** — enforce position limits, confidence threshold (55%), 10-minute cooldown
5. **Execute** — place paper (or live) order via Kraken CLI
6. **Portfolio update** — record trade, compute unrealized PnL, sweep for stop-loss / take-profit triggers

---

## Features

- **Swing trader AI persona** — Groq LLaMA 3.3 70B with an active, decisive system prompt; forced re-evaluation after 3 consecutive HOLDs
- **Market regime detection** — four-state classifier (oversold / overbought / near lower band / near upper band) fed directly into the AI prompt
- **Technical indicators** — RSI(14), SMA(20/50), EMA(12/26), MACD, Bollinger Bands(20,2), volume trend
- **Confidence-based position sizing** — small / medium / large mapped to AI confidence bands
- **Risk management** — per-trade stop-loss, take-profit, max 3 open positions, 10% daily loss limit
- **State reconciliation** — startup reconcile against Kraken paper state catches any desync between sessions
- **Real-time dashboard** — auto-refreshing terminal UI showing live prices, open positions, and PnL
- **Paper and live trading modes** — `--mode paper` (default, safe) or `--mode live`
- **Graceful shutdown** — Ctrl+C prints a full performance report before exiting

---

## Tech Stack

| Layer | Technology |
|---|---|
| Language | Python 3.10+ |
| AI / LLM | Groq API — LLaMA 3.3 70B (`llama-3.3-70b-versatile`) |
| Fallback model | LLaMA 3.1 8B (`llama-3.1-8b-instant`) on 429 rate-limit |
| Exchange | Kraken CLI (paper + live) |
| Indicators | `ta` library + pandas |
| Dev tooling | Claude Code |
| Trading pairs | BTC/USD · ETH/USD · SOL/USD |

---

## Architecture

```
cryptomind-ai/
├── main.py          # Orchestration loop — runs every 15 min, never crashes
├── ai_brain.py      # Groq LLaMA integration — BUY / SELL / HOLD decisions
├── trader.py        # Kraken CLI execution — paper and live trade placement
├── portfolio.py     # Trade recording, PnL tracking, stop-loss sweep, reconciliation
├── market_data.py   # Live ticker + OHLC candle fetching via Kraken CLI
├── indicators.py    # RSI, MACD, Bollinger Bands, SMA, EMA calculation
├── dashboard.py     # Real-time terminal dashboard (auto-refresh)
├── config.py        # All settings — pairs, risk params, API config
├── logger.py        # Structured file + console logging
└── requirements.txt
```

---

## Quick Start

### 1. Prerequisites

- Python 3.10+
- [Kraken CLI](https://github.com/kraken-hpc-io/kraken) installed and in PATH
- [Groq API key](https://console.groq.com/) (free tier — 30 req/min)

### 2. Install

```bash
git clone https://github.com/vardhanv7/cryptomind-ai.git
cd cryptomind-ai
pip install -r requirements.txt
```

### 3. Configure

Create a `.env` file in the project root:

```env
GROQ_API_KEY=your_groq_api_key_here
```

### 4. Run

```bash
# Paper trading (safe default)
python main.py

# Specify cycle count and interval for testing
python main.py --mode paper --cycles 5 --interval 60

# Live trading (real money — use with caution)
python main.py --mode live
```

### CLI options

| Flag | Default | Description |
|---|---|---|
| `--mode` | `paper` | `paper` or `live` |
| `--cycles` | unlimited | Stop after N cycles |
| `--interval` | `900` | Seconds between cycles |

---

## Risk Management

| Rule | Value |
|---|---|
| Stop-loss | 2.5% per position |
| Take-profit | 4.0% per position |
| Max open positions | 3 |
| Min AI confidence | 55% |
| Daily loss limit | 10% of portfolio |
| Trade cooldown (BUY) | 10 minutes |
| SELL cooldown | None — exits are always immediate |

---

## License

MIT — see [LICENSE](LICENSE) for details.
