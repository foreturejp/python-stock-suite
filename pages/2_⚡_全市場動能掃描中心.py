from datetime import datetime
import os
from pathlib import Path
import pickle  # 👈 用於將每日掃描結果快速保存至硬碟
import sys
import numpy as np
import pandas as pd
import streamlit as st
import twstock

# 確保模組路徑包含專案根目錄
root_dir = Path(__file__).resolve().parent.parent
if str(root_dir) not in sys.path:
  sys.path.insert(0, str(root_dir))

from app import call_ai_model, fetch_market_volume_rank, run_unified_market_scan

st.set_page_config(
    page_title="全市場動能掃描中心", page_icon="⚡", layout="wide"
)

# ─── 💾 本地磁碟快取管理（防重新整理 F5 遺失）───
CACHE_DIR = Path(root_dir) / "cache_data"
CACHE_DIR.mkdir(exist_ok=True)
TODAY_STR = datetime.now().strftime("%Y-%m-%d")
CACHE_FILE = CACHE_DIR / f"market_scan_{TODAY_STR}.pkl"


def load_disk_cache():
  if CACHE_FILE.exists():
    try:
      with open(CACHE_FILE, "rb") as f:
        return pickle.load(f)
    except Exception:
      pass
  return None


def save_disk_cache(data):
  try:
    with open(CACHE_FILE, "wb") as f:
      pickle.dump(data, f)
  except Exception:
    pass


# 💡 初始化 Session State 變數
if "persistent_selected_stocks" not in st.session_state or not isinstance(
    st.session_state["persistent_selected_stocks"], set
):
  st.session_state["persistent_selected_stocks"] = set()

if "scan_run" not in st.session_state:
  st.session_state["scan_run"] = False
if "df_top" not in st.session_state:
  st.session_state["df_top"] = pd.DataFrame()
if "qualified_results" not in st.session_state:
  st.session_state["qualified_results"] = []
if "multiday_data" not in st.session_state:
  st.session_state["multiday_data"] = {}
if "multiday_dates" not in st.session_state:
  st.session_state["multiday_dates"] = {}
if "scan_date_str" not in st.session_state:
  st.session_state["scan_date_str"] = ""
if "last_scan_time" not in st.session_state:
  st.session_state["last_scan_time"] = None
if "ai_analysis_result" not in st.session_state:
  st.session_state["ai_analysis_result"] = ""

# 🎯 核心機制：若重新整理（F5），自動由硬碟載入今日已跑過的結果
if not st.session_state.get("scan_run", False):
  cached_today = load_disk_cache()
  if cached_today:
    st.session_state["df_top"] = cached_today["df_top"]
    st.session_state["qualified_results"] = cached_today["qualified_results"]
    st.session_state["multiday_data"] = cached_today["multiday_data"]
    st.session_state["multiday_dates"] = cached_today["multiday_dates"]
    st.session_state["scan_date_str"] = cached_today["scan_date_str"]
    st.session_state["last_scan_time"] = cached_today["last_scan_time"]
    st.session_state["scan_run"] = True

st.title("⚡ 全市場智慧動能掃描與戰略雷達")
st.markdown(
    "一鍵掃描前 300 檔強勢潛力股，透過**多維度戰略訊號篩選器**與**自選 AI"
    " 深度對比分析**精準掌握黑馬！"
)

