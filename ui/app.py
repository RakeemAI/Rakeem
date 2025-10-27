# ui/app.py
import os, sys, json, re
from typing import Optional, List, Dict, Any
import pandas as pd
import plotly.express as px
import streamlit as st

# ---------- Ensure repo import path ----------
REPO_ROOT = os.path.dirname(os.path.dirname(__file__))
if REPO_ROOT not in sys.path:
    sys.path.insert(0, REPO_ROOT)
from engine.forecasting_core import build_revenue_forecast

# ---------- Engine imports ----------
from engine.io import load_excel, load_csv
from engine.validate import validate_columns
from engine.compute_core import compute_core
from engine.taxes import compute_vat, compute_zakat
from engine.export import to_json

# ---------- Forecasting import (optional fallback) ----------
try:
    from engine.forecasting_core import build_revenue_forecast
except Exception:
    import pandas as _pd
    from statsmodels.tsa.holtwinters import ExponentialSmoothing as _ES

    def _prep_monthly_series(_df, _date_col="date", _val_col="revenue"):
        d = _df[[_date_col, _val_col]].copy()
        d[_date_col] = _pd.to_datetime(d[_date_col], errors="coerce")
        d = d.dropna(subset=[_date_col]).sort_values(_date_col)
        d[_date_col] = _pd.DatetimeIndex(d[_date_col]).to_period("M").to_timestamp("MS")
        d = d.drop_duplicates(subset=[_date_col], keep="last").set_index(_date_col).asfreq("MS")
        d[_val_col] = _pd.to_numeric(d[_val_col], errors="coerce").ffill().fillna(0.0)
        return d[_val_col].astype(float)

    def _forecast_series(y, periods=6):
        y = y.dropna()
        if y.size == 0:
            idx = _pd.date_range(_pd.Timestamp.today().to_period("M").to_timestamp("MS") + _pd.offsets.MonthBegin(1),
                                 periods=periods, freq="MS")
            return _pd.Series([0.0]*periods, index=idx)
        if y.nunique() <= 1 or y.size < 4:
            last = float(y.iloc[-1])
            idx = _pd.date_range(y.index.max() + _pd.offsets.MonthBegin(1), periods=periods, freq="MS")
            return _pd.Series([last]*periods, index=idx)
        try:
            fit = _ES(y, trend="add", damped_trend=True, seasonal=None).fit(optimized=True, use_brute=True)
            return fit.forecast(periods)
        except Exception:
            last = float(y.iloc[-1])
            idx = _pd.date_range(y.index.max() + _pd.offsets.MonthBegin(1), periods=periods, freq="MS")
            return _pd.Series([last]*periods, index=idx)

    def build_revenue_forecast(_df, periods=6, entity_col="entity_name"):
        if "date" not in _df.columns or "revenue" not in _df.columns:
            raise ValueError("أعمدة date / revenue مطلوبة للتنبؤ.")
        out = []
        entities = _df[entity_col].dropna().unique().tolist() if entity_col in _df.columns else ["Default"]
        for ent in entities:
            sub = _df[_df[entity_col] == ent] if entity_col in _df.columns else _df
            y = _prep_monthly_series(sub, "date", "revenue")
            fc = _forecast_series(y, periods=periods)
            _res = _pd.DataFrame({"date": fc.index, "forecast": fc.values})
            _res["lower"], _res["upper"] = _res["forecast"]*0.90, _res["forecast"]*1.10
            _res[entity_col] = ent
            out.append(_res)
        return _pd.concat(out, ignore_index=True)

# ---------- Streamlit config ----------
st.set_page_config(page_title="Rakeem", layout="wide")

