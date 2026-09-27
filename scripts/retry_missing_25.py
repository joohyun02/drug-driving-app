"""
누락된 25개 제품 재조회 스크립트
================================================================
식약처 API의 일시적 500에러로 초기 파이프라인 때 못 들어간 25개 제품을
drug_api_test.py의 검증된 함수(search_drug_main_ingredient, match_386,
match_386_by_english, 경고문구 조회)를 그대로 재사용해서 조회하고,
drug_driving.db에 직접 추가합니다.

[실행 전 준비]
1. 이 파일을 scripts/ 폴더 안에 두세요 (drug_api_test.py와 같은 폴더).
2. 반드시 먼저 data/drug_driving.db를 복사해서 백업해두세요.

[실행]
scripts 폴더 안에서:
    python retry_missing_25.py
"""

import sqlite3
import time

from drug_api_test import (
    load_386_list,
    norm,
    match_386,
    match_386_by_english,
    search_drug_main_ingredient,
    search_easy_drug_info,
    extract_driving_warning_text,
    MANUAL_HEALTH_KR_WARNINGS,
)

DB_PATH = "../data/drug_driving.db"

# 초반 500에러로 누락됐던 25개 제품
MISSING_PRODUCTS = [
    "콜바스타에프정", "초감콜쓰리정", "아클린정", "아이프로펜에프시럽(이부프로펜)",
    "코크린정", "그날엔노즈연질캡슐", "그날엔콜드연질캡슐", "코페민연질캡슐",
    "리페손정50mg(에페리손염산염)", "플루탐캡슐45밀리그램(오셀타미비르인산염)",
    "듀로틴캡슐30밀리그램(둘록세틴염산염)", "푸로콜에이캡슐",
    "오파딘점안액0.1%(올로파타딘염산염)", "센테라피연고",
    "워너비스트롱연질캡슐(덱시부프로펜)", "레보펜시럽(덱시부프로펜)",
    "코스피손정(에페리손염산염)", "대웅바이오플루캡슐45밀리그램(오셀타미비르인산염)",
    "타미풀엠캡슐45밀리그램(오셀타미비르인산염)", "삼성아시클로버정",
    "로피리노서방정8mg(로피니롤염산염)", "로피리노서방정4mg(로피니롤염산염)",
    "케이나스틴정20밀리그램(에피나스틴염산염)", "동광에피나스틴정20mg(에피나스틴염산염)",
    "안국오셀타미비르캡슐30밀리그램(오셀타미비르인산염)",
]


def get_or_create_symptom_column(cur):
    cur.execute("PRAGMA table_info(product_ingredients)")
    cols = [c[1] for c in cur.fetchall()]
    if "symptom" not in cols:
        cur.execute("ALTER TABLE product_ingredients ADD COLUMN symptom TEXT")
        print("(symptom 컬럼이 없어서 새로 추가함)")


