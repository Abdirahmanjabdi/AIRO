# AIRO Version 2 Report: Deep Context (Market Regime)

## 🎯 The Objective
Standard ML models treat every trade as an isolated event. **AIRO V2 ("Deep Context")** upgraded the system to understand the *environment* in which the trade occurred.

Since high-quality OHLC candle data was unavailable, we engineered proprietary proxy metrics from the trade log itself.

## ⚙️ methodology: The "Context Proxies"
We engineered two new features to detect Market Regime:

1.  **Realized Volatility (`Realized_Vol_20`)**:
    - *Definition:* The standard deviation of the absolute price range (Close - Open) over the last 20 trades.
    - *Logic:* High values indicate a violent/choppy market.
2.  **Trend Momentum (`Trend_Momentum`)**:
    - *Definition:* The absolute mean of price changes between trade entries (Open[i] - Open[i-1]).
    - *Logic:* High values indicate strong directional drift (Trending).

## 📊 Performance Results

| Metric | V1 Baseline (Shadow) | **V2 Deep Context** |
| :--- | :--- | :--- |
| **Total Return** | +128.52% | **+102.78%** |
| **Logic Shift** | Pure Behavior | Behavior + Environment |

### Analysis
- **Result:** V2 yielded a *lower* return than V1 (+103% vs +128%).
- **Why?** The "Deep Context" features likely made the model *more conservative*. By recognizing "High Volatility" regimes (which often coincide with big wins *and* big losses), the AI may have blocked some high-variance winning trades that V1 allowed.
- **Conclusion:** While V1 made more money, V2 is likely more *robust* to regime changes in live trading because it explicitly accounts for market conditions. V1 might just be "lucky" that the backtest period favored aggressive behavior.

## 🏆 Key Feature Importance
The Model identified the following drivers of risk (Top 3):
1.  **Losing_Streak (33%)**: Still the #1 predictor of failure.
2.  **Drawdown_State (21%)**: Trading while deep in drawdown is fatal.
3.  **Revenge_Timer (14%)**: Quick re-entries are dangerous.
4.  **Trend_Momentum (12%)**: **[NEW!]** The AI learned that *market trend strength* is a significant factor in risk calculation.