# ─── 掃描按鈕操作區 ───
with st.container(border=True):
  col_btn1, col_btn2 = st.columns([4, 1], vertical_alignment="center")

  scan_btn_label = "⚡ 啟動全市場智慧動能掃描 (前300檔)"
  if st.session_state.get("last_scan_time"):
    scan_btn_label = (
        f"⚡ 重新掃描市場動能 (上次更新: {st.session_state['last_scan_time']})"
    )

  with col_btn1:
    start_scan = st.button(scan_btn_label, use_container_width=True)
  with col_btn2:
    clear_cache_btn = st.button("🗑️ 清除今日快取", use_container_width=True)

  if clear_cache_btn:
    if CACHE_FILE.exists():
      CACHE_FILE.unlink()
    st.session_state["scan_run"] = False
    st.session_state["qualified_results"] = []
    st.success("已清除今日快取！")
    st.rerun()

  if st.session_state.get("scan_run", False):
    st.caption(
        f"✅ 已載入今日 ({st.session_state.get('last_scan_time')}) 資料。"
        " 重新整理網頁將保持存在，無須重複運算。"
    )
  else:
    st.info(
        "💡 **貼心提醒**：全市場掃描資金流速建模約需 **10幾分鐘**，跑完一次後今天內重新整理網頁都會瞬間秒開！"
    )

  if start_scan:
    progress_bar = st.progress(0)
    status_box = st.empty()

    # 第一階段：300 大名單
    df_top = fetch_market_volume_rank(
        _progress_bar=progress_bar, _status_box=status_box
    )

    if not df_top.empty:
      st.session_state["df_top"] = df_top

      # 第二階段：技術指標與資金流速
      scored_radar, scan_date, multiday_data, multiday_dates = (
          run_unified_market_scan(
              df_top, _progress_bar=progress_bar, _status_box=status_box
          )
      )

      last_time_str = datetime.now().strftime("%Y-%m-%d %H:%M")
      st.session_state["qualified_results"] = scored_radar
      st.session_state["multiday_data"] = multiday_data
      st.session_state["multiday_dates"] = multiday_dates
      st.session_state["scan_date_str"] = scan_date
      st.session_state["scan_run"] = True
      st.session_state["last_scan_time"] = last_time_str

      # 💾 儲存到本機硬碟檔案
      save_disk_cache({
          "df_top": df_top,
          "qualified_results": scored_radar,
          "multiday_data": multiday_data,
          "multiday_dates": multiday_dates,
          "scan_date_str": scan_date,
          "last_scan_time": last_time_str,
      })

      progress_bar.empty()
      status_box.empty()
      st.rerun()

