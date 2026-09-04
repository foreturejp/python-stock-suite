from datetime import datetime, timedelta
from pathlib import Path
import sys
import warnings
import feedparser
from FinMind.data import DataLoader
import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import requests
import streamlit as st
import yfinance as yf

# 確保模組路徑包含專案根目錄
root_dir = Path(__file__).resolve().parent.parent
if str(root_dir) not in sys.path:
  sys.path.insert(0, str(root_dir))

# 僅從 app 匯入通用變數與共用函式
from app import CB_DATABASE, GOOGLE_SHEET_WEBHOOK_URL, call_ai_model

warnings.filterwarnings("ignore")

st.set_page_config(page_title="個股智慧量化儀表板", page_icon="📊", layout="wide")

st.markdown(
    """
<style>
    div[data-testid="stDataFrame"] div.dom-container table { font-size: 16px !important; }
    div[data-testid="stDataFrame"] th { font-size: 16px !important; text-align: center !important; background-color: #262730 !important; color: white !important; }
    div[data-testid="stDataFrame"] td { text-align: center !important; font-size: 16px !important; }
</style>
""",
    unsafe_allow_html=True,
)


# ─── 優先讀取 stock_list.csv 的股票清單載入函式 ───
@st.cache_data(ttl=3600)
def load_stock_list():
  stock_map = {}
  csv_file = root_dir / "stock_list.csv"

  if csv_file.exists():
    for enc in ["utf-8-sig", "utf-8", "big5", "cp950"]:
      try:
        df_csv = pd.read_csv(csv_file, dtype=str, encoding=enc)
        df_csv.columns = [str(c).strip() for c in df_csv.columns]
        code_col = next(
            (
                c
                for c in df_csv.columns
                if any(k in c for k in ["代號", "code", "id"])
            ),
            None,
        )
        name_col = next(
            (
                c
                for c in df_csv.columns
                if any(k in c for k in ["名稱", "name"])
            ),
            None,
        )
        if code_col and name_col:
          for _, row in df_csv.iterrows():
            c = str(row[code_col]).strip()
            n = str(row[name_col]).strip()
            if c.isdigit() and len(c) == 4:
              stock_map[f"{c} {n}"] = c
          if stock_map:
            break
      except Exception:
        continue

  # 強制保底清單
  defaults = {
      "2330 台積電": "2330",
      "2317 鴻海": "2317",
      "2454 聯發科": "2454",
      "1815 富喬": "1815",
      "6223 旺矽": "6223",
      "2408 南亞科": "2408",
  }
  for k, v in defaults.items():
    if v not in stock_map.values():
      stock_map[k] = v

  return stock_map


# ─── 獨立內建：Google Sheet 記錄函式 ───
def log_anonymous_daily_stock(stock_code, stock_name):
  try:
    if GOOGLE_SHEET_WEBHOOK_URL and "放這裡" not in GOOGLE_SHEET_WEBHOOK_URL:
      payload = {
          "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
          "stock_code": stock_code,
          "stock_name": stock_name,
      }
      requests.post(GOOGLE_SHEET_WEBHOOK_URL, json=payload, timeout=3)
  except Exception:
    pass


# 建立雙向查表字典
raw_stock_list = load_stock_list()
code_to_name = {}
name_to_code = {}
for display_text, code in raw_stock_list.items():
  name = display_text.split()[-1] if " " in display_text else display_text
  code_to_name[code] = name
  name_to_code[name] = code
  name_to_code[display_text] = code

# 🔑 優先讀取 st.secrets 內建付費版 API Key，並支援側邊欄手動覆蓋
user_api_key = ""
try:
  if "GEMINI_API_KEY" in st.secrets:
    user_api_key = st.secrets["GEMINI_API_KEY"]
except Exception:
  pass

with st.sidebar.expander("🔑 API Key 設定（預設已內建）", expanded=False):
  manual_key = st.text_input(
      "手動覆蓋 Key（若需使用個人額度可在此輸入）:",
      value="",
      type="password",
      placeholder="AIzaSy...",
      key="dashboard_manual_api_key",
  )
  if manual_key:
    user_api_key = manual_key


