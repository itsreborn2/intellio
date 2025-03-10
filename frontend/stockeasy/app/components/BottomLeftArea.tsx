'use client'

import { Suspense } from 'react'

// 컨텐츠 컴포넌트
function BottomLeftAreaContent() {
  return (
    <div className="bottom-left-area bottom-area">
      {/* 하단 좌측 영역 컨텐츠 */}
      <div className="p-2 h-full overflow-auto border-t border-l border-white/40">
        {/* 임시 데이터: 기업리포트 요약 내용 */}
        <div className="mb-2">
          <h3 className="text-sm font-bold text-gray-700 mb-1">기업리포트 요약</h3>
          <div className="text-xs text-gray-600">
            <p className="mb-1">
              삼성전자의 2025년 1분기 실적은 전년 동기 대비 매출액 12% 증가, 영업이익 28% 성장으로 
              시장 예상치를 상회했습니다. 특히 메모리 반도체 부문에서 수익성이 크게 개선되었으며, 
              AI 관련 HBM(High Bandwidth Memory) 수요 증가로 인한 ASP 상승이 주요 요인으로 분석됩니다. 
              향후 전망으로는 하반기 AI 수요와 함께 서버 및 모바일 시장 회복으로 메모리 가격 상승이 
              지속될 것으로 예상됩니다.
            </p>
            <p>
              통신장비 및 디스플레이 부문도 5G 인프라 투자 확대와 프리미엄 OLED 패널 수요 증가로 
              실적 개선이 기대됩니다. 회사는 첨단 공정 투자를 지속하며 기술 경쟁력 확보에 주력하고 있으며, 
              주주환원 정책 강화로 배당 확대가 예상됩니다. 목표주가는 90,000원으로 상향 조정되었습니다.
            </p>
          </div>
        </div>
      </div>
    </div>
  )
}

// 메인 컴포넌트
export default function BottomLeftArea() {
  return (
    <Suspense fallback={<div className="bottom-left-area bottom-area animate-pulse">
      <div className="h-full bg-gray-200 rounded"></div>
    </div>}>
      <BottomLeftAreaContent />
    </Suspense>
  )
}