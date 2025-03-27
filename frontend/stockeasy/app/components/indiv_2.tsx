'use client';

import React, { useState, useEffect } from 'react';

/**
 * Indiv2 컴포넌트 - 상단 영역의 두 번째 컴포넌트(25%)
 * 최근 미디어 언급 요약 정보를 표시합니다.
 */
export default function Indiv2() {
  // 선택된 종목 코드 (실제로는 부모 컴포넌트에서 props로 받거나 상태 관리 라이브러리 사용)
  const [selectedStock, setSelectedStock] = useState<{ stockCode: string; stockName: string } | null>(null);
  const [mediaMentions, setMediaMentions] = useState<Array<{
    source: string;
    title: string;
    url: string;
    snippet: string;
    summary: string;
    date: string;
  }>>([]);
  const [isLoading, setIsLoading] = useState<boolean>(false);

  // 예시 데이터 로드 (실제로는 API 호출)
  useEffect(() => {
    // 실제 구현에서는 선택된 종목이 변경될 때 API 호출
    const loadMediaMentions = () => {
      setIsLoading(true);
      
      // 예시 데이터 (실제로는 API 호출 결과)
      setTimeout(() => {
        setMediaMentions([
          {
            source: '네이버 블로그',
            title: '삼성전자(005930) 실적 전망과 투자 포인트',
            url: 'https://blog.naver.com/example/12345',
            snippet: '삼성전자의 메모리 반도체 사업이 회복세를 보이고 있으며, 특히 AI 관련 HBM 수요 증가로 인해 하반기 실적 개선이 기대됩니다...',
            summary: '메모리 반도체 사업 회복세, AI 관련 HBM 수요 증가로 하반기 실적 개선 전망',
            date: '2025-03-25'
          },
          {
            source: '경제 뉴스',
            title: '삼성전자, 신규 파운드리 공장 투자 발표',
            url: 'https://example-news.com/article/67890',
            snippet: '삼성전자가 미국 텍사스주에 신규 파운드리 공장 건설을 위한 대규모 투자를 발표했습니다. 이번 투자는 글로벌 반도체 공급망 강화와...',
            summary: '미국 텍사스주에 신규 파운드리 공장 건설 투자 발표, 글로벌 반도체 공급망 강화 목적',
            date: '2025-03-20'
          },
          {
            source: '유튜브',
            title: '삼성전자 주가 분석 및 전망',
            url: 'https://youtube.com/watch?v=example',
            snippet: '이번 영상에서는 삼성전자의 최근 주가 흐름과 기술적 분석을 통한 향후 전망을 다루고 있습니다. 특히 반도체 슈퍼사이클과 관련된...',
            summary: '반도체 슈퍼사이클 진입 가능성, 기술적 분석 기반 주가 상승 전망',
            date: '2025-03-18'
          }
        ]);
        setIsLoading(false);
      }, 500);
    };
    
    loadMediaMentions();
  }, []);

  return (
    <div className="w-full h-full p-4 pb-0 bg-white rounded-md shadow-md">
      <div style={{ fontSize: 'clamp(0.75rem, 0.9vw, 0.9rem)', marginBottom: '8px' }}>최근 미디어 언급 요약</div>
      <div className="border border-gray-200 rounded-md bg-white h-[calc(100%-2rem)] mb-2 overflow-auto">
        {isLoading ? (
          <div className="flex justify-center items-center h-full">
            <p>데이터를 불러오는 중...</p>
          </div>
        ) : (
          <div className="space-y-3 p-3">
            {mediaMentions.map((mention, index) => (
              <div key={index} className="border border-gray-200 rounded-md p-3 hover:bg-gray-50">
                <div className="flex justify-between items-start">
                  <span className="text-xs px-2 py-0.5 bg-blue-100 text-blue-800 rounded">{mention.source}</span>
                  <span className="text-xs text-gray-500">{mention.date}</span>
                </div>
                <h3 className="font-medium text-sm mt-1 mb-1">
                  <a href={mention.url} target="_blank" rel="noopener noreferrer" className="text-blue-600 hover:underline">
                    {mention.title}
                  </a>
                </h3>
                <p className="text-xs text-gray-700 mb-1 line-clamp-2">{mention.snippet}</p>
                <div className="mt-1 bg-gray-50 p-2 rounded border-l-2 border-blue-400">
                  <p className="text-xs font-medium">요약: {mention.summary}</p>
                </div>
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}
