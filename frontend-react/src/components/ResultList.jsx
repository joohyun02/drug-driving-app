import { levelBadge, herbBadge, isHerbalComplex, parseLevel } from '../utils/level';

export default function ResultList({ results, loading, error, onSelect }) {
  if (loading) return <p className="muted">검색 중...</p>;

  if (error) {
    return (
      <p className="error-box">
        서버에 연결할 수 없습니다. 로컬 FastAPI 서버(uvicorn main:app --reload)가 실행 중인지 확인해주세요.
        <br />
        <span className="err-detail">{error}</span>
      </p>
    );
  }

  if (!results) return null;

  if (!results.length) {
    return <p className="muted">검색 결과가 없습니다. 다른 이름으로 검색해보세요.</p>;
  }

  return (
    <div className="result-list">
      {results.map((p) => {
        const parsed = parseLevel(p.top_level);
        const isHerbal = isHerbalComplex(p.product_name) && !parsed;
        const badge = isHerbal ? herbBadge() : levelBadge(p.top_level);
        return (
          <button key={p.item_seq} className="result-item" onClick={() => onSelect(p.item_seq)}>
            <span className="result-main">
              <span className="result-name">{p.product_name}</span>
              <span className="result-company">{p.company_name}</span>
            </span>
            <span className="badge" style={{ background: badge.bg, color: badge.text }}>
              {badge.label}
            </span>
          </button>
        );
      })}
    </div>
  );
}
