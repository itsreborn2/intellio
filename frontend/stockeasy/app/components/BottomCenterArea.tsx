'use client'

import { Suspense } from 'react'

// 컨텐츠 컴포넌트
function BottomCenterAreaContent() {
  return (
    <div className="bottom-center-area bottom-area">
      {/* 하단 중앙 영역 컨텐츠 */}
      <div className="p-2 h-full overflow-auto border-t border-l border-white/40">
        {/* 임시 데이터: 정기보고서 요약 내용 */}
        <div className="mb-2">
          <h3 className="text-sm font-bold text-gray-700 mb-1">정기보고서 요약</h3>
          <div className="text-xs text-gray-600">
            <p className="mb-1">
              삼성전자의 2024년 사업보고서에 따르면, 전년 대비 매출액은 124조 7,500억원으로 7.1% 증가했으며 
              영업이익은 9조 2,100억원으로 흑자전환에 성공했습니다. 특히 시스템 반도체와 파운드리 부문에서 
              경쟁력 강화를 위한 투자가 지속되었으며, AI 반도체 시장 선점을 위한 R&D 투자가 크게 확대되었습니다. 
              자산 규모는 전년 대비 5.2% 증가한 457조원으로 역대 최대 수준을 기록했습니다.
            </p>
            <p className="mb-1">
              주요 사업 위험 요소로는 글로벌 경쟁 심화, 기술 변화 가속화, 무역 분쟁 및 보호무역주의 강화가 
              언급되었습니다. 이에 대응하기 위해 첨단 공정 기술 확보와 성장 시장인 AI, 자율주행, 데이터센터용 
              반도체 개발에 주력하고 있습니다. 향후 전망으로는 반도체 사업의 수익성 회복과 함께 새로운 
              성장 동력 확보를 위한 투자 확대가 예상됩니다.
            </p>
            <p>
              주주환원 정책으로는 2023-2025년까지 총 배당금의 점진적 확대와 자사주 매입을 
              통한 주주가치 제고를 약속했습니다. ESG 측면에서도 탄소중립 달성을 위한 재생에너지 
              사용 확대와 환경 친화적 생산 시스템 구축을 추진 중입니다.
            </p>
          </div>
        </div>
      </div>
    </div>
  )
}

// 메인 컴포넌트
export default function BottomCenterArea() {
  return (
    <Suspense fallback={<div className="bottom-center-area bottom-area animate-pulse">
      <div className="h-full bg-gray-200 rounded"></div>
    </div>}>
      <BottomCenterAreaContent />
    </Suspense>
  )
}