from datetime import datetime, time, timedelta
import itertools
import os
import warnings
from google import genai
import numpy as np
import pandas as pd
import plotly.express as px
import requests
import streamlit as st
import twstock
import yfinance as yf

warnings.filterwarnings("ignore")

st.set_page_config(
    page_title="台股智慧量化分析與戰略系統", page_icon="📈", layout="wide"
)

# 🎨 幾何風與高質感操盤介面 CSS 優化
st.markdown(
    """
<style>
    html, body, [class*="css"], .stMarkdown, p, span, div {
        font-family: -apple-system, BlinkMacSystemFont, "PingFang TC", "Microsoft JhengHei", "微軟正黑體", sans-serif !important;
        letter-spacing: 0.3px;
    }
    .block-container {
        padding-top: 2rem;
        padding-bottom: 2rem;
        max-width: 100% !important;
    }
    .signal-pill {
        display: inline-block;
        padding: 3px 8px;
        border-radius: 4px;
        font-size: 11px;
        font-weight: 500;
        background-color: #27273a;
        color: #818cf8;
        border: 1px solid #3f3f5f;
        margin-right: 6px;
        margin-top: 4px;
        cursor: help;
    }
    div[data-testid="stModal"] button[kind="secondary"] {
        border: 1px solid #6366f1 !important;
        color: #818cf8 !important;
    }
    div[data-testid="stModal"] button[kind="primary"] {
        background-color: #374151 !important;
        border-color: #4b5563 !important;
    }
    div[data-baseweb="input"] button { display: none !important; }
    div[data-baseweb="input"] input { padding-right: 15px !important; }
    
    div[data-testid="stExpander"] details summary {
        display: flex !important;
        flex-direction: row-reverse !important;
        justify-content: flex-end !important;
        align-items: center !important;
    }
    div[data-testid="stExpander"] details summary svg { margin-right: 8px !important; margin-left: 0px !important; }
    div[data-testid="stExpander"] details summary p { font-weight: 600 !important; color: #e2e8f0 !important; }
</style>
""",
    unsafe_allow_html=True,
)

GOOGLE_SHEET_WEBHOOK_URL = "您的_GOOGLE_APPS_SCRIPT_URL_放這裡"


