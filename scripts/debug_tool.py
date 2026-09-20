"""
디버그 전용 스크립트
================================================================
목적: drug_api_test.py(본 파이프라인)는 절대 건드리지 않고,
      여기서만 "이 제품 e약은요 raw 응답 좀 보자" 같은 임시 확인을 합니다.
"""

from drug_api_test import (
    search_easy_drug_info,
    search_drug_main_ingredient,
    search_drug_detail,
    extract_driving_warning_text,
    load_386_list,
    match_386,
    norm,
    MANUAL_HEALTH_KR_WARNINGS,
)

# =========================================================
# 여기서 실험하기
# =========================================================
if __name__ == "__main__":
    import openpyxl
    wb = openpyxl.load_workbook("후보목록_전체.xlsx", data_only=True)
    ws = wb.active
    names = [row[1] for row in ws.iter_rows(min_row=2, values_only=True) if row[1]]
    unique_names = list(dict.fromkeys(names))
    
    # 14350번째 근처(0-indexed로 14349) 확인
    for i in [14349, 14400, 14500, 14600, 14700, 14761]:
        name = unique_names[i]
        result = search_drug_main_ingredient(product_name=name, num_of_rows=50)
        total = result.get("body", {}).get("totalCount", 0)
        print(f"[{i}] '{name}' → {total}건")