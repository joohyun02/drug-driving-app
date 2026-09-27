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
    result = search_drug_main_ingredient(product_name="콜바스타에프정")
    print(result)  # items만 말고 전체 다 출력