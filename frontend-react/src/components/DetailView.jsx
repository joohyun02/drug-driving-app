import { levelBadge, herbBadge, isHerbalComplex, parseLevel } from '../utils/level';

export default function DetailView({ detail, loading, error }) {
  if (loading) return <p className="muted">불러오는 중...</p>;

  if (error) {
    return (
      <p className="error-box">
        상세 정보를 불러오지 못했습니다.
        <br />
        <span className="err-detail">{error}</span>
      </p>
    );
  }

  if (!detail) return null;

  const d = detail;
  const hasIngredients = d.matched_ingredients.length > 0;
  const isHerbal = isHerbalComplex(d.product_name) && !hasIngredients;

  // 여러 성분 중 "가장 주의가 필요한" 하나를 골라 상단 대표 배지에 씁니다.
  // (아래 성분별 목록은 이 계산과 무관하게 각자의 원본 라벨을 그대로 보여줍니다.
  //  예: "Level 0~1"인 성분은 대표값 계산엔 1로 반영되지만, 그 줄 자체엔
  //  "Level 0~1"이라는 원본 표기가 그대로 남습니다.)
  let badge;
  if (isHerbal) {
    badge = herbBadge();
  } else if (hasIngredients) {
    const worst = d.matched_ingredients.reduce((best, ing) => {
      const parsed = parseLevel(ing.level);
      if (!parsed) return best;
      if (!best || parsed.sortValue > best.sortValue) return { ing, sortValue: parsed.sortValue };
      return best;
    }, null);
    badge = worst ? levelBadge(worst.ing.level) : levelBadge(null);
  } else {
    badge = levelBadge(null);
  }

  return (
    <div className="detail-card">
      <p className="detail-name">{d.product_name}</p>
      <p className="detail-company">{d.company_name}</p>
      <span className="badge badge-lg" style={{ background: badge.bg, color: badge.text }}>
        {hasIngredients ? `운전 주의 확인됨 · ${badge.label}` : badge.label}
      </span>
      {hasIngredients && <p className="source-note">등급 출처: 대한약사회 참고자료</p>}

      {isHerbal && (
        <p className="muted" style={{ marginTop: 14 }}>
          한약재 성분으로 구성되어 있어 386개 성분 기준 개별 평가 대상이 아닙니다. 복용 전
          첨부문서의 주의사항을 확인하시거나 약사와 상담하시기 바랍니다.
        </p>
      )}

      {!isHerbal && hasIngredients && (
        <div className="ingredient-block">
          <p className="block-title">확인된 성분</p>
          {d.matched_ingredients.map((ing, idx) => {
            const parsed = parseLevel(ing.level);
            return (
              <p className="ingredient-row" key={idx}>
                · {ing.name}{' '}
                <span className="muted-inline">
                  ({parsed ? parsed.label : 'Level ?'}
                  {ing.symptom ? ` · ${ing.symptom}` : ''}
                  {ing.matched_via_english ? ' · 영문 성분명 매칭' : ''})
                </span>
              </p>
            );
          })}
        </div>
      )}

      {d.warning_text ? (
        <div className="warning-block">
          <p className="warning-text">"{d.warning_text}"</p>
          <p className="warning-source">출처: {d.warning_source || '미상'}</p>
        </div>
      ) : (
        !isHerbal && (
          <p className="muted" style={{ marginTop: 14 }}>
            공식 경고문구가 확인되지 않았습니다. (미확인)
          </p>
        )
      )}
    </div>
  );
}
