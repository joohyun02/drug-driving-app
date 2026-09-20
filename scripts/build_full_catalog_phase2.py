"""
전체 카탈로그 순회 - 2단계 (정밀 매칭 + 경고문구)
================================================================
목적: 1단계에서 뽑은 후보 14,762개 각각에 대해, 정확한 한글 성분명·
      386등급·실제 경고문구까지 채웁니다. 386개 배치 때와 같은
      "구간 나눠서 여러 번 실행" 방식입니다.

[실행 전 확인]
1. drug_api_test.py, 운전주의_약물_386_정제.xlsx,
   후보목록_전체.xlsx, 이 파일을 같은 폴더에 두세요.
2. START_IDX, END_IDX를 이번에 처리할 구간으로 지정하세요.
3. venv 활성화 후 실행: python build_full_catalog_phase2.py
4. 결과는 "카탈로그_결과_N~M.xlsx"로 저장됩니다.

[전체 14,762개, 1000개씩 하면 약 15번 나눠 실행하면 됩니다]
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

CANDIDATE_FILE = "../data/후보목록_전체.xlsx"

# 이번 실행에서 처리할 구간 (0부터 시작)
START_IDX = 12500
END_IDX = 15000


def load_candidate_names():
    wb = openpyxl.load_workbook(CANDIDATE_FILE, data_only=True)
    ws = wb.active
    names = []
    seen = set()
    for row in ws.iter_rows(min_row=2, values_only=True):
        pname = row[1]
        if pname and pname not in seen:
            names.append(pname)
            seen.add(pname)
    return names


def run_phase2():
    candidate_names = load_candidate_names()
    batch = candidate_names[START_IDX:END_IDX]
    print(f"\n========== 2단계 정밀 매칭 - {START_IDX+1}~{min(END_IDX, len(candidate_names))}번째 "
          f"(전체 {len(candidate_names)}개 중 {len(batch)}개) ==========")

    list386 = load_386_list()
    list386_by_norm = {norm(d["kor"]): d for d in list386 if d["kor"]}
    list386_eng_entries = [d for d in list386 if d.get("eng")]

    seen_item_seq = set()
    results = []
    skipped_raw_material = 0
    skipped_export = 0

    for idx, product in enumerate(batch, start=START_IDX + 1):
        if (idx - START_IDX) % 50 == 0:
            print(f"  ... {idx}/{END_IDX} 진행 중 (누적 결과 {len(results)}건)")

        try:
            mcpn = search_drug_main_ingredient(product_name=product, num_of_rows=50)
        except Exception as e:
            print(f"  ⚠ [{product}] API 에러: {e}")
            continue

        items = mcpn.get("body", {}).get("items") or []
        if not items:
            continue

        by_item_seq = {}
        for it in items:
            seq = it.get("ITEM_SEQ")
            pname = it.get("PRDUCT") or ""

            if "원료" in pname:
                skipped_raw_material += 1
                continue
            if "수출용" in pname:
                skipped_export += 1
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
            seen_kor = set()
            for ing in info["성분들"]:
                hit = match_386(ing, list386_by_norm)
                if hit and hit["kor"] not in seen_kor:
                    matched_levels.append(f"{ing}({hit['level']})")
                    seen_kor.add(hit["kor"])

            eng_hits = match_386_by_english(info["영문성분전체"], list386_eng_entries)
            for hit in eng_hits:
                if hit["kor"] not in seen_kor:
                    matched_levels.append(f"{hit['kor']}(영문매칭:{hit['level']})[확인필요]")
                    seen_kor.add(hit["kor"])

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
                "제품명": info["제품명"],
                "업체명": info["업체명"],
                "전체성분": ", ".join(info["성분들"]),
                "386매칭성분": ", ".join(matched_levels) if matched_levels else "없음",
                "실제경고문구": warning_text,
                "출처": warning_source,
            }
            results.append(row)

        time.sleep(0.2)

    output_filename = f"카탈로그_결과_{START_IDX+1}~{min(END_IDX, len(candidate_names))}.xlsx"
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "결과"
    headers = ["품목기준코드", "제품명", "업체명", "전체성분", "386매칭성분", "실제경고문구", "출처"]
    ws.append(headers)
    for r in results:
        ws.append([r.get(h, "") for h in headers])
    for col in ws.columns:
        ws.column_dimensions[col[0].column_letter].width = 25
    wb.save(output_filename)

    print(f"\n========== 완료: {output_filename} 저장됨 ==========")
    print(f"총 {len(results)}건, 원료제외 {skipped_raw_material}건, 수출용제외 {skipped_export}건")
    print(f"다음 구간: START_IDX={END_IDX}, END_IDX={END_IDX+1000} 로 바꿔서 다시 실행하세요.")


if __name__ == "__main__":
    run_phase2()
