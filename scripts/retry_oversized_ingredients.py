"""
300건 초과 성분 재조회 전용 파일 (수동 페이지 분할 버전)
================================================================
목적: 300건 넘게 있어서 일부만 가져왔던 6개 성분을, 이번엔
      "한 번에 끝까지 자동으로"가 아니라, 386개 배치 처리 때처럼
      "성분 1개 + 페이지 범위"를 사람이 지정해서 여러 번 나눠 돌립니다.
      한 번 실행이 실패해도, 그 구간만 다시 돌리면 되니 더 안전합니다.

[대상 6개 성분과 이미 확보된 양 - 100건/페이지 기준]
- 프레가발린: 총 378건, 300건 확보(1~3페이지) → 남은 건 4페이지부터
- 세티리진염산염: 총 303건, 300건 확보 → 남은 건 4페이지부터
- 우황청심원: 총 2053건, 300건 확보 → 남은 건 4~21페이지
- 발사르탄: 총 322건, 300건 확보 → 남은 건 4페이지부터
- 암로디핀: 총 1086건, 300건 확보 → 남은 건 4~11페이지
- 텔미사르탄: 총 503건, 300건 확보 → 남은 건 4~6페이지

[사용법]
1. 아래 TARGET_INGREDIENT를 이번에 할 성분 하나로 지정
2. PAGE_START, PAGE_END를 이번에 가져올 페이지 범위로 지정
   (예: 우황청심원을 한 번에 다 하지 말고 4~10, 11~15, 16~21 이렇게 나눠서)
3. 실행: python retry_oversized_ingredients.py
4. 결과는 "재조회_성분명_페이지범위.xlsx"로 저장됨
5. 다 끝나면 여러 결과 파일을 나중에 합쳐야 함

[실행 전 확인]
drug_api_test.py, 운전주의_약물_386_정제.xlsx, 이 파일을 같은 폴더에 두세요.
"""

import time
import openpyxl

from drug_api_test import (
    search_easy_drug_info,
    search_drug_main_ingredient,
    extract_driving_warning_text,
    load_386_list,
    match_386,
    match_386_by_english,
    norm,
    MANUAL_HEALTH_KR_WARNINGS,
)

# =========================================================
# 이번 실행에서 처리할 것 (매번 이 3줄만 바꿔서 재실행)
# =========================================================
TARGET_INGREDIENT = "우황청심원"
PAGE_START = 18
PAGE_END = 21  # 포함 (이 페이지까지 가져옴)

PAGE_SIZE = 100


def run_retry_single():
    print(f"\n========== '{TARGET_INGREDIENT}' {PAGE_START}~{PAGE_END}페이지 재조회 시작 ==========")
    list386 = load_386_list()
    list386_by_norm = {norm(d["kor"]): d for d in list386 if d["kor"]}
    list386_eng_entries = [d for d in list386 if d.get("eng")]

    all_items = []
    for page_no in range(PAGE_START, PAGE_END + 1):
        print(f"\n[{page_no}페이지 요청 중]")
        try:
            result = search_drug_main_ingredient(
                product_name=TARGET_INGREDIENT, num_of_rows=PAGE_SIZE, page_no=page_no
            )
        except Exception as e:
            print(f"  ⚠ 에러: {e}")
            print(f"  이 페이지는 실패했습니다. 나중에 PAGE_START={page_no}, PAGE_END={page_no}로 다시 시도하세요.")
            continue

        body = result.get("body", {})
        items = body.get("items") or []
        total_count = body.get("totalCount", 0)
        print(f"  → {len(items)}건 수신 (전체 {total_count}건 중 {page_no}페이지)")
        all_items.extend(items)
        time.sleep(0.3)

    if not all_items:
        print("\n이번 실행으로 확보된 데이터가 없습니다. 페이지 범위나 서버 상태를 확인해주세요.")
        return

    by_item_seq = {}
    skipped_raw_material = 0
    for it in all_items:
        seq = it.get("ITEM_SEQ")
        pname = it.get("PRDUCT") or ""

        if "원료" in pname:
            skipped_raw_material += 1
            continue

        by_item_seq.setdefault(
            seq,
            {
                "제품명": pname,
                "업체명": it.get("ENTRPS"),
                "성분들": [],
                "영문성분전체": it.get("MAIN_INGR_ENG"),
            },
        )
        mtral_name = it.get("MTRAL_NM")
        if mtral_name and mtral_name not in by_item_seq[seq]["성분들"]:
            by_item_seq[seq]["성분들"].append(mtral_name)

    results = []
    for seq, info in by_item_seq.items():
        if not info["성분들"]:
            continue

        matched_levels = []
        matched_kor_names = set()

        for ing in info["성분들"]:
            hit = match_386(ing, list386_by_norm)
            if hit:
                matched_levels.append(f"{ing}({hit['level']})")
                matched_kor_names.add(hit["kor"])

        eng_hits = match_386_by_english(info["영문성분전체"], list386_eng_entries)
        for hit in eng_hits:
            if hit["kor"] not in matched_kor_names:
                matched_levels.append(f"{hit['kor']}(영문매칭:{hit['level']})[확인필요]")
                matched_kor_names.add(hit["kor"])

        warning_text = ""
        warning_source = ""
        if matched_levels:
            try:
                easy = search_easy_drug_info(item_name=info["제품명"])
                warning_text = extract_driving_warning_text(easy)
                if warning_text:
                    warning_source = "e약은요"
            except Exception as e:
                warning_text = f"(e약은요 조회 실패: {e})"
            time.sleep(0.15)

            if not warning_text:
                manual = MANUAL_HEALTH_KR_WARNINGS.get(info["제품명"])
                if manual:
                    warning_text = manual
                    warning_source = "약학정보원(수동확인)"
                else:
                    warning_text = "e약은요 미제공 - 386등급 참고"
                    warning_source = "미확인"

        row = {
            "품목기준코드": seq,
            "검색기준성분": TARGET_INGREDIENT,
            "제품명": info["제품명"],
            "업체명": info["업체명"],
            "전체성분": ", ".join(info["성분들"]),
            "386매칭성분": ", ".join(matched_levels) if matched_levels else "없음",
            "실제경고문구": warning_text,
            "출처": warning_source,
        }
        results.append(row)

    output_filename = f"재조회_{TARGET_INGREDIENT}_{PAGE_START}~{PAGE_END}페이지.xlsx"
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "재조회_결과"
    headers = ["품목기준코드", "검색기준성분", "제품명", "업체명", "전체성분", "386매칭성분", "실제경고문구", "출처"]
    ws.append(headers)
    for r in results:
        ws.append([r.get(h, "") for h in headers])
    for col in ws.columns:
        ws.column_dimensions[col[0].column_letter].width = 22
    wb.save(output_filename)

    print(f"\n========== 완료: {output_filename} 저장됨 ==========")
    print(f"총 {len(results)}건, 원료 제외 {skipped_raw_material}건")
    print("다음 페이지 구간을 이어서 하려면 PAGE_START/PAGE_END를 바꿔서 다시 실행하세요.")


if __name__ == "__main__":
    run_retry_single()