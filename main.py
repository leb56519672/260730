import re
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import requests
import streamlit as st

# Streamlit 페이지 기본 설정
st.set_page_config(
    page_title="전국 인구구조 및 고령화 지도",
    page_icon="🗺️",
    layout="wide",
)

# 시도별 중심 좌표 및 Zoom 레벨 매핑
SIDO_CENTER_MAP = {
    "전국": {"center": {"lat": 35.9, "lon": 127.8}, "zoom": 6.2},
    "서울특별시": {"center": {"lat": 37.5665, "lon": 126.9780}, "zoom": 9.5},
    "부산광역시": {"center": {"lat": 35.1796, "lon": 129.0756}, "zoom": 9.5},
    "대구광역시": {"center": {"lat": 35.8714, "lon": 128.6014}, "zoom": 9.0},
    "인천광역시": {"center": {"lat": 37.4563, "lon": 126.7052}, "zoom": 9.0},
    "광주광역시": {"center": {"lat": 35.1595, "lon": 126.8526}, "zoom": 10.0},
    "대전광역시": {"center": {"lat": 36.3504, "lon": 127.3845}, "zoom": 10.0},
    "울산광역시": {"center": {"lat": 35.5384, "lon": 129.3114}, "zoom": 9.5},
    "세종특별자치시": {"center": {"lat": 36.4800, "lon": 127.2890}, "zoom": 10.5},
    "경기도": {"center": {"lat": 37.4138, "lon": 127.5183}, "zoom": 8.0},
    "강원특별자치도": {"center": {"lat": 37.8228, "lon": 128.1555}, "zoom": 7.8},
    "충청북도": {"center": {"lat": 36.6357, "lon": 127.4912}, "zoom": 8.2},
    "충청남도": {"center": {"lat": 36.5184, "lon": 126.8000}, "zoom": 8.2},
    "전북특별자치도": {"center": {"lat": 35.7175, "lon": 127.1530}, "zoom": 8.2},
    "전라남도": {"center": {"lat": 34.8679, "lon": 126.9910}, "zoom": 7.8},
    "경상북도": {"center": {"lat": 36.4919, "lon": 128.8889}, "zoom": 7.8},
    "경상남도": {"center": {"lat": 35.4606, "lon": 128.2132}, "zoom": 8.0},
    "제주특별자치도": {"center": {"lat": 33.4890, "lon": 126.4983}, "zoom": 9.0},
}


@st.cache_data
def load_data():
    """인구 데이터와 GeoJSON 경계 데이터를 불러와 전처리하는 함수입니다."""
    # 1. GeoJSON 경계 데이터 불러오기
    geojson_url = "https://raw.githubusercontent.com/greatsong/modudata/main/data/boundaries/sigungu_kr.geojson"
    geojson_data = requests.get(geojson_url).json()

    # GeoJSON에 존재하는 시군구 코드 집합 생성
    valid_geojson_codes = set(
        f["properties"]["코드"] for f in geojson_data["features"]
    )

    # 2. 인구 CSV 데이터 불러오기 (코드 열은 문자열로 처리)
    csv_url = "https://raw.githubusercontent.com/greatsong/modudata/main/data/population_yearly.csv.gz"
    df = pd.read_csv(csv_url, dtype={"코드": str})

    # '코드' 열의 앞 5자리를 시군구 코드로 사용
    df["sigungu_code"] = df["코드"].str[:5]

    # 행정구역 개편에 따른 과거 시군구 코드 매핑 변환
    def remap_code(code):
        if code == "47720":
            return "27720"
        elif code.startswith("42"):
            return "51" + code[2:]
        elif code.startswith("45"):
            return "52" + code[2:]
        return code

    df["sigungu_code"] = df["sigungu_code"].apply(remap_code)

    # 전체 나이 열 목록 (계_0세 ~ 계_100세 이상)
    total_cols = [c for c in df.columns if c.startswith("계_")]

    # 유소년(0~14세) 및 고령(65세 이상) 열 구분
    youth_cols = []
    elderly_cols = []
    for c in total_cols:
        age_str = c.replace("계_", "").replace("세 이상", "").replace("세", "")
        if age_str.isdigit():
            age = int(age_str)
            if age <= 14:
                youth_cols.append(c)
            elif age >= 65:
                elderly_cols.append(c)

    return df, total_cols, youth_cols, elderly_cols, geojson_data, valid_geojson_codes


# 데이터 로드
(
    df_raw,
    total_cols,
    youth_cols,
    elderly_cols,
    geojson_data,
    valid_geojson_codes,
) = load_data()