def get_stock_sector(code, name):
  code_str = str(code).strip()
  name_str = str(name).strip()

  if code_str == "2408" or "南亞科" in name_str:
    return "💾 記憶體與控制模組"
  if code_str == "1303" or name_str == "南亞":
    return "🧪 塑膠與化學工業"

  SECTOR_MAP = {
      "2330": "⚡ 晶圓代工",
      "2303": "⚡ 晶圓代工",
      "5347": "⚡ 晶圓代工",
      "6770": "⚡ 晶圓代工",
      "2454": "🧠 IC設計",
      "2379": "🧠 IC設計",
      "3034": "🧠 IC設計",
      "3035": "🧠 IC設計",
      "6415": "🧠 IC設計",
      "4961": "🧠 IC設計",
      "4968": "🧠 IC設計",
      "3227": "🧠 IC設計",
      "6531": "🧠 IC設計",
      "3545": "🧠 IC設計",
      "6237": "🧠 IC設計",
      "8016": "🧠 IC設計",
      "6732": "🧠 IC設計",
      "3527": "🧠 IC設計",
      "4919": "🧠 IC設計",
      "2458": "🧠 IC設計",
      "3661": "💎 矽智財與ASIC",
      "3443": "💎 矽智財與ASIC",
      "3529": "💎 矽智財與ASIC",
      "6643": "💎 矽智財與ASIC",
      "6526": "💎 矽智財與ASIC",
      "6684": "💎 矽智財與ASIC",
      "3711": "⚙️ 先進封測",
      "2449": "⚙️ 先進封測",
      "6239": "⚙️ 先進封測",
      "3374": "⚙️ 先進封測",
      "6147": "⚙️ 先進封測",
      "8150": "⚙️ 先進封測",
      "6223": "⚙️ 測試介面與探針卡",
      "6515": "⚙️ 測試介面與探針卡",
      "6683": "⚙️ 測試介面與探針卡",
      "3131": "🔬 半導體設備與廠務",
      "3583": "🔬 半導體設備與廠務",
      "6187": "🔬 半導體設備與廠務",
      "3680": "🔬 半導體設備與廠務",
      "2404": "🔬 半導體設備與廠務",
      "6139": "🔬 半導體設備與廠務",
      "5536": "🔬 半導體設備與廠務",
      "1560": "🔬 半導體設備與廠務",
      "3413": "🔬 半導體設備與廠務",
      "6667": "🔬 半導體設備與廠務",
      "5434": "🔬 半導體設備與廠務",
      "8028": "🔬 半導體設備與廠務",
      "6488": "🔬 半導體晶圓材料",
      "5483": "🔬 半導體晶圓材料",
      "6182": "🔬 半導體晶圓材料",
      "2408": "💾 記憶體與控制模組",
      "2344": "💾 記憶體與控制模組",
      "8299": "💾 記憶體與控制模組",
      "3260": "💾 記憶體與控制模組",
      "4967": "💾 記憶體與控制模組",
      "3006": "💾 記憶體與控制模組",
      "2337": "💾 記憶體與控制模組",
      "2451": "💾 記憶體與控制模組",
      "2317": "🤖 AI伺服器組裝",
      "2382": "🤖 AI伺服器組裝",
      "3231": "🤖 AI伺服器組裝",
      "6669": "🤖 AI伺服器組裝",
      "2376": "🤖 AI伺服器組裝",
      "2356": "🤖 AI伺服器組裝",
      "2357": "🤖 AI伺服器組裝",
      "2353": "🤖 AI伺服器組裝",
      "4938": "🤖 AI伺服器組裝",
      "3706": "🤖 AI伺服器組裝",
      "2059": "🖥️ 伺服器機殼與導軌",
      "8210": "🖥️ 伺服器機殼與導軌",
      "3693": "🖥️ 伺服器機殼與導軌",
      "3013": "🖥️ 伺服器機殼與導軌",
      "5274": "🖥️ 伺服器機殼與導軌",
      "6805": "🖥️ 伺服器機殼與導軌",
      "3376": "🖥️ 伺服器機殼與導軌",
      "6117": "🖥️ 伺服器機殼與導軌",
      "5426": "🖥️ 伺服器機殼與導軌",
      "2395": "🏭 工業電腦IPC",
      "6414": "🏭 工業電腦IPC",
      "6206": "🏭 工業電腦IPC",
      "6579": "🏭 工業電腦IPC",
      "8114": "🏭 工業電腦IPC",
      "3088": "🏭 工業電腦IPC",
      "3017": "🧊 水冷與散熱模組",
      "3324": "🧊 水冷與散熱模組",
      "3653": "🧊 水冷與散熱模組",
      "8996": "🧊 水冷與散熱模組",
      "3338": "🧊 水冷與散熱模組",
      "2421": "🧊 水冷與散熱模組",
      "3483": "🧊 水冷與散熱模組",
      "6230": "🧊 水冷與散熱模組",
      "2383": "🧬 PCB與高階載板",
      "6274": "🧬 PCB與高階載板",
      "6213": "🧬 PCB與高階載板",
      "2368": "🧬 PCB與高階載板",
      "3037": "🧬 PCB與高階載板",
      "8046": "🧬 PCB與高階載板",
      "3189": "🧬 PCB與高階載板",
      "2313": "🧬 PCB與高階載板",
      "4958": "🧬 PCB與高階載板",
      "6269": "🧬 PCB與高階載板",
      "8358": "🧬 PCB與高階載板",
      "1815": "🧬 PCB與高階載板",
      "8039": "🧬 PCB與高階載板",
      "3715": "🧬 PCB與高階載板",
      "5469": "🧬 PCB與高階載板",
      "2308": "🔋 電源管理與儲能",
      "2301": "🔋 電源管理與儲能",
      "6282": "🔋 電源管理與儲能",
      "2327": "🔋 被動元件與電感",
      "2492": "🔋 被動元件與電感",
      "3026": "🔋 被動元件與電感",
      "6173": "🔋 被動元件與電感",
      "2478": "🔋 被動元件與電感",
      "6207": "🔋 被動元件與電感",
      "3665": "🔌 連接器與高頻傳輸",
      "3533": "🔌 連接器與高頻傳輸",
      "3023": "🔌 連接器與高頻傳輸",
      "5457": "🔌 連接器與高頻傳輸",
      "6197": "🔌 連接器與高頻傳輸",
      "6290": "🔌 連接器與高頻傳輸",
      "3217": "🔌 連接器與高頻傳輸",
      "5269": "🔌 連接器與高頻傳輸",
      "2455": "🔥 光通訊與矽光子",
      "3081": "🔥 光通訊與矽光子",
      "6442": "🔥 光通訊與矽光子",
      "4979": "🔥 光通訊與矽光子",
      "3450": "🔥 光通訊與矽光子",
      "3163": "🔥 光通訊與矽光子",
      "3234": "🔥 光通訊與矽光子",
      "4977": "🔥 光通訊與矽光子",
      "3363": "🔥 光通訊與矽光子",
      "3105": "🔥 化合物半導體PA",
      "8086": "🔥 化合物半導體PA",
      "2345": "🌐 網通與高速交換器",
      "6285": "🌐 網通與高速交換器",
      "5388": "🌐 網通與高速交換器",
      "3596": "🌐 網通與高速交換器",
      "3704": "🌐 網通與高速交換器",
      "2314": "🌐 網通與高速交換器",
      "4906": "🌐 網通與高速交換器",
      "3380": "🌐 網通與高速交換器",
      "3008": "📷 光學鏡頭與影像",
      "3406": "📷 光學鏡頭與影像",
      "3504": "📷 光學鏡頭與影像",
      "3019": "📷 光學鏡頭與影像",
      "2409": "📺 面板及光電顯示",
      "3481": "📺 面板及光電顯示",
      "6116": "📺 面板及光電顯示",
      "8105": "📺 面板及光電顯示",
      "3702": "📦 通路代理與資服",
      "3036": "📦 通路代理與資服",
      "6214": "📦 通路代理與資服",
      "4953": "📦 通路代理與資服",
      "3029": "📦 通路代理與資服",
      "8112": "📦 通路代理與資服",
      "1519": "⚡ 重電與電網基建",
      "1503": "⚡ 重電與電網基建",
      "1513": "⚡ 重電與電網基建",
      "1514": "⚡ 重電與電網基建",
      "2371": "⚡ 重電與電網基建",
      "1504": "⚡ 重電與電網基建",
      "1605": "⚡ 重電與電線電纜",
      "1609": "⚡ 重電與電線電纜",
      "2049": "🦾 工具機與機器人",
      "1590": "🦾 工具機與機器人",
      "2359": "🦾 工具機與機器人",
      "4583": "🦾 工具機與機器人",
      "4576": "🦾 工具機與機器人",
      "6188": "🦾 工具機與機器人",
      "2365": "🦾 工具機與機器人",
      "2603": "🚢 航運交通",
      "2609": "🚢 航運交通",
      "2615": "🚢 航運交通",
      "2606": "🚢 航運交通",
      "2637": "🚢 航運交通",
      "2618": "✈️ 航空客貨運",
      "2610": "✈️ 航空客貨運",
      "2634": "✈️ 航太與軍工基建",
      "6869": "🌱 綠能儲能與售電",
      "6806": "🌱 綠能儲能與售電",
      "2412": "🌱 電信與公用事業",
      "2881": "🏦 金融控股",
      "2882": "🏦 金融控股",
      "2888": "🏦 金融控股",
      "5880": "🏦 金融控股",
      "2886": "🏦 金融控股",
      "2891": "🏦 金融控股",
      "2892": "🏦 金融控股",
      "2884": "🏦 金融控股",
      "2885": "🏦 金融控股",
      "5871": "🏦 金融控股",
      "1301": "🧪 塑膠與化學工業",
      "1303": "🧪 塑膠與化學工業",
      "1326": "🧪 塑膠與化學工業",
      "6505": "🧪 塑膠與化學工業",
      "1710": "🧪 塑膠與化學工業",
      "1775": "🧪 半導體特化材料",
      "2002": "🔩 鋼鐵工業",
      "2027": "🔩 鋼鐵工業",
      "1101": "🧱 水泥與綠能建材",
      "2542": "🏘️ 營建與地產開發",
      "2520": "🏘️ 營建與地產開發",
      "2501": "🏘️ 營建與地產開發",
      "2548": "🏘️ 營建與地產開發",
      "2540": "🏘️ 營建與地產開發",
      "2207": "🚗 汽車整車與零組件",
      "1319": "🚗 汽車整車與零組件",
      "6472": "💊 生技醫療CDMO",
      "6446": "💊 生技醫療CDMO",
      "1795": "💊 生技醫療CDMO",
      "1216": "🛍️ 民生消費與零售",
      "2912": "🛍️ 民生消費與零售",
  }

  if code_str in SECTOR_MAP:
    return SECTOR_MAP[code_str]

  if any(
      k in name_str
      for k in [
          "華邦電",
          "群聯",
          "威剛",
          "十銓",
          "宇瞻",
          "創見",
          "晶豪科",
          "旺宏",
      ]
  ):
    return "💾 記憶體與控制模組"
  if any(
      k in name_str
      for k in [
          "光聖",
          "華星光",
          "光環",
          "波若威",
          "上詮",
          "聯光通",
          "聯亞",
          "全新",
          "創威",
      ]
  ):
    return "🔥 光通訊與矽光子"
  if any(
      k in name_str
      for k in [
          "奇鋐",
          "雙鴻",
          "健策",
          "高力",
          "泰碩",
          "力致",
          "動力",
          "業強",
      ]
  ):
    return "🧊 水冷與散熱模組"
  if any(
      k in name_str
      for k in [
          "弘塑",
          "辛耘",
          "萬潤",
          "均華",
          "志聖",
          "家登",
          "中砂",
          "昇陽半",
      ]
  ):
    return "🔬 半導體設備與廠務"
  if any(
      k in name_str
      for k in [
          "台光電",
          "金像電",
          "欣興",
          "南電",
          "景碩",
          "台燿",
          "聯茂",
          "華通",
          "定穎",
      ]
  ):
    return "🧬 PCB與高階載板"
  if any(
      k in name_str
      for k in ["勤誠", "營邦", "晟銘電", "迎廣", "川湖", "富世達"]
  ):
    return "🖥️ 伺服器機殼與導軌"
  if any(k in name_str for k in ["華城", "士電", "中興電", "亞力", "大同"]):
    return "⚡ 重電與電網基建"
  if any(
      k in name_str
      for k in ["上銀", "亞德客", "所羅門", "大銀微", "精銳", "昆盈"]
  ):
    return "🦾 工具機與機器人"
  if any(
      k in name_str
      for k in ["貿聯", "嘉澤", "信邦", "宏致", "健和興", "凡甲"]
  ):
    return "🔌 連接器與高頻傳輸"
  if any(
      k in name_str
      for k in ["國巨", "華新科", "立隆電", "凱美", "日電貿"]
  ):
    return "🔋 被動元件與電感"
  if any(k in name_str for k in ["大立光", "玉晶光", "先進光", "亞光"]):
    return "📷 光學鏡頭與影像"
  if any(k in name_str for k in ["群創", "友達", "彩晶"]):
    return "📺 面板及光電顯示"
  if any(
      k in name_str
      for k in ["長榮", "陽明", "萬海", "裕民", "慧洋", "新興"]
  ):
    return "🚢 航運交通"
  if any(k in name_str for k in ["保瑞", "藥華藥", "美時", "康霈"]):
    return "💊 生技醫療CDMO"
  if any(k in name_str for k in ["興富發", "冠德", "國建", "華固"]):
    return "🏘️ 營建與地產開發"
  if any(
      k in name_str
      for k in ["台塑", "台化", "台苯", "國喬", "聯成", "塑膠", "化學"]
  ):
    return "🧪 塑膠與化學工業"

  try:
    c_int = int(code_str)
  except Exception:
    c_int = 0

  if 2800 <= c_int <= 2899 or any(
      k in name_str for k in ["銀行", "金控", "證券", "保險"]
  ):
    return "🏦 金融控股"
  elif 2600 <= c_int <= 2649 or any(
      k in name_str for k in ["海運", "航運", "航空"]
  ):
    return "🚢 航運交通"
  elif 2500 <= c_int <= 2599:
    return "🏘️ 營建與地產開發"
  elif 1300 <= c_int <= 1349:
    return "🧪 塑膠與化學工業"
  elif 2000 <= c_int <= 2049:
    return "🔩 鋼鐵工業"
  elif 1500 <= c_int <= 1599:
    return "⚡ 重電與電網基建"
  elif 1600 <= c_int <= 1699:
    return "⚡ 重電與電線電纜"
  elif 1700 <= c_int <= 1799 or 4100 <= c_int <= 4199:
    return "💊 生技醫療CDMO"
  elif (
      2300 <= c_int <= 2499
      or 3000 <= c_int <= 3799
      or 6000 <= c_int <= 6999
      or 8000 <= c_int <= 8999
  ):
    return "🔌 電子零組件與模組"

  return "📊 其他傳統產業與消費"


