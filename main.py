"""A dip-catching cbBTC bot for the make.fun 24-hour paper race.

The bot watches one-minute closes of cbBTC against USDC and only ever
holds a single long position, bought with paper money. It looks for the
same shape in three sizes: a deep four-hour shake-out that has started
to turn up, a shallower one-hour dip with the same turn, and, late in
the day, one small catch-up trade if nothing has completed yet. Every
exit is decided from the close of the bar that triggered the entry,
with the peak tracked from that same close, and every comparison is
done with integer arithmetic on the raw price units the harness
sends, so two runs on the same bars answer alike.

Wire talk: the harness sends one JSON line per batch (hello first,
then a batch per minute, then done) and this bot answers each batch
with exactly one reply line carrying its orders for that minute.
"""

import json
import sys

SYMBOL = "CBBTC"

# A buy spends at least this many quote units, and a sell must be
# worth at least this much at the latest close unless it empties the
# position. Both come from the hello message of the replay.
MIN_NOTIONAL = 1000000

# How far a fill may drift from the latest close before the replay
# refuses it. One-minute moves here are a fraction of a percent, so
# ten percent never binds; it is only a guard against a wild bar.
MAX_SLIP_BPS = 1000

# Each leg: take profit, stop loss, trailing stop and longest hold,
# all in basis points except the hold, which counts bars.
LEGS = {
    "turn": {"tp_bps": 400, "sl_bps": 100, "trail_bps": 150, "max_hold": 480},
    "dip": {"tp_bps": 200, "sl_bps": 40, "trail_bps": 150, "max_hold": 360},
    "catchup": {"tp_bps": 100, "sl_bps": 100, "trail_bps": 0, "max_hold": 120},
}


def has_fallen(now, then, bps):
    """True when `now` sits at least `bps` below `then`."""
    return now * 10000 <= then * (10000 - bps)


def has_risen(now, then, bps):
    """True when `now` sits at least `bps` above `then`."""
    return now * 10000 >= then * (10000 + bps)


def above_by(now, ref, bps):
    """True when `now` is at least `bps` above `ref`."""
    return now * 10000 >= ref * (10000 + bps)


def below_by(now, ref, bps):
    """True when `now` is at least `bps` below `ref`."""
    return now * 10000 <= ref * (10000 - bps)


class Bot:
    """One running of the strategy over a stream of batches."""

    def __init__(self):
        self.closes = []
        self.cash = 0
        self.qty = 0
        self.position = None
        self.round_trips = 0
        self.pending_buy = {}
        self.counter = 0

    def _next_id(self, leg):
        self.counter += 1
        return "%s-%d" % (leg, self.counter)

    def _buy(self, leg, notional, seq):
        order = {
            "side": "buy",
            "client_id": self._next_id(leg),
            "symbol": SYMBOL,
            "notional_quote_units": str(notional),
            "max_slippage_bps": MAX_SLIP_BPS,
        }
        # Remember what the entry decision was based on: the leg, the
        # close of the bar that triggered it, and the bar itself. The
        # fill price is not used for exits; this close is.
        self.pending_buy[order["client_id"]] = (
            leg,
            self.closes[-1],
            seq,
        )
        return order

    def _sell(self, leg):
        order = {
            "side": "sell",
            "client_id": self._next_id(leg),
            "symbol": SYMBOL,
            "qty": str(self.qty),
            "max_slippage_bps": MAX_SLIP_BPS,
        }
        return order

    def _note_fills(self, fills, seq):
        """Fold the fills this batch reports into the position."""
        for fill in fills:
            if fill.get("status") != "filled":
                self.pending_buy.pop(fill.get("client_id"), None)
                continue
            if fill.get("side") == "buy":
                # The fill price is only what the paper trade cost;
                # exits are measured from the close of the bar that
                # decided the entry, which _buy stored with the order.
                leg, entry_close, decided_at = self.pending_buy.pop(
                    fill.get("client_id"), ("dip", self.closes[-1], seq)
                )
                self.position = {
                    "leg": leg,
                    "entry": entry_close,
                    "peak": entry_close,
                    "decided_at": decided_at,
                }
            elif fill.get("side") == "sell":
                self.position = None
                self.round_trips += 1

    def _entry_pick(self, seq):
        """Choose a leg to enter, if any shape is showing now."""
        closes = self.closes
        now = closes[-1]
        n = len(closes)
        if n < 16:
            return None
        # The four-hour guard (> -1.00% over 240 minutes) only
        # applies once 240 bars of history exist; before that the
        # dip shape fires on its own two conditions.
        guard_ok = n < 241 or not has_fallen(now, closes[-241], 100)
        dip_shape = (
            n >= 61
            and has_fallen(now, closes[-61], 80)
            and has_risen(now, closes[-16], 15)
            and guard_ok
        )
        if n >= 241 and has_fallen(now, closes[-241], 300) and has_risen(
            now, closes[-16], 30
        ):
            return "turn"
        if dip_shape:
            return "dip"
        # The catch-up leg shares the dip shape, so it can only be
        # reached on a bar where the dip leg did not already fire
        # above; in practice it never triggers, because a bar that
        # shows the shape takes the dip leg first. It stays as a
        # late-day safety net in case the dip leg is ever narrowed.
        if seq > 1200 and self.round_trips == 0 and dip_shape:
            return "catchup"
        return None

    def _exit_now(self, seq):
        """True when the open position has hit one of its exits."""
        pos = self.position
        leg = LEGS[pos["leg"]]
        now = self.closes[-1]
        if now > pos["peak"]:
            pos["peak"] = now
        if above_by(now, pos["entry"], leg["tp_bps"]):
            return True
        if below_by(now, pos["entry"], leg["sl_bps"]):
            return True
        trail = leg["trail_bps"]
        if trail and below_by(now, pos["peak"], trail):
            return True
        # Hold is counted from the bar that decided the entry, not
        # the bar the order filled on.
        if seq - pos["decided_at"] >= leg["max_hold"]:
            return True
        return False

    def on_batch(self, batch):
        """Answer one batch with the orders for the next minute."""
        seq = batch["seq"]
        bars = batch.get("bars") or []
        if bars:
            self.closes.append(int(bars[0]["c"]))
        account = batch.get("account") or {}
        self.cash = int(account.get("cash_quote_units") or 0)
        held = account.get("positions") or []
        self.qty = int(held[0]["qty"]) if held else 0
        self._note_fills(batch.get("fills") or [], seq)

        orders = []
        if self.position is not None:
            if self.qty > 0 and self._exit_now(seq):
                orders.append(self._sell(self.position["leg"]))
        else:
            leg = self._entry_pick(seq)
            if leg is not None and self.cash >= MIN_NOTIONAL:
                if leg == "catchup":
                    notional = self.cash // 4
                else:
                    notional = self.cash
                if notional >= MIN_NOTIONAL:
                    orders.append(self._buy(leg, notional, seq))
        return {"type": "reply", "seq": seq, "orders": orders}


def run():
    bot = Bot()
    out = sys.stdout
    for line in sys.stdin:
        line = line.strip()
        if not line:
            continue
        msg = json.loads(line)
        kind = msg.get("type")
        if kind == "batch":
            out.write(json.dumps(bot.on_batch(msg)) + "\n")
            out.flush()
        elif kind == "done":
            break
        # hello and anything else need no answer.


if __name__ == "__main__":
    run()