# ---------- Custom CSS (RTL + numeric list fix) ----------
st.markdown("""
<style>
.block-container {padding-top:1rem; padding-bottom:2rem;}
.rtl {direction: rtl; text-align: right;}

.kpi-card {background:#f8fafc;border:1px solid #e5e7eb;border-radius:12px;padding:12px 14px;margin-bottom:10px}
.kpi-label{font-size:0.9rem;color:#64748b}
.kpi-value{font-weight:700;font-size:1.3rem}
.note{background:#fff7ed;border:1px dashed #fdba74;border-radius:10px;padding:10px 12px;margin:8px 0}
.hr{height:1px;background:#e5e7eb;margin:14px 0}

/* ===== Chat bubble ===== */
.chat-bubble{
  border:1px solid #e5e7eb;
  border-radius:14px;
  padding:10px 12px;
  margin:6px 0;
  max-width:100%;
  box-sizing:border-box;
  direction: rtl;
  text-align: right;
  unicode-bidi: plaintext;
  overflow-wrap:anywhere;
  word-break:break-word;
}
.chat-bubble *{
  overflow-wrap:anywhere;
  word-break:break-word;
}
.chat-bubble.user{background:#ecfeff}
.chat-bubble.assistant{background:#f8fafc}

/* ✅ تعداد رقمي أنيق داخل الصندوق */
.chat-bubble ul, .chat-bubble ol {
  list-style: none;
  counter-reset: item;
  margin: 6px 0;
  padding: 0;
}
.chat-bubble li {
  position: relative;
  margin: 6px 0;
  padding-right: 1.6rem;
}
.chat-bubble li::before {
  counter-increment: item;
  content: counter(item) ".";
  position: absolute;
  right: 0;
  top: 0;
  color: #1e3a8a;
  font-weight: 700;
}

/* شيبس لعناوين Topic/Question/Answer/Source/Example */
.label-chip{
  display:inline-block;
  background:#eef2ff; color:#111827;
  border:1px solid #c7d2fe; border-radius:9999px;
  padding:2px 8px;
  font-size:.80rem;
  font-weight:700;
  line-height:1.1;
  margin:0 6px 6px 0;
  vertical-align:middle;
}

/* صناديق التنبيه RTL */
[data-testid="stAlert"] { direction: rtl; text-align: right; }
</style>
""", unsafe_allow_html=True)

def sar(x: float) -> str:
    try:
        return f"{float(x):,.0f} ريال"
    except Exception:
        return "—"

# ---------- Header ----------
st.title("ركيم — Rakeem (SME Financial Assistant) 🇸🇦")
st.markdown("""
<div class="rtl">
  <p><b>📂 ارفع ملفك المالي</b> لعرض مؤشرات الأداء، وحساب ضريبة القيمة المضافة والزكاة، مع رسوم بيانية مبسطة.</p>
  <div class="note">تنبيه: الأنواع المسموح بها: Excel (.xlsx) و CSV (.csv).</div>
</div>
<div class="hr"></div>
<p><b>📂Upload your financial file</b> to see key performance metrics, VAT and Zakat, with simple visual charts.</p>
<div class="note">Note: Supported formats are Excel (.xlsx) and CSV (.csv) only.</div>
""", unsafe_allow_html=True)

# ---------- Sidebar ----------
st.sidebar.header("📂 رفع الملف المالي")
uploaded_file = st.sidebar.file_uploader(
    "Upload Excel (.xlsx/.xls) or CSV", type=["xlsx", "xls", "csv"]
)
if uploaded_file is None:
    st.info("للبدء من فضلك ارفع الملف من الشريط الجانبي.")
    st.stop()

# ---------- Load file ----------
try:
    ext = uploaded_file.name.split(".")[-1].lower()
    if ext in ("xlsx", "xls"):
        df_raw = load_excel(uploaded_file, sheet=0)
    elif ext == "csv":
        df_raw = load_csv(uploaded_file)
    else:
        st.error("صيغة الملف غير مدعومة.")
        st.stop()
except Exception as e:
    st.error(f"خطأ أثناء قراءة الملف: {e}")
    st.stop()

# ---------- Validate ----------
try:
    validate_columns(df_raw)
except Exception as e:
    st.error(f"خطأ في التحقق من الأعمدة: {e}")
    st.stop()

# ---------- Compute ----------
try:
    df = compute_core(df_raw)
except Exception as e:
    st.error(f"خطأ أثناء الحسابات الأساسية: {e}")
    st.stop()

try:
    net_vat = float(compute_vat(df))
except Exception:
    net_vat = 0.0
try:
    zakat_due = float(compute_zakat(df))
except Exception:
    zakat_due = 0.0

# ---------- Engine Output ----------
try:
    engine_json = to_json(df, include_rows=False)
    engine_output = json.loads(engine_json)
except Exception:
    engine_output = None

