import pandas as pd
import plotly.express as px
import requests
import streamlit as st

# Streamlit 페이지 기본 설정
st.set_page_config(
    page_title="전국 인구구조 지도",
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
    # - 강원: 42 -> 51
    # - 전북: 45 -> 52
    # - 군위군: 47720 -> 27720
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
# 사이드바 컨트롤러 (지표, 연도, 시도 선택, 애니메이션 모드)
# -----------------------------------------------------------------------------
st.sidebar.title("⚙️ 설정")

# 1. 지표 선택
metric_option = st.sidebar.radio(
    "📊 분석 지표 선택",
    ["고령화율 (65세 이상)", "유소년 비율 (0~14세)"],
    index=0,
)

# 2. 애니메이션 재생 여부 선택
enable_animation = st.sidebar.checkbox(
    "▶️ 연도별 시계열 애니메이션 모드",
    value=False,
    help="체크 시 지도 하단 플레이 버튼으로 연도별 변화 과정을 재생할 수 있습니다.",
)

# 애니메이션 모드가 아닐 때만 연도 선택 슬라이더 활성화
available_years = sorted(df_raw["연도"].unique().tolist())
if not enable_animation:
    selected_year = st.sidebar.slider(
        "📅 연도 선택",
        min_value=int(min(available_years)),
        max_value=int(max(available_years)),
        value=int(max(available_years)),
        step=1,
    )
else:
    # 애니메이션 모드일 경우 가장 최신 연도를 기본값으로 사용 (카드 및 표 표시용)
    selected_year = int(max(available_years))
    st.sidebar.info("💡 애니메이션 모드가 활성화되어 슬라이더가 비활성화됩니다.")

# 3. 시도 선택 드롭다운 (지역 확대)
sido_list = ["전국"] + list(df_raw["시도"].unique())
sido_options = [s for s in SIDO_CENTER_MAP.keys() if s in sido_list or s == "전국"]
selected_sido = st.sidebar.selectbox("📍 지역 선택 (확대)", sido_options)

# -----------------------------------------------------------------------------
# 데이터 집계 및 비율 계산
# -----------------------------------------------------------------------------
# 연도별, 시군구별 인구 합산
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

# 애니메이션을 위한 정렬 (연도순)
grouped_all = grouped_all.sort_values(by=["연도", "sigungu_code"])

# 선택된 연도 데이터 추출 (상단 지표 카드 및 하단 표용)
grouped = grouped_all[grouped_all["연도"] == selected_year].copy()

# 전국 합계 계산
national_total_pop = grouped["총인구"].sum()
national_elderly_pop = grouped["고령인구"].sum()
national_youth_pop = grouped["유소년인구"].sum()

national_elderly_rate = round(national_elderly_pop / national_total_pop * 100, 1)
national_youth_rate = round(national_youth_pop / national_total_pop * 100, 1)

# 선택된 지표에 따른 타겟 칼럼 및 색상 구간(5단계) 설정
if metric_option == "고령화율 (65세 이상)":
    target_col = "고령화율"
    metric_name = "고령화율"
    national_rate = national_elderly_rate

    # 고령화율 고정 구간: 19%, 23%, 28%, 38%
    bins = [-1, 19, 23, 28, 38, 100]
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
else:
    target_col = "유소년비율"
    metric_name = "유소년 비율"
    national_rate = national_youth_rate

    # 유소년 비율 맞춤 구간: 8%, 10%, 12%, 14%
    bins = [-1, 8, 10, 12, 14, 100]
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

# 전체 데이터셋 및 선택 연도 데이터셋 모두 범주화 적용
grouped_all["비율_구간"] = pd.cut(
    grouped_all[target_col], bins=bins, labels=labels, right=False
)
grouped["비율_구간"] = pd.cut(
    grouped[target_col], bins=bins, labels=labels, right=False
)

# -----------------------------------------------------------------------------
# 메인 화면 구성
# -----------------------------------------------------------------------------
title_year_str = "지난 12년간 변화" if enable_animation else f"{selected_year}년"
st.title(f"🗺️ 전국 시군구 {metric_name} 지도 ({title_year_str})")
st.caption(
    f"선택한 지표({metric_name})를 기준으로 시군구별 인구 비율을 5단계 구분도로 시각화합니다."
)

# 최고 / 최저 지역 추출
max_row = grouped.loc[grouped[target_col].idxmax()]
min_row = grouped.loc[grouped[target_col].idxmin()]

# 지도 상단 지표 카드 3개 나란히 배치
col_m1, col_m2, col_m3 = st.columns(3)

with col_m1:
    st.metric(
        label=f"🌐 전국 평균 {metric_name} ({selected_year}년)",
        value=f"{national_rate:.1f}%",
    )

with col_m2:
    st.metric(
        label=f"🔴 최고 {metric_name} 지역 ({selected_year}년)",
        value=f"{max_row['시도']} {max_row['시군구']}",
        delta=f"{max_row[target_col]:.1f}%",
    )

with col_m3:
    st.metric(
        label=f"🔵 최저 {metric_name} 지역 ({selected_year}년)",
        value=f"{min_row['시도']} {min_row['시군구']}",
        delta=f"{min_row[target_col]:.1f}%",
    )

st.markdown("---")

# 시도 선택에 따른 지도 바운딩 위치 변경
map_setting = SIDO_CENTER_MAP.get(selected_sido, SIDO_CENTER_MAP["전국"])

# 애니메이션 모드 여부에 따른 데이터소스 및 타임라인 프레임 설정
if enable_animation:
    fig_data = grouped_all
    animation_frame = "연도"
else:
    fig_data = grouped
    animation_frame = None

# Plotly 구분도 생성
fig = px.choropleth_mapbox(
    fig_data,
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
        target_col: ":.1f%",
        "총인구": ":,명",
        "고령인구": ":,명" if metric_option == "고령화율 (65세 이상)" else False,
        "유소년인구": ":,명" if metric_option == "유소년 비율 (0~14세)" else False,
        "비율_구간": False,
    },
    animation_frame=animation_frame,  # 애니메이션 활성화 시 프레임 축 설정
    center=map_setting["center"],
    zoom=map_setting["zoom"],
    mapbox_style="white-bg",  # 타일 없이 경계선만 표시
)

fig.update_layout(
    margin={"r": 0, "t": 10, "l": 0, "b": 0},
    height=650,
    legend_title_text=f"{metric_name} 구간",
    legend=dict(yanchor="top", y=0.98, xanchor="left", x=0.01),
)

# 애니메이션 모드일 때 슬라이더 컨트롤 및 트랜지션 세부 설정
if enable_animation:
    fig.update_layout(
        sliders=[
            dict(
                active=len(available_years) - 1,
                currentvalue={"prefix": "📅 연도: "},
                pad={"t": 20},
            )
        ]
    )

st.plotly_chart(fig, use_container_width=True)

# -----------------------------------------------------------------------------
# 경계 지도 데이터 미매핑 지역 안내
# -----------------------------------------------------------------------------
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
# 하단 표 영역 (상위 10개 / 하위 10개)
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
else:
    display_cols.append("유소년인구")

format_dict = {
    target_col: "{:.1f}%",
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
