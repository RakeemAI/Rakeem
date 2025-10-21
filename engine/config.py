from __future__ import annotations
from dataclasses import dataclass, field
from typing import Tuple

@dataclass(frozen=True)
class ColumnMap:
    date: Tuple[str, ...] = ("date", "month", "period")
    revenue: Tuple[str, ...] = ("revenue", "sales", "turnover")
    expenses: Tuple[str, ...] = ("expenses", "costs", "opex", "total_expenses")
    vat_collected: Tuple[str, ...] = ("vat_collected", "output_vat", "vat_out")
    vat_paid: Tuple[str, ...] = ("vat_paid", "input_vat", "vat_in")
    opening_cash: Tuple[str, ...] = ("opening_cash", "cash_opening", "begin_cash")
    closing_cash: Tuple[str, ...] = ("closing_cash", "cash_closing", "end_cash")
    zakat_base: Tuple[str, ...] = ("zakat_base", "zakatable_base")

DEFAULT_COL_MAP = ColumnMap()

@dataclass(frozen=True)
class TaxConfig:
    vat_rate: float = 0.15
    zakat_rate: float = 0.025
    zakat_mode: str = "base_if_available_else_zero"

DEFAULT_TAX = TaxConfig()

@dataclass(frozen=True)
class EngineConfig:
    colmap: ColumnMap = field(default_factory=lambda: DEFAULT_COL_MAP)
    taxes: TaxConfig = field(default_factory=lambda: DEFAULT_TAX)
    required_min: Tuple[str, ...] = ("revenue", "expenses")
    date_col_fallback: str = "date"

DEFAULT_ENGINE_CONFIG = EngineConfig()
