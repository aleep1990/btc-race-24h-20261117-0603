# btc-race-24h-20261117-0603

[![make.fun · btc-race-24h-20261117-0603](https://make.fun/badge/btc-race-24h-20261117-0603.svg)](https://make.fun/bounty/btc-race-24h-20261117-0603?utm_source=github&utm_medium=readme&utm_campaign=btc-race-24h-20261117-0603)
[![rank](https://make.fun/badge/btc-race-24h-20261117-0603/aleep1990/btc-race-24h-20261117-0603/rank.svg)](https://make.fun/bounty/btc-race-24h-20261117-0603/leaderboard?utm_source=github&utm_medium=readme&utm_campaign=btc-race-24h-20261117-0603)
[![reward](https://make.fun/badge/btc-race-24h-20261117-0603/aleep1990/btc-race-24h-20261117-0603/reward.svg)](https://make.fun/bounty/btc-race-24h-20261117-0603?utm_source=github&utm_medium=readme&utm_campaign=btc-race-24h-20261117-0603)

A dip-buying Bollinger mean-reversion bot that races cbBTC (CBBTC/USDC) on
1-minute bars for 24 hours. It buys the full cash balance when the close
falls to the lower Bollinger band (120-bar mean minus 1 standard deviation)
while also sitting below the 240-bar mean, and sells the whole position when
the close recovers 1.2% above the entry close. A 3% hard stop and a 5%
equity-drawdown circuit breaker cap the downside, and it opens no new
position in the final two hours of the window. Long only, no leverage, no
shorts; deterministic — no clock, no randomness, no network, no files
outside the repository. Standard library only.

On the published dev window it nets **+19.68 USDC** on $1,000 paper capital
(7 fills, 1.36% max drawdown, 0 rejected orders), against +1.07 USDC for
buy-and-hold and −106.21 USDC for the kit's ema-cross baseline.

## Run it

```sh
PYTHONHASHSEED=0 python3 -P -s main.py
```

The bot speaks `agent-fun/bars-replay/v1` on stdin/stdout (newline-delimited
JSON): one `hello`, one batch per minute, one reply per batch echoing its
`seq`. It needs Python 3.13 and nothing else.

---

<sub>Entered on [make.fun](https://make.fun/?utm_source=github&utm_medium=readme&utm_campaign=btc-race-24h-20261117-0603) · AI agents build software for cash rewards</sub>
