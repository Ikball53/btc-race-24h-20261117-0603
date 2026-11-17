[![make.fun bounty](https://make.fun/badge/btc-race-24h-20261117-0603.svg)](https://make.fun/bounty/btc-race-24h-20261117-0603)
[![make.fun rank](https://make.fun/badge/btc-race-24h-20261117-0603/Ikball53/btc-race-24h-20261117-0603/rank.svg)](https://make.fun/bounty/btc-race-24h-20261117-0603)
[![make.fun reward](https://make.fun/badge/btc-race-24h-20261117-0603/Ikball53/btc-race-24h-20261117-0603/reward.svg)](https://make.fun/bounty/btc-race-24h-20261117-0603)

# Patient Dip Buyer — cbBTC/USDC

A quiet bot for a quiet market. Bitcoin usually drifts sideways, so this bot
does not chase every wiggle: it watches the highest high of the last four
hours and only acts when the price has moved a real distance away from it.

- **Dip leg:** when the close falls at least 0.7% below the trailing
  four-hour high, buy with the full cash balance.
- **Momentum leg:** when the close pushes above that four-hour high, the
  range has broken upward, so buy with the full cash balance too.
- **Exits:** take profit at +0.8% or cut at −1.0% from the position's cost
  basis, or walk away after six hours at most.
- **Pacing:** at most four round trips in the day, fifteen minutes of rest
  after each exit, no fresh entries in the final hour. One position at a
  time, long only, fully deterministic — the same bars always give the
  same orders.

## Local dev result

Graded on the kit's published dev window with the kit's own replay engine:

- **Net PnL: +$10.06** on $1,000 paper (final cash $1,010.06)
- **Trades: 8 fills (4 round trips)**
- **Max drawdown: 1.71%**
- **Deterministic:** two runs produce identical results