def main():
    list386 = load_386_list()
    list386_by_norm = {norm(d["kor"]): d for d in list386 if d["kor"]}
    list386_eng_entries = [d for d in list386 if d.get("eng")]

    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    get_or_create_symptom_column(cur)

    added, skipped_exists, no_result, api_error = [], [], [], []

    for product in MISSING_PRODUCTS:
        print(f"\n[조회 중] {product}")
        try:
            mcpn = search_drug_main_ingredient(product_name=product)
        except Exception as e:
            print(f"  ⚠ 주성분 API 에러: {e}")
            api_error.append(product)
            continue

        items = mcpn.get("body", {}).get("items") or []
        if not items:
            print("  → 검색 결과 없음")
            no_result.append(product)
            continue

        by_item_seq = {}
        for it in items:
            seq = str(it.get("ITEM_SEQ"))
            by_item_seq.setdefault(
                seq,
                {
                    "제품명": it.get("PRDUCT"),
                    "업체명": it.get("ENTRPS"),
                    "성분들": [],
                    "영문성분전체": it.get("MAIN_INGR_ENG"),
                },
            )
            by_item_seq[seq]["성분들"].append(it.get("MTRAL_NM"))

        # 같은 제품명으로 여러 버전(ITEM_SEQ)이 있으면 가장 최근 것만 남김 (기존 파이프라인과 동일 규칙)
        by_product_name = {}
        for seq, info in by_item_seq.items():
            pname = info["제품명"]
            if pname not in by_product_name or seq > by_product_name[pname][0]:
                by_product_name[pname] = (seq, info)
        by_item_seq = {seq: info for pname, (seq, info) in by_product_name.items()}

        for seq, info in by_item_seq.items():
            cur.execute("SELECT id FROM products WHERE item_seq = ?", (seq,))
            if cur.fetchone():
                print(f"  → {info['제품명']} (item_seq={seq}) 이미 DB에 있음 - 건너뜀")
                skipped_exists.append(info["제품명"])
                continue

            matched = []  # [{name, level, symptom, matched_via_english}]
            matched_kor_names = set()

            # 1순위: 한글 성분명 매칭
            for ing in info["성분들"]:
                hit = match_386(ing, list386_by_norm)
                if hit:
                    matched.append({
                        "name": ing,
                        "level": hit["level"],
                        "symptom": hit.get("symptom"),
                        "matched_via_english": 0,
                    })
                    matched_kor_names.add(hit["kor"])

            # 2순위: 영문 성분명 보조 매칭
            eng_hits = match_386_by_english(info["영문성분전체"], list386_eng_entries)
            for hit in eng_hits:
                if hit["kor"] not in matched_kor_names:
                    matched.append({
                        "name": hit["kor"],
                        "level": hit["level"],
                        "symptom": hit.get("symptom"),
                        "matched_via_english": 1,
                    })
                    matched_kor_names.add(hit["kor"])

            warning_text = ""
            warning_source = ""
            if matched:
                try:
                    easy = search_easy_drug_info(item_name=info["제품명"])
                    warning_text = extract_driving_warning_text(easy)
                    if warning_text:
                        warning_source = "e약은요"
                except Exception as e:
                    warning_text = ""
                time.sleep(0.2)

                if not warning_text:
                    manual = MANUAL_HEALTH_KR_WARNINGS.get(info["제품명"])
                    if manual:
                        warning_text = manual
                        warning_source = "약학정보원(수동확인)"
                    else:
                        warning_text = "e약은요 미제공 - 386등급 참고"
                        warning_source = "미확인"

            all_ingredients = ", ".join(info["성분들"])

            cur.execute(
                "INSERT INTO products (item_seq, product_name, company_name, all_ingredients, warning_text, warning_source) "
                "VALUES (?, ?, ?, ?, ?, ?)",
                (seq, info["제품명"], info["업체명"], all_ingredients, warning_text, warning_source),
            )
            product_id = cur.lastrowid

            for m in matched:
                cur.execute(
                    "INSERT INTO product_ingredients (product_id, ingredient_name, level, matched_via_english, symptom) "
                    "VALUES (?, ?, ?, ?, ?)",
                    (product_id, m["name"], m["level"], m["matched_via_english"], m["symptom"]),
                )

            print(f"  → 추가됨: {info['제품명']} | 매칭 성분: "
                  f"{[(m['name'], m['level'], m['symptom']) for m in matched] if matched else '없음(386 매칭 성분 없음)'}")
            added.append(info["제품명"])

        time.sleep(0.3)

    conn.commit()
    conn.close()

    print("\n========== 결과 요약 ==========")
    print(f"새로 추가됨: {len(added)}개")
    for p in added:
        print("  -", p)
    if skipped_exists:
        print(f"\n이미 DB에 있어서 건너뜀: {len(skipped_exists)}개")
        for p in skipped_exists:
            print("  -", p)
    if no_result:
        print(f"\n검색 결과 없음 (제품명 재확인 필요): {len(no_result)}개")
        for p in no_result:
            print("  -", p)
    if api_error:
        print(f"\nAPI 에러 (다시 시도 필요): {len(api_error)}개")
        for p in api_error:
            print("  -", p)


if __name__ == "__main__":
    main()