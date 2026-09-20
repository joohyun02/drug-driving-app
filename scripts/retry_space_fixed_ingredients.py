"""
공백표기 문제로 놓친 성분 재조회 전용 파일
================================================================
목적: 386리스트 원본에 공백/슬래시가 섞여 있어서(예: "슈도에페드린 염산염"),
      그 형태 그대로 검색했을 때 0건으로 나왔던 성분들을, 공백 제거한
      정확한 이름으로 다시 검색합니다. (2026.8.10 발견)

[대상 - 총 17개, 공백만 제거하면 실제 결과가 나오는 것들만]
클로니딘염산염, 에페드린염산염, 케토롤락트로메타민, 아토목세틴염산염,
발록사비르마르복실, 베포타스틴베실산염, 덱스케토프로펜트로메타몰,
클로닉신리시네이트, 몬테루카스트나트륨, dl-메틸에페드린염산염,
슈도에페드린염산염, 록소프로펜나트륨, 옥시메타졸린염산염,
자일로메타졸린염산염, 오셀타미비르인산염, 페닐레프린염산염, 나파졸린염산염

(이미다졸살리실레이트, 이프라트로피움브롬화물은 공백 제거해도 0건이라 제외)

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

FIXED_INGREDIENTS = [
    "클로니딘염산염",
    "에페드린염산염",
    "케토롤락트로메타민",
    "아토목세틴염산염",
    "발록사비르마르복실",
    "베포타스틴베실산염",
    "덱스케토프로펜트로메타몰",
    "클로닉신리시네이트",
    "몬테루카스트나트륨",
    "dl-메틸에페드린염산염",
    "슈도에페드린염산염",
    "록소프로펜나트륨",
    "옥시메타졸린염산염",
    "자일로메타졸린염산염",
    "오셀타미비르인산염",
    "페닐레프린염산염",
    "나파졸린염산염",
]

START_IDX = 12
END_IDX = 17
PAGE_SIZE = 300


def fetch_all_pages(kor_name: str) -> list:
    """페이지를 넘겨가며 해당 성분의 모든 검색 결과를 끝까지 가져옵니다."""
    all_items = []
    page_no = 1
    while True:
        result = None
        for attempt in range(1, 3):
            try:
                result = search_drug_main_ingredient(
                    product_name=kor_name, num_of_rows=PAGE_SIZE, page_no=page_no
                )
                break
            except Exception as e:
                print(f"  ⚠ {page_no}페이지 {attempt}번째 시도 실패: {e}")
                if attempt < 2:
                    time.sleep(3)

        if result is None:
            print(f"  ✗ {page_no}페이지 실패, 이 성분은 여기까지만 처리")
            break

        body = result.get("body", {})
        items = body.get("items") or []
        total_count = body.get("totalCount", 0)
        all_items.extend(items)
        print(f"  [{page_no}페이지] {len(items)}건 수신 (누적 {len(all_items)}/{total_count})")

        if len(all_items) >= total_count or not items:
            break
        page_no += 1
        time.sleep(0.3)

    return all_items


def run_fixed_ingredients():
    print(f"\n========== 공백표기 수정 성분 {len(FIXED_INGREDIENTS)}개 재조회 시작 ==========")
    list386 = load_386_list()
    list386_by_norm = {norm(d["kor"]): d for d in list386 if d["kor"]}
    list386_eng_entries = [d for d in list386 if d.get("eng")]

    seen_item_seq = set()
    results = []
    skipped_raw_material = 0

    for kor_name in FIXED_INGREDIENTS[START_IDX:END_IDX]:
        print(f"\n[성분 검색 중] {kor_name}")
        items = fetch_all_pages(kor_name)

        by_item_seq = {}
        for it in items:
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

        for seq, info in by_item_seq.items():
            if seq in seen_item_seq:
                continue
            seen_item_seq.add(seq)

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
                "검색기준성분": kor_name,
                "제품명": info["제품명"],
                "업체명": info["업체명"],
                "전체성분": ", ".join(info["성분들"]),
                "386매칭성분": ", ".join(matched_levels) if matched_levels else "없음",
                "실제경고문구": warning_text,
                "출처": warning_source,
            }
            results.append(row)

        time.sleep(0.3)

    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "공백수정_재조회결과"
    headers = ["품목기준코드", "검색기준성분", "제품명", "업체명", "전체성분", "386매칭성분", "실제경고문구", "출처"]
    ws.append(headers)
    for r in results:
        ws.append([r.get(h, "") for h in headers])
    for col in ws.columns:
        ws.column_dimensions[col[0].column_letter].width = 22
    wb.save(f"공백수정_재조회_{START_IDX}_{END_IDX}.xlsx")

    print(f"\n========== 완료: 공백수정_재조회_{START_IDX}_{END_IDX}.xlsx 저장됨 ==========")
    print(f"총 {len(results)}건, 원료 제외 {skipped_raw_material}건")


if __name__ == "__main__":
    run_fixed_ingredients()
