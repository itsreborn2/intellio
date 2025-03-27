'use client';

import React, { useState, useEffect } from 'react';

/**
 * Indiv3 컴포넌트 - 상단 영역의 세 번째 컴포넌트(25%)
 * 공시요약 정보를 표시합니다.
 */
export default function Indiv3() {
  // 선택된 종목 코드 (실제로는 부모 컴포넌트에서 props로 받거나 상태 관리 라이브러리 사용)
  const [selectedStock, setSelectedStock] = useState<{ stockCode: string; stockName: string } | null>(null);
  const [disclosures, setDisclosures] = useState<Array<{
    title: string;
    date: string;
    summary: string;
    url: string;
  }>>([]);
  const [isLoading, setIsLoading] = useState<boolean>(false);

  // 예시 데이터 로드 (실제로는 API 호출)
  useEffect(() => {
    // 실제 구현에서는 선택된 종목이 변경될 때 API 호출
    const loadDisclosures = () => {
      setIsLoading(true);
      
      // 예시 데이터 (실제로는 API 호출 결과)
      setTimeout(() => {
        setDisclosures([
          {
            title: "유상증자 결정",
            date: "2025-03-20",
            summary: "주주배정 후 실권주 일반공모 방식, 750억원 규모",
            url: "https://dart.fss.or.kr/example/12345"
          },
          {
            title: "주요 사업 투자 결정",
            date: "2025-03-15",
            summary: "미국 텍사스 반도체 공장 신설, 1조 5천억원 투자",
            url: "https://dart.fss.or.kr/example/23456"
          },
          {
            title: "분기보고서 공시",
            date: "2025-03-10",
            summary: "1분기 매출 8,500억원(+15%), 영업이익 1,200억원(+20%)",
            url: "https://dart.fss.or.kr/example/34567"
          },
          {
            title: "자기주식 취득 결정",
            date: "2025-03-05",
            summary: "500억원 규모, 보통주 100만주 취득 예정",
            url: "https://dart.fss.or.kr/example/45678"
          },
          {
            title: "타법인 주식 취득",
            date: "2025-03-01",
            summary: "AI 반도체 스타트업 지분 30% 인수, 300억원",
            url: "https://dart.fss.or.kr/example/56789"
          }
        ]);
        setIsLoading(false);
      }, 500);
    };
    
    loadDisclosures();
  }, []);

  return (
    <div className="w-full h-full p-4 pb-0 bg-white rounded-md shadow-md">
      <div style={{ fontSize: 'clamp(0.75rem, 0.9vw, 0.9rem)', marginBottom: '8px' }}>공시 요약</div>
      <div className="border border-gray-200 rounded-md bg-white h-[calc(100%-2rem)] mb-2 overflow-auto">
        {isLoading ? (
          <div className="flex justify-center items-center h-full">
            <p>데이터를 불러오는 중...</p>
          </div>
        ) : (
          <div className="space-y-3 p-3">
            {disclosures.map((disclosure, index) => (
              <div key={index} className="border border-gray-200 rounded-md p-2 hover:bg-gray-50">
                <div className="flex justify-between items-start">
                  <h3 className="font-medium text-xs">
                    <a href={disclosure.url} target="_blank" rel="noopener noreferrer" className="text-blue-600 hover:underline">
                      {disclosure.title}
                    </a>
                  </h3>
                  <span className="text-xs text-gray-500">{disclosure.date}</span>
                </div>
                <p className="text-xs text-gray-700 mt-1">{disclosure.summary}</p>
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}