if st.session_state.scan_run and not st.session_state.df_top.empty:
  scan_display_date = st.session_state.get(
      "scan_date_str", datetime.now().strftime("%Y-%m-%d")
  )
  st.markdown(f"📅 **市場掃描基準日期：{scan_display_date} 收盤結算**")

  with st.expander("📊 全市場成交排行總覽 (前50大)"):
    st.dataframe(
        st.session_state.df_top.head(50), use_container_width=True, height=250
    )

  st.markdown("---")

  if st.session_state.qualified_results:
    st.markdown("🎛️ **戰略訊號篩選器（嚴格交集 AND）**")

    # 🎨 定義 6 個篩選選項與各自的專屬色彩
    filter_options = [
        {"name": "CB 飆股基因", "color": "#e67e22"},
        {"name": "成交量放大", "color": "#3498db"},
        {"name": "極值壓力突破", "color": "#9b59b6"},
        {"name": "MACD 綠翻紅", "color": "#27ae60"},
        {"name": "多方動能續航", "color": "#1abc9c"},
        {"name": "市場人氣焦點", "color": "#e84393"},
    ]

    cols_filter = st.columns(3)
    selected_filters = []

    for idx, opt in enumerate(filter_options):
      with cols_filter[idx % 3]:
        c_chk, c_box = st.columns([1, 6], vertical_alignment="center")

        with c_chk:
          if st.checkbox(
              "選取",
              key=f"filter_chk_{opt['name']}",
              label_visibility="collapsed",
          ):
            selected_filters.append(opt["name"])

        with c_box:
          st.markdown(
              f"""
              <div style="
                  background-color: {opt['color']}; 
                  color: #ffffff; 
                  padding: 8px 12px; 
                  border-radius: 6px; 
                  text-align: center; 
                  font-weight: bold; 
                  font-size: 14px; 
                  box-shadow: 0 2px 4px rgba(0,0,0,0.2);
              ">
                  {opt['name']}
              </div>
              """,
              unsafe_allow_html=True,
          )

    st.markdown("<br>", unsafe_allow_html=True)

    filtered_results = []
    for res in st.session_state.qualified_results:
      tags_list = res["tags"]
      if not selected_filters:
        filtered_results.append(res)
      else:
        if all(any(f in t for t in tags_list) for f in selected_filters):
          filtered_results.append(res)

    st.success(
        f"🎯 篩選完成！符合條件的強勢標的有 **{len(filtered_results)} 檔**："
    )

    if not filtered_results:
      st.warning("⚠️ 目前無符合條件的標的。")
    else:
      st.markdown(
          "📋 **強勢標的戰略雷達卡片清單 (內建捲軸，請於卡片左側勾選標的)**"
      )

      signal_color_map = {
          "CB 飆股基因": "#e67e22",
          "成交量放大": "#3498db",
          "極值壓力突破": "#9b59b6",
          "MACD 綠翻紅": "#27ae60",
          "多方動能續航": "#1abc9c",
          "市場人氣焦點": "#e84393",
      }

      # 💡 滾動容器
      with st.container(height=520, border=True):
        for res in filtered_results:
          code = res["code"]
          name = res["name"]
          score = res["score"]
          volume = res["volume"]
          tags = res["tags"]

          with st.container(border=True):
            col_chk, col_detail = st.columns(
                [1, 15], vertical_alignment="center"
            )

            with col_chk:
              # 🎯 核心同步邏輯：以 persistent_selected_stocks 為唯一依據
              is_checked = (
                  code in st.session_state.persistent_selected_stocks
              )
              chk_val = st.checkbox(
                  "選擇",
                  value=is_checked,
                  key=f"card_chk_{code}",
                  label_visibility="collapsed",
              )

              # 當使用者手動點擊切換狀態時，立即同步並更新
              if (
                  chk_val
                  and code not in st.session_state.persistent_selected_stocks
              ):
                st.session_state.persistent_selected_stocks.add(code)
                st.rerun()
              elif (
                  not chk_val
                  and code in st.session_state.persistent_selected_stocks
              ):
                st.session_state.persistent_selected_stocks.discard(code)
                st.rerun()

            with col_detail:
              tags_html_parts = []
              for t in tags:
                bg_color = "#3f3f5f"
                for k, color in signal_color_map.items():
                  if k in t:
                    bg_color = color
                    break
                tags_html_parts.append(
                    f'<span style="background-color: {bg_color}; color: #ffffff;'
                    f' padding: 3px 8px; border-radius: 4px; font-size: 12px;'
                    f' font-weight: bold; margin-right: 6px; display:'
                    f' inline-block; box-shadow: 0 1px 2px'
                    f' rgba(0,0,0,0.2);">{t}</span>'
                )

              tags_html = "".join(tags_html_parts)

              st.markdown(
                  f"### 🏷️ 【{code} {name}】<br>"
                  f"**📌 戰略訊號** : {tags_html} <br><br>"
                  f"**戰略評分** : `{score}` 分 | **成交量** : `{volume:,}` 張",
                  unsafe_allow_html=True,
              )

      st.markdown("---")

    # ─────────────────────────────────────────────────────────
    # 🎯 右側主畫面：AI 戰略對比推理大看板（寬版高質感呈現）
    # ─────────────────────────────────────────────────────────
    if st.session_state.ai_analysis_result:
      st.markdown("---")
      col_rep_t, col_rep_btn = st.columns([5, 1], vertical_alignment="center")
      with col_rep_t:
        st.subheader("🧠 AI 跨標的深度戰略推理報告")
      with col_rep_btn:
        if st.button("✕ 關閉報告", key="close_ai_report"):
          st.session_state.ai_analysis_result = ""
          st.rerun()

      with st.container(border=True):
        st.markdown(st.session_state.ai_analysis_result)

    # ─────────────────────────────────────────────────────────
    # 🧠 側邊欄 AI 智慧比對中樞（標的選取、自訂問題、啟動發送）
    # ─────────────────────────────────────────────────────────
    with st.sidebar:
      st.markdown("---")
      st.markdown("### 🤖 AI 跨標的比對中樞")

      col_title, col_clear = st.columns([3, 2], vertical_alignment="center")
      with col_title:
        st.markdown("📌 **已勾選目標**")
      with col_clear:
        if st.session_state.persistent_selected_stocks:
          if st.button(
              "🗑️ 清空全部", key="clear_all_selected", use_container_width=True
          ):
            st.session_state.persistent_selected_stocks.clear()
            st.rerun()

      selected_for_ai = [
          res
          for res in st.session_state.qualified_results
          if res["code"] in st.session_state.persistent_selected_stocks
      ]

      if not st.session_state.persistent_selected_stocks:
        st.info("💡 尚未勾選任何個股\n請從主畫面卡片勾選欲比對的標的。")
      else:
        current_selected_codes = list(
            st.session_state.persistent_selected_stocks
        )

        for stock_code in current_selected_codes:
          s_name = next(
              (
                  r["name"]
                  for r in st.session_state.qualified_results
                  if r["code"] == stock_code
              ),
              "",
          )

          c_box, c_btn = st.columns([4, 1], vertical_alignment="center")

          with c_box:
            st.markdown(
                f"""
                <div style="
                    background-color: #1e1e2f; 
                    border: 1px solid #3d3d5d; 
                    padding: 8px 10px; 
                    border-radius: 6px; 
                    font-size: 12px;
                    color: #ffffff;
                    font-weight: bold;
                    white-space: nowrap;
                    overflow: hidden;
                    text-overflow: ellipsis;
                ">
                    🏷️ {stock_code} {s_name}
                </div>
                """,
                unsafe_allow_html=True,
            )

          with c_btn:
            # 🎯 點擊「✕」時，從 persistent_selected_stocks 剔除，並立即重新整理同步畫面
            if st.button("✕", key=f"del_side_{stock_code}", help="移除此標的"):
              st.session_state.persistent_selected_stocks.discard(stock_code)
              st.rerun()

        st.markdown("<br>", unsafe_allow_html=True)

        # 🎯 備用 Key 設定區（如果 secrets.toml 沒讀到，可展開直接輸入）
        with st.expander("🔑 API Key 設定（可選/備用）", expanded=False):
          manual_api_key = st.text_input(
              "手動輸入 Key（支援逗號分隔兩組）:",
              value="",
              type="password",
              placeholder="AIzaSy..., AIzaSy...",
              key="sidebar_manual_api_key",
          )

        # 🎯 自訂提問輸入框
        user_ai_question = st.text_area(
            "💬 自訂 AI 提問/戰略焦點（可選）：",
            placeholder=(
                "例如：請針對這幾檔短線突破力道與籌碼面進行深度評估，並給予操作建議..."
            ),
            height=100,
            key="custom_ai_prompt_sidebar",
        )

        run_ai_btn = st.button(
            "🚀 啟動 AI 深度對比推理",
            use_container_width=True,
            key="run_ai_comparison_sidebar_btn",
        )

        if run_ai_btn:
          if not selected_for_ai:
            st.warning("⚠️ 請勾選至少一檔個股！")
          else:
            with st.spinner("🤖 AI 正在進行跨個股強弱對比推理..."):
              stock_list_str = "\n".join([
                  f"- 代號: {t['code']} {t['name']} | 戰略評分: {t['score']} 分 |"
                  f" 訊號: {', '.join(t['tags'])} | 成交量: {t['volume']} 張"
                  for t in selected_for_ai
              ])

              custom_instruction = (
                  f"【使用者的具體關注重點】：\n{user_ai_question}\n\n"
                  if user_ai_question.strip()
                  else ""
              )

              batch_prompt = f"""
你是一位專業的台股量化操盤室戰略分析師。請針對使用者目前勾選的強勢標的進行深度交叉比對：

【目標標的清單與訊號】：
{stock_list_str}

{custom_instruction}
請從以下維度進行具體推理（請用專業、精煉、具操作價值的繁體中文分析）：
1. 標的強弱梯隊排序與資金集中度
2. 型態突破與成交量健康度
3. 潛在風險提示（高檔爆量滯漲或假突破）
4. 具體進出場防守點位與戰略總結
"""
              st.session_state.ai_analysis_result = call_ai_model(
                  manual_api_key, batch_prompt
              )
              st.rerun()
