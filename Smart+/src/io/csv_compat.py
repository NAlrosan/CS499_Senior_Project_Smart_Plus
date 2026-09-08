from ..config import CFG
import os
import pandas as pd

def df_to_csv_if_enabled(df: pd.DataFrame, name: str) -> None:
    if not CFG.dashboard_writes_csv: 
        return
    path = os.path.join(CFG.csv_dir, name)
    df.to_csv(path, index=False)