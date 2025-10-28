from generator.report_generator import generate_report
import sys, traceback
from pathlib import Path
import pandas as pd
from engine.rules_engine import make_recommendations
import forecast_module as fm

ROOT = Path(__file__).parent
DATA = ROOT / "data"

def load_or_mock_data():
    csv_path = DATA / "forecast_results.csv"
    if csv_path.exists():
        df = pd.read_csv(csv_path)
        if "date" in df.columns:
            df["date"] = pd.to_datetime(df["date"])
        return df
    print("⚠️ لا يوجد data/forecast_results.csv — سأولّد بيانات تجريبية.")
    dates = pd.date_range("2024-01-01", periods=18, freq="MS")
    return pd.DataFrame({
        "date": dates,
        "revenue": (100000 + (dates.month * 2500)).astype(float),
        "expenses": (70000 + (dates.month * 2000)).astype(float),
    })

def run_pipeline(periods: int = 6) -> dict:
    raw_df = None
    try:
        raw_df = fm.load_input_csv()
    except Exception:
        pass
    if raw_df is None or raw_df.empty:
        raw_df = load_or_mock_data()

    out = fm.run_forecast(raw_df, periods=periods)
    forecast_df: pd.DataFrame = out["forecast"]
    if forecast_df is None or forecast_df.empty:
        raise RuntimeError("لم يتم توليد أي توقعات.")

    recs = make_recommendations(forecast_df)
    tail = forecast_df.tail(12).copy()
    tail["profit"] = tail.get("revenue", 0) - tail.get("expenses", 0)

    metrics = {
        "total_revenue": float(tail["revenue"].sum()),
        "total_expenses": float(tail["expenses"].sum()),
        "total_profit": float(tail["profit"].sum()),
        "total_cashflow": float(tail["profit"].sum()),
        "net_vat": float((tail["revenue"].sum() - tail["expenses"].sum()) * 0.15),
        "zakat_due": float(max(tail["profit"].sum() * 0.025, 0.0)),
    }

    tables = {"توقعات الإيرادات": tail[["date","revenue","expenses","profit"]]}

    pdf_path = generate_financial_report(
        company_name="ركيم المالية",
        report_title="التقرير المالي الشامل",
        metrics=metrics,
        recommendations=recs,
        data_tables=tables,
        template_path=str(ROOT / "generator" / "report_template.html"),
        output_pdf=str(ROOT / "financial_report.pdf"),
    )

    return {"pdf_path": str(pdf_path)}

def main():
    try:
        print("✅ البيئة جاهزة.\n🚀 تشغيل خط الأنابيب...")
        result = run_pipeline(periods=6)
        print(f"\n🎉 تم إنشاء التقرير بنجاح: {result['pdf_path']}")
    except Exception:
        print("💥 حدث خطأ أثناء التشغيل:")
        print(traceback.format_exc())

if __name__ == "__main__":
    main()
