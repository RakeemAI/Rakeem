# ui/app.py
import os, sys, json, re
from typing import Optional, List, Dict, Any
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

# ---------- Ensure repo import path ----------
REPO_ROOT = os.path.dirname(os.path.dirname(__file__))
GEN_DIR = os.path.join(REPO_ROOT, "generator")
if REPO_ROOT not in sys.path:
    sys.path.insert(0, REPO_ROOT)

# ---------- Engine imports ----------
from engine.io import load_excel, load_csv
from engine.validate import validate_columns
from engine.compute_core import compute_core
from engine.taxes import compute_vat, compute_zakat
from engine.export import to_json

# ---------- Forecasting (with fallback) ----------
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

# ---------- THEME / CSS ----------
PRIMARY = "#0b3a75"     # أزرق داكن
ACCENT = "#ffcc66"      # برتقالي هادئ
MUTED  = "#64748b"      # رمادي أزرق
DANGER = "#E11D48"      # أحمر توكيد
BG_CARD = "#ffffff"

st.markdown("""
<style>
/* ====== Layout basics ====== */
.block-container {padding-top:.8rem; padding-bottom:2rem;}
.rtl {direction: rtl; text-align: right;}

/* ====== Header ====== */
.header-wrap{
  background: linear-gradient(135deg,#002147 0%,#004a8f 100%);
  color:#fff; border-radius:14px; padding:18px 20px; margin-bottom:14px;
  box-shadow: 0 4px 20px rgba(0,0,0,.08);
}
.header-title{margin:0; font-size:28px; font-weight:800; letter-spacing:.3px}
.header-sub{opacity:.95; margin:6px 0 10px; font-weight:600}
.badge-date{display:inline-block; background:#ffcc66; color:#151515; padding:4px 10px;
  border-radius:9999px; font-weight:800; font-size:13px}

/* ====== KPI cards ====== */
.kpi-grid{display:grid; grid-template-columns: repeat(4, minmax(0,1fr)); gap:12px; margin:10px 0 2px;}
.kpi-card{background:#fff; border:1px solid #e5e7eb; border-radius:14px; padding:12px 14px;
  box-shadow:0 2px 10px rgba(0,0,0,.03);}
.kpi-top{display:flex; align-items:center; justify-content:space-between; margin-bottom:6px}
.kpi-label{font-size:.92rem; color:#64748b; font-weight:700}
.kpi-ico{font-size:18px; opacity:.85}
.kpi-value{font-weight:800; font-size:1.35rem; color:#0f172a;}

/* ====== Section title ====== */
.sec-title{
  color:#0b3a75; font-size:18px; margin:0 0 10px;
  padding-bottom:8px; border-bottom:2px solid #ffcc66; font-weight:900;
}

/* ====== Summary card (نفس ستايل الصفحة) ====== */
.summary-card{
  background:#f8fafc; border:1px solid #e5e7eb; border-radius:12px;
  padding:12px 14px; margin-top:6px; box-shadow:0 2px 8px rgba(0,0,0,.03);
}
.summary-card ul{margin:8px 0 0; padding:0 20px; list-style: disc;}
.summary-card li{margin:6px 0;}

/* ====== Chat ====== */
.chat-bubble{
  background:#ffffff; border:1px solid #e5e7eb; border-radius:14px; padding:10px 12px; margin:10px 0;
  direction: rtl; text-align: right; unicode-bidi: plaintext; box-shadow:0 1px 6px rgba(0,0,0,.04);
}
.chat-bubble.assistant{border-right:4px solid #0b3a75;}
.chat-bubble.user{border-right:4px solid #16a34a; background:#f7fff9;}
.msg-header{display:flex; align-items:center; gap:8px; margin-bottom:6px;}
.role-pill{background:#eef2ff; color:#0b3a75; border:1px solid #c7d2fe;
  font-weight:800; font-size:.72rem; padding:4px 10px; border-radius:9999px;}
.msg-body{color:#111827; font-weight:500; line-height:1.7;}
.msg-body b{font-weight:700}

/* ✅ قوائم داخل ردود الشات: bullets داخلة */
.msg-body ul{list-style: disc; margin:6px 0 0; padding-right:22px;}
.msg-body li{margin:4px 0;}

/* ====== Inline chips (Topic/Question/Answer/Source/Example) ====== */
.chips-wrap{margin:6px 0 0;}
.chip{
  display:inline-flex; align-items:center; justify-content:center;
  border:1px solid #cbd5e1; background:#f1f5f9; color:#111827;
  font-weight:700; font-size:.75rem; padding:3px 8px; border-radius:9999px;
  margin:0 6px 6px 0;
}
.chip.topic{background:#e0e7ff; border-color:#0B3A75;;}      /* Topic صار chip مو دائرة */
.chip.question{background:#e6fffb; border-color:#99f6e4;}
.chip.answer{background:#fff7ed; border-color:#fde68a;}
.chip.source{background:#eef2ff; border-color:#c7d2fe;}
.chip.example{background:#fef2f2; border-color:#fecaca;}

/* ====== Alerts RTL ====== */
[data-testid="stAlert"]{direction: rtl; text-align: right;}

/* ====== Responsive ====== */
@media (max-width: 1100px){ .kpi-grid{grid-template-columns: repeat(2, 1fr);} }
@media (max-width: 700px){ .kpi-grid{grid-template-columns: 1fr;} }
</style>
""", unsafe_allow_html=True)

