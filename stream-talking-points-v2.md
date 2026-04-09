OPENING



"Hey everyone, I'm Vardhan. I'm from Hyderabad, India.

I'm a B.Tech Electronics student. And I'm building solo for the lablab.ai AI Trading Agents Hackathon.

\[pause]

My project is called CryptoMind AI. It's an AI trading bot for crypto. It runs on its own, with no human help."





WHAT IT DOES



"So here's how it works.

Every 15 minutes, the bot wakes up. It checks live prices for Bitcoin, Ethereum, and Solana. It gets this data from Kraken.

Then it runs some simple math on the prices. Things like RSI, moving averages, MACD. If you know stock trading, you know these.

\[pause]

After that, it sends everything to an AI model from Groq. The AI looks at the data and says: buy, sell, or hold. It also gives a confidence score.

If the confidence is high enough, the bot places a trade. It also sets a stop-loss to protect the money."





TECH STACK



"The tech is very simple. Python for the main code. Kraken CLI for all the trading. Groq's free AI for the brain. And a small dashboard to watch it live.

Everything is open source on my GitHub. And I built the whole thing with Claude Code."





PECULIAR MOMENTS (this is your gold — slow down here)



"Now, the fun part. Three things I didn't expect.

\[pause]

First. Kraken does not work in India. I could not even make an account.

But the Kraken CLI has a paper trading mode. It works without any account. So I built the whole bot using paper trading and live market data. No real account needed.

\[pause]

Second. The Groq free tier has limits. The big AI model hits the limit fast. So the bot falls back to a smaller model. The smaller one is more aggressive. I had to design the bot to handle both.

\[pause]

Third. I had a bug. The bot was thinking it held coins that it did not actually have. It took me a full day to find and fix. I wrote a function to check and sync the state every cycle. Now it's solid."





LIVE DEMO



"Okay, let me show you the bot in action.

\[Alt-tab to dashboard — pause 3 seconds]

So this is my dashboard. You can see here — 102 trades so far. Win rate around 50 percent. Three open positions right now, in Bitcoin, Ethereum, and Solana. This updates live.

\[Alt-tab to terminal — pause 3 seconds]

And this is the bot running in the terminal. You can see the last cycle ran a few minutes ago. It fetched prices, asked the AI, and made a decision.

\[Alt-tab to GitHub — pause 3 seconds]

Here's the code on GitHub. It's fully open source, MIT license. Anyone can fork it.

\[Alt-tab to Surge — pause 3 seconds]

And this is my project page on Surge Discovery. Full writeup is here."





CLOSE



"So that's CryptoMind AI.

\[pause]

Final submission is on April 12. You can find everything on my GitHub. My username is vardhanv7.

If you want to talk, find me on X. My handle is Vardhan underscore underscore seven.

Big thanks to lablab.ai and Surge for this hackathon. And thanks everyone for watching."