CB_DATABASE = {
    "3715": {
        "cb_name": "定穎投控一",
        "convert_start": "2025-06-15",
        "put_date": "2026-12-20",
        "conversion_price": 65.5,
        "status": "進入可轉換期・注意主力拉抬解鎖壓力",
    },
    "2327": {
        "cb_name": "國巨一",
        "convert_start": "2024-10-10",
        "put_date": "2027-03-15",
        "conversion_price": 580.0,
        "status": "長期潛伏期・籌碼安定",
    },
}


def get_cached_shareholding_dict():
  cache_file = os.path.join(
      os.path.dirname(__file__),
      "cache_data",
      "weekly_large_shareholders.parquet",
  )
  if not os.path.exists(cache_file):
    return {}, "無大戶快取資料"

  file_mtime = datetime.fromtimestamp(os.path.getmtime(cache_file))
  if datetime.now() - file_mtime > timedelta(days=7):
    return {}, f"快取已過期 (建立於 {file_mtime.strftime('%m/%d')})"

  try:
    df_cache = pd.read_parquet(cache_file)
    shareholding_map = df_cache.set_index("代號").to_dict(orient="index")
    return (
        shareholding_map,
        f"資料基準: {file_mtime.strftime('%Y-%m-%d %H:%M')}",
    )
  except Exception:
    return {}, "讀取快取失敗"


