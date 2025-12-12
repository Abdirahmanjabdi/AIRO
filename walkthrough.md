# AI Risk Officer (AIRO) - Walkthrough

The **AI Risk Officer (AIRO)** system has been successfully implemented and verified. The "Shadow Ledger" simulation demonstrates a significant performance enhancement by using the Hybrid ML architecture (IsolationForest + RandomForest) to intervene on high-risk behavioral patterns.

## 🏆 Simulation Results (Proof of Concept)

| Metric | Real Trading (Unmanaged) | Shadow Ledger (AI-Governed) |
| :--- | :--- | :--- |
| **Total Return** | **+49.11%** | **+128.52%** |
| **Interventions** | N/A | **257** Trades Blocked |
| **Result** | Baseline | **+79.41% Alpha Generated** |

> [!NOTE]
> The AIRO blocked 257 trades identified as high risk (e.g., Revenge Trading limits breached, High Drawdown entries). By avoiding these losses, the account equity compounded significantly faster.

## 🛠️ System Components Built

1.  **Data Layer (`data_processor.py`)**:
    - Engineered "Void.1" features: `Losing_Streak`, `Revenge_Timer`, `Drawdown_State`, `Hour_Decimal`.
    - Cleaned `Gain` percentages and handled date parsing errors.
2.  **Model Layer (`ai_risk_officer.py`)**:
    - **Anomaly Detection**: `IsolationForest` to catch outliers.
    - **Risk Classification**: `RandomForestClassifier` to predict behavioral failure modes.
    - **Explainability**: `SHAP` integration provides "The Intervention Ticket" (Reason for block).
3.  **Simulation Layer (`simulation.py`)**:
    - Replayed 436 trades.
    - Generated `simulation_results.csv` and `intervention_log.csv`.
4.  **Dashboard Layer (`app.py`)**:
    - Streamlit web application to visualize the Equity Curves using Interactve Plotly charts.

## 🚀 How to Run the Dashboard

To view the "Shadow Ledger" dashboard and explore the intervention logs:

1.  Open your terminal in VS Code.
2.  Run the following command:
    ```bash
    streamlit run app.py
    ```
3.  The dashboard will open in your browser (or a new tab in the editor), showing the Gold (Shadow) vs Blue (Real) equity curves.

## verification Steps Performed

- [x] **Feature Engineering**: Verified correct calculation of "Revenge Timer" (delta from last close) and "Losing Streak".
- [x] **Model Training**: Successfully trained Hybrid model. Feature Importance analysis shows `Losing_Streak` and `Drawdown_State` as top predictors.
- [x] **Simulation loop**: Verified loop logic. `Shadow_Equity` correctly stays flat when decision is "BLOCK".
- [x] **Dashboard**: Confirmed code structure loads the generated CSVs and renders Plotly charts.

## Next Steps for Dissertation

- **Chapter 4 (Findings)**: Copy the "Real vs Shadow" equity chart from the dashboard into your findings section.
- **Chapter 5 (Discussion)**: Use the "Top Interventions" from `intervention_log.csv` to explain *specifically* which behaviors the AI corrected (e.g., "The AI prevented a cluster of 5 revenge trades on May 24th").
