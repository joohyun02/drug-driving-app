"""
약물운전 확인 서비스 - API 서버 (FastAPI)
================================================================
목적: drug_driving.db(13,605개 제품)를 실제로 검색할 수 있는
      웹 API 서버로 만듭니다.

[제공하는 기능]
1. GET /search?name=제품명       -> 이름으로 검색, 여러 개면 목록 반환
2. GET /product/{item_seq}       -> 특정 제품의 상세정보(등급/성분/경고문구)

[실행 전 확인]
1. pip install fastapi uvicorn (아직 안 하셨으면)
2. ../data/drug_driving.db 파일이 있어야 합니다
3. 이 파일이 있는 폴더(backend)에서 실행: uvicorn main:app --reload
4. 실행 후 브라우저에서 http://127.0.0.1:8000/docs 열면
   테스트용 화면이 자동으로 생깁니다 (버튼 눌러서 바로 확인 가능)
"""

import sqlite3
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware

DB_PATH = "../data/drug_driving.db"

app = FastAPI(title="약물운전 확인 서비스 API")

# 나중에 프런트엔드(화면)에서 이 API를 호출할 때, 브라우저 보안정책에
# 막히지 않도록 허용해주는 설정입니다. 지금은 전부 허용(*)해두고,
# 실제 서비스로 나갈 때는 우리 도메인만 허용하도록 좁히면 됩니다.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


def get_connection():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row  # 결과를 딕셔너리처럼 다룰 수 있게 함
    return conn


@app.get("/")
def root():
    return {"message": "약물운전 확인 서비스 API. /docs 에서 사용법을 확인하세요."}


@app.get("/search")
def search_products(name: str):
    """
    제품명으로 검색합니다. (부분일치 - '판콜'만 넣어도 '판콜에스내복액' 등 다 나옴)
    결과가 여러 개면 목록으로, 각 제품의 대표 등급(가장 높은 Level)도 같이 보여줍니다.
    """
    if not name or not name.strip():
        raise HTTPException(status_code=400, detail="검색어(name)를 입력하세요.")

    conn = get_connection()
    cur = conn.cursor()

    cur.execute(
        """
        SELECT id, item_seq, product_name, company_name
        FROM products
        WHERE product_name LIKE ?
        ORDER BY product_name
        LIMIT 30
        """,
        (f"%{name.strip()}%",),
    )
    products = cur.fetchall()

    results = []
    for p in products:
        # 이 제품의 매칭 성분 중 가장 높은 Level 하나를 대표로 가져옴
        cur.execute(
            """
            SELECT level FROM product_ingredients
            WHERE product_id = ?
            ORDER BY level DESC
            LIMIT 1
            """,
            (p["id"],),
        )
        level_row = cur.fetchone()
        top_level = level_row["level"] if level_row else None

        results.append({
            "item_seq": p["item_seq"],
            "product_name": p["product_name"],
            "company_name": p["company_name"],
            "top_level": top_level,  # None이면 386 매칭 성분 없음(정보 없음)
        })

    conn.close()

    return {
        "query": name,
        "count": len(results),
        "results": results,
    }


@app.get("/product/{item_seq}")
def get_product_detail(item_seq: str):
    """
    특정 제품의 상세정보를 반환합니다.
    - 매칭된 성분과 각각의 등급(Level)
    - 실제 경고문구와 출처
    """
    conn = get_connection()
    cur = conn.cursor()

    cur.execute(
        "SELECT id, item_seq, product_name, company_name, all_ingredients, warning_text, warning_source "
        "FROM products WHERE item_seq = ?",
        (item_seq,),
    )
    product = cur.fetchone()

    if not product:
        conn.close()
        raise HTTPException(status_code=404, detail="해당 품목기준코드의 제품을 찾을 수 없습니다.")

    cur.execute(
        "SELECT ingredient_name, level, matched_via_english, symptom FROM product_ingredients WHERE product_id = ?",
        (product["id"],),
    )
    ingredients = cur.fetchall()

    conn.close()

    return {
        "item_seq": product["item_seq"],
        "product_name": product["product_name"],
        "company_name": product["company_name"],
        "all_ingredients": product["all_ingredients"],
        "matched_ingredients": [
            {
                "name": ing["ingredient_name"],
                "level": ing["level"],
                "matched_via_english": bool(ing["matched_via_english"]),
                "symptom": ing["symptom"],
                
            }
            for ing in ingredients
        ],
        "warning_text": product["warning_text"],
        "warning_source": product["warning_source"],
    }