# ---------- KPIs ----------
total_revenue = float(df.get("revenue", pd.Series([0])).fillna(0).sum())
total_expenses = float(df.get("expenses", pd.Series([0])).fillna(0).sum())
total_profit   = float(df.get("profit", pd.Series([0])).fillna(0).sum())
total_cashflow = float(df.get("cash_flow", pd.Series([0])).fillna(0).sum())

k1, k2, k3, k4 = st.columns(4)
with k1: st.markdown(f'<div class="kpi-card rtl"><div class="kpi-label">إجمالي الإيرادات</div><div class="kpi-value">{sar(total_revenue)}</div></div>', unsafe_allow_html=True)
with k2: st.markdown(f'<div class="kpi-card rtl"><div class="kpi-label">إجمالي المصروفات</div><div class="kpi-value">{sar(total_expenses)}</div></div>', unsafe_allow_html=True)
with k3: st.markdown(f'<div class="kpi-card rtl"><div class="kpi-label">صافي الربح</div><div class="kpi-value">{sar(total_profit)}</div></div>', unsafe_allow_html=True)
with k4: st.markdown(f'<div class="kpi-card rtl"><div class="kpi-label">التدفق النقدي</div><div class="kpi-value">{sar(total_cashflow)}</div></div>', unsafe_allow_html=True)

t1, t2 = st.columns(2)
with t1: st.markdown(f'<div class="kpi-card rtl"><div class="kpi-label">صافي ضريبة القيمة المضافة</div><div class="kpi-value">{sar(net_vat)}</div></div>', unsafe_allow_html=True)
with t2: st.markdown(f'<div class="kpi-card rtl"><div class="kpi-label">الزكاة المستحقة</div><div class="kpi-value">{sar(zakat_due)}</div></div>', unsafe_allow_html=True)

# ---------- Summary ----------
date_min = pd.to_datetime(df["date"]).min() if "date" in df.columns else None
date_max = pd.to_datetime(df["date"]).max() if "date" in df.columns else None
st.markdown(f"""
<div class="rtl">
  <h4>📊 ملخص مالي مختصر</h4>
  <ul>
    <li>📈 إجمالي الإيرادات: <b>{sar(total_revenue)}</b></li>
    <li>💸 إجمالي المصروفات: <b>{sar(total_expenses)}</b></li>
    <li>💰 صافي الربح: <b>{sar(total_profit)}</b></li>
    <li>💧 التدفق النقدي: <b>{sar(total_cashflow)}</b></li>
    <li>🗓 الفترة: <b>{date_min:%d-%m-%Y}</b> → <b>{date_max:%d-%m-%Y}</b></li>
  </ul>
</div>
""", unsafe_allow_html=True)

# ---------- Charts ----------
st.markdown('<div class="rtl"><h4>📈 الاتجاهات الشهرية</h4></div>', unsafe_allow_html=True)
tabs = st.tabs(["الإيرادات", "المصروفات", "الربح"])
with tabs[0]: st.plotly_chart(px.line(df, x="date", y="revenue", title="الإيرادات"), use_container_width=True)
with tabs[1]: st.plotly_chart(px.line(df, x="date", y="expenses", title="المصروفات"), use_container_width=True)
with tabs[2]: st.plotly_chart(px.line(df, x="date", y="profit", title="الربح"), use_container_width=True)

# ---------- Helpers ----------
def stylize_labels(text: str) -> str:
    if not isinstance(text, str):
        return text
    text = re.sub(r"\[\s*(Topic|Question|Answer|Example|Source)\s*\]", r"\1", text)
    for lab in ["Topic", "Question", "Answer", "Source", "Example"]:
        text = re.sub(rf"\b{lab}\b", f'<span class="label-chip"><b>{lab}</b></span>', text)
    return text