@st.cache_data(ttl=86400)
def load_stock_list():
  try:
    url_twse = "https://www.twse.com.tw/rwd/zh/afterTrading/MI_INDEX?response=json&type=ALL"
    headers = {"User-Agent": "Mozilla/5.0"}
    res = requests.get(url_twse, headers=headers, timeout=10)
    stock_map = {}
    if res.status_code == 200 and res.text.strip().startswith("{"):
      json_data = res.json()
      if "tables" in json_data:
        for table in json_data["tables"]:
          if "fields" in table and "data" in table:
            fields = table["fields"]
            if any("證券代號" in str(f) for f in fields) and any(
                "證券名稱" in str(f) for f in fields
            ):
              c_idx = [
                  i for i, f in enumerate(fields) if "證券代號" in str(f)
              ][0]
              n_idx = [
                  i for i, f in enumerate(fields) if "證券名稱" in str(f)
              ][0]
              for row in table["data"]:
                c, n = str(row[c_idx]).strip(), str(row[n_idx]).strip()
                if c.isdigit() and len(c) == 4:
                  stock_map[f"{c} {n}"] = c

    defaults = {
        "2330 台積電": "2330",
        "2317 鴻海": "2317",
        "2454 聯發科": "2454",
        "2455 全新": "2455",
        "3081 聯亞": "3081",
        "2408 南亞科": "2408",
        "2382 廣達": "2382",
        "3017 奇鋐": "3017",
        "2059 川湖": "2059",
    }
    stock_map.update(defaults)
    return stock_map
  except Exception:
    return {
        "2330 台積電": "2330",
        "2317 鴻海": "2317",
        "2454 聯發科": "2454",
        "2455 全新": "2455",
        "2408 南亞科": "2408",
    }


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


