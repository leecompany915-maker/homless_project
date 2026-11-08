# -*- coding: utf-8 -*-
"""
공중화장실 CSV의 주소를 geopy(Nominatim, OpenStreetMap)로 위도/경도로 변환합니다.

사용법
  1) 설치:   pip install geopy pandas
  2) 실행:   python geocode_toilets.py 공중화장실정보.csv
     결과:   공중화장실정보_위경도.csv  (엑셀에서 바로 열리는 UTF-8 BOM CSV)

특징
  - Nominatim 이용 규칙에 따라 1초에 1건씩 요청합니다. (5,600건 → 약 1~2시간)
  - 같은 주소는 한 번만 조회하고, 조회 결과를 geocode_cache.json 에 저장합니다.
    중간에 끊겨도 다시 실행하면 이미 조회한 주소는 건너뛰고 이어서 진행합니다.
  - 도로명주소 → 도로명주소(건물번호까지만) → 지번주소 → 동 단위 순서로 시도하며,
    어떤 방식으로 찾았는지 '좌표정확도' 열에 기록합니다.
  - 테스트로 앞쪽 일부만 돌려보려면:  python geocode_toilets.py 파일.csv --limit 20
"""
import argparse
import json
import os
import re
import sys
import time

import pandas as pd
from geopy.extra.rate_limiter import RateLimiter
from geopy.geocoders import Nominatim

# 자기 이메일이나 고유한 이름으로 바꾸세요. (Nominatim 정책상 식별 가능한 User-Agent 필요)
USER_AGENT = "seoul-public-toilet-geocoder"
CACHE_FILE = "geocode_cache.json"
ROAD_COL = "소재지도로명주소"
JIBUN_COL = "소재지지번주소"


# ---------------------------------------------------------------- 주소 정리
def clean(addr):
    """공백/오타/표기 통일."""
    if not isinstance(addr, str):
        return ""
    a = addr.strip().strip('"')
    a = a.replace(",", " ").replace("?", " ")
    a = re.sub(r"\s+", " ", a).strip()
    a = re.sub(r"^서을특별시", "서울특별시", a)
    a = re.sub(r"^서울특별시(?=\S)", "서울특별시 ", a)
    a = re.sub(r"^서울 ", "서울특별시 ", a)
    if re.match(r"^\S+구 ", a) and not a.startswith("서울"):
        a = "서울특별시 " + a
    # '대학로120' -> '대학로 120' (단, '종로3가'처럼 뒤에 글자가 붙은 경우는 그대로)
    a = re.sub(r"(로|길)(\d+(?:-\d+)?)(?=\s|$|\()", r"\1 \2", a)
    if a in ("없음", "서울특별시"):
        return ""
    return a


def road_core(addr):
    """도로명주소에서 '도로명 + 건물번호'까지만 남김. 예) ... 율곡로 지하 308 (종로6가) -> ... 율곡로 지하 308"""
    m = re.match(r"^(.*?(?:로|길)\s+(?:지하\s*)?\d+(?:-\d+)?)(?=\s|$|\()", addr)
    return m.group(1) if m else ""


def jibun_core(addr):
    """지번주소에서 '동 + 번지'까지만 남김. 예) ... 동숭동 산2-32 등 -> ... 동숭동 산2-32"""
    m = re.match(r"^(.*?(?:동|가|리)\s+(?:산\s*)?\d+(?:-\d+)?)(?=\s|$|\()", addr)
    return m.group(1) if m else ""


def dong_only(addr):
    """동 단위까지만 남김 (최후의 수단, 대략적인 위치)."""
    m = re.match(r"^(서울특별시 \S+구 \S+(?:동|가))", addr)
    return m.group(1) if m else ""


def candidates(road, jibun):
    """조회할 주소 후보를 (정확도, 주소) 순서대로 만듦."""
    r, j = clean(road), clean(jibun)
    out = []
    for level, q in (
        ("도로명", r),
        ("도로명(건물번호까지)", road_core(r)),
        ("지번", jibun_core(r)),          # 도로명 칸에 지번이 들어간 경우
        ("지번", jibun_core(j)),
        ("동 단위(근사)", dong_only(j) or dong_only(r)),
    ):
        if q and q not in [x[1] for x in out]:
            out.append((level, q))
    return out


# ---------------------------------------------------------------- 지오코딩
def load_cache():
    if os.path.exists(CACHE_FILE):
        with open(CACHE_FILE, encoding="utf-8") as f:
            return json.load(f)
    return {}


def save_cache(cache):
    tmp = CACHE_FILE + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(cache, f, ensure_ascii=False)
    os.replace(tmp, CACHE_FILE)


def make_geocoder():
    geo = Nominatim(user_agent=USER_AGENT, timeout=15)
    return RateLimiter(
        geo.geocode,
        min_delay_seconds=1.1,      # Nominatim: 초당 1건 이하
        max_retries=3,
        error_wait_seconds=5,
        swallow_exceptions=True,    # 오류 시 None 반환
    )


def lookup(query, geocode, cache):
    if query in cache:
        return cache[query]
    loc = geocode(query, country_codes="kr", language="ko")
    res = [loc.latitude, loc.longitude, loc.address] if loc else None
    cache[query] = res
    return res


def read_csv(path):
    for enc in ("utf-8-sig", "cp949"):
        try:
            return pd.read_csv(path, dtype=str, encoding=enc, keep_default_na=False)
        except UnicodeDecodeError:
            continue
    sys.exit("CSV 인코딩을 읽을 수 없습니다 (UTF-8, CP949 모두 실패).")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("csv")
    ap.add_argument("--limit", type=int, default=0, help="앞에서 N행만 처리 (테스트용)")
    args = ap.parse_args()

    df = read_csv(args.csv)
    if args.limit:
        df = df.head(args.limit).copy()
    for col in (ROAD_COL, JIBUN_COL):
        if col not in df.columns:
            sys.exit(f"'{col}' 열이 없습니다. 열 이름: {list(df.columns)}")

    cache = load_cache()
    geocode = make_geocoder()
    lats, lons, levels, found = [], [], [], []
    n = len(df)
    start = time.time()

    for i, (road, jibun) in enumerate(zip(df[ROAD_COL], df[JIBUN_COL]), 1):
        lat = lon = level = addr = ""
        for lv, q in candidates(road, jibun):
            res = lookup(q, geocode, cache)
            if res:
                lat, lon, addr = res
                level = lv
                break
        lats.append(lat); lons.append(lon); levels.append(level or "실패"); found.append(addr)

        if i % 50 == 0 or i == n:
            save_cache(cache)
            ok = sum(1 for x in levels if x != "실패")
            print(f"{i}/{n} 처리, 성공 {ok}건, 경과 {int(time.time() - start)}초", flush=True)

    df["위도"] = lats
    df["경도"] = lons
    df["좌표정확도"] = levels
    df["찾은주소(OSM)"] = found

    out = os.path.splitext(args.csv)[0] + "_위경도.csv"
    df.to_csv(out, index=False, encoding="utf-8-sig")
    print("\n저장:", out)
    print(df["좌표정확도"].value_counts().to_string())
    print("성공")


if __name__ == "__main__":
    main()