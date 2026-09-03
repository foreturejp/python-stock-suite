from datetime import datetime
import numpy as np
import pandas as pd
import plotly.express as px
import streamlit as st

st.set_page_config(
    page_title="巨觀資金輪動戰情室", page_icon="🌊", layout="wide"
)

# 🎨 注入高質感操盤介面專屬 CSS 樣式
st.markdown(
    """
<style>
    .timeline-card {
        background-color: #181824;
        border: 1px solid #2d2d3d;
        padding: 20px 15px 15px 15px;
        border-radius: 12px;
        box-shadow: 0 4px 12px rgba(0,0,0,0.3);
        margin-bottom: 20px;
    }
</style>
""",
    unsafe_allow_html=True,
)

st.title("🌊 巨觀次產業與概念題材資金輪動戰情室")
st.markdown(
    "結合 **5日流暢資金動能時間軸** 與 **雙層級折疊熱力圖**"
    "：初始僅呈現各族群當日市場資金佔比，點擊該族群方塊後才會展開族內個股！"
)

if "scan_run" not in st.session_state or not st.session_state.scan_run:
  st.warning(
      "⚠️ 請先至「⚡ 全市場動能掃描中心」頁面執行掃描，以載入巨觀板塊數據！"
  )
else:
  # 初始化當前選中的時間點索引 (預設為 4，即最新 T 日)
  if "timeline_step_idx" not in st.session_state:
    st.session_state.timeline_step_idx = 4

  multiday_dates = st.session_state.get(
      "multiday_dates",
      {"T-4": "", "T-3": "", "T-2": "", "T-1": "", "T": ""},
  )

  timeline_keys = ["T-4", "T-3", "T-2", "T-1", "T"]

  # 🎛️ 模式切換器選擇區
  analysis_mode = st.radio(
      "模式切換",
      [
          "🌐 全市場產業熱力圖 (嚴格無重疊)",
          "🔥 概念題材熱力圖 (主題式篩選)",
      ],
      horizontal=True,
  )

  st.markdown("<br>", unsafe_allow_html=True)

  # 🌟 質感面板外框（時間軸滑桿 + 點選按鈕雙向操控）
  st.markdown("<div class='timeline-card'>", unsafe_allow_html=True)
  st.markdown("⏳ **5 日資金動能時間軸操控盤 (可滑動滑桿或直接點選下方天數切換)**")

  col_l, col_slider_box, col_r = st.columns([0.5, 9, 0.5])

  with col_slider_box:

    def on_slider_change():
      st.session_state.timeline_step_idx = (
          st.session_state.timeline_slider_widget
      )

    # 1. 滑桿（與 session_state 雙向連動）
    st.slider(
        "時間軸",
        min_value=0,
        max_value=4,
        value=st.session_state.timeline_step_idx,
        step=1,
        key="timeline_slider_widget",
        on_change=on_slider_change,
        label_visibility="collapsed",
    )

    # 2. 下方 5 個純淨的點選按鈕 (去除多餘字眼，保留 T-N 與日期)
    cols_btn = st.columns(5)
    for i, key in enumerate(timeline_keys):
      with cols_btn[i]:
        date_str = multiday_dates.get(key, "")
        btn_label = f"**{key}**\n\n{date_str}" if date_str else f"**{key}**"
        is_active = st.session_state.timeline_step_idx == i

        # 選中時採用 Primary 亮色強調，未選中採用 Secondary
        if st.button(
            btn_label,
            key=f"btn_timeline_{key}",
            use_container_width=True,
            type="primary" if is_active else "secondary",
        ):
          st.session_state.timeline_step_idx = i
          st.rerun()

  st.markdown("</div>", unsafe_allow_html=True)
  st.markdown("<br>", unsafe_allow_html=True)

  active_key = timeline_keys[st.session_state.timeline_step_idx]
  active_date = multiday_dates.get(active_key, "")
  selected_timeline_label = (
      f"{active_key}日 ({active_date})" if active_date else f"{active_key}日"
  )

  df_temp_data = st.session_state.get("multiday_data", {}).get(active_key, [])
  df_treemap = pd.DataFrame(df_temp_data)

  if not df_temp_data:
    st.info("⚠️ 無對應的矩形樹狀圖數據。")
  else:
    # 確保數值型別正確
    df_treemap["漲跌幅"] = pd.to_numeric(
        df_treemap["漲跌幅"], errors="coerce"
    ).fillna(0.0)
    df_treemap["成交金額(億)"] = pd.to_numeric(
        df_treemap["成交金額(億)"], errors="coerce"
    ).fillna(0.0)

    # 計算全市場總成交金額
    total_market_vol = df_treemap["成交金額(億)"].sum()

    if "🌐 全市場產業熱力圖" in analysis_mode:
      # ──────────────────────────────────────────────────────────
      # 模式一：全市場產業熱力圖
      # ──────────────────────────────────────────────────────────
      sector_totals = df_treemap.groupby("次產業板塊")[
          "成交金額(億)"
      ].transform("sum")
      df_treemap["次產業佔比%"] = (
          sector_totals / (total_market_vol + 1e-9)
      ) * 100

      # 僅保留資金佔比 >= 1.0% 的板塊
      df_plot_market = df_treemap[df_treemap["次產業佔比%"] >= 1.0].copy()
      df_plot_market["市場總覽"] = (
          f"核心次產業 (>=1%) [{selected_timeline_label}]"
      )

      fig_map = px.treemap(
          df_plot_market,
          path=["市場總覽", "次產業板塊", "標的"],
          values="成交金額(億)",
          color="漲跌幅",
          color_continuous_scale="RdYlGn_r",  # 紅漲綠跌
          color_continuous_midpoint=0.0,
      )

      fig_map.update_traces(
          maxdepth=2,
          texttemplate=(
              "<span style='font-size:32px;"
              " font-weight:900;'>%{label}</span><br><span style='font-size:22px;"
              " font-weight:700;'>%{percentRoot:.1%}</span>"
          ),
          textposition="middle center",
          insidetextfont=dict(size=44),
          hovertemplate=(
              "<b>%{label}</b><br>漲跌幅: %{color:+.2f}%<extra></extra>"
          ),
          marker=dict(cornerradius=6),
          root_color="#1e1e2f",
      )
      fig_map.update_layout(
          template="plotly_dark",
          height=700,
          margin=dict(t=10, l=10, r=10, b=10),
      )

      st.subheader(
          "📊 全市場核心次產業資金輪動 (佔比 ≥ 1%) —"
          f" 【{selected_timeline_label}】"
      )
      st.plotly_chart(fig_map, use_container_width=True)

    else:
      # ──────────────────────────────────────────────────────────
      # 模式二：概念題材熱力圖（已徹底拆分通路代理）
      # ──────────────────────────────────────────────────────────
      st.subheader(
          "🔥 核心概念題材資金聚焦熱力圖 (佔比 ≥ 1%) —"
          f" 【{selected_timeline_label}】"
      )

      def map_theme(row):
        s = str(row.get("次產業板塊", ""))
        target = str(row.get("標的", ""))

        if "3036" in target or "文曄" in target:
          return "🚗 車用工控晶片代理(文曄)"
        if "8112" in target or "至上" in target:
          return "💾 記憶體大宗代理(至上)"
        if "3702" in target or "大聯大" in target:
          return "📦 運算與全方位IC通路(大聯大)"
        if any(k in target for k in ["6189", "豐藝", "3528", "安馳"]):
          return "🔌 高階FPGA與利基代理"
        if "通路" in s or "代理" in s:
          return "📦 綜合電子零組件通路"

        if any(
            k in s
            for k in [
                "晶圓代工",
                "IC設計",
                "矽智財",
                "ASIC",
                "先進封測",
                "測試介面",
            ]
        ):
          return "⚡ 半導體核心與先進運算"
        if any(k in s for k in ["設備", "廠務", "晶圓材料", "特化"]):
          return "🔬 半導體設備材料與耗材"
        if any(k in s for k in ["記憶體"]):
          return "💾 記憶體與儲存架構"

        if any(k in s for k in ["AI伺服器", "組裝", "工業電腦"]):
          return "🤖 AI 伺服器與運算組裝"
        if any(k in s for k in ["機殼", "導軌", "機構"]):
          return "🖥️ 伺服器機殼與滑軌導軌"
        if any(k in s for k in ["散熱", "水冷", "風扇"]):
          return "🧊 水冷與高效散熱模組"
        if any(k in s for k in ["PCB", "CCL", "載板", "銅箔"]):
          return "🧬 高頻高速載板與PCB"
        if any(k in s for k in ["電源", "儲能", "被動元件", "電感"]):
          return "🔋 電源管理與被動元件"
        if any(k in s for k in ["連接器", "傳輸線", "線束"]):
          return "🔌 高頻連接線與傳輸機構"

        if any(
            k in s for k in ["光通訊", "CPO", "矽光子", "化合物", "PA"]
        ):
          return "🔥 矽光子CPO與光通訊"
        if any(k in s for k in ["網通", "交換器", "低軌衛星"]):
          return "🌐 高速網通與衛星通訊"
        if any(k in s for k in ["鏡頭", "光學", "面板", "光電"]):
          return "📷 光學鏡頭與光電顯示"

        if any(k in s for k in ["重電", "電網", "線纜", "綠能"]):
          return "⚡ 重電電網與綠能儲能"
        if any(k in s for k in ["機器人", "工具機", "自動化"]):
          return "🦾 機器人與智慧製造"
        if any(k in s for k in ["航運", "海運", "航空", "客貨"]):
          return "🚢 航運交通與航空貨運"
        if any(k in s for k in ["營建", "地產", "建案"]):
          return "🏘️ 營建地產與資產開發"
        if any(k in s for k in ["金控", "銀行", "壽險", "證券"]):
          return "🏦 金融控股與資產管理"
        if any(k in s for k in ["生技", "CDMO", "新藥", "醫材"]):
          return "💊 生技製藥與醫療健康"
        if any(k in s for k in ["塑膠", "化學", "鋼鐵", "水泥"]):
          return "🧪 大宗原物料與重工業"
        if any(k in s for k in ["汽車", "車用"]):
          return "🚗 汽車工業與車用電子"
        if any(k in s for k in ["資服", "軟體", "資訊", "資安"]):
          return "💻 資訊系統與資安軟體"
        if any(k in s for k in ["消費", "食品", "零售", "運動"]):
          return "🛍️ 民生消費與生活零售"

        return "🌐 其他中小型題材"

      df_treemap["概念題材"] = df_treemap.apply(map_theme, axis=1)

      theme_totals = df_treemap.groupby("概念題材")[
          "成交金額(億)"
      ].transform("sum")
      df_treemap["題材資金佔比%"] = (
          theme_totals / (total_market_vol + 1e-9)
      ) * 100

      df_plot_theme = df_treemap[df_treemap["題材資金佔比%"] >= 1.0].copy()
      df_plot_theme["市場大盤"] = (
          f"核心概念題材 (>=1%) [{selected_timeline_label}]"
      )

      fig_theme = px.treemap(
          df_plot_theme,
          path=["市場大盤", "概念題材", "標的"],
          values="成交金額(億)",
          color="漲跌幅",
          color_continuous_scale="RdYlGn_r",
          color_continuous_midpoint=0.0,
      )

      fig_theme.update_traces(
          maxdepth=2,
          texttemplate=(
              "<span style='font-size:32px;"
              " font-weight:900;'>%{label}</span><br><span style='font-size:22px;"
              " font-weight:700;'>%{percentRoot:.1%}</span>"
          ),
          textposition="middle center",
          insidetextfont=dict(size=44),
          hovertemplate=(
              "<b>%{label}</b><br>漲跌幅: %{color:+.2f}%<extra></extra>"
          ),
          marker=dict(cornerradius=6),
          root_color="#1e1e2f",
      )
      fig_theme.update_layout(
          template="plotly_dark",
          height=700,
          margin=dict(t=10, l=10, r=10, b=10),
      )

      st.plotly_chart(fig_theme, use_container_width=True)

      # 📊 概念題材純數值動能明細表
      st.markdown(
          "<br><h5>📋 當日核心概念題材數值明細 (佔比 ≥ 1.0%)</h5>",
          unsafe_allow_html=True,
      )
      df_plot_theme["金額_x_漲跌"] = (
          df_plot_theme["成交金額(億)"] * df_plot_theme["漲跌幅"]
      )
      theme_summary = (
          df_plot_theme.groupby("概念題材")
          .agg(
              成交金額_億=("成交金額(億)", "sum"),
              加權分子=("金額_x_漲跌", "sum"),
              成分股家數=("標的", "count"),
          )
          .reset_index()
      )

      theme_summary["加權平均漲跌%"] = (
          theme_summary["加權分子"] / (theme_summary["成交金額_億"] + 1e-9)
      ).round(2)
      theme_summary["全市場資金佔比%"] = (
          (theme_summary["成交金額_億"] / (total_market_vol + 1e-9)) * 100
      ).round(2)

      theme_table = theme_summary[[
          "概念題材",
          "成交金額_億",
          "全市場資金佔比%",
          "加權平均漲跌%",
          "成分股家數",
      ]].sort_values(by="成交金額_億", ascending=False)

      def color_val(val):
        if val > 0:
          return "color: #ff4d4f; font-weight: bold;"
        elif val < 0:
          return "color: #52c41a; font-weight: bold;"
        return "color: #8c8c8c;"

      styled_theme_table = (
          theme_table.style.format({
              "成交金額_億": "{:,.2f} 億",
              "全市場資金佔比%": "{:.2f}%",
              "加權平均漲跌%": "{:+.2f}%",
              "成分股家數": "{:d} 檔",
          })
          .map(color_val, subset=["加權平均漲跌%"])
          .bar(
              subset=["全市場資金佔比%"],
              color="rgba(33, 150, 243, 0.25)",
              vmin=0,
          )
      )

      st.dataframe(styled_theme_table, use_container_width=True, height=360)

  # =========================================================================
  # 📈 次產業資金與趨勢統計表（近 3 日 / 近 5 日 數字變化）
  # =========================================================================
  st.markdown(
      "<br><hr style='border: 1px solid #2d2d3d;'>", unsafe_allow_html=True
  )
  st.subheader("📋 各次產業板塊動能趨勢統計表 (近 3 日 / 近 5 日 數值變化)")

  all_multiday = st.session_state.get("multiday_data", {})

  if all(k in all_multiday for k in ["T", "T-1", "T-2", "T-3", "T-4"]):
    df_T = pd.DataFrame(all_multiday.get("T", []))
    df_T1 = pd.DataFrame(all_multiday.get("T-1", []))
    df_T2 = pd.DataFrame(all_multiday.get("T-2", []))
    df_T3 = pd.DataFrame(all_multiday.get("T-3", []))
    df_T4 = pd.DataFrame(all_multiday.get("T-4", []))

    def calc_sector_summary(df_day):
      if df_day.empty:
        return pd.DataFrame(
            columns=["次產業板塊", "成交金額(億)", "加權漲跌幅"]
        )
      df_day["成交金額(億)"] = pd.to_numeric(
          df_day["成交金額(億)"], errors="coerce"
      ).fillna(0.0)
      df_day["漲跌幅"] = pd.to_numeric(
          df_day["漲跌幅"], errors="coerce"
      ).fillna(0.0)

      df_day["金額_x_漲跌"] = df_day["成交金額(億)"] * df_day["漲跌幅"]
      grouped = (
          df_day.groupby("次產業板塊")
          .agg(總成交金額=("成交金額(億)", "sum"), 加權分子=("金額_x_漲跌", "sum"))
          .reset_index()
      )
      grouped["加權漲跌幅"] = (
          grouped["加權分子"] / (grouped["總成交金額"] + 1e-9)
      ).round(2)
      return grouped[["次產業板塊", "總成交金額", "加權漲跌幅"]]

    s_T = calc_sector_summary(df_T).rename(
        columns={"加權漲跌幅": "pct_T", "總成交金額": "amt_T"}
    )
    s_T1 = calc_sector_summary(df_T1).rename(
        columns={"加權漲跌幅": "pct_T1", "總成交金額": "amt_T1"}
    )
    s_T2 = calc_sector_summary(df_T2).rename(
        columns={"加權漲跌幅": "pct_T2", "總成交金額": "amt_T2"}
    )
    s_T3 = calc_sector_summary(df_T3).rename(
        columns={"加權漲跌幅": "pct_T3", "總成交金額": "amt_T3"}
    )
    s_T4 = calc_sector_summary(df_T4).rename(
        columns={"加權漲跌幅": "pct_T4", "總成交金額": "amt_T4"}
    )

    m_df = (
        s_T.merge(
            s_T1[["次產業板塊", "pct_T1", "amt_T1"]],
            on="次產業板塊",
            how="left",
        )
        .merge(
            s_T2[["次產業板塊", "pct_T2", "amt_T2"]],
            on="次產業板塊",
            how="left",
        )
        .merge(
            s_T3[["次產業板塊", "pct_T3", "amt_T3"]],
            on="次產業板塊",
            how="left",
        )
        .merge(
            s_T4[["次產業板塊", "pct_T4", "amt_T4"]],
            on="次產業板塊",
            how="left",
        )
        .fillna(0.0)
    )

    m_df["最新成交金額(億)"] = m_df["amt_T"].round(1)
    m_df["量能增減%"] = (
        ((m_df["amt_T"] - m_df["amt_T1"]) / (m_df["amt_T1"] + 1e-9)) * 100
    ).round(1)
    m_df["最新漲跌(T)"] = m_df["pct_T"]
    m_df["近3日累積漲跌%"] = (
        m_df["pct_T"] + m_df["pct_T1"] + m_df["pct_T2"]
    ).round(2)
    m_df["近5日累積漲跌%"] = (
        m_df["pct_T"]
        + m_df["pct_T1"]
        + m_df["pct_T2"]
        + m_df["pct_T3"]
        + m_df["pct_T4"]
    ).round(2)

    # 僅保留最新金額大於 1 億的活躍板塊
    m_df = m_df[m_df["最新成交金額(億)"] >= 1.0]

    display_df = m_df[[
        "次產業板塊",
        "最新成交金額(億)",
        "量能增減%",
        "最新漲跌(T)",
        "近3日累積漲跌%",
        "近5日累積漲跌%",
    ]].sort_values(by="最新成交金額(億)", ascending=False).reset_index(drop=True)

    def color_pct(val):
      if val > 0:
        return "color: #ff4d4f; font-weight: bold;"
      elif val < 0:
        return "color: #52c41a; font-weight: bold;"
      return "color: #8c8c8c;"

    styled_table = (
        display_df.style.format({
            "最新成交金額(億)": "{:,.1f}",
            "量能增減%": "{:+.1f}%",
            "最新漲跌(T)": "{:+.2f}%",
            "近3日累積漲跌%": "{:+.2f}%",
            "近5日累積漲跌%": "{:+.2f}%",
        }).map(
            color_pct,
            subset=[
                "量能增減%",
                "最新漲跌(T)",
                "近3日累積漲跌%",
                "近5日累積漲跌%",
            ],
        )
    )

    st.dataframe(styled_table, use_container_width=True, height=520)

    # ─────────────────────────────────────────────────────────────
    # 🎯 全市場巨觀資金動能總結與即時操盤指引
    # ─────────────────────────────────────────────────────────────
    st.markdown(
        "<br><hr style='border: 1px solid #2d2d3d;'>", unsafe_allow_html=True
    )
    st.subheader("💡 今日資金動能全景總結與戰略解讀")

    total_amt_T = m_df["最新成交金額(億)"].sum()
    total_amt_T1 = m_df["amt_T1"].sum()
    vol_change_pct = (
        (total_amt_T - total_amt_T1) / (total_amt_T1 + 1e-9)
    ) * 100

    up_sectors = (m_df["最新漲跌(T)"] > 0).sum()
    down_sectors = (m_df["最新漲跌(T)"] < 0).sum()
    flat_sectors = len(m_df) - up_sectors - down_sectors

    top3_sectors = m_df.head(3)
    top3_names = "、".join(top3_sectors["次產業板塊"].tolist())

    # 判斷市場量價結構
    if vol_change_pct > 15:
      vol_status = "🔥 顯著放量攻擊"
      tactical_hint = (
          "市場主力買氣充沛，攻擊量能就緒。強勢板塊具備持續推升力道，可沿 5"
          " 日線積極順勢操作。"
      )
    elif vol_change_pct < -15:
      vol_status = "🧊 明顯量縮觀望 (低周轉)"
      tactical_hint = (
          "市場追價意願不足，呈現量縮整理。若大盤位於高檔需提防動能衰竭；若位於箱底支撐則是低接良機，忌盲目追高。"
      )
    else:
      vol_status = "⚪ 量能常態持平"
      tactical_hint = (
          "大盤資金流速穩定，市場處於常態輪動結構，重點在於板塊之間的「資金蹺蹺板」換手效應。"
      )

    with st.container(border=True):
      c1, c2, c3, c4 = st.columns(4)
      c1.metric(
          "市場監測板塊總額",
          f"{total_amt_T:,.1f} 億",
          f"量能變動 {vol_change_pct:+.1f}%",
      )
      c2.metric("量能活躍狀態", vol_status)
      c3.metric(
          "板塊多空比例 (上漲/下跌)",
          f"{up_sectors} 漲 / {down_sectors} 跌",
          f"持平: {flat_sectors} 家",
      )
      c4.metric(
          "最吸金前三大板塊",
          top3_sectors.iloc[0]["次產業板塊"] if not top3_sectors.empty else "無",
      )

      st.markdown("---")
      st.markdown(f"""
        **📌 操盤室量化戰略指引：**
        * **資金聚焦度**：今日資金主要重兵駐紮在 **【{top3_names}】** 等前三大次產業，佔監測資金顯著份額，主力方向未變前切勿逆勢做空龍頭。
        * **量能警示**：目前市場為 **{vol_status}**（較前一交易日變化 **{vol_change_pct:+.1f}%**）。
        * **行動建議**：{tactical_hint}
        """)
  else:
    st.info(
        "💡 尚未抓齊完整的 5 日歷史資料，請確認「⚡ 全市場動能掃描中心」已完成掃描。"
    )