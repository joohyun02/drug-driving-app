// DB의 level 값은 상황에 따라 세 가지 형태로 올 수 있습니다:
//  - 순수 숫자 (0~3)               : DB를 정수로 고친 이후
//  - "Level 2" 같은 문자열         : 고치기 전 기본 형태
//  - "Level 0~1" 같은 범위 문자열  : 386 원본 자료에 범위로 기재된 성분
//    (예: 옥시메타졸린염산염, 자일로메타졸린염산염, 펙소페나딘염산염)
//
// parseLevel()은 이 세 가지를 모두 이해해서, 화면에 보여줄 라벨(label)과
// 여러 성분 중 "가장 주의가 필요한" 것을 고를 때만 쓰는 비교값(sortValue)을
// 함께 돌려줍니다. 범위값은 절대 하나의 숫자로 뭉개지 않고 "Level 0~1" 그대로
// 표시합니다 — sortValue는 색상/대표값 계산에만 쓰이고 화면 텍스트는 안 바꿉니다.
export function parseLevel(raw) {
  if (raw === null || raw === undefined) return null;

  if (typeof raw === 'number' && !Number.isNaN(raw)) {
    return { label: 'Level ' + raw, sortValue: raw };
  }

  const s = String(raw).trim();

  const rangeMatch = s.match(/(\d+)\s*~\s*(\d+)/);
  if (rangeMatch) {
    const hi = parseInt(rangeMatch[2], 10);
    return { label: `Level ${rangeMatch[1]}~${rangeMatch[2]}`, sortValue: hi };
  }

  const numMatch = s.match(/\d+/);
  if (numMatch) {
    const n = parseInt(numMatch[0], 10);
    return { label: 'Level ' + n, sortValue: n };
  }

  return null;
}

const LEVEL_COLORS = {
  0: { bg: '#e9edf3', text: '#4b5768' },
  1: { bg: '#fdf1c6', text: '#8a6d1a' },
  2: { bg: '#ffe6cc', text: '#b1560f' },
  3: { bg: '#fde2e2', text: '#b3261e' },
};
const NONE_STYLE = { bg: '#eef0f3', text: '#8b93a1', label: '확인된 성분 없음' };
const HERB_STYLE = { bg: '#e3edf7', text: '#2f5f8a', label: '한약재 복합제' };

// 배지 색상은 sortValue(범위면 상단값) 기준으로 고르고, 실제 표시 텍스트(label)는
// parseLevel이 만든 원본 그대로 씁니다.
// 예: "Level 0~1"은 Level 1과 같은 색으로 칠하되 글자는 "Level 0~1" 그대로 남습니다.
export function levelBadge(rawLevel) {
  const parsed = parseLevel(rawLevel);
  if (!parsed) return NONE_STYLE;
  const clamped = Math.max(0, Math.min(3, Math.round(parsed.sortValue)));
  const color = LEVEL_COLORS[clamped] || LEVEL_COLORS[3];
  return { bg: color.bg, text: color.text, label: parsed.label };
}

export function herbBadge() {
  return HERB_STYLE;
}

// ※ 이름 표기가 다른 유사 한약재 복합제가 더 있다면 이 배열에 추가하면 됩니다.
const HERBAL_COMPLEX_PATTERNS = ['우황청심원'];
export function isHerbalComplex(name) {
  if (!name) return false;
  return HERBAL_COMPLEX_PATTERNS.some((p) => name.includes(p));
}
