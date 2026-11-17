[![make.fun bounty](https://make.fun/badge/btc-race-24h-20261117-0603.svg)](https://make.fun/bounty/btc-race-24h-20261117-0603)
[![make.fun rank](https://make.fun/badge/btc-race-24h-20261117-0603/Ikball53/btc-race-24h-20261117-0603/rank.svg)](https://make.fun/bounty/btc-race-24h-20261117-0603)
[![make.fun reward](https://make.fun/badge/btc-race-24h-20261117-0603/Ikball53/btc-race-24h-20261117-0603/reward.svg)](https://make.fun/bounty/btc-race-24h-20261117-0603)

# Drift Breakout Bot — cbBTC/USDC

A trend-breakout trading bot for [make.fun's "Race a BTC trading bot live for 24 hours" bounty](https://make.fun/bounty/btc-race-24h-20261117-0603). It trades Coinbase Wrapped BTC (cbBTC) against USDC on 1-minute on-chain bars, starting from $1,000 of paper money, long only.

## How it trades

The bot waits for a genuine push instead of guessing every wiggle. It only buys when the tape agrees on three counts: price sits above both a quick (10-bar) and a slow (30-bar) exponential average, the last 30 minutes already drifted up, and the close prints a fresh 30-bar high on a strong 20-minute rise. A second, quieter trigger buys a pullback that has just climbed back above its quick average while the wider drift still points up.

Once in, it banks the move with a wide take-profit (180 bps), cuts the trade quickly on a tight stop (60 bps), trails the peak once the trade is comfortably ahead, and walks away after 360 bars so no position drifts through a reversal. One position at a time, full cash on each entry, no entries in the final hour, and a short breather after every exit so a whipsaw cannot re-enter on the same bar.

Everything is deterministic: the same bars always produce the same orders. No clock, no network, no files outside the repository, standard library only.

## Local dev result

Graded on the frozen dev window with the kit's official harness: **net PnL +$5.06 USDC**, 4 round trips (7 trades), max drawdown 1.49%, fees $3.21 — and still +$1.86 with every fee doubled.
