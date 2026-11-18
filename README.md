# Dip-rebound cbBTC bot — btc-race-24h-20261118-1444

[![make.fun · btc-race-24h-20261118-1444](https://make.fun/badge/btc-race-24h-20261118-1444.svg)](https://make.fun/bounty/btc-race-24h-20261118-1444?utm_source=github&utm_medium=readme&utm_campaign=btc-race-24h-20261118-1444)
[![rank](https://make.fun/badge/btc-race-24h-20261118-1444/0xazazul/btc-race-24h-20261118-1444/rank.svg)](https://make.fun/bounty/btc-race-24h-20261118-1444/leaderboard?utm_source=github&utm_medium=readme&utm_campaign=btc-race-24h-20261118-1444)
[![reward](https://make.fun/badge/btc-race-24h-20261118-1444/0xazazul/btc-race-24h-20261118-1444/reward.svg)](https://make.fun/bounty/btc-race-24h-20261118-1444?utm_source=github&utm_medium=readme&utm_campaign=btc-race-24h-20261118-1444)

This is a paper-money trader for make.fun's 24-hour BTC race. It buys
Coinbase Wrapped BTC with USDC, one minute at a time, starting from
$1,000 of play money. It only ever goes long, it never borrows, and it
never carries more than a single open position.

## The wire

The harness speaks `agent-fun/bars-replay/v1`: a hello line, then one
batch per minute, then done. Each batch carries one fresh bar plus the
fills and account state. The bot answers every batch with a single
reply line holding that minute's orders. An order decided on one bar
fills on the next bar's open, paying a 4 bps fee, 2 bps of slippage,
and constant-product impact against the pool depth — so a complete
round trip costs on the order of 26–40 bps. The bot therefore waits
for a shape strong enough to pay that cost and otherwise stays in cash.

## The three entry shapes

Every minute the bot tests three patterns, in this order, and takes the
first that matches. It never holds more than one position, so at most
one of them can be live at a time.

**1. TURN — the four-hour washout.** The price has dropped at least
3.00% across the past 240 minutes and is already climbing again, up at
least 0.30% over the past 15 minutes. The bot puts all its cash in.
A long sell-off that has begun to reverse is the steadiest intraday
pattern in the data; on the 2026-11-15 window, a day BTC fell 4%, this
pattern alone earned roughly +$35.64. It leaves at +4.00% profit,
−1.00% loss, a trailing stop 1.50% under the best price since entry,
or after 480 bars.

**2. DIP — the one-hour dip, with a trend check.** The price has fallen
at least 0.80% over the past 60 minutes and turned up at least 0.15%
over the past 15 minutes. Once 240 bars of history exist, the bot also
requires the 240-minute return to be better than −1.00% — that filter
is what separates a dip from a falling knife: without it the same rule
loses on down days, with it the leg is positive on every window seen.
Before 240 bars exist the dip fires on its two short conditions alone,
and that early firing is what creates this window's two round trips.
It leaves at +2.00% profit, a tight −0.40% loss, a 1.50% trailing
stop, or after 360 bars. The stop is tight on purpose: after this
window's first dip entry the price slid about another 1%, so a 1.00%
stop would have handed back roughly $10 while the 0.40% stop kept the
damage near $4 — and the tighter stop measured better on all three
windows.

**3. CATCH-UP — a small late trade.** Only past bar 1200, only when no
round trip has finished yet, and only on the same dip shape, the bot
buys with a quarter of its cash. It leaves at +1.00%, −1.00%, or after
120 bars. In practice this leg never triggers: any bar showing the dip
shape is taken by the DIP leg first. It stays in the code as a late-day
safety net in case the dip rule is ever tightened.

## What the exits are measured from

Every exit is measured from the close of the bar that triggered the
entry — not from the price the order actually filled at. The hold
clock starts on that same decision bar, and the peak the trailing stop
watches is tracked from that decision close as well. All comparisons
use exact integer arithmetic on the raw price units the harness sends:
no floats, no clock, no network, no files, no randomness. The same
bars always produce the same orders.

## Measured results

The bot was driven through the wire protocol on the kit's frozen
24-hour dev window (1,440 one-minute bars, 2026-11-17T14:45Z to
2026-11-18T14:44Z, BTC $65,083 down to $63,261, −2.80%). The local
replay driver reproduces the official grader's house-baseline numbers
to six decimals (buy-and-hold reproduced exactly at −$31.633698), and
the baseline figures below are the official `grade-local` results on
this window.

| Bot | Net PnL | Trades | Max drawdown |
| --- | --- | --- | --- |
| **this bot** | **+$6.28** | **4 (2 round trips)** | **1.5%** |
| hold-cash | $0.00 | 0 | 0.0% |
| momentum | −$23.87 | 1 | 3.2% |
| buy-and-hold | −$31.63 | 1 | 3.2% |
| rsi-bollinger | −$39.92 | 19 | 4.4% |
| adx-momentum | −$75.57 | 30 | 7.6% |
| ema-cross | −$148.17 | 80 | 15.0% |

The same bot on the two earlier races' dev windows earns **+$26.21**
(2026-11-15, BTC −4.0%, 4 trades, max drawdown 1.2%) and **+$29.25**
(2026-11-17, BTC +0.49%, 4 trades, max drawdown 0.7%). It is positive
on all three observed 24-hour windows, was driven through the wire
protocol on each of them twice with byte-identical results, and had
zero rejected orders.

An honest caveat: this window's +$6.28 is just two round trips, and a
tempting extra leg — a 240-minute dip with a 240-bar cooldown after a
loss — measured +$17.25 on this window alone but only +$4.18 and
+$0.85 on the two earlier windows, so it was left out. One window's
gain is not worth the other windows' losses. These numbers show the bot
clears the dev gate with margin on the windows observed; they are not a
promise about the unseen race window.
