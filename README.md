# btc-race-24h-20261118-1444

[![make.fun · btc-race-24h-20261118-1444](https://make.fun/badge/btc-race-24h-20261118-1444.svg)](https://make.fun/bounty/btc-race-24h-20261118-1444?utm_source=github&utm_medium=readme&utm_campaign=btc-race-24h-20261118-1444)
[![rank](https://make.fun/badge/btc-race-24h-20261118-1444/0xazazul/btc-race-24h-20261118-1444/rank.svg)](https://make.fun/bounty/btc-race-24h-20261118-1444/leaderboard?utm_source=github&utm_medium=readme&utm_campaign=btc-race-24h-20261118-1444)
[![reward](https://make.fun/badge/btc-race-24h-20261118-1444/0xazazul/btc-race-24h-20261118-1444/reward.svg)](https://make.fun/bounty/btc-race-24h-20261118-1444?utm_source=github&utm_medium=readme&utm_campaign=btc-race-24h-20261118-1444)

A long-only cbBTC trading bot for make.fun's "Race a BTC trading bot live for 24 hours" bounty ($250 in USDC). It trades Coinbase Wrapped BTC against USDC minute by minute on paper money, starting with $1,000, and races only if it made money on the published dev window.

## Strategy

Fills land at the next minute's open and pay 4 bps fee + 2 bps slippage + constant-product price impact, so a full-size round trip costs roughly 26–40 bps: a trade has to catch a real move, not noise. The bot has three legs, one position at a time, checked in this order:

1. **TURN — buy the capitulation rebound.** After the price has fallen at least 3.00% over 240 minutes *and* the last 15 minutes have turned up at least 0.30%, buy with all cash. A 4-hour washout that is already turning is the reliable intraday edge: on the 2026-11-15 race's dev window (a −4% day) this leg alone made +$35.64. Exit on take-profit +4.00%, stop-loss −1.00%, a trailing stop 1.50% below the peak since entry, or 480 bars.
2. **DIP — buy the shallow dip, but only when the longer trend is not falling.** After a 60-minute fall of at least 0.80% with the last 15 minutes turning up at least 0.15%, buy with all cash — but only if the 240-minute return is better than −1.00%. The trend filter is what keeps this leg from catching falling knives: without it the same rule loses money on a falling day; with it, it is positive on every observed dev window. Exit on take-profit +2.00%, stop-loss −0.40%, a trailing stop 1.50% below the peak, or 360 bars. The stop is tight (0.40%, not 1.00%): on this window's first dip trade the price kept falling about 1% after entry, so a 1.00% stop gives back ~$10 while 0.40% exits for ~$4; the tighter stop measured better on all three observed windows.
3. **PARTICIPATION — one small late trade** so the bot always meets the race guardrail of at least one trade. Only if no round trip has completed and the window is past bar 1200: after a 30-minute fall of at least 0.50% with the last 15 minutes turning up at least 0.20%, buy a quarter of the cash; exit on take-profit +1.00%, stop-loss −1.00%, or 120 bars.

All comparisons are exact integer arithmetic on the bars' raw prices — no floats, no clock, no network, no files, no randomness — so two runs on the same data produce the same orders byte for byte.

## Local measurement (dev window, exact replay)

Graded on the kit's frozen 24-hour dev window (1,440 one-minute bars, 2026-11-17T14:45Z–2026-11-18T14:44Z, BTC $65,083 → $63,261, −2.80%) with a replay that reproduces the official grader's numbers for the house baselines to 6 decimals (verified with `grade-local --driver process`, buy-and-hold reproduced exactly at −$31.633698). House baseline numbers below are the official `grade-local` results on this window:

| Bot | Net PnL | Trades | Max drawdown |
|---|---|---|---|
| **this bot** | **+$6.28** | **4 (2 round trips)** | **1.5%** |
| hold-cash | $0.00 | 0 | 0.0% |
| momentum | −$23.87 | 1 | 3.2% |
| buy-and-hold | −$31.63 | 1 | 3.2% |
| rsi-bollinger | −$39.92 | 19 | 4.4% |
| adx-momentum | −$75.57 | 30 | 7.6% |
| ema-cross | −$148.17 | 80 | 15.0% |

The same bot on the two earlier races' dev windows makes **+$26.21** (2026-11-15, BTC −4.0%, 4 trades, max drawdown 1.2%) and **+$29.25** (2026-11-17, BTC +0.49%, 4 trades, max drawdown 0.7%), so it is positive on all three observed 24-hour windows. The real bot was driven through the wire protocol on all three windows, twice each: byte-identical both runs, 0 rejected orders.

Honest caveat: this window's +$6.28 is two round trips, and a 240-minute dip leg with a 240-bar post-loss cooldown measured +$17.25 on this window alone but only +$4.18 / +$0.85 on the two earlier windows, so it was left out — one window's gain is not worth the other windows' losses. These numbers say the bot clears the dev gate with margin on the observed windows; they are not a promise about the unseen race window.
