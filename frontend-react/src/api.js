// FastAPI 백엔드 주소. .env 파일의 VITE_API_BASE 값을 읽습니다.
// .env가 없으면 로컬 기본값(127.0.0.1:8000)을 사용합니다.
export const API_BASE = import.meta.env.VITE_API_BASE || 'http://127.0.0.1:8000';

export async function searchProducts(name) {
  const res = await fetch(`${API_BASE}/search?name=${encodeURIComponent(name)}`);
  if (!res.ok) throw new Error('서버 응답 오류 (status ' + res.status + ')');
  return res.json();
}

export async function getProductDetail(itemSeq) {
  const res = await fetch(`${API_BASE}/product/${encodeURIComponent(itemSeq)}`);
  if (!res.ok) throw new Error('서버 응답 오류 (status ' + res.status + ')');
  return res.json();
}
