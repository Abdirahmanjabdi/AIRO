import pandas as pd
import numpy as np

# ==============================================================================
# MODULE: DATA PROCESSOR (The "Sensory System")
# PURPOSE: Loads raw trade history and converts it into "Features" the AI can understand.
# ==============================================================================

class DataLoader:
    def __init__(self, filepath):
        """
        Initialize the loader with the path to your CSV file.
        filepath: Location of 'Abdirahman Jama Abdi - REmodal.csv'
        """
        self.filepath = filepath
        self.df = None # Placeholder for the data (DataFrame)

    def load_data(self):
        """Loads CSV and performs basic cleaning (removing % signs, fixing dates)."""
        # 1. Read CSV into a Pandas DataFrame
        self.df = pd.read_csv(self.filepath)
        
        # 2. Clean 'Gain' column
        # Raw data looks like "1.5%". Machine needs "1.5".
        # We strip the '%' string and convert to float (decimal number).
        if self.df['Gain'].dtype == object:
            self.df['Gain'] = self.df['Gain'].str.replace('%', '').astype(float)
            
        # 3. Parse Dates
        # Convert text timestamps ("2024-05-20 14:00") into Python DateTime objects.
        # errors='coerce' means: If a date is impossible (e.g. Feb 30th), turn it into NaT (Not a Time)
        self.df['Open Time'] = pd.to_datetime(self.df['Open Time'], errors='coerce')
        self.df['Close Time'] = pd.to_datetime(self.df['Close Time'], errors='coerce')
        
        # 4. Remove bad data
        # Drop rows where Time is NaT (the errors from step 3)
        self.df = self.df.dropna(subset=['Open Time', 'Close Time'])
        
        # Sort chronologically (Oldest first) to ensure 'Losing Streak' math works correctly
        self.df = self.df.sort_values('Open Time').reset_index(drop=True)
        return self.df

    def engineer_features(self):
        """
        Creates the 'Void.1' Behavioral Features. 
        This is where we translate 'Psychology' into 'Math'.
        """
        if self.df is None: return None
        df = self.df.copy()
        
        # FEATURE 1: Hour Decimal
        # AI handles "14.5" better than "14:30". 
        # Logic: Hour + (Minute / 60)
        df['Hour_Decimal'] = df['Open Time'].dt.hour + (df['Open Time'].dt.minute / 60)
        
        # FEATURE 2: Revenge Timer (The "Tilt" Detector)
        # Logic: Time difference between NOW (Open) and Previous Trade (Close).
        # .shift(1) moves the column down by 1, allowing us to see the PAST row.
        df['Last_Close'] = df['Close Time'].shift(1)
        # Calculate gap in minutes
        df['Revenge_Timer'] = (df['Open Time'] - df['Last_Close']).dt.total_seconds() / 60
        # Fill the very first trade (which has no previous trade) with a large number (9999) so it's not marked as revenge
        df['Revenge_Timer'] = df['Revenge_Timer'].fillna(9999)

        # FEATURE 3: Losing Streak (Pattern Recognition)
        # Logic: Count continuous 'Losses' (PnL < 0).
        # We create a mask (1 for Loss, 0 for Win).
        loss_mask = (df['PnL'] < 0).astype(int)
        # Complex Pandas magic: Group by "Changes in Streak" and count size of group.
        # Effectively: [L, L, W, L] -> [1, 2, 0, 1]
        df['Losing_Streak'] = loss_mask.groupby((loss_mask != loss_mask.shift()).cumsum()).cumsum()

        # FEATURE 4: Drawdown State (Context)
        # Logic: How much money have we lost from the peak? (High Watermark)
        # .cumsum() tracks running total PnL.
        df['Equity_Curve'] = df['PnL'].cumsum()
        df['Peak_Equity'] = df['Equity_Curve'].cummax() # Highest point reached so far
        # Drawdown is the distance from Peak to Current
        df['Drawdown_State'] = df['Peak_Equity'] - df['Equity_Curve']

        # FEATURE 5: Lot Deviation (Fat Finger Detector)
        # Logic: Is this trade huge compared to my normal size?
        # Z-Score: (Current lots - Average lots) / Standard Deviation
        rolling_mean = df['Lots'].rolling(20).mean() # Avg of last 20 trades
        rolling_std = df['Lots'].rolling(20).std()   # Volatility of size
        df['Lot_Deviation'] = (df['Lots'] - rolling_mean) / rolling_std
        df['Lot_Deviation'] = df['Lot_Deviation'].fillna(0) # Handle start of data

        # --- THE TARGET LABEL (What we want to predict) ---
        # We don't just predict "Losses". We predict "BAD BEHAVIOR".
        # Logic: Loss AND (High Drawdown OR High Streak OR Revenge Entry)
        bad_condition = (df['Drawdown_State'] > 5) | (df['Losing_Streak'] >= 3) | (df['Revenge_Timer'] < 15)
        df['Is_High_Risk'] = ((df['PnL'] < 0) & bad_condition).astype(int)

        self.df = df
        return df

    def engineer_context_features(self):
        """
        Creates 'Market Regime' features (V2 Update).
        Detects if market is Volatile or Trending.
        """
        df = self.df.copy()
        
        # FEATURE 6: Realized Volatility (The "Chop" Detector)
        # Since we don't have Candle High/Low, we use the Trade Range (Close - Open).
        # Logic: If ranges are huge, market is volatile.
        df['Trade_Range'] = (df['Close Price'] - df['Open Price']).abs()
        df['Realized_Vol_20'] = df['Trade_Range'].rolling(20).std().fillna(0)
        
        # FEATURE 7: Trend Momentum
        # Logic: Directional drift between trade entries.
        df['Price_Change'] = df['Open Price'].diff()
        df['Trend_Momentum'] = df['Price_Change'].rolling(20).mean().abs().fillna(0)
        
        self.df = df
        return df
