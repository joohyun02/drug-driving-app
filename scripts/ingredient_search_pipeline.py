"""
성분명 기반 검색 파이프라인 (386개 전체, 배치 실행)
================================================================
목적: "제품명 → 성분"이 아니라 반대로 "386개 성분명 → 그 성분이
      들어간 모든 제품"을 찾습니다. drug_api_test.py의 핵심 함수를
      그대로 가져다 씁니다.

[이번 버전]
- 10개 샘플 테스트 통과 후, 386개 전체를 한 번에 안 돌리고
  30개씩 나눠서(배치) 돌리도록 변경 (2026.8.9)
- 파일 맨 위 BATCH_START/BATCH_END 숫자만 바꿔서 여러 번 실행
- 원료의약품("(원료)" 포함 제품명) 제외
- 성분명(MTRAL_NM) 비어있는 항목 건너뜀
- 같은 제품 안에서 같은 성분이 여러 행(TAMT_SEQ 등)으로 중복 오는
  문제 발견하여 수정 (2026.8.9, 세트린정 사례로 확인)

[실행 전 확인]
1. drug_api_test.py, 운전주의_약물_386_정제.xlsx, 이 파일을 같은 폴더에 두세요.
2. 아래 BATCH_START, BATCH_END를 이번에 처리할 구간으로 설정하세요.
3. venv 활성화 후 실행: python ingredient_search_pipeline.py
4. 결과는 "성분검색_결과_N~M.xlsx" 형태로 배치마다 별도 저장됩니다.
5. 386개 전부 끝나면, 배치 파일들을 합쳐서 전체 기준 중복 제거를
   한 번 더 해야 합니다 (지금은 배치 내에서만 중복 제거됨).
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
# 386개 전체 리스트를 배치로 나눠서 실행
# =========================================================
# 이번 실행에서 처리할 구간 (0부터 시작하는 인덱스, 끝은 포함 안 함)
# 예: BATCH_START=0, BATCH_END=30  → 386개 중 1~30번째만 처리
# 다음 배치를 돌릴 땐 이 두 숫자만 바꿔서 다시 실행하면 됩니다.
BATCH_START = 360
BATCH_END = 386

def run_batch():
    list386 = load_386_list()
    all_ingredients = [d["kor"] for d in list386 if d["kor"]]
    all_ingredients = list(dict.fromkeys(all_ingredients))  # 순서 유지하며 중복 제거

    batch_ingredients = all_ingredients[BATCH_START:BATCH_END]
    print(f"\n========== 성분명 기반 검색 - {BATCH_START+1}~{min(BATCH_END, len(all_ingredients))}번째 "
          f"(전체 {len(all_ingredients)}개 중 {len(batch_ingredients)}개) ==========")

    list386_by_norm = {norm(d["kor"]): d for d in list386 if d["kor"]}
    list386_eng_entries = [d for d in list386 if d.get("eng")]

    seen_item_seq = set()
    results = []
    skipped_raw_material = 0

    for kor_name in batch_ingredients:
        print(f"\n[성분 검색 중] {kor_name}")
        try:
            mcpn = search_drug_main_ingredient(product_name=kor_name, num_of_rows=100)
        except Exception as e:
            print(f"  ⚠ API 에러: {e}")
            continue

        items = mcpn.get("body", {}).get("items") or []
        total_count = mcpn.get("body", {}).get("totalCount", 0)
        print(f"  → 전체 {total_count}건 (이번 응답에 {len(items)}건 포함)")
        if total_count and total_count > len(items):
            print(f"  ⚠ 300건 넘게 있어서 일부만 가져왔습니다({len(items)}/{total_count}건). 필요시 별도 확인 필요.")

        by_item_seq = {}
        for it in items:
            seq = it.get("ITEM_SEQ")
            pname = it.get("PRDUCT") or ""

            # 원료의약품 제외
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
                # 같은 제품 안에서 이미 나온 성분명이면 중복 추가 안 함
                # (TAMT_SEQ가 다르면 같은 성분이 여러 행으로 오는 경우 있음, 2026.8.9 확인)
                by_item_seq[seq]["성분들"].append(mtral_name)

        for seq, info in by_item_seq.items():
            if seq in seen_item_seq:
                continue  # 이미 이번 배치 내 다른 성분 검색에서 발견된 제품이면 중복 제외
            seen_item_seq.add(seq)

            if not info["성분들"]:
                continue  # 성분 정보가 전부 비어있으면 건너뜀

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

        time.sleep(0.2)

    output_filename = f"../archive/성분검색_결과_{BATCH_START+1}~{min(BATCH_END, len(all_ingredients))}.xlsx"

    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "성분검색_결과"
    headers = ["품목기준코드", "검색기준성분", "제품명", "업체명", "전체성분", "386매칭성분", "실제경고문구", "출처"]
    ws.append(headers)
    for r in results:
        ws.append([r.get(h, "") for h in headers])
    for col in ws.columns:
        ws.column_dimensions[col[0].column_letter].width = 22
    wb.save(output_filename)

    print(f"\n========== 완료: {output_filename} 저장됨 ==========")
    print(f"총 {len(results)}건 (이번 배치 내 중복 제거)")
    print(f"원료의약품으로 제외된 건수: {skipped_raw_material}건")
    print(f"다음 배치를 돌리려면 BATCH_START={BATCH_END}, BATCH_END={BATCH_END+30} 로 바꿔서 다시 실행하세요.")
    print("(전체 386개를 다 돌리면 배치별 결과 파일들을 나중에 합쳐서 전체 중복도 한 번 더 제거해야 합니다.)")


if __name__ == "__main__":
    run_batch()