"""
ai_brain.py — Groq AI Integration for CryptoMind AI
=====================================================
This module sends technical indicator data to Groq's LLaMA 3.3 70B model
and gets back intelligent BUY / SELL / HOLD trading decisions.
 
Think of it like this:
- market_data.py = your eyes (sees prices)
- indicators.py = your calculator (computes RSI, MACD, etc.)
- ai_brain.py = your BRAIN (makes the trading decision)
 
Uses Groq API free tier: 30 requests/minute, model: llama-3.3-70b-versatile
"""
 
import os
import json
import time
import requests
from dotenv import load_dotenv
 
# Load API key from .env file
load_dotenv()
GROQ_API_KEY = os.getenv("GROQ_API_KEY")
 
# Groq API settings
GROQ_API_URL = "https://api.groq.com/openai/v1/chat/completions"
GROQ_MODEL = "llama-3.3-70b-versatile"
 
# Rate limit tracking (Groq free tier = 30 requests/min)
last_request_time = 0
MIN_REQUEST_GAP = 2  # Wait at least 2 seconds between requests (safe limit)
 
 
def get_trade_signal(indicators, recent_prices, current_price, pair="BTCUSD", holding=False):
    """
    Send indicator data to Groq AI and get a trading decision.
    
    This is the MAIN function of this module. It:
    1. Takes your indicators (RSI, MACD, etc.) from indicators.py
    2. Takes recent price history (last few candles)
    3. Builds a prompt explaining the market situation to the AI
    4. Sends it to Groq's LLaMA model
    5. Gets back: BUY, SELL, or HOLD with confidence and reasoning
    
    Parameters:
    -----------
    indicators : dict
        Output from indicators.analyze() — contains RSI, SMA, MACD, etc.
    recent_prices : list
        List of recent closing prices (last 10-20 candles)
    current_price : float
        The current/latest price of the asset
    pair : str
        Trading pair name like "BTCUSD", "ETHUSD", "SOLUSD"
    
    Returns:
    --------
    dict with keys:
        action: "BUY" or "SELL" or "HOLD"
        confidence: 0.0 to 1.0
        reason: brief explanation
        suggested_size: "small" or "medium" or "large"
        stop_loss_pct: suggested stop loss percentage
        take_profit_pct: suggested take profit percentage
    
    Returns None if API call fails.
    """
    global last_request_time
    
    # --- Step 1: Check API key ---
    if not GROQ_API_KEY:
        print("[AI Brain] ERROR: GROQ_API_KEY not found in .env file!")
        print("[AI Brain] Add this line to your .env file: GROQ_API_KEY=your_key_here")
        return None
    
    # --- Step 2: Rate limiting (don't exceed 30 req/min) ---
    current_time = time.time()
    time_since_last = current_time - last_request_time
    if time_since_last < MIN_REQUEST_GAP:
        wait_time = MIN_REQUEST_GAP - time_since_last
        print(f"[AI Brain] Rate limit: waiting {wait_time:.1f}s...")
        time.sleep(wait_time)
    
    # --- Step 3: Calculate price change for context ---
    if len(recent_prices) >= 2:
        price_change_24h = ((current_price - recent_prices[0]) / recent_prices[0]) * 100
    else:
        price_change_24h = 0.0

    # --- Step 3b: Detect market regime ---
    # [CHANGE] Four-state regime detection feeds directly into the prompt so the
    # AI has an explicit, pre-computed context rather than inferring it itself.
    rsi          = indicators.get('rsi', 50) or 50
    bb_upper     = indicators.get('bollinger_upper') or 0
    bb_lower     = indicators.get('bollinger_lower') or 0
    bb_width     = bb_upper - bb_lower if (bb_upper and bb_lower) else 0

    # How far is the current price from each band, expressed as % of band width?
    # A value < 15 means the price is hugging that band.
    pct_from_lower = ((current_price - bb_lower) / bb_width * 100) if bb_width > 0 else 50
    pct_from_upper = ((bb_upper - current_price) / bb_width * 100) if bb_width > 0 else 50

    if rsi < 30:
        market_regime = "OVERSOLD — RSI below 30, high-probability bounce BUY zone"
        regime_bias   = "BUY"
    elif rsi > 70:
        market_regime = "OVERBOUGHT — RSI above 70, high-probability SELL/fade zone"
        regime_bias   = "SELL"
    elif pct_from_lower < 15:
        market_regime = "NEAR LOWER BOLLINGER BAND — price at support, potential BUY"
        regime_bias   = "BUY"
    elif pct_from_upper < 15:
        market_regime = "NEAR UPPER BOLLINGER BAND — price at resistance, potential SELL"
        regime_bias   = "SELL"
    else:
        market_regime = "NEUTRAL — no extreme readings, look for momentum signals"
        regime_bias   = "NEUTRAL"

    # --- Step 4: Build the AI prompt ---
    # Position status drives which actions are valid.
    if holding:
        position_status = f"HOLDING {pair} — position is open"
        valid_actions   = "SELL or HOLD  (BUY is NOT valid — already holding)"
    else:
        position_status = f"NOT HOLDING {pair} — no open position"
        valid_actions   = "BUY or HOLD  (SELL is NOT valid — nothing to sell)"

    prompt = f"""You are a short-term swing trader, not a long-term investor. Be decisive.
Analyze the following data for {pair} and make a clear BUY, SELL, or HOLD decision.
Your timeframe is 15 minutes to 4 hours — you are hunting short-term opportunities.

=== CURRENT MARKET DATA ===
Asset: {pair}
Current Price: ${current_price:,.2f}
24h Price Change: {price_change_24h:+.2f}%
Recent Prices (oldest to newest): {[round(p, 2) for p in recent_prices[-10:]]}

=== MARKET REGIME ===
Regime: {market_regime}
Regime Bias: {regime_bias}

=== POSITION STATUS ===
Current position: {position_status}
VALID ACTIONS FOR THIS TRADE: {valid_actions}
You MUST only respond with one of the valid actions above. Choosing an invalid action wastes the trade opportunity.

=== TECHNICAL INDICATORS ===
RSI (14-period): {indicators.get('rsi', 'N/A')}
  → Interpretation: {"OVERSOLD — bounce likely" if rsi < 30 else "OVERBOUGHT — pullback likely" if rsi > 70 else "Neutral range"}
SMA (20-period): {indicators.get('sma_20', 'N/A')}
SMA (50-period): {indicators.get('sma_50', 'N/A')}
EMA (12-period): {indicators.get('ema_12', 'N/A')}
EMA (26-period): {indicators.get('ema_26', 'N/A')}
MACD Line: {indicators.get('macd', 'N/A')}
MACD Signal: {indicators.get('macd_signal', 'N/A')}
Bollinger Upper Band: {indicators.get('bollinger_upper', 'N/A')}
Bollinger Lower Band: {indicators.get('bollinger_lower', 'N/A')}
  → Price is {pct_from_lower:.1f}% of band-width above the lower band
  → Price is {pct_from_upper:.1f}% of band-width below the upper band
Volume Trend: {indicators.get('volume_trend', 'N/A')}
Price vs SMA: {indicators.get('price_vs_sma', 'N/A')}
Overall Trend: {indicators.get('trend', 'N/A')}

=== TRADING RULES ===
- You are a SHORT-TERM swing trader targeting 15min–4hr moves.
- Small dips of 1–3% in an otherwise stable asset are BUYING opportunities, not reasons to HOLD.
- Even in a broader bearish market, there are bounce trades to catch — find them.
- Use HOLD ONLY when indicators are genuinely mixed with no clear edge.
- If the market regime is OVERSOLD or near the lower Bollinger Band, lean BUY.
- If the market regime is OVERBOUGHT or near the upper Bollinger Band, lean SELL.
- A bearish overall trend does NOT automatically mean HOLD — look for the bounce.
- Be decisive: a clear signal at 55% confidence is better than a paralysed HOLD.

=== RESPONSE FORMAT ===
Respond with ONLY a valid JSON object, no extra text before or after:
{{
    "action": {valid_actions},
    "confidence": 0.0 to 1.0,
    "reason": "brief 1-2 sentence explanation",
    "suggested_size": "small" or "medium" or "large",
    "stop_loss_pct": number between 1.0 and 5.0,
    "take_profit_pct": number between 2.0 and 10.0
}}"""
 
    # --- Step 5: Call Groq API ---
    try:
        print(f"[AI Brain] Asking Groq AI for {pair} trade decision...")
        
        headers = {
            "Authorization": f"Bearer {GROQ_API_KEY}",
            "Content-Type": "application/json"
        }
        
        payload = {
            "model": GROQ_MODEL,
            "messages": [
                {
                    # [CHANGE] System prompt now establishes the short-term swing
                    # trader persona upfront, before any market data is shown.
                    "role": "system",
                    "content": (
                        "You are an aggressive short-term crypto swing trader. "
                        "Your job is to find and act on short-term price opportunities "
                        "(15 min to 4 hr timeframe). "
                        "HOLD is your last resort — only use it when there is genuinely "
                        "no edge in either direction. "
                        "In bearish markets, you look for bounce trades. "
                        "In bullish markets, you look for continuation entries. "
                        "Respond ONLY with a valid JSON object. No markdown, no code blocks, no extra text."
                    )
                },
                {
                    "role": "user",
                    "content": prompt
                }
            ],
            "temperature": 0.3,  # Low temperature = more consistent decisions
            "max_tokens": 300    # Keep response short and focused
        }
        
        response = requests.post(GROQ_API_URL, headers=headers, json=payload, timeout=30)
        last_request_time = time.time()  # Update rate limit tracker
        
        # --- Step 6: Check for API errors ---
        if response.status_code != 200:
            print(f"[AI Brain] API Error: Status {response.status_code}")
            print(f"[AI Brain] Response: {response.text}")
            return None
        
        # --- Step 7: Parse the AI's response ---
        result = response.json()
        ai_text = result["choices"][0]["message"]["content"].strip()
        
        # Clean up the response (remove markdown code blocks if AI adds them)
        ai_text = ai_text.replace("```json", "").replace("```", "").strip()
        
        # Parse JSON
        signal = json.loads(ai_text)
        
        # --- Step 8: Validate the response ---
        # Make sure all required fields exist
        required_fields = ["action", "confidence", "reason", "suggested_size", 
                          "stop_loss_pct", "take_profit_pct"]
        for field in required_fields:
            if field not in signal:
                print(f"[AI Brain] WARNING: Missing field '{field}' in AI response")
                return None
        
        # Validate action is one of BUY/SELL/HOLD
        if signal["action"] not in ["BUY", "SELL", "HOLD"]:
            print(f"[AI Brain] WARNING: Invalid action '{signal['action']}'")
            signal["action"] = "HOLD"  # Default to HOLD if invalid
        
        # Validate confidence is between 0 and 1
        signal["confidence"] = max(0.0, min(1.0, float(signal["confidence"])))

        # [CHANGE] Override suggested_size based on confidence bands.
        # This ensures trade sizing is always consistent regardless of what
        # the AI returns, and scales risk up only when conviction is high.
        #   0.50 – 0.60  →  small   (cautious entry)
        #   0.60 – 0.75  →  medium  (moderate conviction)
        #   0.75 +       →  large   (high conviction)
        conf = signal["confidence"]
        if conf >= 0.75:
            signal["suggested_size"] = "large"
        elif conf >= 0.60:
            signal["suggested_size"] = "medium"
        else:
            signal["suggested_size"] = "small"

        # Validate stop_loss and take_profit are numbers
        signal["stop_loss_pct"] = float(signal.get("stop_loss_pct", 3.0))
        signal["take_profit_pct"] = float(signal.get("take_profit_pct", 5.0))
        
        # --- Step 9: Print the decision ---
        print(f"\n[AI Brain] === TRADE SIGNAL for {pair} ===")
        print(f"  Action:      {signal['action']}")
        print(f"  Confidence:  {signal['confidence']:.0%}")
        print(f"  Reason:      {signal['reason']}")
        print(f"  Size:        {signal['suggested_size']}")
        print(f"  Stop Loss:   {signal['stop_loss_pct']}%")
        print(f"  Take Profit: {signal['take_profit_pct']}%")
        print(f"  ================================\n")
        
        return signal
        
    except json.JSONDecodeError as e:
        print(f"[AI Brain] ERROR: Could not parse AI response as JSON")
        print(f"[AI Brain] Raw response: {ai_text}")
        print(f"[AI Brain] Error: {e}")
        return None
        
    except requests.exceptions.Timeout:
        print("[AI Brain] ERROR: Groq API request timed out (30s)")
        return None
        
    except requests.exceptions.ConnectionError:
        print("[AI Brain] ERROR: Could not connect to Groq API. Check internet.")
        return None
        
    except Exception as e:
        print(f"[AI Brain] ERROR: Unexpected error: {e}")
        return None
 
 