def sar(x: float) -> str:
    try:
        return f"{float(x):,.0f} ريال"
    except Exception:
        return "—"

# ---------- Header ----------
st.markdown(f"""
<div class="header-wrap rtl">
  <h1 class="header-title">ركيم — Rakeem (SME Financial Assistant) 🇸🇦</h1>
  <div class="header-sub">لوحة مختصرة لمؤشرات الأداء + الضريبة + الزكاة، مع رسوم تفاعلية.</div>
  <span class="badge-date">اليوم: {pd.Timestamp.now():%Y-%m-%d}</span>
</div>
""", unsafe_allow_html=True)

# ---------- Sidebar ----------
st.sidebar.header("📂 رفع الملف المالي")
uploaded_file = st.sidebar.file_uploader("Upload Excel (.xlsx/.xls) or CSV", type=["xlsx", "xls", "csv"])

if uploaded_file is None:
    st.info("للبدء: ارفع الملف من الشريط الجانبي.")
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

# ---------- Taxes ----------
try:
    net_vat = float(compute_vat(df))
except Exception:
    net_vat = 0.0
try:
    zakat_due = float(compute_zakat(df))
except Exception:
    zakat_due = 0.0

# ---------- Engine Output (optional) ----------
try:
    engine_json = to_json(df, include_rows=False)
    engine_output = json.loads(engine_json)
except Exception:
    engine_output = None

# ---------- Date filter (affects visuals only) ----------
df["date"] = pd.to_datetime(df["date"], errors="coerce")
dmin, dmax = df["date"].min(), df["date"].max()
c1, c2 = st.columns([2, 1])
with c1:
    st.markdown('<div class="sec-title rtl">⚙ نطاق زمني للعرض</div>', unsafe_allow_html=True)
with c2:
    st.download_button("⬇ تنزيل البيانات المعروضة (CSV)", data=df.to_csv(index=False).encode("utf-8"),
                       file_name="data_filtered.csv", mime="text/csv")

start, end = st.slider(
    "الفترة الزمنية",
    min_value=dmin.to_pydatetime(), max_value=dmax.to_pydatetime(),
    value=(dmin.to_pydatetime(), dmax.to_pydatetime()),
    format="YYYY-MM",
)
view_df = df[(df["date"] >= pd.to_datetime(start)) & (df["date"] <= pd.to_datetime(end))].copy()

