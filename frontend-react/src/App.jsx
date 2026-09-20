import { useState, useEffect, useRef } from 'react';
import SearchBar from './components/SearchBar';
import ResultList from './components/ResultList';
import DetailView from './components/DetailView';
import LegalDisclaimer from './components/LegalDisclaimer';
import { searchProducts, getProductDetail } from './api';

export default function App() {
  const [query, setQuery] = useState('');
  const [results, setResults] = useState(null);
  const [searchLoading, setSearchLoading] = useState(false);
  const [searchError, setSearchError] = useState(null);

  const [detail, setDetail] = useState(null);
  const [detailLoading, setDetailLoading] = useState(false);
  const [detailError, setDetailError] = useState(null);

  const debounceRef = useRef(null);

  useEffect(() => {
    clearTimeout(debounceRef.current);
    setDetail(null);
    setDetailError(null);

    const q = query.trim();
    if (!q) {
      setResults(null);
      return;
    }
    debounceRef.current = setTimeout(() => runSearch(q), 300);
    return () => clearTimeout(debounceRef.current);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [query]);

  async function runSearch(q) {
    setSearchLoading(true);
    setSearchError(null);
    try {
      const data = await searchProducts(q);
      setResults(data.results);
    } catch (err) {
      setSearchError(String(err.message || err));
      setResults(null);
    } finally {
      setSearchLoading(false);
    }
  }

  async function handleSelect(itemSeq) {
    setDetailLoading(true);
    setDetailError(null);
    try {
      const data = await getProductDetail(itemSeq);
      setDetail(data);
    } catch (err) {
      setDetailError(String(err.message || err));
      setDetail(null);
    } finally {
      setDetailLoading(false);
    }
  }

  return (
    <div className="app">
      <header>
        <h1>약 체크</h1>
        <p>약 이름으로 운전 시 주의사항을 확인해보세요</p>
      </header>

      <SearchBar value={query} onChange={setQuery} />
      <ResultList
        results={results}
        loading={searchLoading}
        error={searchError}
        onSelect={handleSelect}
      />
      <DetailView detail={detail} loading={detailLoading} error={detailError} />

      <LegalDisclaimer />
    </div>
  );
}