@st.cache_data(ttl=86400)
def fetch_finmind_chips(stock_code, api_key=""):
  df_margin_15 = pd.DataFrame()
  df_inst_chart = pd.DataFrame()

  if not api_key:
    return df_inst_chart, df_margin_15

  try:
    api = DataLoader()
    api.login_by_token(api_key)

    start_date = (datetime.now() - timedelta(days=180)).strftime("%Y-%m-%d")

    df_inst = api.get_data(
        dataset="TaiwanStockInstitutionalInvestorsBuySell",
        stock_id=stock_code,
        start_date=start_date,
    )
    if not df_inst.empty:
      df_inst["date"] = pd.to_datetime(df_inst["date"]).dt.strftime("%Y-%m-%d")
      pivoted = df_inst.pivot_table(
          index="date", columns="name", values="buy"
      ) - df_inst.pivot_table(index="date", columns="name", values="sell")
      col_mapping = {}
      for c in pivoted.columns:
        if "外資" in c:
          col_mapping[c] = "外資買賣超"
        elif "投信" in c:
          col_mapping[c] = "投信買賣超"
        elif "自營商" in c:
          col_mapping[c] = "自營商買賣超"
      df_inst_chart = pivoted.rename(columns=col_mapping).fillna(0)

    df_margin = api.get_data(
        dataset="TaiwanStockMarginPurchaseShortSale",
        stock_id=stock_code,
        start_date=(datetime.now() - timedelta(days=60)).strftime("%Y-%m-%d"),
    )
    if not df_margin.empty:
      df_margin["date"] = pd.to_datetime(df_margin["date"]).dt.strftime(
          "%Y-%m-%d"
      )
      df_m_15 = (
          df_margin.tail(15)
          .copy()
          .sort_values(by="date", ascending=False)
          .reset_index(drop=True)
      )

      margin_buy = (
          df_m_15["MarginPurchaseBuy"]
          if "MarginPurchaseBuy" in df_m_15.columns
          else 0
      )
      margin_sell = (
          df_m_15["MarginPurchaseSell"]
          if "MarginPurchaseSell" in df_m_15.columns
          else 0
      )
      short_buy = (
          df_m_15["ShortSaleBuy"] if "ShortSaleBuy" in df_m_15.columns else 0
      )
      short_sell = (
          df_m_15["ShortSaleSell"] if "ShortSaleSell" in df_m_15.columns else 0
      )

      short_balance = (
          df_m_15["ShortSaleTodayBalance"]
          if "ShortSaleTodayBalance" in df_m_15.columns
          else 0
      )
      margin_balance = (
          df_m_15["MarginPurchaseTodayBalance"]
          if "MarginPurchaseTodayBalance" in df_m_15.columns
          else 1
      )

      margin_balance = margin_balance.replace(0, 1)
      margin_change = (
          margin_buy - margin_sell if hasattr(margin_buy, "__sub__") else 0
      )
      short_change = (
          short_buy - short_sell if hasattr(short_buy, "__sub__") else 0
      )
      margin_ratio = round((short_balance / margin_balance) * 100, 1)

      df_margin_15 = pd.DataFrame({
          "日期": df_m_15["date"],
          "融資增減(張)": margin_change,
          "融券增減(張)": short_change,
          "券資比(%)": margin_ratio,
      }).set_index("日期")
  except Exception as e:
    print(f"FinMind 數據抓取例外: {e}")

  return df_inst_chart, df_margin_15


def calculate_dual_track_targets(df, window=5):
  df_recent = df.tail(40).copy() if len(df) >= 40 else df.copy()

  box_high = round(float(df_recent["High"].max()), 1)
  box_low = round(float(df_recent["Low"].min()), 1)

  df_dense = df.tail(7).copy()
  dense_height = df_dense["High"].max() - df_dense["Low"].min()
  typical_height = round(box_high * 0.06, 1)
  effective_box_height = (
      dense_height
      if (dense_height > 0 and dense_height <= box_high * 0.12)
      else typical_height
  )

  short_t1 = round(box_high + effective_box_height, 1)
  short_t2 = round(box_high + (effective_box_height * 1.618), 1)

  macro_wave_height = box_high - box_low
  macro_t1 = round(box_high + macro_wave_height, 1)
  macro_t2 = round(box_high + (macro_wave_height * 1.618), 1)

  down_t1 = round(max(box_low - effective_box_height, box_low * 0.85), 1)

  return box_high, box_low, short_t1, short_t2, macro_t1, macro_t2, down_t1


