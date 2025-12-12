from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from ai_risk_officer import AIRiskOfficer
from ai_agent_v4 import ActiveAgent
import pandas as pd
import uvicorn
import threading

# Initialize App & Model
app = FastAPI(title="VOIDQUANT AIRO API", version="5.0")

# We use the Active Agent (V4) logic as it's the most advanced
# In production, we'd load a saved model (pickle). Here we retrain on start for demo.
print("Initializing AIRO V5 Nervous System...")
# Quick retrain on startup (Proof of Concept)
from data_processor import DataLoader
filepath = "c:/Users/jamaa/OneDrive/Documents/AIRO/Abdirahman Jama Abdi - REmodal.csv"
loader = DataLoader(filepath)
loader.load_data()
df = loader.engineer_features()
agent = ActiveAgent()
agent.train(df)
print("AIRO V5 Active & Listening.")

# Define Request Model
class TradeRequest(BaseModel):
    Hour_Decimal: float
    Losing_Streak: int
    Drawdown_State: float
    Lot_Deviation: float
    Revenge_Timer: float
    Lots: float = 1.0
    RR_Ratio: float = 2.0

@app.get("/")
def home():
    return {"status": "AIRO V5 Operational", "mode": "Active Agent"}

@app.post("/analyze_trade")
def analyze_trade(trade: TradeRequest):
    """
    Receives trade context and returns Governance Decision.
    """
    try:
        # Convert request to DataFrame
        row_dict = trade.model_dump()
        row = pd.Series(row_dict)
        
        # Get AI Decision
        size_multiplier, risk_prob = agent.get_position_sizer(row)
        
        decision = "ALLOW"
        if size_multiplier == 0:
            decision = "BLOCK"
        elif size_multiplier < 1.0:
            decision = "REDUCE_SIZE"
            
        return {
            "decision": decision,
            "risk_score": round(float(risk_prob), 4),
            "size_multiplier": round(float(size_multiplier), 2),
            "message": f"AI Risk assessment: {risk_prob:.1%}. sugg_size: {size_multiplier:.2f}x"
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

if __name__ == "__main__":
    # Run server
    uvicorn.run(app, host="127.0.0.1", port=8000)