# -----------------------------------------------------------------------------
# 전체 연도 시군구 및 전국 인구 지표 집계
# -----------------------------------------------------------------------------
grouped_all = (
    df_raw.groupby(["연도", "sigungu_code", "시도", "시군구"])[total_cols]
    .sum()
    .reset_index()
)

grouped_all["총인구"] = grouped_all[total_cols].sum(axis=1)
grouped_all["고령인구"] = grouped_all[elderly_cols].sum(axis=1)
grouped_all["유소년인구"] = grouped_all[youth_cols].sum(axis=1)

grouped_all["고령화율"] = (grouped_all["고령인구"] / grouped_all["총인구"] * 100).round(1)
grouped_all["유소년비율"] = (grouped_all["유소년인구"] / grouped_all["총인구"] * 100).round(1)

# 노령화지수 안전 계산 (유소년 0명 방지)
grouped_all["노령화지수"] = (
    grouped_all["고령인구"] / grouped_all["유소년인구"].replace(0, float("nan")) * 100
).fillna(0).round(1)

# -----------------------------------------------------------------------------
# 사이드바 컨트롤러
# -----------------------------------------------------------------------------
st.sidebar.title("⚙️ 설정")

# 1. 지표 선택
metric_option = st.sidebar.radio(
    "📊 분석 지표 선택",
    ["고령화율 (65세 이상)", "유소년 비율 (0~14세)", "노령화지수 (인구 역전 지표)"],
    index=0,
)

# 2. 연도 선택 슬라이더
available_years = sorted(df_raw["연도"].unique().tolist())
selected_year = st.sidebar.slider(
    "📅 연도 선택",
    min_value=int(min(available_years)),
    max_value=int(max(available_years)),
    value=int(max(available_years)),
    step=1,
)

# 3. 시도 선택 드롭다운
sido_list = ["전국"] + list(df_raw["시도"].unique())
sido_options = [s for s in SIDO_CENTER_MAP.keys() if s in sido_list or s == "전국"]
selected_sido = st.sidebar.selectbox("📍 지역 선택 (확대)", sido_options)

# -----------------------------------------------------------------------------
# 선택된 연도의 데이터 추출 및 지표 설정
# -----------------------------------------------------------------------------
grouped = grouped_all[grouped_all["연도"] == selected_year].copy()

# 전국 총합 계산
national_total_pop = grouped["총인구"].sum()
national_elderly_pop = grouped["고령인구"].sum()
national_youth_pop = grouped["유소년인구"].sum()

national_elderly_rate = round(national_elderly_pop / national_total_pop * 100, 1)
national_youth_rate = round(national_youth_pop / national_total_pop * 100, 1)
national_aging_idx = round(national_elderly_pop / (national_youth_pop if national_youth_pop > 0 else 1) * 100, 1)

# 지표별 안전한 구간(bins) 및 색상 설정
if metric_option == "고령화율 (65세 이상)":
    target_col = "고령화율"
    metric_name = "고령화율"
    unit_str = "%"
    national_rate = national_elderly_rate

    bins = [-1.0, 19.0, 23.0, 28.0, 38.0, float("inf")]
    labels = [
        "1. 19% 미만",
        "2. 19% 이상 ~ 23% 미만",
        "3. 23% 이상 ~ 28% 미만",
        "4. 28% 이상 ~ 38% 미만",
        "5. 38% 이상",
    ]
    color_map = {
        "1. 19% 미만": "#edf8e9",
        "2. 19% 이상 ~ 23% 미만": "#bae4b3",
        "3. 23% 이상 ~ 28% 미만": "#74c476",
        "4. 28% 이상 ~ 38% 미만": "#31a354",
        "5. 38% 이상": "#006d2c",
    }
elif metric_option == "유소년 비율 (0~14세)":
    target_col = "유소년비율"
    metric_name = "유소년 비율"
    unit_str = "%"
    national_rate = national_youth_rate

    bins = [-1.0, 8.0, 10.0, 12.0, 14.0, float("inf")]
    labels = [
        "1. 8% 미만",
        "2. 8% 이상 ~ 10% 미만",
        "3. 10% 이상 ~ 12% 미만",
        "4. 12% 이상 ~ 14% 미만",
        "5. 14% 이상",
    ]
    color_map = {
        "1. 8% 미만": "#fef0d9",
        "2. 8% 이상 ~ 10% 미만": "#fdd49e",
        "3. 10% 이상 ~ 12% 미만": "#fdbb84",
        "4. 12% 이상 ~ 14% 미만": "#fc8d59",
        "5. 14% 이상": "#d7301f",
    }
