from datetime import datetime, time, timedelta
import json
import os
import warnings
from google import genai
from google.oauth2 import service_account
import numpy as np
import pandas as pd
import plotly.express as px
import requests
import streamlit as st
import twstock
import yfinance as yf

# ─────────────────────────────────────────────────────────────
# 🔑 確保 100% 成功的 GCP 服務帳戶（JSON 字典）初始化
# ─────────────────────────────────────────────────────────────
client = None

try:
  if "gcp_service_account" in st.secrets:
    # 1. 直接將 Streamlit Secrets 中的 Service Account 轉為 Python 字典
    sa_info = dict(st.secrets["gcp_service_account"])
    project_id = sa_info.get("project_id", "streamlit-vertex-sa")

    # 2. 使用 Google 官方授權模組直接從 Dict 建立認證物件
    credentials = service_account.Credentials.from_service_account_info(
        sa_info,
        scopes=["https://www.googleapis.com/auth/cloud-platform"],
    )

    # 3. 完美綁定 Vertex AI 通道、專案與憑證
    client = genai.Client(
        vertexai=True,
        credentials=credentials,
        project=project_id,
        location="us-central1",
    )
except Exception as e:
  print(f"GCP 服務帳戶初始化例外: {e}")

# 安全退守機制
if client is None:
  try:
    client = genai.Client(vertexai=True)
  except Exception as e:
    print(f"退守初始化失敗: {e}")

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


# ─────────────────────────────────────────────────────────────
# 🎯 鎖定使用 gemini-3.7-flash 的安全 AI 呼叫核心
# ─────────────────────────────────────────────────────────────
def call_ai_model(api_key, prompt_text):
  global client
  try:
    if client is not None:
      response = client.models.generate_content(
          model="gemini-3.7-flash", contents=prompt_text
      )
      return response.text
    else:
      return "❌ AI 客戶端尚未初始化，請檢查 Streamlit Secrets 中的 gcp_service_account 設定。"
  except Exception as e:
    return f"❌ AI 調用失敗 (Vertex AI): {e}"