# ─────────────────────────────────────────────────────────────
# 🎯 多組 API Key 自動輪換與故障轉移（Round-Robin & Failover）
# ─────────────────────────────────────────────────────────────
def get_all_configured_keys():
  keys = []
  try:
    if "GEMINI_API_KEYS" in st.secrets:
      val = st.secrets["GEMINI_API_KEYS"]
      if isinstance(val, list):
        keys.extend([str(k).strip() for k in val if str(k).strip()])
      elif isinstance(val, str):
        keys.extend([k.strip() for k in val.split(",") if k.strip()])
    if "GEMINI_API_KEY_1" in st.secrets:
      keys.append(str(st.secrets["GEMINI_API_KEY_1"]).strip())
    if "GEMINI_API_KEY_2" in st.secrets:
      keys.append(str(st.secrets["GEMINI_API_KEY_2"]).strip())
    if "GEMINI_API_KEY" in st.secrets:
      keys.append(str(st.secrets["GEMINI_API_KEY"]).strip())
  except Exception:
    pass
  return list(dict.fromkeys(keys))


if "key_cycle_iter" not in st.session_state:
  configured_keys = get_all_configured_keys()
  st.session_state.key_cycle_iter = (
      itertools.cycle(configured_keys) if configured_keys else None
  )


def call_ai_model(api_key, prompt_text):
  candidate_keys = []
  if api_key and str(api_key).strip():
    candidate_keys.append(str(api_key).strip())

  all_keys = get_all_configured_keys()
  if all_keys:
    if (
        "key_cycle_iter" not in st.session_state
        or st.session_state.key_cycle_iter is None
    ):
      st.session_state.key_cycle_iter = itertools.cycle(all_keys)
    primary_key = next(st.session_state.key_cycle_iter)
    if primary_key not in candidate_keys:
      candidate_keys.append(primary_key)
    for k in all_keys:
      if k not in candidate_keys:
        candidate_keys.append(k)

  if not candidate_keys:
    return "❌ 尚未設定任何可用的 API Key！請於側邊欄輸入或配置 Secrets。"

  last_error = ""
  for idx_k, cur_key in enumerate(candidate_keys):
    try:
      if cur_key.startswith("sk-ant-"):
        headers = {
            "x-api-key": cur_key,
            "anthropic-version": "2023-06-01",
            "content-type": "application/json",
        }
        data = {
            "model": "claude-3-5-sonnet-20241022",
            "max_tokens": 2048,
            "messages": [{"role": "user", "content": prompt_text}],
        }
        res = requests.post(
            "https://api.anthropic.com/v1/messages",
            headers=headers,
            json=data,
            timeout=30,
        )
        if res.status_code == 200:
          return res.json().get("content", [{}])[0].get("text", "無回應內容")
        elif res.status_code in [429, 503]:
          last_error = f"Key #{idx_k + 1} 限速/配額耗盡 ({res.status_code})"
          continue
        else:
          return f"❌ Claude API 錯誤 ({res.status_code}): {res.text}"

      elif cur_key.startswith("sk-"):
        headers = {
            "Authorization": f"Bearer {cur_key}",
            "content-type": "application/json",
        }
        data = {
            "model": "gpt-4o",
            "messages": [{"role": "user", "content": prompt_text}],
        }
        res = requests.post(
            "https://api.openai.com/v1/chat/completions",
            headers=headers,
            json=data,
            timeout=30,
        )
        if res.status_code == 200:
          return (
              res.json()
              .get("choices", [{}])[0]
              .get("message", {})
              .get("content", "無回應內容")
          )
        elif res.status_code in [429, 503]:
          last_error = f"Key #{idx_k + 1} 限速/配額耗盡 ({res.status_code})"
          continue
        else:
          return f"❌ OpenAI API 錯誤 ({res.status_code}): {res.text}"

      else:
        ai_client = genai.Client(api_key=cur_key)
        response = ai_client.models.generate_content(
            model="gemini-3.6-flash", contents=prompt_text
        )
        return response.text

    except Exception as e:
      last_error = str(e)
      continue

  return f"❌ 所有可用 API Key 調用皆失敗。最後例外錯誤: {last_error}"


