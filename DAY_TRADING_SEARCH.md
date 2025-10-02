# Day Trading Strategy Search

**Goal:** Find a strategy with 1-2 week maximum drawdown duration suitable for day trading

**Key Requirements:**
- Max drawdown duration: 1-2 weeks
- Win rate: 45-60% (psychologically manageable)
- Use RMM to filter out unfavorable conditions
- Any timeframe, any instrument, any strategy type

**Strategy Types to Test:**
1. Mean reversion (RSI oversold/overbought)
2. Momentum breakouts (volume + price)
3. Range trading (Bollinger Bands)
4. Support/Resistance bounces
5. VWAP reversion
6. Multiple timeframe confirmation

**Instruments to Test:**
- EUR/USD, GBP/USD, USD/JPY (majors - tight spreads)
- EUR/JPY, GBP/JPY (crosses - more volatility)

**Timeframes to Test:**
- 5m, 15m, 30m (day trading ranges)
- 1H (swing day trading)

**RMM Strategy:**
- Use ADX to identify ranging vs trending markets
- Trade mean reversion ONLY in ranges (ADX < 25)
- Trade breakouts ONLY in trends (ADX > 25)
- Or: separate strategies for each regime

Starting search...