def should_trade(signal, portfolio_value=10000, open_positions=0, 
                 last_trade_time=0, daily_pnl=0):
    """
    Risk management filter — decides if we SHOULD act on the AI's signal.
    
    Even if the AI says "BUY", this function can say "NO" based on risk rules.
    Think of this as the risk manager sitting next to the trader.
    
    Similar to how SEBI has circuit breakers on NSE/BSE — we have our own!
    
    Parameters:
    -----------
    signal : dict
        The trade signal from get_trade_signal()
    portfolio_value : float
        Total portfolio value in USD
    open_positions : int
        Number of currently open positions
    last_trade_time : float
        Unix timestamp of last trade (from time.time())
    daily_pnl : float
        Today's profit/loss in USD
    
    Returns:
    --------
    tuple: (should_trade: bool, reason: str)
    """
    if signal is None:
        return False, "No signal received from AI"
    
    action = signal.get("action", "HOLD")
    confidence = signal.get("confidence", 0)
    
    # Rule 1: If AI says HOLD, don't trade
    if action == "HOLD":
        return False, "AI recommends HOLD — no trade needed"
    
    # Rule 2: Minimum confidence threshold
    if confidence < 0.5:
        return False, f"AI confidence too low ({confidence:.0%}). Need at least 50%"
    
    # Rule 3: Maximum 3 open positions at any time
    if action == "BUY" and open_positions >= 3:
        return False, f"Already have {open_positions} open positions (max 3)"
    
    # Rule 4: Cooldown — wait at least 10 minutes between trades
    # [CHANGE] Reduced from 30 min → 10 min to allow catching short-term swings.
    current_time = time.time()
    minutes_since_last = (current_time - last_trade_time) / 60
    if last_trade_time > 0 and minutes_since_last < 10:
        return False, f"Cooldown active: only {minutes_since_last:.0f}min since last trade (need 10min)"
    
    # Rule 5: Daily loss limit — stop if lost more than 10% today
    daily_loss_limit = portfolio_value * 0.10  # 10% of portfolio
    if daily_pnl < -daily_loss_limit:
        return False, f"Daily loss limit hit: ${daily_pnl:.2f} (limit: -${daily_loss_limit:.2f})"
    
    # Rule 6: Don't risk more than 5% of portfolio on a single trade
    max_trade_value = portfolio_value * 0.05
    
    # All checks passed!
    return True, f"Trade approved! Action: {action}, Confidence: {confidence:.0%}, Max size: ${max_trade_value:.2f}"
 
 
