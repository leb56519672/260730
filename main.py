import pandas as pd
import plotly.express as px
import requests
import streamlit as st

# Streamlit 페이지 기본 설정
st.set_page_config(
    page_title="전국 시군구 고령화 지도",
    page_icon="🗺️",
    layout="wide",
)


@st.cache_data
def load_data():
    """인구 데이터와 GeoJSON 지리 경계 데이터를 로드하고 전처리하는 함수입니다.

    캐싱(@st.cache_data)을 적용하여 앱 재실행 시 속도를 높입니다.
    """
    # 1. GeoJSON 경계 데이터 불러오기
    geojson_url = "https://raw.githubusercontent.com/greatsong/modudata/main/data/boundaries/sigungu_kr.geojson"
    geojson_data = requests.get(geojson_url).json()

    # 2. 인구 CSV 데이터 불러오기 (코드 열을 문자열로 읽도록 dtype 지정)
    csv_url = "https://raw.githubusercontent.com/greatsong/modudata/main/data/population_yearly.csv.gz"
    df = pd.read_csv(csv_url, dtype={"코드": str})

    # '코드' 열의 앞 5자리를 추출하여 시군구 코드로 사용
    df["sigungu_code"] = df["코드"].str[:5]

    # 데이터 중 가장 최신 연도 추출
    latest_year = df["연도"].max()
    df_latest = df[df["연도"] == latest_year].copy()

    # 3. 고령 인구 및 총인구 계산
    # '계_0세'부터 '계_100세 이상'까지 모든 총인구 열(계_) 추출
    total_cols = [c for c in df_latest.columns if c.startswith("계_")]

    # 65세 이상에 해당하는 '계_65세' ~ '계_100세 이상' 열 추출
    elderly_cols = []
    for c in total_cols:
        # '계_X세' 형태에서 숫자 부분만 추출하여 판별
        age_str = c.replace("계_", "").replace("세 이상", "").replace("세", "")
        if age_str.isdigit() and int(age_str) >= 65:
            elderly_cols.append(c)

    # 읍면동 데이터를 시군구(5자리 코드) 단위로 합산
    grouped = (
        df_latest.groupby(["sigungu_code", "시도", "시군구"])[
            total_cols
        ]
        .sum()
        .reset_index()
    )

    # 총인구 및 65세 이상 인구 합계 계산
    grouped["총인구"] = grouped[total_cols].sum(axis=1)
    grouped["고령인구"] = grouped[elderly_cols].sum(axis=1)

    # 고령화율(%) 계산 (소수점 첫째 자리까지 반올림)
    grouped["고령화율"] = (
        grouped["고령인구"] / grouped["총인구"] * 100
    ).round(1)

    # 4. 고령화율을 5개 범주로 나눔 (구간: 19% 미만, 19%~23%, 23%~28%, 28%~38%, 38% 이상)
    bins = [-1, 19, 23, 28, 38, 100]
    labels = [
        "1. 19% 미만",
        "2. 19% 이상 ~ 23% 미만",
        "3. 23% 이상 ~ 28% 미만",
        "4. 28% 이상 ~ 38% 미만",
        "5. 38% 이상",
    ]

    grouped["고령화_구간"] = pd.cut(
        grouped["고령화율"], bins=bins, labels=labels, right=False
    )

    return latest_year, grouped, geojson_data


# 데이터 로드
latest_year, df_sigungu, geojson_data = load_data()

# App 타이틀 영역
st.title(f"🗺️ 전국 시군구 고령화 지도 ({latest_year}년 기준)")
st.caption(
    "65세 이상 인구 비율을 기준(19%, 23%, 28%, 38%)으로 5단계 구분도를 시각화합니다."
)

# 색상 팔레트 설정 (연한 색 -> 진한 색)
color_map = {
    "1. 19% 미만": "#edf8e9",
    "2. 19% 이상 ~ 23% 미만": "#bae4b3",
    "3. 23% 이상 ~ 28% 미만": "#74c476",
    "4. 28% 이상 ~ 38% 미만": "#31a354",
    "5. 38% 이상": "#006d2c",
}

# Plotly 지도 생성
fig = px.choropleth_mapbox(
    df_sigungu,
    geojson=geojson_data,
    locations="sigungu_code",  # GeoJSON 매핑용 코드
    featureidkey="properties.코드",  # GeoJSON 내부 속성 키
    color="고령화_구간",  # 색상 기준이 되는 5단계 범주
    color_discrete_map=color_map,  # 지정된 색상 매핑 사용
    category_orders={"고령화_구간": list(color_map.keys())},  # 범례 순서 정렬
    hover_name="시군구",  # 툴팁 제목
    hover_data={
        "sigungu_code": False,  # 코드 숨김
        "시도": True,  # 시도 명칭 표시
        "고령화율": ":.1f%",  # 고령화율 퍼센트 표시
        "총인구": ":,명",  # 총인구 천단위 쉼표 표시
        "고령인구": ":,명",  # 고령인구 천단위 쉼표 표시
        "고령화_구간": False,  # 구간 명칭 툴팁에서는 숨김
    },
    center={"lat": 35.9, "lon": 127.8},  # 대한민국 중심 좌표
    zoom=6.2,  # 초기 확대 비율
    mapbox_style="white-bg",  # 지도 배경 타일 없이 경계선만 표시
)

# 지도 레이아웃 세부 조정
fig.update_layout(
    margin={"r": 0, "t": 10, "l": 0, "b": 0},
    height=650,
    legend_title_text="고령화율 구간",
    legend=dict(yanchor="top", y=0.98, xanchor="left", x=0.01),
)

# 지도 화면 출력
st.plotly_chart(fig, use_container_width=True)

st.markdown("---")

# 지도 하단 상위/하위 10개 지역 표 출력
st.subheader("📊 고령화율 극단 지역 비교")

col1, col2 = st.columns(2)

# 고령화율 높은 순 상위 10개
top_10 = df_sigungu.sort_values(by="고령화율", ascending=False).head(10)[
    ["시도", "시군구", "고령화율", "총인구", "고령인구"]
]

# 고령화율 낮은 순 하위 10개
bottom_10 = df_sigungu.sort_values(by="고령화율", ascending=True).head(10)[
    ["시도", "시군구", "고령화율", "총인구", "고령인구"]
]

with col1:
    st.markdown("### 🔴 고령화율 가장 높은 10곳")
    st.dataframe(
        top_10.style.format(
            {"고령화율": "{:.1f}%", "총인구": "{:,}명", "고령인구": "{:,}명"}
        ),
        use_container_width=True,
        hide_index=True,
    )

with col2:
    st.markdown("### 🔵 고령화율 가장 낮은 10곳")
    st.dataframe(
        bottom_10.style.format(
            {"고령화율": "{:.1f}%", "총인구": "{:,}명", "고령인구": "{:,}명"}
        ),
        use_container_width=True,
        hide_index=True,
    )
