from typing import List
import pandas as pd
from engine.config import DEFAULT_ENGINE_CONFIG

def validate_columns(df: pd.DataFrame) -> List[str]:
    colmap = DEFAULT_ENGINE_CONFIG.colmap
    aliases = {
        "revenue": colmap.revenue,
        "expenses": colmap.expenses,
    }
    found, missing = [], []
    for key, alist in aliases.items():
        if any(a in df.columns for a in alist) or key in df.columns:
            found.append(key)
        else:
            missing.append(key)
    if missing:
        raise ValueError(f"Missing required columns: {missing}")
    return found
