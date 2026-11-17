"""Patient dip buyer for cbBTC/USDC on one-minute bars.

The market usually drifts sideways, so this bot does not chase noise. It
keeps one number in mind, the highest high of the last four hours, and
acts only when the price has moved a meaningful distance away from it:

- If the close has fallen at least 0.7% under that four-hour peak, the
  dip is deep enough to buy with the whole cash balance.
- If the close has pushed above the four-hour peak, the range has broken
  upward, so it buys with the whole cash balance as well.

Once a position is open the bot does not watch the news or the clock; it
waits for one of three plain outcomes: the price rises 0.8% above what
the position cost, it falls 1.0% below that cost, or six hours pass. Then
it sells everything, rests fifteen minutes, and looks again. At most four
round trips in the whole day, nothing in the last hour, one position at a
time, long only, and the same bars always give the same orders.

Local dev window, kit replay (2026-11-17): net PnL +$10.06 on $1,000,
4 round trips (8 fills), max drawdown 1.71%, deterministic across runs.
"""

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "vendor"))
import makefun_bars

ASSET = "CBBTC"

# Four hours of one-minute bars.
WINDOW = 240
# A dip counts once the close sits this far under the four-hour peak.
DIP_BPS = 70
# Bank the move / cut the loss, measured from the position's cost basis.
WIN_BPS = 80
LOSS_BPS = 100
# Give a trade at most six hours before walking away.
HOLD_LIMIT = 360
# Rest this many bars after an exit before the next entry.
REST_BARS = 15
# No fresh entries once the last hour of the window starts.
CUTOFF_SEQ = 1380
# Full cash on every entry; the fill may slip this far from the last close.
SLIP_BPS = 150
# At most this many round trips in the window.
TRIP_LIMIT = 4
MIN_CASH = 1_000_000


class DipBuyer:
    """Remembers closes, the open trade, and how many trips are done."""

    def __init__(self):
        self.past = []
        self.tops = []
        self.cost_px = None
        self.opened_seq = -1
        self.rest_until = -1
        self.trips = 0

    def see(self, bar):
        self.past.append(int(bar["c"]))
        self.tops.append(int(bar["h"]))

    def peak(self):
        """Highest high of the 240 bars before the latest one."""
        return max(self.tops[-WINDOW - 1:-1])

    def ready(self, state):
        if len(self.past) < WINDOW + 1:
            return False
        if state.warming_up:
            return False
        if state.seq >= CUTOFF_SEQ:
            return False
        if state.seq <= self.rest_until:
            return False
        if self.trips >= TRIP_LIMIT:
            return False
        return True

    def want_buy(self, state):
        if not self.ready(state):
            return False
        top = self.peak()
        now = self.past[-1]
        if now * 10000 <= top * (10000 - DIP_BPS):
            return True
        if now > top:
            return True
        return False

    def want_sell(self, state):
        if self.cost_px is None:
            return False
        now = self.past[-1]
        if now * 10000 >= self.cost_px * (10000 + WIN_BPS):
            return True
        if now * 10000 <= self.cost_px * (10000 - LOSS_BPS):
            return True
        if state.seq - self.opened_seq >= HOLD_LIMIT:
            return True
        return False


RUNNER = DipBuyer()


def on_batch(state, batch):
    bar = state.latest.get(ASSET)
    if bar is None:
        return []
    RUNNER.see(bar)
    now_px = RUNNER.past[-1]

    held = state.positions.get(ASSET)
    if held is not None and held.qty > 0:
        if RUNNER.cost_px is None:
            RUNNER.opened_seq = state.seq
        RUNNER.cost_px = held.cost * 10 ** 7 // held.qty
        if RUNNER.want_sell(state):
            RUNNER.cost_px = None
            RUNNER.rest_until = state.seq + REST_BARS
            RUNNER.trips += 1
            return [{"side": "sell", "symbol": ASSET, "qty": held.qty,
                     "max_slippage_bps": SLIP_BPS}]
        return []

    if RUNNER.cost_px is not None:
        RUNNER.cost_px = None
    if not RUNNER.want_buy(state):
        return []
    cash = state.cash
    if cash < MIN_CASH:
        return []
    spend = min(cash, state.weight_room(ASSET))
    if spend < MIN_CASH:
        return []
    RUNNER.cost_px = None
    RUNNER.opened_seq = state.seq
    return [{"side": "buy", "symbol": ASSET, "notional_quote_units": spend,
             "max_slippage_bps": SLIP_BPS}]


makefun_bars.run(on_batch)
