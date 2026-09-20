import { useState } from 'react';

export default function LegalDisclaimer() {
  const [open, setOpen] = useState(false);

  return (
    <footer className="disclaimer">
      <p>
        이 서비스가 제공하는 등급 및 경고문구는 참고용 정보이며 공식 의학적 조언이나 법적
        판단이 아닙니다. 등급은 대한약사회 참고자료를 기반으로 하며 공식 가이드라인이
        아닙니다. 실제 운전 가능 여부는 복용 후 본인의 상태와 관련 법령을 기준으로
        판단되므로, 필요 시 의사·약사와 상담하시기 바랍니다.
      </p>
      <button id="legalToggle" onClick={() => setOpen((v) => !v)}>
        {open ? '법적 근거 접기' : '법적 근거 자세히 보기'}
      </button>
      {open && (
        <div className="legal-panel">
          <p>
            도로교통법 제45조는 음주 상태 외에도 과로·질병·약물 등의 영향으로 정상적인
            운전이 어려운 상태에서 운전하는 것을 금지하고 있습니다. 즉 처벌 여부는 복용한
            약의 종류가 아니라, 복용 후 실제 운전자의 상태를 기준으로 판단됩니다.
          </p>
          <p>
            2026년 4월 2일 시행된 개정 도로교통법에 따라 약물운전 처벌 기준이 기존 3년
            이하 징역 또는 1천만 원 이하 벌금에서 5년 이하 징역 또는 2천만 원 이하 벌금으로
            강화되었고, 측정 불응죄도 신설되었습니다.
          </p>
          <p className="cite">
            출처: 국가법령정보센터 ·{' '}
            <a
              href="https://www.law.go.kr/%EB%B2%95%EB%A0%B9/%EB%8F%84%EB%A1%9C%EA%B5%90%ED%86%B5%EB%B2%95"
              target="_blank"
              rel="noopener noreferrer"
            >
              도로교통법 전문 보기
            </a>{' '}
            (접속 후 제45조 검색)
          </p>
          <p className="cite">
            출처: 대한민국 정책브리핑, "도로교통법령, 2026년에 이렇게 달라집니다" ·{' '}
            <a
              href="https://www.korea.kr/news/policyNewsView.do?newsId=148957500"
              target="_blank"
              rel="noopener noreferrer"
            >
              기사 보기
            </a>
          </p>
        </div>
      )}
    </footer>
  );
}
