# Learning Guide Level 1: The Foundation (Data)

You asked for **"Bar for Bar"**. Here is the breakdown of `data_processor.py`. This file is the "Sensory System" of your AI. Before the AI can think, it must *feel* the market.

## 1. The Setup (Dependencies)
```python
import pandas as pd
import numpy as np
```
- **Pandas (`pd`):** The "Excel of Python". It creates the Spreadsheet (DataFrame) we work on.
- **Numpy (`np`):** The "Calculator". We use it for fast math (like `where` logic).

---

## 2. Converting Time to Numbers (`Hour_Decimal`)
**Concept:** AI cannot read a clock like "14:30". It needs a number.
**The Code:**
```python
df['Hour_Decimal'] = df['Open Time'].dt.hour + (df['Open Time'].dt.minute / 60)
```
**Bar for Bar:**
1.  `df['Open Time'].dt.hour`: Extract "14" from "14:30".
2.  `df['Open Time'].dt.minute / 60`: Extract "30", divide by 60 to get "0.5".
3.  **Result:** "14.5". Now the AI knows 14.5 is close to 15.0 (Market Close), so it can learn time-based patterns.

---

## 3. Detecting Anger (`Revenge_Timer`)
**Concept:** If you enter a trade 1 minute after closing the last one, you are likely titled.
**The Code:**
```python
df['Last_Close'] = df['Close Time'].shift(1)
df['Revenge_Timer'] = (df['Open Time'] - df['Last_Close']).dt.total_seconds() / 60
```
**Bar for Bar:**
1.  `.shift(1)`: Takes the Close Time of the *previous* row and puts it next to the *current* row.
2.  `Open Time - Last_Close`: Calculates the time gap (timedelta).
3.  `.dt.total_seconds() / 60`: Converts that gap into minutes.
    -   *If Result is 2.0:* You entered 2 mins after a loss. Warning sign!
    -   *If Result is 600.0:* You waited 10 hours. You are calm.

---

## 4. The "Streak" Counter (`Losing_Streak`)
**Concept:** Losses cluster. If you lost 3 in a row, the 4th is statistically likely to be a rage trade.
**The Code:**
```python
# Create a boolean mask: 1 if Loss, 0 if Win
loss_mask = (df['PnL'] < 0).astype(int)

# Group consecutive 1s together
df['Losing_Streak'] = loss_mask.groupby((loss_mask != loss_mask.shift()).cumsum()).cumsum()
```
**Bar for Bar (The Complex Part):**
1.  `loss_mask`: Turns your PnL into a barcode `[1, 1, 1, 0, 1]`.
2.  `loss_mask != loss_mask.shift()`: Detects when the streak *changes* (e.g., from Loss to Win).
3.  `.cumsum()`: Assigns a unique ID to each "block" of streaks.
4.  **Result:** It counts up `1, 2, 3` but resets to `0` when you win.

---

## 5. The "Target" (`Is_High_Risk`)
**Concept:** We don't just want to predict "Losses". Losing is normal. We want to predict **"Stupid Losses"**.
**The Code:**
```python
bad_condition = (df['Drawdown_State'] > 5) | (df['Losing_Streak'] >= 3)
df['Is_High_Risk'] = ((df['PnL'] < 0) & bad_condition).astype(int)
```
**Bar for Bar:**
1.  We define "Stupid" as: Coding while in Drawdown OR on a Losing Streak.
2.  `&`: efficient logical "AND".
3.  **Logic:** If I lost money AND I was doing something stupid -> Mark as "1" (Target).
4.  If I lost money but I was calm -> Mark as "0" (Normal Loss). The AI learns to *ignore* normal losses.