@st.cache_data(ttl=86400)
def fetch_institutional_investors(stock_code, days=120):
  try:
    url = f"https://www.twse.com.tw/rwd/zh/fund/T86?response=json&date=&selectType=ALLBUT0999&stockNo={stock_code}"
    response = requests.get(url, timeout=5)
    if response.status_code == 200 and response.text.strip().startswith("{"):
      data = response.json()
      if "data" in data and data["data"]:
        df = pd.DataFrame(data["data"], columns=data["fields"])
        df["日期"] = (
            df["日期"]
            .str.replace("/", "-")
            .apply(
                lambda x: str(int(x.split("-")[0]) + 1911)
                + "-"
                + "-".join(x.split("-")[1:])
            )
        )
        df["日期"] = pd.to_datetime(df["日期"])
        for col in ["外資買賣超", "投信買賣超"]:
          if col in df.columns:
            df[col] = df[col].astype(str).str.replace(",", "", regex=False)
            df[col] = pd.to_numeric(df[col], errors="coerce").fillna(0)
        return df.set_index("日期").sort_index().tail(days)
  except Exception:
    pass
  return pd.DataFrame()


# ─────────────────────────────────────────────────────────────
# 🎯 階段 1/2：下載市場成交排行（支援傳入即時進度條）
# ─────────────────────────────────────────────────────────────
def fetch_market_volume_rank(_progress_bar=None, _status_box=None):
  market_data = []
  headers = {
      "User-Agent": (
          "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML,"
          " like Gecko) Chrome/120.0.0.0 Safari/537.36"
      )
  }

  if _status_box:
    _status_box.info("🔍 [階段 1/2] 正在連線臺灣證券交易所與櫃買中心下載市場名單...")
  if _progress_bar:
    _progress_bar.progress(0.05)

  try:
    url_twse = "https://www.twse.com.tw/rwd/zh/afterTrading/MI_INDEX?response=json&type=ALL"
    res = requests.get(url_twse, headers=headers, timeout=10)
    if res.status_code == 200 and res.text.strip().startswith("{"):
      json_data = res.json()
      if "tables" in json_data:
        for table in json_data["tables"]:
          fields = table.get("fields", [])
          data = table.get("data", [])
          if any("成交股數" in str(f) for f in fields) and any(
              "證券代號" in str(f) for f in fields
          ):
            c_idx = [i for i, f in enumerate(fields) if "證券代號" in str(f)][0]
            n_idx = [i for i, f in enumerate(fields) if "證券名稱" in str(f)][0]
            v_idx = [i for i, f in enumerate(fields) if "成交股數" in str(f)][0]
            p_idx = [i for i, f in enumerate(fields) if "收盤價" in str(f)][0]

            for row in data:
              code, name = str(row[c_idx]).strip(), str(row[n_idx]).strip()
              if code.isdigit() and len(code) == 4:
                try:
                  close_p = float(
                      str(row[p_idx]).replace(",", "").replace("--", "0")
                  )
                  vol = int(str(row[v_idx]).replace(",", ""))
                  if close_p > 0:
                    market_data.append({
                        "代號": code,
                        "名稱": name,
                        "成交量(張)": int(vol / 1000),
                        "收盤價": close_p,
                        "市場": "上市",
                    })
                except Exception:
                  continue

    if _progress_bar:
      _progress_bar.progress(0.15)

    url_tpex = "https://www.tpex.org.tw/web/stock/aftertrading/otc_quotes_no14/stk_qt_result.php?l=zh-tw&o=json"
    res_otc = requests.get(url_tpex, headers=headers, timeout=10)
    if res_otc.status_code == 200 and res_otc.text.strip().startswith("{"):
      otc_json = res_otc.json()
      if "aaData" in otc_json:
        for row in otc_json["aaData"]:
          try:
            code, name = str(row[0]).strip(), str(row[1]).strip()
            if code.isdigit() and len(code) == 4:
              close_p = float(str(row[2]).replace(",", "").replace("---", "0"))
              vol = int(str(row[7]).replace(",", "")) * 1000
              if close_p > 0:
                market_data.append({
                    "代號": code,
                    "名稱": name,
                    "成交量(張)": int(vol / 1000),
                    "收盤價": close_p,
                    "市場": "上櫃",
                })
          except Exception:
            continue
  except Exception:
    pass

  if _progress_bar:
    _progress_bar.progress(0.25)

  if market_data:
    df_all = pd.DataFrame(market_data)
    df_all["成交金額(億)"] = (
        (df_all["成交量(張)"] * df_all["收盤價"]) / 100000.0
    ).round(2)

    top_amount = df_all.sort_values(by="成交金額(億)", ascending=False).head(
        350
    )
    top_volume = df_all.sort_values(by="成交量(張)", ascending=False).head(150)

    df_market = (
        pd.concat([top_amount, top_volume])
        .drop_duplicates(subset=["代號"])
        .reset_index(drop=True)
    )
    df_market = df_market.sort_values(
        by="成交金額(億)", ascending=False
    ).reset_index(drop=True)

    changes, pcts = [], []
    total_target = len(df_market["代號"])

    for idx_c, code in enumerate(df_market["代號"]):
      if _progress_bar:
        _progress_bar.progress(0.25 + (0.75 * (idx_c + 1) / total_target))
      if _status_box and (idx_c % 15 == 0 or idx_c == total_target - 1):
        _status_box.markdown(
            f"🔍 **[階段 1/2] 正在確認市場最新報價：`{idx_c + 1} /"
            f" {total_target}` 檔**..."
        )

      chg_val, pct_val, pct_str, success = 0.0, 0.0, "0.0%", False
      try:
        stock = twstock.Stock(code)
        if len(stock.price) >= 2:
          p_today, p_yest = float(stock.price[-1]), float(stock.price[-2])
          chg_val = round(p_today - p_yest, 2)
          pct_val = round((chg_val / p_yest) * 100, 2)
          pct_str = f"{pct_val:+.2f}%"
          success = True
      except Exception:
        pass

      changes.append(chg_val)
      pcts.append(pct_str)

    df_market["漲跌價差"] = changes
    df_market["漲跌幅"] = pcts
    return df_market

  return pd.DataFrame()


