# 약 체크 - 프런트엔드 (React + Vite)

기존 `index.html` 프로토타입과 기능은 동일합니다 (검색 → 목록 → 상세, 등급 배지,
한약재 복합제 안내, 마약류 제외 안내, 하단 면책문구 + 법적근거 패널).

## 폴더 구조

```
drug-driving-app/
├── backend/          ← 기존 main.py (변경 없음)
├── data/
└── frontend-react/   ← 이 폴더를 여기에 놓으면 됩니다
```

## 로컬 실행

1. `npm install`
2. `.env.example`을 복사해서 `.env` 파일 생성 (같은 폴더, 내용은 기본값 그대로 둬도 됨)
3. backend 폴더에서 `uvicorn main:app --reload` 먼저 켜두기
4. `npm run dev`
5. 터미널에 뜨는 주소(보통 `http://localhost:5173`)를 브라우저에서 열기

## 나중에 배포할 때

- **프런트엔드**: 이 폴더를 Vercel 프로젝트로 연결. Vercel 환경변수에
  `VITE_API_BASE` = 배포된 백엔드 주소로 설정 (예: `https://drug-check-api.onrender.com`)
- **백엔드**: `backend/main.py`를 Render나 Railway에 배포
  - CORS는 이미 `allow_origins=["*"]`라 프런트엔드 도메인이 바뀌어도 당장은 동작하지만,
    실제로 서비스를 공개할 땐 프런트엔드 도메인만 허용하도록 좁히는 걸 권장합니다
  - SQLite(`drug_driving.db`)를 그대로 배포 서버에 올려서 씁니다 (읽기 전용 용도라 문제 없음)

## 기존 `index.html`과의 차이

- 기능/디자인은 동일하고, 컴포넌트 단위(`SearchBar`, `ResultList`, `DetailView`,
  `LegalDisclaimer`)로 나뉜 것과 API 주소를 `.env`로 관리한다는 점만 다릅니다
- `index.html` 파일은 이제 안 써도 되지만, 지우지 않고 로컬 빠른 테스트용으로 남겨둬도 무방합니다
