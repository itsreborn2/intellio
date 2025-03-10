'use client'

import { Suspense } from 'react'

// 컨텐츠 컴포넌트
function BottomRightArea1Content() {
  return (
    <div className="bottom-right-area-1 bottom-area">
      {/* 하단 우측 영역 1 컨텐츠 */}
      <div className="p-2 h-full overflow-auto border-t border-l border-white/40">
        {/* 임시 데이터: 산업리포트 요약 내용 */}
        <div className="mb-2">
          <h3 className="text-sm font-bold text-gray-700 mb-1">산업리포트 요약</h3>
          <div className="text-xs text-gray-600">
            <p className="mb-1">
              반도체 산업은 2025년 글로벌 AI 수요 확대로 메모리 시장의 강세가 예상됩니다. 
              특히 데이터센터용 HBM 및 서버 DRAM의 공급 부족 현상이 두드러질 것으로 전망되며, 
              이는 메모리 가격 상승으로 이어질 것입니다. 파운드리 시장에서는 선단 공정 경쟁이 
              심화되는 가운데, 삼성전자와 TSMC의 3나노 이하 공정 경쟁이 본격화될 전망입니다.
            </p>
            <p className="mb-1">
              국내 반도체 산업은 메모리와 비메모리 부문 모두에서 경쟁력 강화가 진행 중입니다. 
              정부의 K-반도체 벨트 전략에 따른 투자 지원과 세제 혜택이 확대되고 있으며, 
              인력 양성과 기술 개발을 위한 산학연 협력이 강화되고 있습니다. 특히 시스템 반도체와 
              파운드리 분야의 경쟁력 확보를 위한 대규모 투자가 이어질 것으로 예상됩니다.
            </p>
            <p>
              글로벌 공급망 재편 과정에서 한국 반도체 산업의 위상은 더욱 중요해질 것으로 
              분석됩니다. 미국과 중국 간 기술 패권 경쟁이 심화되는 상황에서 다변화된 공급망 
              구축과 기술 자립도 제고가 산업 경쟁력의 핵심 요소로 부각되고 있습니다. 
              장기적으로는 AI, 자율주행, 바이오 등 신성장 분야와의 융합이 반도체 산업의 
              새로운 성장 동력이 될 것입니다.
            </p>
          </div>
        </div>
      </div>
    </div>
  )
}

// 메인 컴포넌트
export default function BottomRightArea1() {
  return (
    <Suspense fallback={<div className="bottom-right-area-1 bottom-area animate-pulse">
      <div className="h-full bg-gray-200 rounded"></div>
    </div>}>
      <BottomRightArea1Content />
    </Suspense>
  )
}