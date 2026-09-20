"""
운전주의 약물 확인 서비스 - 통합 파이프라인 (386매칭 + 실제 경고문구 + 영문 보조매칭)
================================================================

[실행 전 확인]
1. 이 파일과 "운전주의_약물_386_정제.xlsx"를 같은 폴더에 두세요.
2. 아래 SERVICE_KEY에 data.go.kr Decoding 서비스키를 넣으세요.
3. venv 활성화 후 실행: python drug_api_test.py

[2026.8.9 수정 내역]
- 영문 매칭에서 "Chlorpheniramine 안에 pheniramine이 글자로만 포함되어
  오매칭되는 문제"를 발견하여, 단순 포함(in) 검사 대신 '단어 경계(\\b)'를
  확인하는 정규식 매칭으로 교체함. (예: Dexibuprofen 안의 ibuprofen도 동일 문제였음)
- MANUAL_HEALTH_KR_WARNINGS에서 누락됐던 지르텍정 항목 복원.
"""

import re
import time
import requests
import openpyxl

# =========================================================
# 0) 설정
# =========================================================
SERVICE_KEY = "j5CynYkfG05WrHwHLpDERhswnWLqqhEFtHq/BcVv5X9NalLQFWWuKoSvEZ7ZaXY/UMmGSyvBz9fsK/iyfRdfhg=="


# =========================================================
# 1) e약은요 (의약품개요정보) - 실제 경고문구 조회용
# =========================================================
EASY_DRUG_URL = "https://apis.data.go.kr/1471000/DrbEasyDrugInfoService/getDrbEasyDrugList"


def search_easy_drug_info(item_name: str, num_of_rows: int = 5) -> dict:
    """제품명으로 e약은요 정보 조회 (주의사항 등)."""
    params = {
        "serviceKey": SERVICE_KEY,
        "pageNo": "1",
        "numOfRows": str(num_of_rows),
        "type": "json",
        "itemName": item_name,
    }
    resp = requests.get(EASY_DRUG_URL, params=params, timeout=10)
    resp.raise_for_status()
    return resp.json()


def extract_driving_warning_text(easy_drug_json: dict) -> str:
    """
    e약은요 응답에서 '주의사항'(atpnQesitm) 필드 중 '운전'/'기계조작'이
    포함된 문장만 뽑아서 반환. 없으면 빈 문자열.
    """
    try:
        items = easy_drug_json["body"]["items"]
    except (KeyError, TypeError):
        return ""
    if not items:
        return ""

    atpn = items[0].get("atpnQesitm") or ""
    sentences = re.split(r"(?<=[.\n])", atpn)
    warning_sentences = [s.strip() for s in sentences if ("운전" in s or "기계조작" in s)]
    return " ".join(warning_sentences)


# =========================================================
# 2) 의약품 제품 허가정보 - 주성분 상세정보
# =========================================================
DRUG_PRDT_SERVICE_BASE = "https://apis.data.go.kr/1471000/DrugPrdtPrmsnInfoService07"
DRUG_PRDT_MCPN_URL = f"{DRUG_PRDT_SERVICE_BASE}/getDrugPrdtMcpnDtlInq07"


def search_drug_main_ingredient(product_name: str = None, entrps: str = None, num_of_rows: int = 10, page_no: int = 1) -> dict:
    """제품명(product_name, 한글) 또는 업체명(entrps)으로 주성분 상세정보 조회."""
    params = {
        "serviceKey": SERVICE_KEY,
        "pageNo": str(page_no),
        "numOfRows": str(num_of_rows),
        "type": "json",
    }
    if product_name:
        params["Prduct"] = product_name
    if entrps:
        params["Entrps"] = entrps

    resp = requests.get(DRUG_PRDT_MCPN_URL, params=params, timeout=30)
    resp.raise_for_status()
    return resp.json()