# ---------- KPIs ----------
total_revenue = float(view_df.get("revenue", pd.Series([0])).fillna(0).sum())
total_expenses = float(view_df.get("expenses", pd.Series([0])).fillna(0).sum())
total_profit   = float(view_df.get("profit", pd.Series([0])).fillna(0).sum())
total_cashflow = float(view_df.get("cash_flow", pd.Series([0])).fillna(0).sum())

st.markdown('<div class="sec-title rtl">📊 مؤشرات رئيسية</div>', unsafe_allow_html=True)
st.markdown('<div class="kpi-grid rtl">', unsafe_allow_html=True)

def _kpi(label, value, ico="•"):
    st.markdown(
        f"""
        <div class="kpi-card">
          <div class="kpi-top">
            <div class="kpi-label">{label}</div>
            <div class="kpi-ico">{ico}</div>
          </div>
          <div class="kpi-value">{sar(value)}</div>
        </div>
        """,
        unsafe_allow_html=True,
    )

k_cols = st.columns(4)
with k_cols[0]: _kpi("إجمالي الإيرادات", total_revenue, "📈")
with k_cols[1]: _kpi("إجمالي المصروفات", total_expenses, "💸")
with k_cols[2]: _kpi("صافي الربح", total_profit, "💰")
with k_cols[3]: _kpi("التدفق النقدي", total_cashflow, "💧")

k2_cols = st.columns(2)
with k2_cols[0]: _kpi("صافي ضريبة القيمة المضافة", net_vat, "🧾")
with k2_cols[1]: _kpi("الزكاة المستحقة", zakat_due, "🕌")

# ---------- Summary ----------
st.markdown('<div class="sec-title rtl">📌 ملخص مالي مختصر</div>', unsafe_allow_html=True)
st.markdown(f"""
<div class="summary-card rtl">
  <ul>
    <li>📈 إجمالي الإيرادات: <b>{sar(total_revenue)}</b></li>
    <li>💸 إجمالي المصروفات: <b>{sar(total_expenses)}</b></li>
    <li>💰 صافي الربح: <b>{sar(total_profit)}</b></li>
    <li>💧 التدفق النقدي: <b>{sar(total_cashflow)}</b></li>
    <li>🗓 الفترة المعروضة: <b>{pd.to_datetime(start):%d-%m-%Y}</b> → <b>{pd.to_datetime(end):%d-%m-%Y}</b></li>
  </ul>
</div>
""", unsafe_allow_html=True)

# ---------- Charts ----------
# ---------- Charts ----------
st.markdown('<div class="sec-title rtl">📈 الاتجاهات الشهرية</div>', unsafe_allow_html=True)

def _make_chart(df_in: pd.DataFrame, ycol: str, title: str):
    d = df_in[["date", ycol]].dropna().sort_values("date").copy()
    if d.empty:
        return None

    hover = "<b>%{x|%Y-%m}</b><br>" + title + ": <b>%{y:,.0f} ريال</b>"

    # رسم ثابت: خط + نقاط (بدون إعدادات جانبية)
    fig = px.line(
        d, x="date", y=ycol, title=title,
        template="plotly_white", markers=True
    )
    fig.update_traces(hovertemplate=hover)
    fig.update_layout(
        height=360, margin=dict(l=10, r=10, t=50, b=10),
        title=dict(x=0.02, y=0.95, font=dict(size=16, color=PRIMARY)),
        xaxis_title="التاريخ", yaxis_title="القيمة (ريال)",
        xaxis=dict(showgrid=False, rangeslider=dict(visible=True)),
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
    )
    return fig

tabs = st.tabs(["الإيرادات", "المصروفات", "الربح"])

with tabs[0]:
    fig = _make_chart(view_df, "revenue", "الإيرادات")
    if fig: st.plotly_chart(fig, use_container_width=True)

with tabs[1]:
    fig = _make_chart(view_df, "expenses", "المصروفات")
    if fig: st.plotly_chart(fig, use_container_width=True)

with tabs[2]:
    fig = _make_chart(view_df, "profit", "الربح")
    if fig: st.plotly_chart(fig, use_container_width=True)
