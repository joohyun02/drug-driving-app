"""
마약류 542개 확장 파이프라인 (전용 파일)
================================================================
목적: drug_api_test.py(22개 파일럿 본체)는 건드리지 않고,
      규모가 큰 542개 마약류 처리는 여기서 따로 실행합니다.
      drug_api_test.py의 핵심 함수(성분매칭, 경고문구 조회 등)를
      그대로 가져다 씁니다 - 로직 중복 없이 재사용.

[포함 기능]
1. 542개 마약류 리스트 로드 (대한약사회 원본 파일에서 제품명만 추출)
2. 제형 추정(경구/주사/패치) - 이름 패턴 기반, "확인필요" 표시
3. 주사제(추정)로 확실히 분류된 것만 API 호출 없이 제외 (시간 절약)
   → 제외된 목록은 별도 파일로 저장해서 나중에 눈으로 검토 가능
4. 나머지(경구/패치/확인필요)는 386매칭[한글+영문]+경고문구까지 전체 실행

[실행 전 확인]
1. drug_api_test.py, 운전주의_약물_386_정제.xlsx,
   운전금지약물_도로교통법기준_식약처목록_20260403.xlsx,
   그리고 이 파일을 전부 같은 폴더에 두세요.
2. drug_api_test.py 안의 SERVICE_KEY가 이미 채워져 있어야 합니다.
3. venv 활성화 후 실행: python narcotics_pipeline.py
   (542개 규모라 몇 분 정도 걸립니다. 실행 중 노트북 절전 주의)
"""

import re
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
# 1) 제형 추정 (경구/주사/패치) - 패턴 추정, 확정 아님
# =========================================================
def guess_dosage_form(product_name: str) -> str:
    """
    제품명 키워드로 제형을 '추정'합니다.
    ⚠ 식약처 API로 확인된 공식 데이터가 아니라 이름만 보고 짐작한
    패턴 추정입니다. 8개 샘플로 검증 완료(2026.8.9)했지만, 자동으로
    걸러내지 말고 참고만 하세요.

    - "주사/앰플/바이알/수액" 포함 → 주사제(추정)
    - "OO주10mg"처럼 '주' 바로 뒤에 숫자·%·괄호 오는 패턴 → 주사제(추정)
    - "패취/패치/첩부" 포함 → 패치(추정)
    - 그 외 전부 → "경구/기타(확인필요)"로 남김 (억지로 경구 단정 안 함)
    """
    if not product_name:
        return "불명"
    name = product_name
    if any(kw in name for kw in ["주사", "앰플", "바이알", "수액"]):
        return "주사제(추정)"
    if re.search(r"주(?=[0-9%\(])", name):
        return "주사제(추정)"
    if any(kw in name for kw in ["패취", "패치", "첩부"]):
        return "패치(추정)"
    return "경구/기타(추정 - 확인필요)"


# =========================================================
# 2) 542개 마약류 리스트 로드
# =========================================================
def load_542_list(path="운전금지약물_도로교통법기준_식약처목록_20260403.xlsx", sheet="식약처 기준"):
    """
    대한약사회 원본(식약처 기준 마약/향정 완제품 542개) 로드.
    제품명 컬럼(B열)만 추려서 중복 제거된 리스트로 반환.
    """
    wb = openpyxl.load_workbook(path, data_only=True)
    ws = wb[sheet]
    names = []
    seen = set()
    for row in ws.iter_rows(min_row=2, values_only=True):
        pname = row[1]  # B열: 제품명
        if pname and pname not in seen:
            names.append(pname)
            seen.add(pname)
    return names


