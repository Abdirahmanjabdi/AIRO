# Learning Guide Level 2: The Brain (Machine Learning)

Now that we have data, we need a **Brain**. This is `ai_risk_officer.py`.
This module uses a "Hybrid" approach: Two different brains working together.

## 1. The Components
```python
from sklearn.ensemble import IsolationForest, RandomForestClassifier
```
- **IsolationForest (The Watchdog):** An unsupervised model. It doesn't know what "Loss" is. It only knows what "Weird" is.
- **RandomForestClassifier (The Analyst):** A supervised model. It studies your past losses to predict future ones.

---

## 2. The Setup (`__init__`)
```python
def __init__(self, features=None):
    self.iso_forest = IsolationForest(contamination=0.05)
    self.classifier = RandomForestClassifier(n_estimators=100, max_depth=5)
```
**Bar for Bar:**
1.  `contamination=0.05`: We tell the Watchdog, "Assume 5% of my trades are freaks/errors." It will flag the top 5% weirdest rows.
2.  `n_estimators=100`: The Analyst is actually a council of 100 small brains (Decision Trees). They vote on the answer.
3.  `max_depth=5`: Each tree can only ask 5 questions (e.g., "Is Revenge > 5?", then "Is Streak > 2?", etc.). This prevents them from memorizing the data (Overfitting).

---

## 3. The Training (`train`)
```python
def train(self, df):
    X = df[self.features] # The Inputs (Streak, Time, Drawdown)
    y = df['Is_High_Risk'] # The Answer Key (1 = Bad Trade, 0 = OK)
    
    self.iso_forest.fit(X)
    self.classifier.fit(X, y)
```
**Concept:**
- `.fit(X)` for Watchdog: It builds a map of "Normal". Anything far from the cluster is an Anomaly.
- `.fit(X, y)` for Analyst: It looks at `X` and tries to guess `y`. If it sees "Streak=3" and "Time=1min", and the Answer is "1", it learns that pattern.

---

## 4. The Prediction (`predict`)
```python
def predict(self, row):
    # Transform single row into a 2D array because Scikit-Learn expects a table
    data = np.array([row[f] for f in self.features]).reshape(1, -1)
    
    # 1. Ask the Watchdog
    anomaly_score = self.iso_forest.predict(data)[0] 
    is_anomaly = anomaly_score == -1 # -1 means "Weird"
    
    # 2. Ask the Analyst
    risk_prob = self.classifier.predict_proba(data)[0][1]
    
    # 3. The Verdict
    decision = "BLOCK" if (risk_prob > 0.70 or is_anomaly) else "ALLOW"
```
**Bar for Bar:**
1.  `reshape(1, -1)`: Technical fix. The model expects a list of rows, but we only have 1 row. We wrap it.
2.  `.predict(data)`: Watchdog returns `1` (Normal) or `-1` (Weird).
3.  `.predict_proba(data)`: Analyst returns `[0.20, 0.80]`.
    -   `0.20` is chance of Class 0 (Safe).
    -   `0.80` is chance of Class 1 (Risky).
    -   We take `[0][1]` to get the **Risk Probability (0.80)**.
4.  **The Logic:** If risk > 70% OR it's a Weird Trade -> BLOCK.

---

## 5. The Explanation (`shap`)
**Concept:** The boss asks "Why did you block this?". The AI needs to point to the specific column.
```python
explainer = shap.TreeExplainer(self.classifier)
shap_values = explainer.shap_values(data)
```
- **SHAP (SHapley Additive exPlanations):** A Game Theory formula.
- It calculates: "How much did 'Losing_Streak=3' push the probability from 50% to 80%?"
- If Streak added +30%, then **Streak is the reason**.
