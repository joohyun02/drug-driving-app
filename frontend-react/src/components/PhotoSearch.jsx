import { useRef, useState } from 'react';
import { extractProductNameFromImage } from '../api';

export default function PhotoSearch({ onExtracted }) {
  const inputRef = useRef(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);

  async function handleFileChange(e) {
    const file = e.target.files && e.target.files[0];
    e.target.value = ''; // 같은 파일을 다시 선택해도 onChange가 발생하도록 초기화
    if (!file) return;

    setLoading(true);
    setError(null);
    try {
      const data = await extractProductNameFromImage(file);
      onExtracted(data.extracted_name);
    } catch (err) {
      setError(String(err.message || err));
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="photo-search">
      <button
        type="button"
        className="photo-search-btn"
        onClick={() => inputRef.current && inputRef.current.click()}
        disabled={loading}
      >
        {loading ? '인식 중...' : '📷 사진으로 검색'}
      </button>
      <input
        ref={inputRef}
        type="file"
        accept="image/*"
        capture="environment"
        style={{ display: 'none' }}
        onChange={handleFileChange}
      />
      {error && <p className="error-box" style={{ marginTop: 8 }}>{error}</p>}
    </div>
  );
}
