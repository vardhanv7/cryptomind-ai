SECTION 1 — HOOK + PROBLEM (20 sec)

\[SHOW: Dashboard running, live trades ticking]

"Crypto markets never sleep. They move 24 hours a day, 7 days a week. No human can watch them that long. \[pause] So I built an AI that can. This is CryptoMind AI, an autonomous crypto trading agent for the lablab.ai AI Trading Agents Hackathon."



SECTION 2 — WHAT IT DOES (45 sec)

\[SHOW: Architecture — or just keep dashboard visible]

"CryptoMind AI trades Bitcoin, Ethereum, and Solana on its own. No human clicks. No human decisions. \[pause]

Every 15 minutes, the bot does five things. \[pause] First, it fetches live market data from Kraken. Second, it calculates technical indicators — RSI, moving averages, MACD. The same tools professional traders use. \[pause] Third, it sends everything to an AI model on Groq. The AI reads the data and decides: buy, sell, or hold. Fourth, if the confidence is high enough, the bot places the trade with a stop-loss to protect the money. \[pause] And fifth, it logs everything to a live dashboard you can watch in real time."



SECTION 3 — LIVE DEMO (90 sec)

\[SHOW: Alt-tab through each screen as you narrate]

"Let me show you the bot in action. \[pause]

\[SHOW: Dashboard] This is the live dashboard. Right now you can see 102 trades executed so far. 42 positions closed. Win rate around 50 percent. And three open positions — in Bitcoin, Ethereum, and Solana. All of this updates automatically. \[pause]

\[SHOW: Terminal running bot] This is the bot itself, running in the terminal. You can see the last cycle ran a few minutes ago. It fetched prices, asked the AI, and made a decision. Then it goes to sleep for 15 minutes, and repeats. \[pause]

\[SHOW: GitHub repo] Here is the full source code on GitHub. It's open source under MIT license, as required by the hackathon. Anyone can clone it and run it. \[pause]

\[SHOW: Surge Discovery page] And this is the project page on Surge Discovery, where I documented the full build."



SECTION 4 — TECHNICAL HIGHLIGHTS + CHALLENGES (60 sec)

\[SHOW: Back to dashboard or code]

"Three things made this build interesting. \[pause]

First — and this was the biggest challenge — Kraken does not serve India. I am based in Hyderabad. I could not even create a Kraken account. \[pause] So I built the entire bot around Kraken's paper trading mode and public market data. No account needed. The bot uses real live prices from Kraken, executes trades in paper mode, and tracks everything as if it were real. This proves the full system works. \[pause]

Second, I used Groq's free tier for the AI brain. The free tier has rate limits, so I designed the bot to handle fallback gracefully — when the main model is rate limited, it switches to a smaller model automatically. \[pause]

Third, I hit a subtle bug where the bot's internal state could drift from the actual Kraken paper account. I wrote a reconcile function that syncs the two every cycle. Now it's rock solid."



SECTION 5 — RESULTS + CLOSE (25 sec)

\[SHOW: Dashboard with stats visible]

"The results so far: 102 autonomous trades over 10 days. 42 closed positions. Zero human intervention. A fully working AI trading agent built solo, with open source tools, on a free budget. \[pause]

The code is on GitHub at vardhanv7/cryptomind-ai. The project is live on Surge Discovery. \[pause] Big thanks to lablab.ai, Kraken, and Surge for running this hackathon. I'm Vardhan, and this is CryptoMind AI. Thanks for watching."

