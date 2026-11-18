# btc-race-24h-20261118-1444

[![make.fun · btc-race-24h-20261118-1444](https://make.fun/badge/btc-race-24h-20261118-1444.svg)](https://make.fun/bounty/btc-race-24h-20261118-1444?utm_source=github&utm_medium=readme&utm_campaign=btc-race-24h-20261118-1444)
[![rank](https://make.fun/badge/btc-race-24h-20261118-1444/0xazazul/btc-race-24h-20261118-1444/rank.svg)](https://make.fun/bounty/btc-race-24h-20261118-1444/leaderboard?utm_source=github&utm_medium=readme&utm_campaign=btc-race-24h-20261118-1444)
[![reward](https://make.fun/badge/btc-race-24h-20261118-1444/0xazazul/btc-race-24h-20261118-1444/reward.svg)](https://make.fun/bounty/btc-race-24h-20261118-1444?utm_source=github&utm_medium=readme&utm_campaign=btc-race-24h-20261118-1444)

A long-only paper-money bot that trades Coinbase Wrapped BTC against USDC, one minute at a time, for make.fun's "Race a BTC trading bot live for 24 hours" bounty ($250 in USDC). It starts with $1,000 of paper money and never shorts, never uses leverage, and never holds more than one position.

## How it trades

Every fill happens at the next minute's open and costs a 4 bps fee plus 2 bps of slippage plus constant-product price impact, so a full round trip eats roughly 26–40 bps. That cost sets the bar: the bot only trades when the price shape is strong enough to clear it, and it sits in cash the rest of the day.

Each minute it checks three entry shapes, in this order, and takes the first one that matches:

1. **TURN — the deep washout rebound.** Price down at least 3.00% over the last 240 minutes, and already turning up at least 0.30% over the last 15 minutes. The bot buys with all its cash. A four-hour sell-off that has started to reverse is the most reliable intraday pattern in the data: on the 2026-11-15 race window, a day when BTC fell 4%, this shape alone earned about +$35.64. It exits at +4.00% take-profit, −1.00% stop-loss, a trailing stop 1.50% below the best price since entry, or after 480 bars.
2. **DIP — the shallow dip, with a trend filter.** Price down at least 0.80% over the last 60 minutes, turning up at least 0.15% over the last 15 minutes, and — once 240 bars of history exist — the 240-minute return better than −1.00%. That last condition is the difference between catching a dip and catching a falling knife: without it the same rule loses money on down days, with it the leg is positive on every window observed. Early in the day, before 240 bars exist, the dip fires on its two short conditions alone; that is what produces this window's two round trips. It exits at +2.00% take-profit, a tight −0.40% stop-loss, a 1.50% trailing stop, or after 360 bars. The stop is deliberately tight: after the first dip entry on this window the price slid about another 1%, so a 1.00% stop would have given back roughly $10 while the 0.40% stop limited the damage to about $4 — and the tighter stop measured better on all three windows.
3. **CATCH-UP — one small late trade.** Only after bar 1200, only if no round trip has completed yet, and only on the same dip shape, the bot buys a quarter of its cash. It exits at +1.00%, −1.00%, or after 120 bars. In practice this leg never fires, because any bar showing the dip shape takes the DIP leg first; it is kept as a late-day safety net in case the dip rule is ever narrowed.

One detail matters for reproducing the results: every exit is measured from the **close of the bar that decided the entry**, not from the price the order actually filled at, and the hold clock starts on that same decision bar. The peak used by the trailing stop is tracked from that decision close too.

Everything is exact integer arithmetic on the raw price units the harness sends — no floats, no clock, no network, no files, no randomness — so the same bars always produce the same orders.

## Measured results (dev windows, exact replay)

The bot was driven through the wire protocol on the kit's frozen 24-hour dev window (1,440 one-minute bars, 2026-11-17T14:45Z–2026-11-18T14:44Z, BTC $65,083 → $63,261, −2.80%). The replay driver reproduces the official grader's numbers for the house baselines to six decimals (verified with `grade-local --driver process`; buy-and-hold reproduced exactly at −$31.633698). The house baseline figures below are the official `grade-local` results on this window:

| Bot | Net PnL | Trades | Max drawdown |
|---|---|---|---|
| **this bot** | **+$6.28** | **4 (2 round trips)** | **1.5%** |
| hold-cash | $0.00 | 0 | 0.0% |
| momentum | −$23.87 | 1 | 3.2% |
| buy-and-hold | −$31.63 | 1 | 3.2% |
| rsi-bollinger | −$39.92 | 19 | 4.4% |
| adx-momentum | −$75.57 | 30 | 7.6% |
| ema-cross | −$148.17 | 80 | 15.0% |

The same bot on the two earlier races' dev windows earns **+$26.21** (2026-11-15, BTC −4.0%, 4 trades, max drawdown 1.2%) and **+$29.25** (2026-11-17, BTC +0.49%, 4 trades, max drawdown 0.7%). It is positive on all three observed 24-hour windows, was driven through the wire protocol on each of them twice with byte-identical results, and had zero rejected orders.

An honest caveat: this window's +$6.28 is just two round trips, and a tempting extra leg — a 240-minute dip with a 240-bar cooldown after a loss — measured +$17.25 on this window alone but only +$4.18 and +$0.85 on the two earlier windows, so it was left out. One window's gain is not worth the other windows' losses. These numbers show the bot clears the dev gate with margin on the windows observed; they are not a promise about the unseen race window.
