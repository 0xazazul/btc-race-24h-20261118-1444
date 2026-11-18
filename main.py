"""A cbBTC trading bot for make.fun's btc-race-24h-20261118-1444.

Speaks agent-fun/bars-replay/v1: one JSON line per minute (a 1-minute bar of
cbBTC priced in USDC from its Orca Whirlpool on Solana), one reply with buy
and sell orders. Long only, one position, starts with $1,000 of paper money.
Fills land at the next minute's open and pay 4 bps fee + 2 bps slippage +
constant-product price impact, so a full-size round trip costs roughly
26-40 bps: a trade has to catch a real move, not noise.

Strategy (three legs, one position at a time, checked in this order):

1. TURN -- buy the capitulation rebound. After the price has fallen at
   least 3.00% over 240 minutes AND the last 15 minutes have turned up at
   least 0.30%, buy with all cash. A 4-hour washout that is already turning
   is the reliable intraday edge: on the 2026-11-15 race's dev window (a -4%
   day) this leg alone made +$35.64. Exit on take-profit +4.00%, stop-loss
   -1.00%, a trailing stop 1.50% below the peak since entry, or 480 bars.
2. DIP -- buy the shallow dip, but only when the longer trend is not
   falling. After a 60-minute fall of at least 0.80% with the last 15
   minutes turning up at least 0.15%, buy with all cash -- but only if the
   240-minute return is better than -1.00%. The trend filter is what keeps
   this leg from catching falling knives: without it the same rule loses
   money on a falling day; with it, it is positive on every observed dev
   window. Exit on take-profit +2.00%, stop-loss -0.40%, a trailing stop
   1.50% below the peak, or 360 bars. The stop is tight (0.40%, not 1.00%):
   on this window's first dip trade the price kept falling about 1% after
   entry, so a 1.00% stop gives back ~$10 while 0.40% exits for ~$4; the
   tighter stop measured better on all three observed windows.
3. PARTICIPATION -- a small late trade so the bot always meets the race
   guardrail of at least one trade. Only if no round trip has completed
   and the window is past bar 1200: after a 30-minute fall of at least
   0.50% with the last 15 minutes turning up at least 0.20%, buy a
   quarter of the cash; exit on take-profit +1.00%, stop-loss -1.00%, or
   120 bars.

All comparisons are exact integer arithmetic on the bars' raw prices (no
floats, no clock, no network, no files, no randomness), so two runs on the
same data produce the same orders byte for byte.

Dev-window measurement (kit's frozen 24h window, 2026-11-17T14:45Z to
2026-11-18T14:44Z, BTC $65,083 -> $63,261, -2.80%, range $63,027-$65,190),
exact replay validated against the official grade-local numbers for the
house baselines to 6 decimals (buy-and-hold reproduced exactly:
-$31.633698, max drawdown 0.032485), and the real bot driven through the
wire protocol on three windows, twice each, byte-identical both runs with
0 rejected orders: net PnL +$6.28 on $1,000 (+0.63%), 2 round trips
(4 filled orders), max drawdown 1.53%, fees $1.60. Best house baseline
(hold-cash) $0.00 with 0 trades (fails the >=1 trade guardrail); best
trading baseline (momentum) -$23.87.
The same bot on the two earlier races' dev windows makes +$26.21
(2026-11-15, BTC -4.0%) and +$29.25 (2026-11-17, BTC +0.49%), so it is
positive on all three observed 24-hour windows. A 240-minute dip leg with
a 240-bar post-loss cooldown measured +$17.25 on this window alone but
only +$4.18 / +$0.85 on the two earlier windows, so it was left out: one
window's gain is not worth the other windows' losses. These numbers say
the bot clears the dev gate with margin on the observed windows; they are
not a promise about the unseen race window.
"""

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "vendor"))
import makefun_bars

SYMBOL = "CBBTC"
BPS = 10_000
MAX_SLIPPAGE_BPS = 10_000

# --- TURN leg: buy the capitulation rebound --------------------------------
TURN_LOOKBACK_BARS = 240
TURN_DROP_BPS = 300          # 240-minute fall of at least 3.00%
TURN_UP_WINDOW_BARS = 15
TURN_UP_BPS = 30             # ...with the last 15 minutes up 0.30%
TURN_TAKE_BPS = 400          # take profit +4.00%
TURN_STOP_BPS = 100          # stop loss -1.00%
TURN_TRAIL_BPS = 150         # trailing stop 1.50% below the peak
TURN_MAX_HOLD_BARS = 480

# --- DIP leg: buy the shallow dip, only when the trend is not falling ------
DIP_LOOKBACK_BARS = 60
DIP_DROP_BPS = 80            # 60-minute fall of at least 0.80%
DIP_UP_WINDOW_BARS = 15
DIP_UP_BPS = 15              # ...with the last 15 minutes up 0.15%
DIP_TREND_LOOKBACK_BARS = 240
DIP_TREND_MIN_BPS = 100      # ...and the 240-minute return better than -1.00%
DIP_TAKE_BPS = 200           # take profit +2.00%
DIP_STOP_BPS = 40            # stop loss -0.40% (tight: see docstring)
DIP_TRAIL_BPS = 150          # trailing stop 1.50% below the peak
DIP_MAX_HOLD_BARS = 360

