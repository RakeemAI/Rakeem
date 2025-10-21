from pydantic import BaseModel
from typing import Optional, List, Any, Dict

class KPISummary(BaseModel):
    total_revenue: float
    total_expenses: float
    total_profit: float
    avg_profit_margin: float
    total_cash_flow: float
    net_vat: float
    zakat_due: float

class EngineOutput(BaseModel):
    kpis: KPISummary
    rows: Optional[List[Dict[str, Any]]] = None