# 허가 상세정보 API - "성상"(제형) 필드는 있으나, Prduct 파라미터 필터링이
# 실제로 작동하지 않는 것으로 확인됨(2026.8.9). 현재는 사용하지 않음.
DRUG_PRDT_DETAIL_URL = f"{DRUG_PRDT_SERVICE_BASE}/getDrugPrdtPrmsnDtlInq06"


def search_drug_detail(product_name: str = None, entrps: str = None, num_of_rows: int = 5) -> dict:
    """허가 상세정보 조회 - 성상(제형) 필드 확인용 (현재 필터링 미작동, 디버그용으로만 남겨둠)"""
    params = {
        "serviceKey": SERVICE_KEY,
        "pageNo": "1",
        "numOfRows": str(num_of_rows),
        "type": "json",
    }
    if product_name:
        params["Prduct"] = product_name
    if entrps:
        params["Entrps"] = entrps

    resp = requests.get(DRUG_PRDT_DETAIL_URL, params=params, timeout=10)
    resp.raise_for_status()
    return resp.json()


# =========================================================
# 3) 로컬 386개 성분 리스트 로드
# =========================================================
def load_386_list(path="../data/운전주의_약물_386_정제.xlsx"):
    wb = openpyxl.load_workbook(path, data_only=True)
    ws = wb["운전주의 약물 386"]
    result = []
    for row in ws.iter_rows(min_row=2, values_only=True):
        result.append(
            {"level": row[0], "kor": row[1], "eng": row[2], "symptom": row[3], "atc": row[7]}
        )
    return result


def norm(s: str) -> str:
    """한글 성분명 정규화 - 공백 제거"""
    return re.sub(r"\s+", "", s) if s else s


# 식약처 원본 데이터 표기 오타/변형 보정 테이블
# (발견될 때마다 여기 한 줄씩 추가하는 방식)
INGREDIENT_SYNONYMS = {
    "수도에페드린": "슈도에페드린",
    "페티딘": "페치딘",
    "독시라민": "독실아민",
    "발라시클로비르": "발라시클로버",
    "리팜피신": "리팜핀",
    "팜시클로비르": "팜시클로버",  # -clovir 계열 항바이러스제, 발라시클로버와 동일 패턴 (2026.8.10)
    "클래리트로마이신": "클래리스로마이신",  # 표기 차이 (2026.8.10)
    "올메사탄": "올메사르탄",  # 약학정보원 자료 내에서도 혼용 확인 (2026.8.10)
}

# health.kr(약학정보원)에서 직접 확인한 경고문구 (e약은요에 없을 때 대체용)
# 출처: health.kr 개별 제품 페이지, 2026.8.9 확인
MANUAL_HEALTH_KR_WARNINGS = {
    "부루펜정200밀리그램(이부프로펜)": "복용하는 동안 환자의 반응시간에 영향을 미칠 수 있으므로 운전을 할 때나 기계조작 시 주의가 필요하다.",
    "클라리틴정(로라타딘)": "임상시험에서 이 약은 운전 및 기계 작동 등의 활동에 영향을 주지 않았다. 그러나 매우 드물게 일부 사람들이 졸음을 경험한다는 것을 알아야 하며, 이는 기계를 운전하거나 사용하는 능력에 영향을 미칠 수 있다.",
    "디부루펜정400밀리그램(덱시부프로펜디.씨)": "이 약을 복용하면 이상반응으로 어지러움 또는 피로가 나타날 수 있어서 환자의 반응능력이 감소할 가능성이 있다. 그러므로 운전이나 기계를 작동하는 경우에는 주의해서 복용해야 한다.",
    "미아론정(아플로쿠알론)": "졸음, 반사운동능력의 저하 등이 나타날 수 있으므로 이 약을 투여중인 환자는 자동차운전 등 위험이 수반되는 기계조작을 하지 않도록 주의한다.",
    "쿠아론정(아플로쿠알론)": "졸음, 반사운동능력의 저하 등이 나타날 수 있으므로 이 약을 투여중인 환자는 자동차운전 등 위험이 수반되는 기계조작을 하지 않도록 주의한다.",
    "티아론정(티아넵틴나트륨)": "어떤 환자들에게서는 약물복용에 따른 경각심 손상이 발생할 수도 있다. 따라서 운전중인 환자나 기계조작중인 자에서는 이 약의 사용과 관련된 졸음발생의 위험성에 주의해야 한다.",
    "스티아론정(티아넵틴나트륨)": "어떤 환자들에게서는 약물복용에 따른 경각심 손상이 발생할 수도 있다. 따라서 운전중인 환자나 기계조작중인 자에서는 이 약의 사용과 관련된 졸음발생의 위험성에 주의해야 한다.",
    "화콜노즈정": "복용하는 동안 졸음이 오는 경우가 있으므로 자동차 운전 또는 기계류의 운전 조작을 피할 것.",
    "지르텍정(세티리진염산염)": "졸음이 올 수 있으므로 운전, 위험한 기계조작시 주의하세요. (원 첨부문서: 임상용량에서 반응시간 부작용은 없었으나, 운전·기계조작 시 권장 용량을 초과하지 않을 것)",
}