# ---------- Forecast (expander) ----------
st.markdown('<div class="sec-title rtl">🔮 التنبؤ المالي</div>', unsafe_allow_html=True)
with st.expander("افتح لعرض التنبؤ (Holt-Winters)", expanded=False):

    cols = st.columns(3)
    with cols[0]:
        periods = st.slider("عدد الأشهر القادمة", min_value=3, max_value=12, value=6, step=1)

    has_entity = "entity_name" in df.columns

    def _compute_forecast_now(_df, _periods):
        return build_revenue_forecast(_df, periods=_periods)

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

        fig = go.Figure()
        fig.add_trace(go.Scatter(
            x=hist["date"], y=hist["revenue"], mode="lines+markers",
            name="الإيرادات التاريخية", line=dict(width=2, color=PRIMARY)
        ))
        fig.add_trace(go.Scatter(
            x=fc_ent["date"], y=fc_ent["forecast"],
            name="التنبؤ", line=dict(dash="dash", width=3, color=DANGER),
            marker=dict(size=6, color=DANGER)
        ))
        if len(hist) and len(fc_ent):
            x_min = hist["date"].min()
            x_max = fc_ent["date"].max()
            fig.update_xaxes(range=[x_min, x_max + pd.Timedelta(days=5)])

        fig.update_layout(
            height=420, template="plotly_white",
            margin=dict(l=10, r=10, t=30, b=10),
            xaxis_title="التاريخ", yaxis_title="الإيرادات",
            legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1)
        )
        st.plotly_chart(fig, use_container_width=True)

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
            tips.append("لا توجد إشارات مقلقة حاليًا؛ استمر بالمراقبة الشهرية.")
        st.markdown("<div class='chat-bubble assistant rtl'>" + "<br>".join(f"• {t}" for t in tips) + "</div>", unsafe_allow_html=True)

    except Exception as _e:
        st.warning(f"تعذر حساب التنبؤ: {_e}")

# ---------- Chat Section ----------
# ---------- Chat Section ----------
st.markdown('<div class="sec-title rtl">💬 المحادثة الذكية</div>', unsafe_allow_html=True)

# اختيار الباك-إند (كما هو)
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

# ===== تنسيقات الرد (Topic دائرة + باقيها Chips) =====
def stylize_labels(text: str) -> str:
    if not isinstance(text, str):
        return text
    # شيل الأقواس المربعة حول الوسوم [Topic] [Question] ...
    text = re.sub(r'\[\s*(Topic|Question|Answer|Source|Example)\s*\]', r'\1', text)

    # بدّل الكلمات بالـ chips (Topic لون مختلف)
    text = text.replace("Topic",    '<span class="chip topic">Topic</span>')
    text = text.replace("Question", '<span class="chip question">Question</span>')
    text = text.replace("Answer",   '<span class="chip answer">Answer</span>')
    text = text.replace("Source",   '<span class="chip source">Source</span>')
    text = text.replace("Example",  '<span class="chip example">Example</span>')
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
    return f'<div class="msg-body">{stylize_labels(normalize_fin_summary(content))}</div>'

def render_sources(sources: List[str]) -> None:
    if not sources:
        return
    chips = []
    for s in sources:
        label = (s or "").strip()
        if label == "ZATCA":
            chips.append(
                "<a href='https://zatca.gov.sa' target='_blank' "
                "class='chip source' style='text-decoration:none; color:inherit;'>ZATCA</a>"
            )
        else:
            chips.append(f"<span class='chip source'>{label}</span>")
    st.markdown(f"<div class='rtl'>{' '.join(chips)}</div>", unsafe_allow_html=True)

def _df_ctx():
    for key in ("df","financial_df","computed_df","results_df"):
        if key in globals() and "DataFrame" in str(type(globals()[key])): 
            return globals()[key]
        if key in st.session_state and "DataFrame" in str(type(st.session_state[key])): 
            return st.session_state[key]
    return df  # fallback

