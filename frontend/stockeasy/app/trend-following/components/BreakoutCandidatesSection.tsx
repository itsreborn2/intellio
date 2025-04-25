'use client'
// 돌파 종목 후보군 섹션 (CSV 연동)
import { useEffect, useState } from 'react';

export default function BreakoutCandidatesSection() {
  // CSV에서 불러온 후보군 데이터 상태
  const [candidates, setCandidates] = useState<string[]>([]);

  useEffect(() => {
    async function fetchCandidates() {
      try {
        const response = await fetch('/requestfile/trend-following/trend-following.csv', { cache: 'no-store' });
        if (!response.ok) return;
        const text = await response.text();
        const lines = text.split(/\r?\n/).map(line => line.trim()).filter(Boolean);
        // 첫 줄은 컬럼명, 이후가 데이터
        setCandidates(lines.slice(1));
      } catch (e) {
        setCandidates([]);
      }
    }
    fetchCandidates();
  }, []);

  return (
    <section>
      {/* 제목 및 여백: 18px, 상단 여백 없음, 하단만 mb-4 */}
      <div className="font-semibold text-gray-700 mb-4" style={{ fontSize: '18px' }}>돌파 종목 후보군</div>
      {/* 본문 컨텐츠: 14px(반응형), CSV에서 동적 렌더링 */}
      <ul className="text-[14px] md:text-[14px] text-gray-700 space-y-1">
        {candidates.length === 0 ? (
          <li>데이터 없음</li>
        ) : (
          candidates.map((item, idx) => (
            <li key={idx}>{item}</li>
          ))
        )}
      </ul>
    </section>
  );
}