def match_386(ingredient_name: str, list386_by_norm: dict):
    """
    한글 성분명으로 386리스트 매칭 (기존 방식, 1순위).

    ⚠ 2026.8.10 수정: 기존엔 "가장 먼저 발견된 매칭"을 썼는데, 이러면
    "코데인"과 "디히드로코데인"처럼 짧은 이름이 긴 이름 안에 포함된
    경우, 386리스트에 어느 게 먼저 등재됐는지에 따라 엉뚱한(부정확한)
    성분으로 잘못 매칭될 위험이 있었음(전수조사 결과 실제 등급 오류는
    발견 안 됐지만, 구조적으로 위험한 상태였음). 이제는 "가장 길고
    구체적인 이름"을 우선 선택하도록 변경 - 순서에 의존하지 않음.
    """
    n = norm(ingredient_name)
    for wrong, correct in INGREDIENT_SYNONYMS.items():
        if wrong in n:
            n = n.replace(wrong, correct)

    best_match = None
    best_len = 0
    for name_n, info in list386_by_norm.items():
        if name_n and name_n in n and len(name_n) > best_len:
            best_match = info
            best_len = len(name_n)
    return best_match


def match_386_by_english(main_ingr_eng: str, list386_eng_entries: list):
    """
    영문 성분명으로 386리스트 보조 매칭 (한글 매칭 실패 시 2순위 시도).

    ⚠ 2026.8.9 수정: 단순 포함(in) 검사는 "Chlorpheniramine" 안에
    "pheniramine"이 글자로만 포함된 것까지 매칭시키는 오류가 있었음
    (Dexibuprofen ⊃ ibuprofen도 동일 문제). 이를 막기 위해 정규식
    단어경계(\\b)를 사용해, 독립된 단어/구로 존재할 때만 매칭하도록 변경.

    main_ingr_eng는 제품 전체의 영문 성분명이 '/'로 이어진 문자열이므로
    '/' 단위로 나눠서 각 구간별로 정확히 대조합니다.
    ⚠ 그래도 자동 매칭 결과이므로, 실제 서비스 반영 전 사람 확인을 권장합니다.
    """
    if not main_ingr_eng:
        return []
    hits = []
    segments = [seg.strip() for seg in main_ingr_eng.split("/") if seg.strip()]
    seen_kor = set()
    for seg in segments:
        seg_lower = seg.lower()
        for entry in list386_eng_entries:
            eng_name = (entry.get("eng") or "").strip()
            if not eng_name or entry["kor"] in seen_kor:
                continue
            pattern = r"\b" + re.escape(eng_name.lower()) + r"\b"
            if re.search(pattern, seg_lower):
                hits.append(entry)
                seen_kor.add(entry["kor"])
    return hits


