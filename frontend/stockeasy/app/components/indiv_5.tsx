'use client';

import React, { useState, useEffect } from 'react';

/**
 * Indiv5 컴포넌트 - 하단 영역의 두 번째 컴포넌트(50%)
 * 삼성전자 관련 산업 리포트 요약 정보를 표시합니다.
 */
export default function Indiv5() {
  // 선택된 종목 코드 (실제로는 부모 컴포넌트에서 props로 받거나 상태 관리 라이브러리 사용)
  const [selectedStock, setSelectedStock] = useState<{ stockCode: string; stockName: string } | null>(null);
  const [industryReports, setIndustryReports] = useState<Array<{
    industry: string;
    date: string;
    title: string;
    firm: string;
    summary: string;
    keyTrends: string[];
    impact: string;
  }>>([]);
  const [isLoading, setIsLoading] = useState<boolean>(false);

  // 예시 데이터 로드 (실제로는 API 호출)
  useEffect(() => {
    // 실제 구현에서는 선택된 종목이 변경될 때 API 호출
    const loadIndustryReports = () => {
      setIsLoading(true);
      
      // 예시 데이터 (실제로는 API 호출 결과)
      setTimeout(() => {
        setIndustryReports([
          {
            industry: "반도체",
            date: "2025-03-24",
            title: "글로벌 반도체 산업 전망: AI 수요 급증으로 인한 시장 변화",
            firm: "하나증권",
            summary: "AI 수요 증가로 메모리 및 파운드리 시장 성장세 가속화. 특히 HBM과 AI 반도체 수요 급증으로 인한 공급 부족 현상 지속 전망.",
            keyTrends: [
              "HBM 수요 증가로 인한 가격 상승세 지속",
              "파운드리 시장 경쟁 심화로 기술 격차 중요성 증가",
              "AI 반도체 시장 연평균 45% 성장 전망"
            ],
            impact: "삼성전자에 긍정적. HBM 생산 확대와 파운드리 경쟁력 강화로 수익성 개선 기대."
          },
          {
            industry: "스마트폰",
            date: "2025-03-22",
            title: "글로벌 스마트폰 시장: AI 기능 탑재로 교체 수요 증가 전망",
            firm: "KB증권",
            summary: "AI 기능이 탑재된 프리미엄 스마트폰 출시로 교체 수요 증가 예상. 특히 갤럭시 S26 시리즈의 AI 기능 강화로 시장 점유율 확대 기대.",
            keyTrends: [
              "AI 기능 탑재 스마트폰 수요 증가",
              "프리미엄 스마트폰 시장 성장세 지속",
              "중국 시장에서의 경쟁 심화"
            ],
            impact: "삼성전자의 스마트폰 사업 실적 개선 기대. 특히 AI 기능 강화로 ASP 상승 예상."
          },
          {
            industry: "디스플레이",
            date: "2025-03-20",
            title: "OLED 시장 전망: 프리미엄 TV 및 IT 기기 수요 증가",
            firm: "신한투자증권",
            summary: "프리미엄 TV 및 IT 기기용 OLED 패널 수요 증가 전망. 특히 QD-OLED 기술 적용 제품의 시장 확대로 삼성디스플레이 경쟁력 강화.",
            keyTrends: [
              "QD-OLED TV 패널 수요 증가",
              "IT 기기용 OLED 패널 적용 확대",
              "중소형 OLED 시장 경쟁 심화"
            ],
            impact: "삼성전자 계열사인 삼성디스플레이의 실적 개선으로 간접적 수혜 예상."
          },
          {
            industry: "가전",
            date: "2025-03-18",
            title: "프리미엄 가전 시장: AI 기반 스마트홈 생태계 확대",
            firm: "대신증권",
            summary: "AI 기반 스마트홈 생태계 확대로 프리미엄 가전 수요 증가 전망. 특히 에너지 효율성과 AI 연동 기능이 강화된 제품 선호도 상승.",
            keyTrends: [
              "AI 기반 스마트홈 생태계 확대",
              "에너지 효율성 높은 제품 수요 증가",
              "프리미엄 가전 시장 성장세 지속"
            ],
            impact: "삼성전자의 생활가전 사업 실적 개선 기대. 특히 스마트싱스 생태계 확대로 경쟁력 강화."
          }
        ]);
        setIsLoading(false);
      }, 500);
    };
    
    loadIndustryReports();
  }, []);

  return (
    <div className="w-full h-full p-4 pb-0 bg-white rounded-md shadow-md">
      <div style={{ fontSize: 'clamp(0.75rem, 0.9vw, 0.9rem)', marginBottom: '8px' }}>삼성전자 관련 산업 리포트 요약</div>
      <div className="border border-gray-200 rounded-md bg-white h-[calc(100%-2rem)] mb-2 overflow-auto">
        {isLoading ? (
          <div className="flex justify-center items-center h-full">
            <p>데이터를 불러오는 중...</p>
          </div>
        ) : (
          <div className="space-y-3 p-3">
            {industryReports.map((report, index) => (
              <div key={index} className="border border-gray-200 rounded-md p-3 hover:bg-gray-50">
                <div className="flex justify-between items-start mb-1">
                  <div className="flex items-center">
                    <span className="text-xs px-2 py-0.5 bg-purple-100 text-purple-800 rounded mr-2">{report.industry}</span>
                    <span className="text-xs px-2 py-0.5 bg-blue-100 text-blue-800 rounded">{report.firm}</span>
                  </div>
                  <span className="text-xs text-gray-500">{report.date}</span>
                </div>
                <h3 className="font-medium text-xs mb-1">{report.title}</h3>
                <p className="text-xs text-gray-700 mb-2">{report.summary}</p>
                <div className="bg-gray-50 p-2 rounded text-xs">
                  <p className="font-medium text-xs mb-1">주요 트렌드:</p>
                  <ul className="list-disc pl-4 space-y-0.5">
                    {report.keyTrends.map((trend, i) => (
                      <li key={i} className="text-xs">{trend}</li>
                    ))}
                  </ul>
                  <p className="font-medium text-xs mt-2 mb-1">삼성전자 영향:</p>
                  <p className="text-xs text-gray-700">{report.impact}</p>
                </div>
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}