else:  # 노령화지수
    target_col = "노령화지수"
    metric_name = "노령화지수"
    unit_str = ""
    national_rate = national_aging_idx

    bins = [-1.0, 100.0, 200.0, 300.0, 500.0, float("inf")]
    labels = [
        "1. 100 미만 (유소년 > 고령)",
        "2. 100 이상 ~ 200 미만",
        "3. 200 이상 ~ 300 미만",
        "4. 300 이상 ~ 500 미만",
        "5. 500 이상 (고령 압도)",
    ]
    color_map = {
        "1. 100 미만 (유소년 > 고령)": "#f7fcf5",
        "2. 100 이상 ~ 200 미만": "#fcbba1",
        "3. 200 이상 ~ 300 미만": "#fc9272",
        "4. 300 이상 ~ 500 미만": "#fb6a4a",
        "5. 500 이상 (고령 압도)": "#67000d",
    }

grouped["비율_구간"] = pd.cut(
    grouped[target_col], bins=bins, labels=labels, right=False
)

# 데이터 다운로드 버튼 (사이드바 하단)
st.sidebar.markdown("---")
st.sidebar.subheader("📥 데이터 다운로드")
csv_data = grouped[
    ["연도", "시도", "시군구", "sigungu_code", "총인구", "고령인구", "유소년인구", target_col]
].to_csv(index=False, encoding="utf-8-sig")

st.sidebar.download_button(
    label=f"📄 {selected_year}년 {metric_name} CSV 다운로드",
    data=csv_data,
    file_name=f"korea_population_{selected_year}.csv",
    mime="text/csv",
)

# -----------------------------------------------------------------------------
# 메인 화면 구성
# -----------------------------------------------------------------------------
st.title(f"🗺️ 전국 시군구 {metric_name} 지도 ({selected_year}년)")
st.caption(
    f"선택한 지표({metric_name})를 기준으로 시군구별 인구 비율을 5단계 구분도로 시각화합니다."
)

# 최고 / 최저 지역 안전 추출
max_idx = grouped[target_col].idxmax()
min_idx = grouped[target_col].idxmin()

max_row = grouped.loc[max_idx]
min_row = grouped.loc[min_idx]

# 지도 상단 지표 카드 3개
col_m1, col_m2, col_m3 = st.columns(3)

with col_m1:
    st.metric(
        label=f"🌐 전국 평균 {metric_name}",
        value=f"{national_rate:.1f}{unit_str}",
    )

with col_m2:
    st.metric(
        label=f"🔴 최고 {metric_name} 지역",
        value=f"{max_row['시도']} {max_row['시군구']}",
        delta=f"{max_row[target_col]:.1f}{unit_str}",
    )

with col_m3:
    st.metric(
        label=f"🔵 최저 {metric_name} 지역",
        value=f"{min_row['시도']} {min_row['시군구']}",
        delta=f"{min_row[target_col]:.1f}{unit_str}",
    )

st.markdown("---")

# 시도 선택 위치 반영
map_setting = SIDO_CENTER_MAP.get(selected_sido, SIDO_CENTER_MAP["전국"])

# Plotly 구분도 생성
fig = px.choropleth_mapbox(
    grouped,
    geojson=geojson_data,
    locations="sigungu_code",
    featureidkey="properties.코드",
    color="비율_구간",
    color_discrete_map=color_map,
    category_orders={"비율_구간": list(color_map.keys())},
    hover_name="시군구",
    hover_data={
        "sigungu_code": False,
        "시도": True,
        target_col: f":.1f{unit_str}",
        "총인구": ":,명",
        "고령인구": ":,명",
        "유소년인구": ":,명",
        "비율_구간": False,
    },
    center=map_setting["center"],
    zoom=map_setting["zoom"],
    mapbox_style="white-bg",
)

fig.update_layout(
    margin={"r": 0, "t": 10, "l": 0, "b": 0},
    height=650,
    legend_title_text=f"{metric_name} 구간",
    legend=dict(yanchor="top", y=0.98, xanchor="left", x=0.01),
)

st.plotly_chart(fig, use_container_width=True)

# 경계 데이터 미매핑 안내
unmapped = grouped[~grouped["sigungu_code"].isin(valid_geojson_codes)]
if not unmapped.empty:
    unmapped_names = (
        unmapped["시도"] + " " + unmapped["시군구"]
    ).unique().tolist()
    st.info(
        f"ℹ️ **행정구역 변경 안내**: 선택하신 {selected_year}년 데이터 중 일부 옛 지역"
        f"({', '.join(unmapped_names)})은 현재 경계 지도(GeoJSON)와 코드가 일치하지 않아 지도에서 회색(미매핑)으로 표시됩니다."
    )

