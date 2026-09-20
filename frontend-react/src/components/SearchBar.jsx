export default function SearchBar({ value, onChange }) {
  return (
    <div className="search-wrap">
      <input
        type="text"
        placeholder="약 이름을 입력하세요 (예: 판콜, 타이레놀)"
        value={value}
        onChange={(e) => onChange(e.target.value)}
        autoComplete="off"
      />
      <p className="narcotics-note">
        마약류(향정신성의약품 포함)는 검색 대상에 포함되지 않습니다.
      </p>
    </div>
  );
}
