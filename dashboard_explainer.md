# Dashboard Mechanics: Under the Hood

You asked to understand the **Toggles** and **Calculations**. Here is the deep dive into what happens when you move those sliders.

## 1. The Architecture Selector (The "Brain" Toggle)
When you switch between V1, V3, and V5, you are changing **how the AI thinks**.

-   **V1 (Baseline):** Uses the `model_v1` which only looks at your psychology (Streak, Time). It is blind to the market conditions.
-   **V2 (Context):** Uses `model_v2` which adds "Market Eyes". It sees Volatility. If you select this, you might see it block trades just because the market is "Choppy", even if your psychology is fine.
-   **V5 (Ultimate):** Enables the specific `AIUltimate` class which combines everything.

---

## 2. Risk Threshold (The "Border Control")
*Visible in V1/V2/V3 Modes.*

**What it calculates:**
The AI gives every trade a score from 0% to 100% (Probability of Ruin).
-   **Low Setting (0.50):** Strict. Blocking any trade with >50% doubt. You will survive, but you will miss good trades (False Positives).
-   **High Setting (0.90):** Loose. Only blocking obvious disasters. You catch more winners but might let a bad trade slip through.

**The "Optuna" Magic (V3):**
When you select V3, notice the slider locks to **0.6537**.
-   Why? Because our optimization script simulated 1000 combinations and found that `0.65` yields the most profit. Moving it higher adds risk; moving it lower kills profit.

---

## 3. Agent Sensitivity (Gamma)
*Visible in V4/V5 Modes.*

This is the most advanced control. It changes the **Dampening Function**.
Formula: $Size = 1.0 - (Risk \times Sensitivity)$

**Scenario: The AI detects High Risk (0.70)**

-   **Sensitivity = 1.0 (Gentle):**
    -   Calculation: $1.0 - (0.70 \times 1.0) = 0.30$
    -   Result: You trade **30% size**. You are still in the game, just cautious.

-   **Sensitivity = 2.0 (Aggressive):**
    -   Calculation: $1.0 - (0.70 \times 2.0) = -0.40 \to 0.0$
    -   Result: You trade **0% size**. The AI killed the trade completely because it doesn't trust you.

**How to use it:**
-   If you feel the AI is "nannying" you too much -> Slide Sensitivity **Left** (Lower).
-   If you want maximum protection -> Slide Sensitivity **Right** (Higher).

---

## 4. The "Alpha" Calculation
On the Metrics row:
> **AIRO Return: +138% (+89% Alpha)**

**Formula:**
$$
Alpha = Return_{AI} - Return_{Human}
$$
$$
89\% = 138\% - 49\%
$$
This number represents the **Pure Value Added** by the system. It is money you made *only* because the AI stopped you from losing it.
