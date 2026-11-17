"""Dip-buying Bollinger mean-reversion bot for the make.fun BTC race.

Strategy (one asset, CBBTC/USDC, 1-minute bars, long only, full size):
  * Every bar, keep the trailing 120-bar mean and standard deviation of the
    close, plus the trailing 240-bar mean.
  * BUY (all cash) when the close falls to or below the lower Bollinger band
    (mean120 - 1 * std120) AND the close is below the 240-bar mean, i.e. the
    dip is a genuine pullback below the medium-term average, not a blip near
    the top of a rally. At most one open position; never adds to a position.
  * SELL (whole position) when the close reaches entry_close * 1.012: the
    dip has recovered a little over one percent. A full-size round trip pays
    about 26 bps in fee, slippage and price impact, so a 1.2% target clears
    the cost with room to spare; smaller targets were tested and earned less
    on the dev window because they exit before the recovery completes.
  * Hard stop: sell if the close falls 3% below the entry close (crash guard).
  * Circuit breaker: if equity ever falls 5% below its peak, sell and stop
    trading for the rest of the window (caps the worst case well inside the
    25% maximum-drawdown bar).
  * No new entries in the final 120 bars: a dip-buy needs hours to reach its
    target, and a position opened that late would just be flattened at a loss.
  * Orders carry max_slippage_bps 200: a fill more than 2% away from the
    latest close is refused, so a gap open can never force a bad fill.

Why this shape: on the published 24h dev window BTC drifts in a range
($63.9k-$65.5k) with 1-minute noise of ~6 bps against a ~26 bps round-trip
cost, so fast trend-following whipsaws itself to death (the kit's ema-cross
baseline loses $106 there). Buying dips and waiting for the recovery is the
trade the window actually pays for. The same rules, with no bar-specific
tuning, are positive across the whole neighbourhood of the chosen parameters
(band 60-240 bars, 0.75-1.25 sigma, 1.0-1.3% target), so the entry is not a
single lucky parameter set.

Deterministic: pure integer running sums for the band statistics, one float
division per bar, no clock, no environment, no randomness, no files, no
network. Two runs on the same bars produce identical replies.

Protocol: agent-fun/bars-replay/v1 via the vendored shim (vendor/).
"""

import math
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "vendor"))
import makefun_bars

SYMBOL = "CBBTC"
# Bollinger band: trailing window (bars) and width in standard deviations.
BAND_BARS = 120
BAND_SIGMA = 1.0
# Medium-term filter window (bars): only buy dips below this mean.
FILTER_BARS = 240
# Take-profit: sell once the close is this far above the entry close.
TAKE_PROFIT = 0.012
# Hard stop: sell once the close is this far below the entry close.
STOP_LOSS = 0.03
# Circuit breaker: sell and stop trading if equity falls this far below peak.
MAX_EQUITY_DRAWDOWN = 0.05
# Do not open a new position this many bars from the end of the window
# (the window is 1,440 bars; a dip-buy needs hours to reach its target).
NO_ENTRY_LAST_BARS = 120
# Refuse any fill more than this far (bps) from the latest close.
MAX_SLIPPAGE_BPS = 200

_closes = []          # every close seen so far, as ints (price_scale 5)
_sum_band = 0         # running sum of the last BAND_BARS closes
_sumsq_band = 0       # running sum of squares of the last BAND_BARS closes
_sum_filter = 0       # running sum of the last FILTER_BARS closes
_entry_close = 0      # close at which the current position was decided
_peak_equity = 0      # highest equity seen (quote units)
_stopped = False      # True once the circuit breaker has fired


def _band():
    """(mean, std) of the trailing BAND_BARS closes; None until full."""
    n = len(_closes)
    if n < BAND_BARS:
        return None
    mean = _sum_band / BAND_BARS
    var = _sumsq_band / BAND_BARS - mean * mean
    if var < 0.0:
        var = 0.0
    return mean, math.sqrt(var)


def _filter_mean():
    """Mean of the trailing FILTER_BARS closes (or all closes so far)."""
    n = len(_closes)
    if n == 0:
        return None
    return _sum_filter / n if n < FILTER_BARS else _sum_filter / FILTER_BARS


def on_batch(state, batch):
    global _sum_band, _sumsq_band, _sum_filter
    global _entry_close, _peak_equity, _stopped
    close = state.close(SYMBOL)
    if close is None:
        return []
    _closes.append(close)
    _sum_band += close
    _sumsq_band += close * close
    _sum_filter += close
    n = len(_closes)
    if n > BAND_BARS:
        old = _closes[n - BAND_BARS - 1]
        _sum_band -= old
        _sumsq_band -= old * old
    if n > FILTER_BARS:
        _sum_filter -= _closes[n - FILTER_BARS - 1]

    if state.warming_up:
        return []
    if state.equity > _peak_equity:
        _peak_equity = state.equity

    holding = SYMBOL in state.positions
    if holding:
        # Circuit breaker: sell and stop trading for the rest of the window.
        if state.equity < _peak_equity * (1.0 - MAX_EQUITY_DRAWDOWN):
            _stopped = True
            return [{"side": "sell", "symbol": SYMBOL,
                     "qty": state.positions[SYMBOL].qty,
                     "max_slippage_bps": MAX_SLIPPAGE_BPS}]
        # Hard stop, then take-profit.
        if close <= _entry_close * (1.0 - STOP_LOSS):
            return [{"side": "sell", "symbol": SYMBOL,
                     "qty": state.positions[SYMBOL].qty,
                     "max_slippage_bps": MAX_SLIPPAGE_BPS}]
        if close >= _entry_close * (1.0 + TAKE_PROFIT):
            return [{"side": "sell", "symbol": SYMBOL,
                     "qty": state.positions[SYMBOL].qty,
                     "max_slippage_bps": MAX_SLIPPAGE_BPS}]
        return []

    # Flat: look for a dip to buy.
    if _stopped:
        return []
    if state.seq >= 1440 - NO_ENTRY_LAST_BARS:
        return []
    band = _band()
    if band is None:
        return []
    mean, std = band
    fmean = _filter_mean()
    if fmean is None:
        return []
    if close <= mean - BAND_SIGMA * std and close < fmean:
        _entry_close = close
        amount = state.cash
        if amount < int(state.hello["fees"]["min_notional_quote_units"]):
            return []
        return [{"side": "buy", "symbol": SYMBOL,
                 "notional_quote_units": amount,
                 "max_slippage_bps": MAX_SLIPPAGE_BPS}]
    return []


makefun_bars.run(on_batch)