# ─────────────────────────────────────────────────────────────
# 🎯 單檔深度分析（具備 14:00 盤中退回昨日結算防護機制）
# ─────────────────────────────────────────────────────────────
@st.cache_data(ttl=86400)
def process_single_stock_scan(code, name, close_p, vol, chg, pct_str):
  try:
    for suffix in [".TW", ".TWO"]:
      df_hist = yf.download(
          f"{code}{suffix}", period="45d", interval="1d", progress=False
      )
      if not df_hist.empty and len(df_hist) >= 30:
        if isinstance(df_hist.columns, pd.MultiIndex):
          df_hist.columns = df_hist.columns.get_level_values(0)
        df_hist = df_hist[df_hist["Volume"] > 0]

        now = datetime.now()
        last_k_date = pd.to_datetime(df_hist.index[-1]).date()

        # 盤中 14:00 前執行，自動剔除今天未收盤資料
        if last_k_date == now.date() and now.time() < time(14, 0):
          df_hist = df_hist.iloc[:-1]

        if len(df_hist) < 25:
          continue

        latest_dt = pd.to_datetime(df_hist.index[-1]).strftime("%Y-%m-%d")
        vols = df_hist["Volume"].values
        closes = df_hist["Close"].values
        sector_name = get_stock_sector(code, name)

        multiday_entries = []
        for days_ago, key_str in zip(
            [0, 1, 2, 3, 4], ["T", "T-1", "T-2", "T-3", "T-4"]
        ):
          idx = -1 - days_ago
          v_val = int(vols[idx] / 1000)
          p_val = closes[idx]
          p_prev = closes[idx - 1] if abs(idx - 1) <= len(closes) else p_val
          pct_val = round(((p_val - p_prev) / p_prev) * 100, 2)
          amt_yi = round((v_val * p_val) / 100000.0, 2)
          velocity = round(pct_val * 2.5, 2)
          multiday_entries.append((
              key_str,
              {
                  "次產業板塊": sector_name,
                  "標的": f"{code} {name}",
                  "成交量": v_val,
                  "成交金額(億)": amt_yi,
                  "資金流速": velocity,
                  "漲跌幅": pct_val,
                  "收盤價": round(p_val, 2),
              },
          ))

        avg_vol_20_shares = (
            np.mean(vols[-21:-1]) if len(vols) >= 21 else np.mean(vols)
        )
        avg_vol_20_zhang = avg_vol_20_shares / 1000.0
        if avg_vol_20_zhang < 100:
          break

        vol_ratio = round(vol / (avg_vol_20_zhang + 1e-9), 2)
        prices = closes
        box_high = max(prices[-20:])
        is_breakout = close_p >= box_high * 0.99

        p_series = pd.Series(prices[-40:])
        ema12 = p_series.ewm(span=12, adjust=False).mean()
        ema26 = p_series.ewm(span=26, adjust=False).mean()
        macd_bar = (
            ema12 - ema26 - (ema12 - ema26).ewm(span=9, adjust=False).mean()
        ) * 2
        m_today, m_yesterday = float(macd_bar.iloc[-1]), float(
            macd_bar.iloc[-2]
        )
        is_green_to_red = (m_yesterday < 0) and (m_today >= 0)

        score, signals = vol_ratio * 15, []
        if vol_ratio >= 1.2:
          signals.append(f"成交量放大 {vol_ratio}倍")
          score += 15
        if is_breakout:
          signals.append("極值壓力突破")
          score += 25
        if is_green_to_red:
          signals.append("MACD 綠翻紅")
          score += 30
        if m_today > 0:
          signals.append("多方動能續航")
          score += 10
        if code in CB_DATABASE:
          signals.append("CB 飆股基因")
          score += 35

        amt_stock_yi = round((vol * close_p) / 100000.0, 2)
        pct_numeric = 0.0
        try:
          pct_numeric = float(
              str(pct_str).replace("%", "").replace("+", "").strip()
          )
        except Exception:
          pct_numeric = 0.0

        is_super_turnover = (amt_stock_yi >= 20.0) and (chg >= 0)
        is_momentum_focus = (
            (amt_stock_yi >= 8.0)
            and (vol_ratio >= 1.8)
            and (pct_numeric >= 3.0)
        )

        if is_super_turnover or is_momentum_focus:
          signals.append("市場人氣焦點")
          score += 15

        radar_item = {
            "code": code,
            "name": name,
            "price": close_p,
            "volume": vol,
            "amount": amt_stock_yi,
            "change": chg,
            "pct": pct_str,
            "tags": signals,
            "score": round(score, 1),
        }
        return radar_item, multiday_entries, latest_dt
  except Exception:
    pass
  return None, [], None