def normalize_fin_summary(text: str) -> str:
    if not isinstance(text, str):
        return text
    text = re.sub(r"\+\s*ملخص\s+مالي\s+مختصر\s[:\-–]\s\*+", r"<b>📊 ملخص مالي مختصر</b>", text)
    pattern = (
        r"(إجمالي الإيرادات:\s*[^-\n]+)\s*-\s*"
        r"(إجمالي المصروفات:\s*[^-\n]+)\s*-\s*"
        r"(صافي الربح:\s*[^-\n]+)\s*-\s*"
        r"(التدفق النقدي:\s*[^-\n]+)"
    )
    def _to_list(m):
        items = [m.group(i) for i in range(1, 5)]
        lis = "".join(f"<li>{it}</li>" for it in items)
        return ('<ul>' + lis + "</ul>")
    text = re.sub(pattern, _to_list, text)
    text = text.replace("إجمالي الإيرادات:", "📈 إجمالي الإيرادات:")
    text = text.replace("إجمالي المصروفات:", "💸 إجمالي المصروفات:")
    text = text.replace("صافي الربح:", "💰 صافي الربح:")
    text = text.replace("التدفق النقدي:", "💧 التدفق النقدي:")
    return text

def format_assistant_html(content: str) -> str:
    return stylize_labels(normalize_fin_summary(content))

def render_sources(sources: List[str]) -> None:
    if not sources:
        return
    chip_parts = []
    for s in sources:
        label = (s or "").strip()
        if label == "ZATCA":
            chip_parts.append(
                "<a href='https://zatca.gov.sa' target='_blank' "
                "class='label-chip' style='text-decoration:none; color:inherit;'>"
                "<b>ZATCA</b></a>"
            )
        else:
            chip_parts.append(f"<span class='label-chip'><b>{label}</b></span>")
    chips = "".join(chip_parts)
    st.markdown(f"<div class='rtl'><b>المصادر:</b> {chips}</div>", unsafe_allow_html=True)

# ---------- Forecast (expander) ----------
st.markdown('<div class="hr"></div>', unsafe_allow_html=True)
with st.expander("🔮 التنبؤ المالي (افتح للعرض)", expanded=False):
    st.markdown('<div class="rtl"><h4>تنـبؤ الإيرادات (Holt-Winters)</h4></div>', unsafe_allow_html=True)

    cols = st.columns(3)
    with cols[0]:
        periods = st.slider("عدد الأشهر القادمة", min_value=3, max_value=12, value=6, step=1)

    has_entity = "entity_name" in df.columns

    
    def _compute_forecast_now(_df, _periods):
        try:
            return build_revenue_forecast(_df, periods=_periods)
        except Exception as e:
            raise RuntimeError(str(e))

    try:
        fc_all = _compute_forecast_now(df, periods)

        if has_entity and "entity_name" in fc_all.columns:
            entity_options = sorted(df["entity_name"].dropna().astype(str).unique().tolist())
            with cols[1]:
                entity = st.selectbox("الشركة", options=entity_options, index=0)
            fc_ent = fc_all[fc_all["entity_name"].astype(str) == str(entity)].copy()
            hist = df[df["entity_name"].astype(str) == str(entity)][["date", "revenue"]].copy()
        else:
            fc_ent = fc_all.copy()
            hist = df[["date", "revenue"]].copy()

        
        hist["date"] = pd.to_datetime(hist["date"], errors="coerce")
        hist = hist.dropna(subset=["date"]).sort_values("date")
        fc_ent["date"] = pd.to_datetime(fc_ent["date"], errors="coerce")
        fc_ent = fc_ent.dropna(subset=["date"]).sort_values("date")

        
        import plotly.graph_objects as go
        fig = go.Figure()
        fig.add_trace(go.Scatter(
            x=hist["date"], y=hist["revenue"],
            mode="lines+markers", name="الإيرادات التاريخية"
        ))
        fig.add_trace(go.Scatter(
            x=fc_ent["date"], y=fc_ent["forecast"],
            mode="lines+markers",
            name="التنبؤ",
            line=dict(dash="dash", width=3, color="#E11D48"),   # أحمر كرِز
            marker=dict(color="#E11D48", size=6)
        ))

        # نضمن أن محور X يشمل التواريخ المستقبلية كلها
        if len(hist) and len(fc_ent):
            x_min = hist["date"].min()
            x_max = fc_ent["date"].max()
            fig.update_xaxes(range=[x_min, x_max + pd.Timedelta(days=5)])

        fig.update_layout(
            height=420, margin=dict(l=10, r=10, t=30, b=10),
            xaxis_title="التاريخ", yaxis_title="الإيرادات",
            legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1)
        )
        st.plotly_chart(fig, use_container_width=True)

        # توصيات مبسّطة
        st.markdown("<div class='rtl'><h5>💡 توصيات سريعة</h5></div>", unsafe_allow_html=True)
        tips = []
        if len(fc_ent) >= 2:
            base = max(float(fc_ent["forecast"].iloc[0]), 1e-9)
            growth = (float(fc_ent["forecast"].iloc[-1]) - base) / base
            if growth > 0.10:
                tips.append("اتجاه نمو متوقع ↑ — زيدي المخزون/الطاقة الإنتاجية وخططي للسيولة.")
            elif growth < -0.10:
                tips.append("اتجاه هبوط متوقع ↓ — راجعي التسعير والتسويق وخفّضي المصروفات المتغيرة.")
        recent_hist = hist.tail(3)["revenue"].mean() if len(hist) else 0
        last_fc = float(fc_ent["forecast"].iloc[-1]) if len(fc_ent) else 0
        if recent_hist > 0:
            delta = (last_fc - recent_hist) / recent_hist
            if delta > 0.15:
                tips.append("التنبؤ أعلى من متوسط الأشهر الأخيرة بـ+15% — استعدّي لطلب أعلى وخططي للسيولة.")
            elif delta < -0.15:
                tips.append("التنبؤ أقل من المتوسط بـ15%− — اضبطي التكاليف الثابتة وراقبي التدفق النقدي.")
        if not tips:
            tips.append("لا توجد إشارات مقلقة حاليًا؛ استمري بالمراقبة الشهرية.")
        st.markdown("<div class='chat-bubble assistant rtl'>" + "<br>".join(f"• {t}" for t in tips) + "</div>", unsafe_allow_html=True)

    except Exception as _e:
        st.warning(f"تعذر حساب التنبؤ: {_e}")