# حالة الجلسة للرسائل
if "chat_messages" not in st.session_state:
    st.session_state.chat_messages = [
        {"role":"assistant","content":"مرحبًا! ارفع الملف ثم اسأل/ي عن الربحية أو الضريبة أو الزكاة.", "sources":[]}
    ]

# عرض الرسائل بهيدر أنيق حسب الدور
for m in st.session_state.chat_messages:
    role = m["role"]
    cls = "assistant" if role == "assistant" else "user"
    header = (
        '<div class="msg-header">'
        + ('<span class="role-pill">Assistant</span>' 
           if role == "assistant" 
           else '<span class="role-pill" style="background:#dcfce7;border-color:#bbf7d0;color:#14532d">You</span>')
        + (' <span class="topic-dot">T</span>' if role == "assistant" else '')
        + '</div>'
    )
    body = format_assistant_html(m["content"]) if role == "assistant" else f'<div class="msg-body">{m["content"]}</div>'
    st.markdown(f'<div class="chat-bubble {cls} rtl">{header}{body}</div>', unsafe_allow_html=True)
    if role == "assistant":
        render_sources(m.get("sources", []))

# إدخال المستخدم + استدعاء الباك-إند
user_q = st.chat_input("اكتب سؤالك هنا…")
if user_q:
    st.session_state.chat_messages.append({"role":"user","content":user_q})
    st.markdown(
        f'<div class="chat-bubble user rtl"><div class="msg-header">'
        f'<span class="role-pill" style="background:#dcfce7;border-color:#bbf7d0;color:#14532d">You</span>'
        f'</div><div class="msg-body">{user_q}</div></div>',
        unsafe_allow_html=True
    )
    try:
        if not _backend:
            raise RuntimeError("لا يوجد باك-إند للشات.")
        mode, fn = _backend
        reply_text, sources = (fn(user_q, df=_df_ctx()) if mode=="simple" else fn(user_q, df=_df_ctx()))
        st.session_state.chat_messages.append({
            "role":"assistant", "content": reply_text, "sources": sources or []
        })
        st.markdown(
            f'<div class="chat-bubble assistant rtl"><div class="msg-header">'
            f'<span class="role-pill">Assistant</span> <span class="topic-dot">T</span>'
            f'</div>{format_assistant_html(reply_text)}</div>',
            unsafe_allow_html=True
        )
        render_sources(sources or [])
    except Exception as e:
        st.error(f"تعذر توليد الرد: {e}")
# ---------- PDF in sidebar ----------
st.sidebar.markdown("---")
st.sidebar.subheader("📄 تقرير PDF")

from generator.report_generator import generate_financial_report

if st.sidebar.button("توليد التقرير (PDF)"):
    try:
        pdf_path = generate_financial_report(
            company_name="ركيم المالية",
            report_title="التقرير المالي الشامل",
            metrics={
                "total_revenue": float(df.get("revenue", pd.Series([0])).fillna(0).sum()),
                "total_expenses": float(df.get("expenses", pd.Series([0])).fillna(0).sum()),
                "total_profit": float(df.get("profit", pd.Series([0])).fillna(0).sum()),
                "total_cashflow": float(df.get("cash_flow", pd.Series([0])).fillna(0).sum()),
                "net_vat": float(net_vat),
                "zakat_due": float(zakat_due),
            },
            data_tables={
                "الإيرادات": df[["date", "revenue"]],
                "المصروفات": df[["date", "expenses"]],
                "الأرباح": df[["date", "profit"]],
            },
            recommendations=[
                "حافظ على نسبة الربح الحالية.",
                "راقب المصروفات المتزايدة في الأشهر القادمة.",
            ],
            template_path="generator/report_template.html",
            output_pdf="financial_report.pdf",
        )
        with open(pdf_path, "rb") as fh:
            st.sidebar.download_button("⬇ تحميل التقرير", fh, "financial_report.pdf", "application/pdf")
        st.sidebar.success("تم توليد التقرير.")
    except Exception as e:
        st.sidebar.error(f"فشل إنشاء التقرير: {e}")
