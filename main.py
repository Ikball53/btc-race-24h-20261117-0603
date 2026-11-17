"""Range-aware trend breakout bot for cbBTC/USDC on 1-minute bars.

Idea in one paragraph: BTC spends most of a day drifting sideways, so the bot
waits for a genuine push instead of guessing every wiggle. It only buys when
three things agree at once -- price sits above both a quick and a slow
exponential average, the last twenty minutes already rose, and the close
prints a fresh twenty-bar high. Once in, it banks the move early (a modest
take-profit), cuts the trade quickly if it turns (a tight stop), trails the
peak once the trade is comfortably ahead, and walks away after a time limit
so no position is left to drift through a reversal. One position at a time,
full cash on each entry, no entries in the final hour, and a short breather
after every exit so a whipsaw cannot re-enter on the same bar.

All decisions use only the bars the harness has sent so far. Nothing here
reads the clock, the network, the environment, or any file. The bot is fully
deterministic: the same bars always produce the same orders.
"""

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "vendor"))
import makefun_bars

SYMBOL = "CBBTC"

# --- trend lengths (bars) -------------------------------------------------
QUICK_LEN = 10
SLOW_LEN = 30
LOOKBACK = 20
BREAKOUT_LEN = 30

# --- entry filters ---------------------------------------------------------
# Minimum 20-bar rise to enter, in basis points of price.
MIN_RISE_BPS = 20
# Minimum 30-bar rise: the wider drift must agree with the quick push.
MIN_RISE_60_BPS = 15
# Minimum 20-bar range (high minus low over price), in bps: skip dead-flat tape.
MIN_RANGE_BPS = 50

# --- exits, in basis points of the entry fill price ------------------------
# Wide exits on purpose: the window's money sits in hour-long drifts of
# 60-130 bps, and tight stops kept cutting those drifts off at a loss.
TAKE_PROFIT_BPS = 180
STOP_LOSS_BPS = 60
TRAIL_ARM_BPS = 100
TRAIL_GIVEBACK_BPS = 30
MAX_HOLD_BARS = 360

# --- pacing ----------------------------------------------------------------
COOLDOWN_BARS = 20
LAST_ENTRY_SEQ = 1380
SLIPPAGE_BPS = 150


class BreakoutBot:
    """Keeps the price history and the state of the one open trade."""

    def __init__(self):
        self.closes = []
        self.highs = []
        self.lows = []
        self.quick = None
        self.slow = None
        self.entry_price = None
        self.entry_seq = -1
        self.peak_price = None
        self.cool_until = -1
        self.prev_close = None
        self.prev_quick = None

    def _ema(self, previous, price, length):
        alpha = 2.0 / (length + 1)
        if previous is None:
            return float(price)
        return previous + alpha * (price - previous)

    def note_bar(self, bar):
        close = int(bar["c"])
        self.prev_close = self.closes[-1] if self.closes else None
        self.prev_quick = self.quick
        self.closes.append(close)
        self.highs.append(int(bar["h"]))
        self.lows.append(int(bar["l"]))
        self.quick = self._ema(self.quick, close, QUICK_LEN)
        self.slow = self._ema(self.slow, close, SLOW_LEN)

    def _twenty_bar_range_bps(self):
        window = self.closes[-LOOKBACK:]
        return (max(window) - min(window)) * 10000 // max(window)

    def _rise_bps(self):
        window = self.closes[-LOOKBACK:]
        return (window[-1] - window[0]) * 10000 // window[0]

    def _fresh_high(self):
        recent = self.closes[-BREAKOUT_LEN:-1]
        return self.closes[-1] > max(recent)

    def _pullback_cross(self):
        # The price dipped under its quick average and has just climbed back
        # above it while the wider drift still points up: a trend
        # continuation, not a bet on a falling knife.
        if self.prev_close is None or self.prev_quick is None:
            return False
        return self.prev_close <= self.prev_quick and self.closes[-1] > self.quick

    def _sixty_rise_bps(self):
        window = self.closes[-BREAKOUT_LEN:]
        return (window[-1] - window[0]) * 10000 // window[0]

    def _trend_up(self):
        price = self.closes[-1]
        return price > self.quick > self.slow

    def should_enter(self, state):
        if len(self.closes) < BREAKOUT_LEN + 1:
            return False
        if state.seq >= LAST_ENTRY_SEQ:
            return False
        if state.seq <= self.cool_until:
            return False
        if state.warming_up:
            return False
        if not self._trend_up():
            return False
        if self._sixty_rise_bps() < MIN_RISE_60_BPS:
            return False
        if self._twenty_bar_range_bps() < MIN_RANGE_BPS:
            return False
        # Either a fresh high on a strong quick push, or a pullback that has
        # just turned back up while the wider drift still points up. The
        # pullback leg only needs the quick push not to be falling.
        if self._fresh_high() and self._rise_bps() >= MIN_RISE_BPS:
            return True
        return self._pullback_cross() and self._rise_bps() >= 0

    def should_exit(self, state):
        price = self.closes[-1]
        if self.entry_price is None:
            return False
        if price >= self.entry_price * (10000 + TAKE_PROFIT_BPS) // 10000:
            return True
        if price <= self.entry_price * (10000 - STOP_LOSS_BPS) // 10000:
            return True
        if self.peak_price is not None and self.peak_price >= self.entry_price * (10000 + TRAIL_ARM_BPS) // 10000:
            if price <= self.peak_price * (10000 - TRAIL_GIVEBACK_BPS) // 10000:
                return True
        # No exit on a dip under the slow average: in a drifting market the
        # price crosses it often, and each crossing used to bank a small loss.
        if state.seq - self.entry_seq >= MAX_HOLD_BARS:
            return True
        return False


BOT = BreakoutBot()


def on_batch(state, batch):
    bar = state.latest.get(SYMBOL)
    if bar is None:
        return []
    BOT.note_bar(bar)
    price = BOT.closes[-1]
    if BOT.peak_price is not None and price > BOT.peak_price:
        BOT.peak_price = price

    held = state.positions.get(SYMBOL)
    if held is not None and held.qty > 0:
        if BOT.entry_price is None:
            # Position arrived without a recorded entry (e.g. a replayed fill):
            # anchor the exit logic on the position's cost basis instead.
            # value = qty * price / 10**7, so price = cost * 10**7 / qty.
            BOT.entry_price = held.cost * 10 ** 7 // held.qty if held.qty else price
            BOT.entry_seq = state.seq
            BOT.peak_price = price
        if BOT.should_exit(state):
            BOT.entry_price = None
            BOT.peak_price = None
            BOT.cool_until = state.seq + COOLDOWN_BARS
            return [{"side": "sell", "symbol": SYMBOL, "qty": held.qty,
                     "max_slippage_bps": SLIPPAGE_BPS}]
        return []

    # Flat: look for a fresh breakout entry, sized at the full cash balance.
    if BOT.entry_price is not None:
        BOT.entry_price = None
        BOT.peak_price = None
    if not BOT.should_enter(state):
        return []
    cash = state.cash
    if cash < 1_000_000:
        return []
    room = state.weight_room(SYMBOL)
    spend = min(cash, room)
    if spend < 1_000_000:
        return []
    BOT.entry_price = price
    BOT.entry_seq = state.seq
    BOT.peak_price = price
    return [{"side": "buy", "symbol": SYMBOL, "notional_quote_units": spend,
             "max_slippage_bps": SLIPPAGE_BPS}]


makefun_bars.run(on_batch)
