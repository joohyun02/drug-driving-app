"""
엑셀 최종본 -> SQLite 데이터베이스 변환
================================================================
목적: 13,605개 제품이 담긴 엑셀(성분검색_진짜최종본.xlsx)을
      검색하기 좋은 구조의 SQLite 데이터베이스로 만듭니다.

[만들어지는 테이블 2개]
1. products        : 제품 하나당 한 행 (제품명, 업체명, 경고문구, 출처 등)
2. product_ingredients : 제품 하나에 매칭된 성분이 여러 개일 수 있어서,
                          "제품-성분-등급"을 한 줄씩 따로 저장

[실행 전 확인]
1. 이 파일과 "성분검색_진짜최종본.xlsx"를 같은 폴더에 두세요.
2. venv 활성화 후 실행: python build_database.py
3. 실행하면 "drug_driving.db" 파일이 생깁니다.
"""

import re
import sqlite3
import openpyxl

EXCEL_PATH = "../data/drug_data_final.xlsx"
DB_PATH = "../data/drug_driving.db"


def parse_matched_ingredients(matched_str: str):
    """
    '386매칭성분' 컬럼의 문자열을 [(성분명, 등급, 영문매칭여부), ...] 형태로 쪼갭니다.
    """
    if not matched_str or matched_str == "없음":
        return []

    results = []
    parts = matched_str.split(", ")
    for part in parts:
        m = re.match(r"^(.+?)\((?:영문매칭:)?(Level[^)]+)\)(\[확인필요\])?$", part.strip())
        if m:
            ing_name = m.group(1).strip()
            level = m.group(2).strip()
            is_english_matched = bool(m.group(3))
            results.append((ing_name, level, is_english_matched))
    return results


def build_database():
    print(f"엑셀 파일 로드 중: {EXCEL_PATH}")
    wb = openpyxl.load_workbook(EXCEL_PATH, data_only=True)
    ws = wb.active
    rows = list(ws.iter_rows(min_row=2, values_only=True))
    print(f"총 {len(rows)}개 제품 로드됨")

    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()

    cur.execute("DROP TABLE IF EXISTS product_ingredients")
    cur.execute("DROP TABLE IF EXISTS products")

    cur.execute("""
        CREATE TABLE products (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            item_seq TEXT UNIQUE,
            product_name TEXT NOT NULL,
            company_name TEXT,
            all_ingredients TEXT,
            warning_text TEXT,
            warning_source TEXT
        )
    """)

    cur.execute("""
        CREATE TABLE product_ingredients (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            product_id INTEGER NOT NULL,
            ingredient_name TEXT NOT NULL,
            level TEXT NOT NULL,
            matched_via_english INTEGER NOT NULL DEFAULT 0,
            FOREIGN KEY (product_id) REFERENCES products(id)
        )
    """)

    cur.execute("CREATE INDEX idx_product_name ON products(product_name)")
    cur.execute("CREATE INDEX idx_ingredient_name ON product_ingredients(ingredient_name)")

    inserted = 0
    ingredient_rows_inserted = 0
    for r in rows:
        item_seq, pname, entp, all_ing, matched, warning, source = r
        if not pname:
            continue

        cur.execute(
            """INSERT OR IGNORE INTO products
               (item_seq, product_name, company_name, all_ingredients, warning_text, warning_source)
               VALUES (?, ?, ?, ?, ?, ?)""",
            (str(item_seq) if item_seq else None, pname, entp, all_ing, warning, source),
        )
        product_id = cur.lastrowid
        if product_id == 0:
            cur.execute("SELECT id FROM products WHERE item_seq = ?", (str(item_seq),))
            row = cur.fetchone()
            product_id = row[0] if row else None

        if product_id:
            inserted += 1
            for ing_name, level, is_eng in parse_matched_ingredients(matched):
                cur.execute(
                    """INSERT INTO product_ingredients
                       (product_id, ingredient_name, level, matched_via_english)
                       VALUES (?, ?, ?, ?)""",
                    (product_id, ing_name, level, 1 if is_eng else 0),
                )
                ingredient_rows_inserted += 1

    conn.commit()

    print(f"\n========== 완료 ==========")
    print(f"products 테이블: {inserted}건")
    print(f"product_ingredients 테이블: {ingredient_rows_inserted}건")
    print(f"저장 위치: {DB_PATH}")

    print("\n--- 확인용 샘플 쿼리 ---")
    cur.execute("SELECT COUNT(*) FROM products")
    print("전체 제품 수:", cur.fetchone()[0])

    cur.execute("SELECT COUNT(DISTINCT product_id) FROM product_ingredients WHERE level LIKE 'Level 3%'")
    print("Level 3 성분이 하나라도 있는 제품 수:", cur.fetchone()[0])

    cur.execute("""
        SELECT p.product_name, pi.ingredient_name, pi.level
        FROM products p JOIN product_ingredients pi ON p.id = pi.product_id
        WHERE p.product_name LIKE '%판콜에스%'
    """)
    print("\n'판콜에스' 검색 예시:")
    for row in cur.fetchall():
        print(" ", row)

    conn.close()


if __name__ == "__main__":
    build_database()