st.markdown("---")

# -----------------------------------------------------------------------------
# 📈 12년간 인구구조 추이 선 그래프
# -----------------------------------------------------------------------------
st.subheader("📈 지난 12년간 주요 인구 지표 추이 분석")

national_trend = (
    grouped_all.groupby("연도")[["총인구", "고령인구", "유소년인구"]]
    .sum()
    .reset_index()
)
national_trend["고령화율"] = (
    national_trend["고령인구"] / national_trend["총인구"] * 100
).round(1)
national_trend["유소년비율"] = (
    national_trend["유소년인구"] / national_trend["총인구"] * 100
).round(1)

col_chart1, col_chart2 = st.columns(2)

with col_chart1:
    fig_trend = go.Figure()
    fig_trend.add_trace(
        go.Scatter(
            x=national_trend["연도"],
            y=national_trend["유소년비율"],
            mode="lines+markers",
            name="유소년 비율 (%)",
            line=dict(color="#fc8d59", width=3),
        )
    )
    fig_trend.add_trace(
        go.Scatter(
            x=national_trend["연도"],
            y=national_trend["고령화율"],
            mode="lines+markers",
            name="고령화율 (%)",
            line=dict(color="#31a354", width=3),
        )
    )

    fig_trend.update_layout(
        title="전국 유소년 비율 vs 고령화율 12년 추이",
        xaxis_title="연도",
        yaxis_title="비율 (%)",
        hovermode="x unified",
        height=380,
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
    )
    st.plotly_chart(fig_trend, use_container_width=True)

with col_chart2:
    current_max_code = max_row["sigungu_code"]
    current_min_code = min_row["sigungu_code"]

    df_max_region = grouped_all[grouped_all["sigungu_code"] == current_max_code]
    df_min_region = grouped_all[grouped_all["sigungu_code"] == current_min_code]

    fig_region_trend = go.Figure()
    fig_region_trend.add_trace(
        go.Scatter(
            x=df_max_region["연도"],
            y=df_max_region[target_col],
            mode="lines+markers",
            name=f"최고: {max_row['시도']} {max_row['시군구']}",
            line=dict(color="#d7301f", width=3),
        )
    )
    fig_region_trend.add_trace(
        go.Scatter(
            x=df_min_region["연도"],
            y=df_min_region[target_col],
            mode="lines+markers",
            name=f"최저: {min_row['시도']} {min_row['시군구']}",
            line=dict(color="#2b8cbe", width=3),
        )
    )

    fig_region_trend.update_layout(
        title=f"현재 선택 지표({metric_name}) 양극단 지역 12년 추이",
        xaxis_title="연도",
        yaxis_title=f"{metric_name} ({unit_str})",
        hovermode="x unified",
        height=380,
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
    )
    st.plotly_chart(fig_region_trend, use_container_width=True)

st.markdown("---")

# -----------------------------------------------------------------------------
# 하단 표 영역
# -----------------------------------------------------------------------------
st.subheader(f"📊 {selected_year}년 {metric_name} 상위 및 하위 10개 지역")

col_table1, col_table2 = st.columns(2)

top_10 = grouped.sort_values(by=target_col, ascending=False).head(10)[
    ["시도", "시군구", target_col, "총인구", "고령인구", "유소년인구"]
]

bottom_10 = grouped.sort_values(by=target_col, ascending=True).head(10)[
    ["시도", "시군구", target_col, "총인구", "고령인구", "유소년인구"]
]

display_cols = ["시도", "시군구", target_col, "총인구"]
if metric_option == "고령화율 (65세 이상)":
    display_cols.append("고령인구")
elif metric_option == "유소년 비율 (0~14세)":
    display_cols.append("유소년인구")
else:
    display_cols.extend(["고령인구", "유소년인구"])

format_dict = {
    target_col: f"{{:.1f}}{unit_str}",
    "총인구": "{:,}명",
    "고령인구": "{:,}명",
    "유소년인구": "{:,}명",
}

with col_table1:
    st.markdown(f"### 🔴 {metric_name} 가장 높은 10곳")
    st.dataframe(
        top_10[display_cols].style.format(format_dict),
        use_container_width=True,
        hide_index=True,
    )

with col_table2:
    st.markdown(f"### 🔵 {metric_name} 가장 낮은 10곳")
    st.dataframe(
        bottom_10[display_cols].style.format(format_dict),
        use_container_width=True,
        hide_index=True,
    )