# ─────────────────────────────────────────────────────────────
# 🎯 階段 2/2：300 檔技術指標與資金流速深度演算
# ─────────────────────────────────────────────────────────────
def run_unified_market_scan(
    df_top_data, _progress_bar=None, _status_box=None, **kwargs
):
  p_bar = _progress_bar or kwargs.get("progress_bar", None)
  s_box = _status_box or kwargs.get("status_box", None)

  scored_radar = []
  latest_dates_collected = []
  historical_multiday_data = {"T-4": [], "T-3": [], "T-2": [], "T-1": [], "T": []}

  scan_targets = df_top_data.head(300)
  total_count = len(scan_targets)

  for idx, (_, row) in enumerate(scan_targets.iterrows()):
    code, name, close_p, vol, chg, pct_str = (
        row["代號"],
        row["名稱"],
        row["收盤價"],
        row["成交量(張)"],
        row["漲跌價差"],
        row["漲跌幅"],
    )

    if p_bar is not None and hasattr(p_bar, "progress"):
      try:
        p_bar.progress((idx + 1) / total_count)
      except Exception:
        pass
    if s_box is not None and hasattr(s_box, "markdown"):
      try:
        s_box.markdown(
            f"⏳ **[階段 2/2] 深度演算進度：`{idx + 1} / {total_count}` 檔** — 正在分析"
            f" **【{code} {name}】**..."
        )
      except Exception:
        pass

    radar_item, multiday_entries, latest_dt = process_single_stock_scan(
        code, name, close_p, vol, chg, pct_str
    )

    if radar_item:
      scored_radar.append(radar_item)
    if latest_dt:
      latest_dates_collected.append(latest_dt)
    for k_str, entry in multiday_entries:
      historical_multiday_data[k_str].append(entry)

  scored_radar = sorted(scored_radar, key=lambda x: x["score"], reverse=True)
  actual_scan_date = (
      max(set(latest_dates_collected), key=latest_dates_collected.count)
      if latest_dates_collected
      else datetime.now().strftime("%Y-%m-%d")
  )

  b_days = (
      pd.bdate_range(end=actual_scan_date, periods=5)
      .strftime("%Y-%m-%d")
      .tolist()
  )

  multiday_dates = {
      "T-4": b_days[0],
      "T-3": b_days[1],
      "T-2": b_days[2],
      "T-1": b_days[3],
      "T": b_days[4],
  }

  return (
      scored_radar[:100],
      actual_scan_date,
      historical_multiday_data,
      multiday_dates,
  )


st.title("📈 台股智慧量化分析與戰略系統")
st.markdown(
    "歡迎使用多頁面模組化台股量化系統！請透過左側側邊欄切換至您想要使用的功能分頁："
)
st.markdown(
    "- **📊 個股智慧量化儀表板**：單一標的極值戰略、MACD、可轉債、集保千張大戶持股與 AI"
    " 深度推理。"
)
st.markdown(
    "- **⚡ 全市場動能掃描中心**：雙軌成交金額/量能精準入榜、嚴格量化市場人氣焦點、即時進度條。"
)
st.markdown(
    "- **🌊 巨觀板塊資金輪動戰情室**：5 日時間軸拉桿、次產業與題材 Treemap"
    " 資金佔比。"
)