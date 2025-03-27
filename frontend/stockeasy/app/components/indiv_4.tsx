'use client';

import React, { useState, useEffect } from 'react';

/**
 * Indiv4 컴포넌트 - 하단 영역의 첫 번째 컴포넌트(50%)
 * 최근 발행 기업 리포트 요약 정보를 표시합니다.
 */
export default function Indiv4() {
  // 선택된 종목 코드 (실제로는 부모 컴포넌트에서 props로 받거나 상태 관리 라이브러리 사용)
  const [selectedStock, setSelectedStock] = useState<{ stockCode: string; stockName: string } | null>(null);
  const [reports, setReports] = useState<Array<{
    firm: string;
    date: string;
    title: string;
    targetPrice: string;
    opinion: string;
    summary: string;
    keyPoints: string[];
  }>>([]);
  const [isLoading, setIsLoading] = useState<boolean>(false);

  // 예시 데이터 로드 (실제로는 API 호출)
  useEffect(() => {
    // 실제 구현에서는 선택된 종목이 변경될 때 API 호출
    const loadReports = () => {
      setIsLoading(true);
      
      // 예시 데이터 (실제로는 API 호출 결과)
      setTimeout(() => {
        setReports([
          {
            firm: "미래에셋증권",
            date: "2025-03-25",
            title: "삼성전자: HBM 수요 증가로 메모리 사업 턴어라운드 전망",
            targetPrice: "100,000원",
            opinion: "매수",
            summary: "AI 서버용 HBM 수요 급증으로 메모리 가격 상승세 지속 예상. 파운드리 사업 경쟁력 강화로 시장점유율 확대 기대.",
            keyPoints: [
              "HBM 출하량 전년 대비 150% 증가 전망",
              "메모리 가격 상승으로 영업이익률 개선 가능성",
              "파운드리 사업 매출 성장세 가속화"
            ]
          },
          {
            firm: "한국투자증권",
            date: "2025-03-22",
            title: "삼성전자: 반도체 슈퍼사이클 진입 임박",
            targetPrice: "95,000원",
            opinion: "매수",
            summary: "AI 반도체 수요 증가와 공급 부족으로 메모리 가격 상승세 지속. 하반기 실적 개선 전망.",
            keyPoints: [
              "DRAM 가격 상승세 2분기부터 가속화 예상",
              "AI 관련 반도체 매출 비중 확대",
              "스마트폰 사업 안정적 수익성 유지"
            ]
          },
          {
            firm: "NH투자증권",
            date: "2025-03-20",
            title: "삼성전자: 메모리 업황 개선으로 실적 턴어라운드 기대",
            targetPrice: "92,000원",
            opinion: "매수",
            summary: "메모리 가격 상승과 수율 개선으로 수익성 회복 전망. 시스템반도체 사업 경쟁력 강화 중.",
            keyPoints: [
              "메모리 ASP 상승으로 영업이익 개선 전망",
              "GAA 공정 도입으로 파운드리 경쟁력 강화",
              "주주환원 정책 강화 가능성"
            ]
          },
          {
            firm: "삼성증권",
            date: "2025-03-18",
            title: "삼성전자: 반도체 업황 개선과 주주환원 정책 강화",
            targetPrice: "98,000원",
            opinion: "매수",
            summary: "메모리 가격 상승과 수요 증가로 실적 개선 전망. 배당 증가와 자사주 매입 등 주주환원 정책 강화 기대.",
            keyPoints: [
              "메모리 수급 개선으로 가격 상승세 지속",
              "AI 관련 반도체 투자 확대",
              "배당성향 상향 조정 가능성"
            ]
          }
        ]);
        setIsLoading(false);
      }, 500);
    };
    
    loadReports();
  }, []);

  return (
    <div className="w-full h-full p-4 pb-0 bg-white rounded-md shadow-md">
      <div style={{ fontSize: 'clamp(0.75rem, 0.9vw, 0.9rem)', marginBottom: '8px' }}>최근 발행 기업 리포트 요약</div>
      <div className="border border-gray-200 rounded-md bg-white h-[calc(100%-2rem)] mb-2 overflow-auto">
        {isLoading ? (
          <div className="flex justify-center items-center h-full">
            <p>데이터를 불러오는 중...</p>
          </div>
        ) : (
          <div className="space-y-3 p-3">
            {reports.map((report, index) => (
              <div key={index} className="border border-gray-200 rounded-md p-3 hover:bg-gray-50">
                <div className="flex justify-between items-start mb-1">
                  <div className="flex items-center">
                    <span className="text-xs px-2 py-0.5 bg-blue-100 text-blue-800 rounded mr-2">{report.firm}</span>
                    <span className="text-xs px-2 py-0.5 bg-green-100 text-green-800 rounded">{report.opinion}</span>
                  </div>
                  <span className="text-xs text-gray-500">{report.date}</span>
                </div>
                <h3 className="font-medium text-xs mb-1">{report.title}</h3>
                <div className="flex justify-between items-center mb-1">
                  <span className="text-xs text-gray-700">목표가: <span className="font-semibold">{report.targetPrice}</span></span>
                </div>
                <p className="text-xs text-gray-700 mb-2">{report.summary}</p>
                <div className="bg-gray-50 p-2 rounded text-xs">
                  <p className="font-medium text-xs mb-1">주요 포인트:</p>
                  <ul className="list-disc pl-4 space-y-0.5">
                    {report.keyPoints.map((point, i) => (
                      <li key={i} className="text-xs">{point}</li>
                    ))}
                  </ul>
                </div>
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}