st.title("📊 個股智慧量化與雙軌戰略儀表板")
with st.container(border=True):
  col_input, col_days = st.columns([2, 1])
  with col_input:
    user_input = st.text_input(
        "🔍 請輸入台股代號或名稱",
        value="",
        placeholder="例如: 2330, 台積電, 1815, 富喬",
    )
  with col_days:
    chart_days_option = st.selectbox(
        "📊 選擇技術圖表歷史天數",
        ["最近 60 天", "最近 120 天 (推薦)", "最近 240 天 (約一年)"],
        index=1,
    )

days_map = {
    "最近 60 天": 60,
    "最近 120 天 (推薦)": 120,
    "最近 240 天 (約一年)": 240,
}
selected_days = days_map[chart_days_option]

if user_input:
  target_code, stock_name = None, "未知股票"
  user_input_clean = user_input.strip()

  if user_input_clean in name_to_code:
    target_code = name_to_code[user_input_clean]
    stock_name = code_to_name.get(target_code, user_input_clean)
  elif user_input_clean in code_to_name:
    target_code = user_input_clean
    stock_name = code_to_name[user_input_clean]
  elif user_input_clean.isdigit():
    target_code = user_input_clean
    stock_name = code_to_name.get(target_code, "自訂個股")
  else:
    st.error(f"❌ 找不到 【{user_input}】。")

  if target_code:
    log_anonymous_daily_stock(target_code, stock_name)
    try:
      with st.spinner(
          f"⏳ 正在透過 yfinance 同步 【{target_code} {stock_name}】"
          f" {selected_days} 天歷史與量化滿足點計算..."
      ):
        yf_code_full = f"{target_code}.TW"
        df_history = yf.download(
            yf_code_full, period="2y", interval="1d", progress=False
        )
        if df_history.empty:
          df_history = yf.download(
              f"{target_code}.TWO", period="2y", interval="1d", progress=False
          )

        if df_history.empty:
          st.error("❌ 找不到此代號的歷史交易資料，請確認代號是否正確。")
        else:
          if isinstance(df_history.columns, pd.MultiIndex):
            df_history.columns = df_history.columns.get_level_values(0)
          df_history = df_history[df_history["Volume"] > 0]

          # 💡 檢查 yfinance 歷史資料長度是否足夠
          if len(df_history) < 30:
            st.error("❌ 歷史資料不足 30 筆，無法計算技術指標。")
          else:
            # 💡 統一使用 yfinance 的收盤價作為唯一計算來源
            df_chart = df_history.tail(selected_days).copy().reset_index()
            date_col = (
                "Date" if "Date" in df_chart.columns else df_chart.columns[0]
            )
            df_chart["Date_DT"] = pd.to_datetime(df_chart[date_col])
            df_chart["Date_Str"] = df_chart["Date_DT"].dt.strftime("%Y-%m-%d")

            close_prices = [float(c) for c in df_chart["Close"]]
            p_latest = close_prices[-1]
            p_prev = close_prices[-2] if len(close_prices) >= 2 else p_latest
            chg_latest = round(p_latest - p_prev, 2)
            pct_latest = (
                round(((p_latest - p_prev) / p_prev) * 100, 2)
                if p_prev != 0
                else 0.0
            )

            b_high, b_low, s_t1, s_t2, m_t1, m_t2, down_t1 = (
                calculate_dual_track_targets(df_chart, window=5)
            )

            df_chart["MA5"] = df_chart["Close"].rolling(window=5).mean()
            ma5_latest = (
                round(float(df_chart["MA5"].iloc[-1]), 1)
                if not df_chart["MA5"].empty
                else b_low
            )

            df_chart["Volume_Lots"] = df_chart["Volume"] / 1000

            df_chart["Vol5"] = (
                df_chart["Volume_Lots"].rolling(window=5).mean()
            )
            df_chart["Vol20"] = (
                df_chart["Volume_Lots"].rolling(window=20).mean()
            )

            vol_latest = (
                int(df_chart["Volume_Lots"].iloc[-1])
                if not df_chart["Volume_Lots"].empty
                else 0
            )
            vol_5ma = (
                int(df_chart["Vol5"].iloc[-1])
                if not df_chart["Vol5"].empty
                else 0
            )
            vol_20ma = (
                int(df_chart["Vol20"].iloc[-1])
                if not df_chart["Vol20"].empty
                else 0
            )

            shrink_vol_limit = int(vol_5ma * 0.75)
            heavy_vol_limit = int(vol_5ma * 1.5)

            delta = df_chart["Close"].diff()
            gain = (delta.where(delta > 0, 0)).rolling(window=14).mean()
            loss = (-delta.where(delta < 0, 0)).rolling(window=14).mean()
            rs = gain / (loss + 1e-9)
            df_chart["RSI"] = round(100 - (100 / (1 + rs)), 1)
            rsi_val = float(df_chart["RSI"].iloc[-1])

            rsi_status = "⚪ 中性區間"
            if rsi_val >= 80:
              rsi_status = "🔥 嚴重超買 (警戒)"
            elif rsi_val >= 70:
              rsi_status = "⚠️ 超買區 (留意追高)"
            elif rsi_val <= 20:
              rsi_status = "💎 嚴重超賣 (強彈)"
            elif rsi_val <= 30:
              rsi_status = "🟢 超賣區 (低接)"

            is_breakout = p_latest > b_high

            st.success(
                f"📅 **目前個股資料日期（yfinance 同步）：{df_chart['Date_Str'].iloc[-1]}**"
                f" (已載入 {selected_days} 天長天期歷史)"
            )

            st.markdown(
                f"### 📊 【{target_code} {stock_name}】 雙軌滿足點戰略儀表板"
            )
            with st.container(border=True):
              st.markdown("#### 📉 【即時行情與短線/波段極限】")
              m1, m2, m3, m4, m5 = st.columns(5)
              chg_color = "normal" if chg_latest >= 0 else "inverse"
              m1.metric(
                  "最新收盤價 (yfinance)",
                  f"{p_latest:.1f}",
                  f"{chg_latest:+.2f} ({pct_latest:+.1f}%)",
                  delta_color=chg_color,
              )
              m2.metric(
                  "🎯 短線箱型極限 (1.618)", f"{s_t2:.1f}", "⬆ 實戰大壓區"
              )
              m3.metric(
                  "🚀 大波段主升極限", f"{m_t2:.1f}", "⬆ 長線極限目標"
              )
              m4.metric("🟢 5日線移動防守", f"{ma5_latest}", "⬆ 短線生命線")
              m5.metric("📌 RSI 狀態評估", rsi_status)

            with st.container(border=True):
              st.markdown(
                  "#### 📌 【雙軌滿足點對照看板：短線小箱型 vs 大波段主升段】"
              )

              r1_c1, r1_c2, r1_c3, r1_c4 = st.columns(4)
              r1_c1.metric(
                  "📦 短線箱型 1倍目標", f"{s_t1:.1f}", "短打務實滿足點"
              )
              r1_c2.metric(
                  "🔥 短線箱型 1.618極限", f"{s_t2:.1f}", "短線強壓"
              )
              r1_c3.metric(
                  "📈 大波段主升 1倍目標", f"{m_t1:.1f}", "中長線波段滿足"
              )
              r1_c4.metric(
                  "🚀 大波段主升 1.618極限", f"{m_t2:.1f}", "長線極限天花板"
              )

              st.markdown("---")
              r2_c1, r2_c2, r2_c3, r2_c4 = st.columns(4)
              r2_c1.metric(
                  "🔴 近端前高壓力", f"{b_high:.1f}", "突破後轉化為支撐"
              )
              r2_c2.metric("🟢 近端箱底支撐", f"{b_low:.1f}", "波段底限")
              r2_c3.metric(
                  "🔻 下檔對稱防守", f"{down_t1:.1f}", "破線修正測量"
              )
              r2_c4.metric(
                  "⚠️ 多空動態狀態",
                  "強勢創高格局" if is_breakout else "區間震盪整理",
              )

            df_inst_api, df_chips_15 = fetch_finmind_chips(
                target_code, user_api_key
            )
            if not df_inst_api.empty:
              df_inst_api["Date_Str"] = df_inst_api.index
              df_chart = df_chart.merge(
                  df_inst_api, left_on="Date_Str", right_on="Date_Str", how="left"
              ).fillna(0)
              for col_name in ["外資買賣超", "投信買賣超", "自營商買賣超"]:
                if col_name not in df_chart.columns:
                  df_chart[col_name] = 0
            else:
              df_chart["外資買賣超"], df_chart["投信買賣超"], (
                  df_chart["自營商買賣超"]
              ) = (0, 0, 0)

            if not df_chips_15.empty:
              df_chips_15["收盤價"] = (
                  df_chart.set_index("Date_Str")["Close"]
                  .reindex(df_chips_15.index)
                  .values
              )
              cols_order = [
                  c
                  for c in [
                      "收盤價",
                      "融資增減(張)",
                      "融券增減(張)",
                      "券資比(%)",
                  ]
                  if c in df_chips_15.columns
              ]
              df_chips_15 = df_chips_15[cols_order]

            close_series = df_chart["Close"]
            ema12 = close_series.ewm(span=12, adjust=False).mean()
            ema26 = close_series.ewm(span=26, adjust=False).mean()
            dif = ema12 - ema26
            dea = dif.ewm(span=9, adjust=False).mean()
            macd_bar = (dif - dea) * 2

            df_chart["DIF"], df_chart["DEA"], df_chart["MACD_Bar"] = (
                round(dif, 1),
                round(dea, 1),
                round(macd_bar, 1),
            )
            macd_today, macd_yesterday = float(
                df_chart["MACD_Bar"].iloc[-1]
            ), (float(df_chart["MACD_Bar"].iloc[-2]))

            tab1, tab2, tab3, tab4 = st.tabs([
                "📊 波段極值與 MACD",
                "🔄 可轉債 (CB) 追蹤",
                "📰 產業鏈新聞",
                "🧠 AI 智慧雙軌推理",
            ])

            with tab1:
              fig = make_subplots(
                  rows=3,
                  cols=1,
                  shared_xaxes=True,
                  vertical_spacing=0.03,
                  row_heights=[0.50, 0.22, 0.28],
                  subplot_titles=(
                      f"{stock_name} 雙軌滿足點戰略線 (yfinance)",
                      "每日成交量 (張)",
                      "MACD 動能指標 (DIF / DEA / 柱狀圖)",
                  ),
              )

              fig.add_trace(
                  go.Candlestick(
                      x=df_chart["Date_Str"],
                      open=df_chart["Open"],
                      high=df_chart["High"],
                      low=df_chart["Low"],
                      close=df_chart["Close"],
                      name="K線行情",
                      hovertemplate=(
                          "日期: %{x}<br>開盤: %{open:.1f}<br>最高:"
                          " %{high:.1f}<br>最低: %{low:.1f}<br><b>收盤:"
                          " %{close:.1f}</b><br>RSI: %{customdata:.1f}<extra></extra>"
                      ),
                      customdata=df_chart["RSI"],
                  ),
                  row=1,
                  col=1,
              )

              fig.add_trace(
                  go.Scatter(
                      x=df_chart["Date_Str"],
                      y=df_chart["MA5"],
                      mode="lines",
                      name="5日均線",
                      line=dict(color="orange", width=1.2),
                  ),
                  row=1,
                  col=1,
              )

              fig.add_hline(
                  y=s_t2,
                  line_dash="dash",
                  line_color="magenta",
                  row=1,
                  col=1,
                  annotation_text=f"短線1.618極限: {s_t2}",
              )
              fig.add_hline(
                  y=m_t2,
                  line_dash="dot",
                  line_color="purple",
                  row=1,
                  col=1,
                  annotation_text=f"大波段1.618極限: {m_t2}",
              )
              fig.add_hline(
                  y=b_high,
                  line_dash="dash",
                  line_color="crimson",
                  row=1,
                  col=1,
                  annotation_text=f"前高壓力: {b_high}",
              )

              vol_colors = [
                  "red" if row["Close"] >= row["Open"] else "green"
                  for index, row in df_chart.iterrows()
              ]
              fig.add_trace(
                  go.Bar(
                      x=df_chart["Date_Str"],
                      y=df_chart["Volume_Lots"],
                      name="成交量(張)",
                      marker_color=vol_colors,
                  ),
                  row=2,
                  col=1,
              )

              if "Vol5" in df_chart.columns:
                fig.add_trace(
                    go.Scatter(
                        x=df_chart["Date_Str"],
                        y=df_chart["Vol5"],
                        mode="lines",
                        name="5日均量",
                        line=dict(color="purple", width=1.5),
                    ),
                    row=2,
                    col=1,
                )

              macd_colors = [
                  "red" if val >= 0 else "green" for val in df_chart["MACD_Bar"]
              ]
              fig.add_trace(
                  go.Bar(
                      x=df_chart["Date_Str"],
                      y=df_chart["MACD_Bar"],
                      name="MACD 柱狀圖",
                      marker_color=macd_colors,
                  ),
                  row=3,
                  col=1,
              )
              fig.add_trace(
                  go.Scatter(
                      x=df_chart["Date_Str"],
                      y=df_chart["DIF"],
                      mode="lines",
                      name="DIF (快線)",
                      line=dict(color="gold", width=1.5),
                  ),
                  row=3,
                  col=1,
              )
              fig.add_trace(
                  go.Scatter(
                      x=df_chart["Date_Str"],
                      y=df_chart["DEA"],
                      mode="lines",
                      name="DEA (慢線)",
                      line=dict(color="cyan", width=1.5),
                  ),
                  row=3,
                  col=1,
              )

              fig.update_layout(
                  template="plotly_dark", height=900, hovermode="x unified"
              )
              fig.update_xaxes(
                  showspikes=False,
                  matches="x",
                  type="category",
                  rangeslider=dict(visible=False),
              )
              fig.update_yaxes(showspikes=False, tickformat=".1f")
              st.plotly_chart(fig, use_container_width=True)

              st.markdown("---")
              st.markdown("### 🎯 最終綜合投資行動與雙軌戰略建議")

              if is_breakout:
                st.markdown(
                    f"""
                    <div style="padding: 20px; border-radius: 10px; background-color: #1e2530; border-left: 6px solid #ff4b4b; color: #f0f2f6;">
                        <h3 style="color: #ff4b4b; margin-top: 0;">🚀 【強勢突破與雙軌戰略導航】</h3>
                        <p style="font-size: 18px; line-height: 1.6; color: #f0f2f6;">
                        1. <b>短線箱型極限 (1.618)</b>：已來到 <span style="color: #ff00ff; font-size: 20px; font-weight: bold;">{s_t2} 元</span> 附近（往往會在此觸發強烈當沖與短線獲利回吐賣壓）。建議在此區實施<b>「逢高分批獲利入袋」</b>。<br>
                        2. <b>大波段主升段極限</b>：中長線宏觀極限看 <span style="color: #da70d6; font-size: 20px; font-weight: bold;">{m_t2} 元</span>。<br>
                        3. <b>絕對防守線</b>：短線生命線鎖定 <span style="color: #ffa500; font-size: 20px; font-weight: bold;">5日均線 ({ma5_latest} 元)</span>。目前 5日均量約為 <b>{vol_5ma:,} 張</b>（縮量標準: < {shrink_vol_limit:,} 張 | 大量標準: > {heavy_vol_limit:,} 張）。只要未帶量跌破 5 日線，核心部位持續多頭續抱！
                        </p>
                    </div>
                    """,
                    unsafe_allow_html=True,
                )
              else:
                st.markdown(
                    f"""
                    <div style="padding: 20px; border-radius: 10px; background-color: #1e2530; border-left: 6px solid #00cc66; color: #f0f2f6;">
                        <h3 style="color: #00cc66; margin-top: 0;">🟢 【箱型區間盤整中】</h3>
                        <p style="font-size: 18px; line-height: 1.6; color: #f0f2f6;">
                        當前股價在 <span style="color: #ff4b4b; font-weight: bold;">箱頂壓力 ({b_high} 元)</span> 與 <span style="color: #00cc66; font-weight: bold;">箱底支撐 ({b_low} 元)</span> 之間來回震盪。目前 5日均量約為 <b>{vol_5ma:,} 張</b>（縮量標準: < {shrink_vol_limit:,} 張 | 大量標準: > {heavy_vol_limit:,} 張）。建議採取高出低吸策略！
                        </p>
                    </div>
                    """,
                    unsafe_allow_html=True,
                )

              st.markdown("---")
              st.markdown(
                  f"### 💬 【對話 AI】與 AI 討論 【{target_code} {stock_name}】"
                  " 的即時操盤對策"
              )

              chat_history_key = f"chat_history_{target_code}"
              if chat_history_key not in st.session_state:
                st.session_state[chat_history_key] = []

              for role, text in st.session_state[chat_history_key]:
                if role == "user":
                  st.markdown(f"**👤 您的提問**：{text}")
                else:
                  st.markdown(f"**🤖 AI 操盤手回覆**：\n{text}")
                st.markdown("---")

              with st.form(key=f"chat_form_{target_code}", clear_on_submit=True):
                user_question = st.text_input(
                    "輸入您的操盤問題或均價狀況：",
                    placeholder=(
                        "例如：我均價目前在這邊，明天成交量要低於多少才算安全縮量？"
                    ),
                )
                col_send, col_clear = st.columns([1, 5])
                with col_send:
                  submitted = st.form_submit_button(
                      "🚀 發送給 AI", use_container_width=True
                  )

              if submitted:
                if not user_api_key:
                  st.warning(
                      "⚠️ 請先在左側欄位輸入您自己的 **Gemini API Key**"
                      " 才能與 AI 對話！"
                  )
                elif user_question:
                  st.session_state[chat_history_key].append(
                      ("user", user_question)
                  )
                  with st.spinner(
                      "🤖 AI 操盤手正在結合當前量化數據與具體量能標準為您擬定對策..."
                  ):
                    context_prompt = f"""
你是一位頂尖的台股量化操盤手與籌碼專家。使用者目前正在詢問關於 【{target_code} {stock_name}】 的操盤問題。
以下是該個股的最新量化與雙軌戰略數據背景（請在回答時務必引用具體張數與價位，絕對不要只給抽象形容詞）：
- 最新收盤價：{p_latest:.1f} (漲跌幅: {chg_latest:+.2f}%)
- 短線箱型極限(1.618)：{s_t2:.1f} 元 | 大波段主升極限(1.618)：{m_t2:.1f} 元
- 近端箱頂壓力：{b_high:.1f} 元 | 近端箱底支撐：{b_low:.1f} 元
- 5日均線防守：{ma5_latest:.1f} 元
- **量能量化指標（關鍵量化參考）**：
  * 當前最新成交量：{vol_latest:,} 張
  * 5日均量（5VMA）：{vol_5ma:,} 張
  * 20日均量（月均量）：{vol_20ma:,} 張
  * **縮量具體標準**：低於 {shrink_vol_limit:,} 張
  * **大量／多量具體標準**：超過 {heavy_vol_limit:,} 張
- 技術指標：RSI={rsi_val:.1f} ({rsi_status}) | MACD柱狀體={macd_today:.1f}

使用者的提問是："{user_question}"

請給予專業、精煉、具備具體操作建議（進出點、均價防守、風險控管，以及明確指名張數的量能解讀）的繁體中文回覆。
"""
                    ai_reply = call_ai_model(user_api_key, context_prompt)
                    st.session_state[chat_history_key].append(
                        ("assistant", ai_reply)
                    )
                    st.rerun()

              if st.button("🗑️ 清除對話紀錄", key=f"clear_{target_code}"):
                st.session_state[chat_history_key] = []
                st.rerun()

            with tab2:
              cb_info = CB_DATABASE.get(target_code, None)
              if cb_info:
                st.success("🔥 此檔個股帶有 **可轉債 (CB) 飆股基因**！")
                cb_c1, cb_c2, cb_c3 = st.columns(3)
                cb_c1.metric("可轉債簡稱", cb_info["cb_name"])
                cb_c2.metric("轉換價參考", cb_info["conversion_price"])
                cb_c3.metric("賣回/到期倒數日", cb_info["put_date"])
                st.markdown(
                    f"**📌 狀態與主力動機解讀**：`{cb_info['status']}`"
                )
              else:
                st.info(
                    f"⚪ 目前系統中暫未登錄 【{target_code} {stock_name}】"
                    " 的可轉債發行紀錄。"
                )

            with tab3:
              feed = feedparser.parse(
                  f"https://news.google.com/rss/search?q={stock_name}+(漲價+OR+缺貨+OR+報價+OR+產能+OR+法說會)&hl=zh-TW&gl=TW&ceid=TW:zh-Hant"
              )
              if feed.entries:
                for entry in feed.entries[:5]:
                  st.markdown(f"- [{entry.title}]({entry.link})")
              else:
                st.info("近期無相關報導。")

            with tab4:
              st.subheader(
                  f"🧠 【{target_code} {stock_name}】 AI 智慧雙軌推理引擎"
              )
              st.markdown(
                  "結合短線箱型極限與大波段主升段目標，進行專業量化操盤手的多空劇本解構。"
              )

              if st.button(
                  "🚀 啟動 AI 進行雙軌滿足點與量能標準深度推理",
                  use_container_width=True,
              ):
                if not user_api_key:
                  st.warning(
                      "⚠️ 請先在左側欄位輸入您自己的 **Gemini API Key**"
                      " 才能執行 AI 深度推理！"
                  )
                else:
                  with st.spinner(
                      "🤖 AI 操盤手正在整合雙軌極限與具體量化張數進行深度推理..."
                  ):
                    cb_info = CB_DATABASE.get(target_code, None)
                    cb_prompt_text = (
                        f"可轉債資訊:名稱={cb_info['cb_name']},"
                        f" 轉換價={cb_info['conversion_price']},"
                        f" 狀態={cb_info['status']}"
                        if cb_info
                        else "無特定可轉債登錄紀錄"
                    )

                    prompt_summary = f"""
你是一位資深的台股量化操盤手與主力和籌碼專家。請針對以下個股進行「雙軌戰略」走勢與量價推理（回答時務必明確帶出具體張數與價位）：
- 股票代號與名稱：{target_code} {stock_name}
- 最新收盤價：{p_latest:.1f} (漲跌幅: {chg_latest:+.2f}%)
- 軌道一【短線箱型極限 (1.618)】：{s_t2:.1f} 元
- 軌道二【大波段主升極限 (1.618)】：{m_t2:.1f} 元
- 近端箱頂：{b_high:.1f} 元 | 箱底：{b_low:.1f} 元
- 5日均線防守：{ma5_latest:.1f} 元
- **量能量化指標**：
  * 5日均量：{vol_5ma:,} 張
  * 縮量具體門檻：低於 {shrink_vol_limit:,} 張
  * 大量／多量具體門檻：超過 {heavy_vol_limit:,} 張
- 技術指標：RSI={rsi_val:.1f} ({rsi_status}) | MACD柱狀體={macd_today:.1f}
- {cb_prompt_text}

請提供結構化專業分析報告：
1. **雙軌獲利調節策略與具體價位**：
2. **進場低接或續抱時的「具體量能張數標準」**：
3. **5日均線防守與風險控管紀律**：
"""
                    ai_response_text = call_ai_model(
                        user_api_key, prompt_summary
                    )
                    st.markdown("---")
                    st.markdown(ai_response_text)
    except Exception as e:
      st.error(f"❌ 查詢錯誤: {e}")
else:
  st.info("💡 **操作提示**：請在上方搜尋框輸入代號。")
