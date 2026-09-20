"""
전체 의약품 카탈로그 순회 - 1단계 (후보 추출)
================================================================
목적: 지금까지의 "386개 성분명으로 검색"은 제품명에 성분명이 안 붙은
      제품(예: 판콜에스내복액)을 놓치는 구조적 사각지대가 있었습니다
      (2026.8.10 발견 - 22개 파일럿 중 9개가 최종본에서 누락됨).

      이번엔 반대로, 식약처에 등록된 "전체 의약품 42,998개"를
      검색어 없이 그대로 페이지 단위로 다 받아온 뒤, 각 제품에 이미
      붙어있는 영문 성분명(ITEM_INGR_NAME)을 386리스트와 직접
      대조합니다. 제품명에 성분이 적혀있든 없든 상관없이 정확합니다.

[중요] getDrugPrdtPrmsnInq07의 Prduct(제품명) 파라미터는 실제로
      필터링이 안 되는 것으로 확인됨(2026.8.10). 그래서 필터 없이
      전체를 페이지로 순회하는 방식으로 설계함.

[이 스크립트가 하는 일 - 1단계]
- 전체 목록을 페이지 단위(500건씩)로 받아옴
- 각 제품의 영문 성분명이 386리스트 영문명과 겹치는지만 확인
- 겹치는 것만 "후보"로 저장 (아직 정확한 한글 성분/등급은 안 매김 - 2단계에서 함)

[실행 전 확인]
1. drug_api_test.py, 운전주의_약물_386_정제.xlsx, 이 파일을 같은 폴더에.
2. PAGE_START, PAGE_END를 이번에 처리할 구간으로 지정 (전체 86페이지 정도)
3. venv 활성화 후 실행: python build_full_catalog.py
"""

import time
import requests
import openpyxl

from drug_api_test import (
    DRUG_PRDT_SERVICE_BASE,
    SERVICE_KEY,
    load_386_list,
    match_386_by_english,
)

CATALOG_URL = f"{DRUG_PRDT_SERVICE_BASE}/getDrugPrdtPrmsnInq07"

# 이번 실행에서 처리할 페이지 구간 (500건씩, 전체 42,998건이면 약 86페이지)
PAGE_START = 81
PAGE_END = 86

NUM_OF_ROWS = 500


def fetch_catalog_page(page_no: int) -> dict:
    params = {
        "serviceKey": SERVICE_KEY,
        "pageNo": str(page_no),
        "numOfRows": str(NUM_OF_ROWS),
        "type": "json",
    }
    resp = requests.get(CATALOG_URL, params=params, timeout=30)
    resp.raise_for_status()
    return resp.json()


def run_phase1():
    print(f"\n========== 전체 카탈로그 순회 - {PAGE_START}~{PAGE_END}페이지 ==========")
    list386 = load_386_list()
    list386_eng_entries = [d for d in list386 if d.get("eng")]

    candidates = []
    total_scanned = 0

    for page_no in range(PAGE_START, PAGE_END + 1):
        result = None
        for attempt in range(1, 3):
            try:
                result = fetch_catalog_page(page_no)
                break
            except Exception as e:
                print(f"  ⚠ {page_no}페이지 {attempt}번째 시도 실패: {e}")
                if attempt < 2:
                    time.sleep(3)

        if result is None:
            print(f"  ✗ {page_no}페이지 실패, 건너뜀")
            continue

        items = result.get("body", {}).get("items") or []
        total_count = result.get("body", {}).get("totalCount", 0)
        total_scanned += len(items)
        print(f"[{page_no}페이지] {len(items)}건 스캔 (전체 {total_count}건 중 누적 {total_scanned}건)")

        for it in items:
            ingr_eng = it.get("ITEM_INGR_NAME")
            if not ingr_eng:
                continue
            hits = match_386_by_english(ingr_eng, list386_eng_entries)
            if hits:
                candidates.append({
                    "품목기준코드": it.get("ITEM_SEQ"),
                    "제품명": it.get("ITEM_NAME"),
                    "업체명": it.get("ENTP_NAME"),
                    "영문성분": ingr_eng,
                    "전문일반구분": it.get("SPCLTY_PBLC"),
                    "허가일자": it.get("ITEM_PERMIT_DATE"),
                    "386매칭후보": ", ".join(f"{h['kor']}({h['level']})" for h in hits),
                })

        time.sleep(0.3)

    output_filename = f"후보목록_{PAGE_START}~{PAGE_END}페이지.xlsx"
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "후보목록"
    headers = ["품목기준코드", "제품명", "업체명", "영문성분", "전문일반구분", "허가일자", "386매칭후보"]
    ws.append(headers)
    for c in candidates:
        ws.append([c.get(h, "") for h in headers])
    for col in ws.columns:
        ws.column_dimensions[col[0].column_letter].width = 25
    wb.save(output_filename)

    print(f"\n========== 완료: {output_filename} 저장됨 ==========")
    print(f"이번 구간 스캔: {total_scanned}건, 후보로 뽑힌 것: {len(candidates)}건")
    print(f"다음 구간을 하려면 PAGE_START={PAGE_END+1}, PAGE_END={PAGE_END+10} 로 바꿔서 다시 실행하세요.")


if __name__ == "__main__":
    run_phase1()
