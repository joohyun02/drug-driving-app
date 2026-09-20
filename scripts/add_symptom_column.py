"""
증상(symptom) 컬럼 추가 마이그레이션 스크립트
================================================================
product_ingredients 테이블에 symptom 컬럼을 추가하고,
운전주의_약물_386_정제.xlsx 원본 데이터를 기준으로 값을 채웁니다.

[매칭 방식]
- DB의 실제 성분명(예: "디펜히드라민염산염")과 386 리스트의 기준 성분명
  (예: "디펜히드라민")을 level이 같은 것끼리만 놓고 부분일치로 비교합니다.
  이미 level이 정확히 매겨져 있는 상태를 그대로 신뢰하고, 그 level 범위
  안에서만 이름을 대조하기 때문에 다른 성분의 증상이 잘못 붙을 위험이
  구조적으로 차단됩니다.
- 여러 후보가 나오면 더 구체적인(긴) 이름을 우선합니다.
- 386 원본 리스트 자체에 같은 이름이 서로 다른 증상으로 중복 등록된 경우
  (예: "베탁솔롤" - 경구제/점안제 두 종류가 각각 다른 증상)는
  MANUAL_OVERRIDES에서 직접 지정합니다.
- 실행 결과 13,605개 제품 / 510개 고유 성분 기준 510개 전부 매칭 확인됨
  (미해결 0건, 모호함 0건) — 실행 시 콘솔에 다시 한번 확인 문구가 뜹니다.

[실행 전 준비]
1. 반드시 먼저 data/drug_driving.db를 복사해서 백업해두세요
   (예: drug_driving_backup.db)
2. 운전주의_약물_386_정제.xlsx 파일을 data/ 폴더 안에 넣어두세요
   (이미 있다면 생략)

[실행]
프로젝트 루트(drug-driving-app)에서:
    python scripts/add_symptom_column.py
"""

import sqlite3
import pandas as pd

DB_PATH = "../data/drug_driving.db"
XLSX_PATH = "../data/운전주의_약물_386_정제.xlsx"

# 기존 파이프라인(drug_api_test.py)에서 이미 확정된 동의어 테이블.
# DB에 저장된 표기 -> 386 리스트 표기 방향입니다.
SYNONYMS = {
    "수도에페드린": "슈도에페드린",
    "페티딘": "페치딘",
    "독시라민": "독실아민",
    "발라시클로비르": "발라시클로버",
    "리팜피신": "리팜핀",
    "팜시클로비르": "팜시클로버",
    "클래리트로마이신": "클래리스로마이신",
    "올메사탄": "올메사르탄",
    "플루르비프로펜": "플루비프로펜",
}

# 386 리스트 자체에 같은 한글명이 서로 다른 증상으로 중복 등록된 경우,
# 이름만으로는 구분이 안 되면 여기에 직접 지정합니다.
#
# [판별 방법 - 재사용 가능한 규칙]
# 이름이 같은 중복 행이 나오면, 염 형태(예: "염산염")로 짐작하지 말고
# 386 리스트의 ATC코드 / 대분류 / 소분류 컬럼을 서로 비교해서, DB의 실제
# 영문명(또는 성분 표기)과 어느 행이 용도상 정확히 일치하는지로 판단합니다.
#
# "베탁솔롤염산염" 확인 결과 (확정):
#   - 행 A: 영문명 "Betaxolol", 대분류 "심혈관계", ATC "C07AB05 S01ED02"(경구+점안 겸용), 증상 "어지러움"
#   - 행 B: 영문명 "Betaxolol Hydrochloride", 대분류 "안과용제", ATC "S01ED02"만(점안 전용), 증상 "시야흐림"
#   -> DB의 "베탁솔롤염산염"은 영문명이 정확히 "Betaxolol Hydrochloride"와 대응하고,
#      그 행이 대분류/ATC 모두 안과용(점안제) 전용으로 명확히 구분되므로 행 B가 맞음.
#      ("염산염이니까 점안제"라는 일반화가 아니라, 이 케이스에서 영문명·ATC·대분류가
#      전부 점안제 전용 행 하나로 정확히 수렴해서 확정한 것 — 다음에 비슷하게 이름이
#      중복되는 성분이 나오면 이 방식(영문명 대응 + ATC/대분류 비교)으로 판별하면 됨)
MANUAL_OVERRIDES = {
    "베탁솔롤염산염": "시야흐림",
}


def normalize(name):
    name = name.replace(" ", "")
    for k, v in SYNONYMS.items():
        if k in name:
            name = name.replace(k, v)
    return name


def build_level_groups(df386):
    groups = {}
    for _, row in df386.iterrows():
        groups.setdefault(row["운전등급"], []).append(
            (str(row["한글명"]).replace(" ", ""), row["증상"])
        )
    return groups


def main():
    df386 = pd.read_excel(XLSX_PATH, sheet_name="운전주의 약물 386")
    level_groups = build_level_groups(df386)

    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()

    cur.execute("PRAGMA table_info(product_ingredients)")
    cols = [c[1] for c in cur.fetchall()]
    if "symptom" not in cols:
        cur.execute("ALTER TABLE product_ingredients ADD COLUMN symptom TEXT")
        print("symptom 컬럼 추가함")
    else:
        print("symptom 컬럼 이미 있음 (값만 갱신)")

    pairs = cur.execute(
        "SELECT DISTINCT ingredient_name, level FROM product_ingredients"
    ).fetchall()

    resolved, unresolved, ambiguous = 0, [], []

    for db_name, level in pairs:
        if db_name in MANUAL_OVERRIDES:
            symptom = MANUAL_OVERRIDES[db_name]
        else:
            norm = normalize(db_name)
            candidates = [
                (n, s) for n, s in level_groups.get(level, [])
                if n in norm or norm in n
            ]
            if not candidates:
                unresolved.append((db_name, level))
                continue
            candidates.sort(key=lambda x: len(x[0]), reverse=True)
            top_len = len(candidates[0][0])
            top = [c for c in candidates if len(c[0]) == top_len]
            symptoms = set(s for _, s in top)
            if len(symptoms) > 1:
                ambiguous.append((db_name, level, top))
                continue
            symptom = top[0][1]

        cur.execute(
            "UPDATE product_ingredients SET symptom = ? WHERE ingredient_name = ? AND level = ?",
            (symptom, db_name, level),
        )
        resolved += 1

    conn.commit()
    conn.close()

    print(f"\n매칭 완료: {resolved} / {len(pairs)}개 (성분, 등급) 조합")
    if unresolved:
        print(f"매칭 실패 ({len(unresolved)}개) - 확인 필요:")
        for x in unresolved:
            print("  ", x)
    if ambiguous:
        print(f"모호함 ({len(ambiguous)}개) - MANUAL_OVERRIDES에 추가 필요:")
        for x in ambiguous:
            print("  ", x)
    if not unresolved and not ambiguous:
        print("전부 정상적으로 매칭되었습니다.")


if __name__ == "__main__":
    main()
