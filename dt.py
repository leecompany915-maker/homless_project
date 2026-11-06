import pandas as pd
import requests 
import folium
#open api
url = "https://api.data.go.kr/openapi/tn_pubr_public_free_mlsv_api"
service_key = (
    "b5e45281de993a79599011f7a1db4389d01d3cba98ffd28f01b04209ddf56696"
)

# 요청 파라미터 설정
def make_map():
    params1 = {
        "serviceKey": service_key,  # 인증키
        "pageNo": "1",  # 페이지 번호
        "numOfRows": "1000",  # 한 페이지당 결과 수
        "type": "json",  # JSON 형식 요청 (API에 따라 '_type': 'json'일 수 있음)
    }
    params2 = {
        "serviceKey": service_key,  # 인증키
        "pageNo": "2",  # 페이지 번호
        "numOfRows": "1000",  # 한 페이지당 결과 수
        "type": "json",  # JSON 형식 요청 (API에 따라 '_type': 'json'일 수 있음)
    }
    try:
    # API 호출
        response1 = requests.get(url, params=params1)
        response1.raise_for_status()  # 오류 발생 시 예외 처리

        # JSON 데이터로 파싱
        data1 = response1.json()
        items1 = data1.get("body", {}).get("items", {}).get("item", [])
        response2 = requests.get(url, params=params2)
        response2.raise_for_status()  # 오류 발생 시 예외 처리

        # JSON 데이터로 파싱
        data2 = response2.json()
        items2 = data2.get("body", {}).get("items", {}).get("item", [])
        #print(items)
        if items1:
            df1 = pd.DataFrame(items1)
            print(f"데이터 로드 성공! 총 {len(df1)}개의 행이 있습니다.")
            df_seoul1 = df1[df1['rdnmadr'].str.startswith('서울특별시', na=False)]
        #print(items)
        if items2:
            df2 = pd.DataFrame(items2)
            print(f"데이터 로드 성공! 총 {len(df2)}개의 행이 있습니다.")
            df_seoul2 = df2[df2['rdnmadr'].str.startswith('서울특별시', na=False)]
        df_seoul = pd.concat([df_seoul1,df_seoul2],ignore_index=True)

    except Exception as e:
        print(f"에러가 발생했습니다: {e}")
        # 1. 지도 생성 (기본 tiles는 빈 값이나 기본값으로 두고 아래에서 TileLayer 추가)
    m = folium.Map(location=[37.5666, 126.9782], width=750, height=750, zoom_start=15)

        # 2. 순정 OSM 타일을 '반복문 밖'에서 단 한 번만 추가 (referrer_policy 필수)
    folium.TileLayer(
    tiles="https://tile.openstreetmap.org/{z}/{x}/{y}.png",
    attr='&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors',
    referrer_policy="no-referrer-when-downgrade"
    ).add_to(m)

    # 3. 마커 추가는 반복문 안에서 수행
    for index, row in df_seoul.iterrows():
        try:
            lat = float(row["latitude"])
            lon = float(row["longitude"])

            folium.Marker(
                location=[lat, lon],
                popup=f"<b>{row.get('fcltyNm', '정보 없음')}</b>",
                icon=folium.Icon(color="blue", icon="info-sign"),
            ).add_to(m)
        except (ValueError, TypeError):
            continue

    m.save("./templates/map.html")