# ---------- Chat Section ----------
st.markdown('<div class="hr"></div>', unsafe_allow_html=True)
st.markdown('<div class="rtl"><h3>💬 المحادثة الذكية</h3></div>', unsafe_allow_html=True)

_backend = None
try:
    from llm.run import chat_answer as _chain_chat_answer
    _backend = ("chain", _chain_chat_answer)
except Exception:
    try:
        from llm.simple_backend import answer as _simple_answer
        _backend = ("simple", _simple_answer)
    except Exception:
        _backend = None
        st.warning("⚠ لا يوجد باك-إند متاح للشات (Chain/Simple).")

def _df_ctx():
    for key in ("df","financial_df","computed_df","results_df"):
        if key in globals() and "DataFrame" in str(type(globals()[key])): return globals()[key]
        if key in st.session_state and "DataFrame" in str(type(st.session_state[key])): return st.session_state[key]
        # fallback
    return df

if "chat_messages" not in st.session_state:
    st.session_state.chat_messages = [
        {"role":"assistant","content":"مرحبًا! ارفعي الملف ثم اسألي عن الربحية أو الضريبة أو الزكاة.", "sources":[]}
    ]

for m in st.session_state.chat_messages:
    cls = "assistant" if m["role"] == "assistant" else "user"
    if m["role"] == "assistant":
        html = format_assistant_html(m["content"])
        st.markdown(f'<div class="chat-bubble {cls} rtl">{html}</div>', unsafe_allow_html=True)
        render_sources(m.get("sources", []))
    else:
        st.markdown(f'<div class="chat-bubble {cls} rtl">{m["content"]}</div>', unsafe_allow_html=True)

user_q = st.chat_input("اكتبي سؤالك هنا…")
if user_q:
    st.session_state.chat_messages.append({"role":"user","content":user_q})
    st.markdown(f'<div class="chat-bubble user rtl">{user_q}</div>', unsafe_allow_html=True)
    try:
        if not _backend:
            raise RuntimeError("لا يوجد باك-إند للشات.")
        mode, fn = _backend
        reply_text, sources = (fn(user_q, df=_df_ctx()) if mode=="simple"
                               else fn(user_q, df=_df_ctx()))
        st.session_state.chat_messages.append({
            "role":"assistant",
            "content": reply_text,
            "sources": sources or []
        })
        st.markdown(
            f'<div class="chat-bubble assistant rtl">{format_assistant_html(reply_text)}</div>',
            unsafe_allow_html=True
        )
        render_sources(sources or [])
    except Exception as e:
        st.error(f"تعذر توليد الرد: {e}")