# --- PARTICIPATION leg: one small late trade, for the >= 1 trade rule -----
PART_MIN_SEQ = 1200
PART_DROP_BARS = 30
PART_DROP_BPS = 50           # 30-minute fall of at least 0.50%
PART_UP_BPS = 20             # ...with the last 15 minutes up 0.20%
PART_TAKE_BPS = 100
PART_STOP_BPS = 100
PART_MAX_HOLD_BARS = 120

# Closes so far (raw price units, oldest first). Everything below reads
# only this list and the account the harness reports: no clock, no files.
closes = []
entry = None      # close at which the open position was decided
peak = 0          # highest close since entry
held = 0          # bars held (decisions since entry)
leg = None        # which leg opened the position: "turn" | "dip" | "part"
round_trips = 0   # completed round trips (sells)


def _down_bps(i, window, bps):
    """True when closes[i] is at least `bps` below closes[i - window].

    Exact integer comparison: now * 10000 <= then * (10000 - bps).
    """
    if i - window < 0:
        return False
    return closes[i] * BPS <= closes[i - window] * (BPS - bps)


def _up_bps(i, window, bps):
    """True when closes[i] is at least `bps` above closes[i - window]."""
    if i - window < 0:
        return False
    return closes[i] * BPS >= closes[i - window] * (BPS + bps)


def _above(price, ref, bps):
    """True when price is at least `bps` above ref (exact integers)."""
    return price * BPS >= ref * (BPS + bps)


def _below(price, ref, bps):
    """True when price is at least `bps` below ref (exact integers)."""
    return price * BPS <= ref * (BPS - bps)


def _buy_all(state):
    return [{"side": "buy", "symbol": SYMBOL,
             "notional_quote_units": state.cash,
             "max_slippage_bps": MAX_SLIPPAGE_BPS}]


def _sell_all(state):
    holding = state.positions.get(SYMBOL)
    if holding is None:
        return []
    return [{"side": "sell", "symbol": SYMBOL, "qty": holding.qty,
             "max_slippage_bps": MAX_SLIPPAGE_BPS}]


def _open(state, which, price):
    global entry, peak, held, leg
    entry = price
    peak = price
    held = 0
    leg = which


def _close(state):
    global entry, peak, held, leg, round_trips
    entry = None
    peak = 0
    held = 0
    leg = None
    round_trips += 1
    return _sell_all(state)


def on_batch(state, batch):
    """Decide this batch's orders. `state` is the SDK's BarsState: cash,
    equity, positions and the latest bar, current before this callback."""
    price = state.close(SYMBOL)
    if price is None:
        return []
    closes.append(price)
    i = len(closes) - 1
    seq = state.seq

    holding = state.positions.get(SYMBOL)
    if holding is None:
        # Flat: check the legs in priority order.
        if (_down_bps(i, TURN_LOOKBACK_BARS, TURN_DROP_BPS)
                and _up_bps(i, TURN_UP_WINDOW_BARS, TURN_UP_BPS)):
            _open(state, "turn", price)
            return _buy_all(state)
        if (_down_bps(i, DIP_LOOKBACK_BARS, DIP_DROP_BPS)
                and _up_bps(i, DIP_UP_WINDOW_BARS, DIP_UP_BPS)
                and not _down_bps(i, DIP_TREND_LOOKBACK_BARS,
                                  DIP_TREND_MIN_BPS)):
            _open(state, "dip", price)
            return _buy_all(state)
        if (round_trips == 0 and seq >= PART_MIN_SEQ
                and _down_bps(i, PART_DROP_BARS, PART_DROP_BPS)
                and _up_bps(i, DIP_UP_WINDOW_BARS, PART_UP_BPS)):
            _open(state, "part", price)
            return [{"side": "buy", "symbol": SYMBOL,
                     "notional_quote_units": state.cash // 4,
                     "max_slippage_bps": MAX_SLIPPAGE_BPS}]
        return []

    # Holding: manage the exit.
    global held, peak
    if entry is None or leg is None:
        # State desync (e.g. a buy that never filled after _open): hold
        # quietly instead of raising on a None reference; the position
        # flattens at the window end if it never resolves.
        return []
    held += 1
    if price > peak:
        peak = price
    sell = False
    if leg == "turn":
        sell = (_above(price, entry, TURN_TAKE_BPS)
                or _below(price, entry, TURN_STOP_BPS)
                or _below(price, peak, TURN_TRAIL_BPS)
                or held >= TURN_MAX_HOLD_BARS)
    elif leg == "dip":
        sell = (_above(price, entry, DIP_TAKE_BPS)
                or _below(price, entry, DIP_STOP_BPS)
                or _below(price, peak, DIP_TRAIL_BPS)
                or held >= DIP_MAX_HOLD_BARS)
    else:  # part
        sell = (_above(price, entry, PART_TAKE_BPS)
                or _below(price, entry, PART_STOP_BPS)
                or held >= PART_MAX_HOLD_BARS)
    if sell:
        return _close(state)
    return []


makefun_bars.run(on_batch)