# ============================================================
# TEST: Run this file directly to test the AI Brain
# Usage: python -m ai_brain
# ============================================================
if __name__ == "__main__":
    print("=" * 60)
    print("  CryptoMind AI — AI Brain Test")
    print("=" * 60)
    
    # Check if API key is set
    if not GROQ_API_KEY:
        print("\n[ERROR] GROQ_API_KEY not found!")
        print("Make sure your .env file has: GROQ_API_KEY=your_key_here")
        exit(1)
    
    print(f"\n[OK] Groq API key found: {GROQ_API_KEY[:8]}...{GROQ_API_KEY[-4:]}")
    print(f"[OK] Model: {GROQ_MODEL}")
    
    # Try importing market_data and indicators
    try:
        from market_data import get_ticker, get_ohlc
        from indicators import calculate_indicators

        print("\n[Step 1] Fetching live BTC price...")
        ticker = get_ticker("XXBTZUSD")
        if ticker is None:
            print("[ERROR] Could not fetch price. Check Kraken CLI.")
            exit(1)
        current_price = ticker["last"]
        print(f"[OK] BTC Price: ${current_price:,.2f}")

        print("\n[Step 2] Fetching OHLC candle data...")
        df = get_ohlc("XXBTZUSD", interval=60)
        if df is None or df.empty:
            print("[ERROR] Could not fetch OHLC data.")
            exit(1)
        print(f"[OK] Got {len(df)} candles")

        print("\n[Step 3] Calculating technical indicators...")
        indicators = calculate_indicators(df)
        print(f"[OK] RSI: {indicators.get('rsi', 'N/A')}")
        print(f"[OK] Trend: {indicators.get('trend', 'N/A')}")
        
        # Get recent closing prices for context
        recent_prices = df["close"].tolist()
        
        print("\n[Step 4] Asking Groq AI for trade decision...")
        signal = get_trade_signal(indicators, recent_prices, current_price, "BTCUSD")
        
        if signal:
            print("\n[Step 5] Checking risk management rules...")
            approved, reason = should_trade(signal)
            print(f"  Trade Approved: {approved}")
            print(f"  Reason: {reason}")
        else:
            print("\n[FAILED] Could not get signal from AI")
    
    except ImportError as e:
        print(f"\n[WARNING] Could not import market_data/indicators: {e}")
        print("[INFO] Running standalone test with sample data instead...\n")
        
        # Use sample data for testing if other modules aren't available
        sample_indicators = {
            "rsi": 62.5,
            "sma_20": 84500,
            "sma_50": 82000,
            "ema_12": 84800,
            "ema_26": 83500,
            "macd": 1300,
            "macd_signal": 900,
            "bollinger_upper": 87000,
            "bollinger_lower": 82000,
            "volume_trend": "above_average",
            "price_vs_sma": "above_both",
            "trend": "bullish"
        }
        
        sample_prices = [82000, 82500, 83000, 83200, 83800, 84000, 84200, 84500, 84300, 84600]
        sample_current_price = 84600
        
        print("[Step 1] Using sample BTC data for testing...")
        print(f"  Sample Price: ${sample_current_price:,.2f}")
        print(f"  Sample RSI: {sample_indicators['rsi']}")
        print(f"  Sample Trend: {sample_indicators['trend']}")
        
        print("\n[Step 2] Asking Groq AI for trade decision...")
        signal = get_trade_signal(sample_indicators, sample_prices, 
                                  sample_current_price, "BTCUSD")
        
        if signal:
            print("\n[Step 3] Checking risk management rules...")
            approved, reason = should_trade(signal)
            print(f"  Trade Approved: {approved}")
            print(f"  Reason: {reason}")
        else:
            print("\n[FAILED] Could not get signal from AI")
    
    print("\n" + "=" * 60)
    print("  AI Brain Test Complete!")
    print("=" * 60)