# =========================================================
# 3) 실행 파이프라인
# =========================================================
def process_product_list(product_list, list386, output_filename):
    print(f"\n========== 파이프라인 시작 - 대상 {len(product_list)}개 ==========")
    list386_by_norm = {norm(d["kor"]): d for d in list386 if d["kor"]}
    list386_eng_entries = [d for d in list386 if d.get("eng")]

    results = []
    for idx, product in enumerate(product_list, start=1):
        if idx % 20 == 0 or idx == 1:
            print(f"\n[{idx}/{len(product_list)}] 진행 중... (누적 결과 {len(results)}건)")

        try:
            mcpn = search_drug_main_ingredient(product_name=product)
        except Exception as e:
            print(f"  ⚠ [{product}] 주성분 API 에러: {e}")
            continue

        items = mcpn.get("body", {}).get("items") or []
        if not items:
            results.append({"제품명": product, "상태": "검색결과없음"})
            continue

        by_item_seq = {}
        for it in items:
            seq = it.get("ITEM_SEQ")
            by_item_seq.setdefault(
                seq,
                {
                    "제품명": it.get("PRDUCT"),
                    "업체명": it.get("ENTRPS"),
                    "성분들": [],
                    "영문성분전체": it.get("MAIN_INGR_ENG"),
                },
            )
            mtral_name = it.get("MTRAL_NM")
            if mtral_name:  # None이나 빈 값이면 아예 리스트에 안 넣음
                by_item_seq[seq]["성분들"].append(mtral_name)

        by_product_name = {}
        for seq, info in by_item_seq.items():
            pname = info["제품명"]
            if pname not in by_product_name or seq > by_product_name[pname][0]:
                by_product_name[pname] = (seq, info)
        by_item_seq = {seq: info for pname, (seq, info) in by_product_name.items()}

        for seq, info in by_item_seq.items():
            matched_levels = []
            matched_kor_names = set()

            for ing in info["성분들"]:
                if not ing: # 성분명이 없는 경우 건너뜀
                    continue
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
                "제품명": info["제품명"],
                "업체명": info["업체명"],
                "제형추정": guess_dosage_form(info["제품명"]),
                "전체성분": ", ".join(info["성분들"]),
                "386매칭성분": ", ".join(matched_levels) if matched_levels else "없음",
                "실제경고문구": warning_text,
                "출처": warning_source,
            }
            results.append(row)

        time.sleep(0.2)

    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "결과"
    headers = ["품목기준코드", "제품명", "업체명", "제형추정", "전체성분", "386매칭성분", "실제경고문구", "출처"]
    ws.append(headers)
    for r in results:
        ws.append([r.get(h, "") for h in headers])
    for col in ws.columns:
        ws.column_dimensions[col[0].column_letter].width = 22
    wb.save(output_filename)

    matched_count = sum(1 for r in results if r.get("386매칭성분") not in (None, "", "없음"))
    print(f"\n========== 완료: {output_filename} 저장됨 ==========")
    print(f"총 {len(results)}건 처리, 386매칭 {matched_count}건")
    print("※ '[확인필요]' 표시는 영문명으로 새로 찾은 매칭이니 꼭 확인해주세요.")
    print("※ '제형추정'은 이름만 보고 짐작한 패턴이니, 자동으로 거르지 말고 참고만 하세요.")


def run_full_scale():
    """
    542개 마약류 전체 확장 실행.
    실행 전에 제형을 먼저 추정해서, '주사제(추정)'으로 확실히 분류된 것만
    API 호출 없이 건너뛰고 별도 리스트로 저장합니다(시간·트래픽 절약).
    '경구/기타(확인필요)'와 '패치(추정)'는 애매하더라도 빠뜨리면 안 되니
    전부 파이프라인을 돌립니다.
    """
    list386 = load_386_list()
    products_542 = load_542_list()
    print(f"542개 리스트에서 중복 제거 후 {len(products_542)}개 제품명 로드됨")

    excluded_injection = []
    to_process = []
    for p in products_542:
        form = guess_dosage_form(p)
        if form == "주사제(추정)":
            excluded_injection.append({"제품명": p, "제형추정": form})
        else:
            to_process.append(p)

    print(f"주사제(추정)로 분류되어 제외: {len(excluded_injection)}개")
    print(f"파이프라인 실행 대상(경구/패치/확인필요): {len(to_process)}개")

    # 제외된 리스트를 별도 파일로 저장 (나중에 사람이 눈으로 검토용)
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "주사제추정_제외목록"
    ws.append(["제품명", "제형추정", "비고"])
    for item in excluded_injection:
        ws.append([item["제품명"], item["제형추정"], "이름 패턴 추정 - 오분류 가능성 있으니 확인 필요"])
    for col in ws.columns:
        ws.column_dimensions[col[0].column_letter].width = 30
    wb.save("제외된_주사제추정_리스트.xlsx")
    print("→ 제외 목록 저장됨: 제외된_주사제추정_리스트.xlsx")

    process_product_list(to_process, list386, "전체확장_마약류_결과.xlsx")


# =========================================================
# 실행부
# =========================================================
if __name__ == "__main__":
    run_full_scale()