# =========================================================
# 4) 통합 파이프라인 - 검증된 22개 (삼콜정 제외, 브로엔시럽 보류)
# =========================================================
PILOT_PRODUCTS = [
    "타이레놀정500밀리그람", "게보린정", "펜잘큐정", "이지엔6프로연질캡슐", "부루펜정",
    "판피린티정", "판콜에스내복액", "화이투벤큐노즈연질캡슐", "콜대원콜드시럽", "타이레놀콜드-에스정",
    "지르텍정", "클라리틴정", "코메키나캡슐",
    "코푸시럽에스",
    "아론정", "슬리펠정",
    "키미테패취",
    "부스코판당의정", "겔포스엠현탁액",
    "판피린큐액", "이가탄에프캡슐", "화콜노즈정",
]


def run_full_pipeline():
    print("\n========== 통합 파이프라인 시작 (386매칭[한글+영문] + 경고문구) ==========")
    list386 = load_386_list()
    list386_by_norm = {norm(d["kor"]): d for d in list386 if d["kor"]}
    list386_eng_entries = [d for d in list386 if d.get("eng")]

    results = []
    for product in PILOT_PRODUCTS:
        print(f"\n[조회 중] {product}")

        try:
            mcpn = search_drug_main_ingredient(product_name=product)
        except Exception as e:
            print(f"  ⚠ 주성분 API 에러: {e}")
            continue

        items = mcpn.get("body", {}).get("items") or []
        if not items:
            print("  → 검색 결과 없음")
            results.append({"제품명": product, "상태": "미검색"})
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
            by_item_seq[seq]["성분들"].append(it.get("MTRAL_NM"))

        # 같은 제품명으로 여러 버전(ITEM_SEQ)이 있으면, 가장 최근 것만 남김
        # ITEM_SEQ가 클수록 최신 버전으로 관찰됨(패턴 관찰, 식약처 공식 스펙으로 확인된 것은 아님)
        by_product_name = {}
        for seq, info in by_item_seq.items():
            pname = info["제품명"]
            if pname not in by_product_name or seq > by_product_name[pname][0]:
                by_product_name[pname] = (seq, info)
        by_item_seq = {seq: info for pname, (seq, info) in by_product_name.items()}

        for seq, info in by_item_seq.items():
            matched_levels = []
            matched_kor_names = set()

            # 1순위: 한글 성분명 매칭
            for ing in info["성분들"]:
                hit = match_386(ing, list386_by_norm)
                if hit:
                    matched_levels.append(f"{ing}({hit['level']})")
                    matched_kor_names.add(hit["kor"])

            # 2순위: 영문 성분명 보조 매칭 (한글로 못 찾은 것 중에서만, 단어경계 확인)
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
                time.sleep(0.2)

                # e약은요에 없으면 수동 확인된 health.kr 데이터로 보완
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
            print(f"  → {info['제품명']} | 386매칭: {matched_levels if matched_levels else '없음'}")
            if warning_text:
                print(f"     경고문구({warning_source}): {warning_text[:60]}...")

        time.sleep(0.3)

    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "통합 결과"
    headers = ["품목기준코드", "제품명", "업체명", "전체성분", "386매칭성분", "실제경고문구", "출처"]
    ws.append(headers)
    for r in results:
        ws.append([r.get(h, "") for h in headers])
    for col in ws.columns:
        ws.column_dimensions[col[0].column_letter].width = 25
    wb.save("통합_파이프라인_결과.xlsx")
    print("\n========== 완료: 통합_파이프라인_결과.xlsx 저장됨 ==========")
    print("※ '[확인필요]' 표시가 붙은 매칭은 영문명으로 새로 찾은 것이니, 꼭 한 번 더 확인해주세요.")


# =========================================================
# 실행부
# =========================================================
if __name__ == "__main__":
    run_full_pipeline()