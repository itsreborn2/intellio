'use client'

import { Suspense } from 'react'

// 컨텐츠 컴포넌트
function TelegramSummaryAreaContent() {
  return (
    <div className="telegram-summary-area">
      {/* 텔레그램 요약 영역 컨텐츠 */}
      <div className="p-2 h-full overflow-auto border-t border-l border-white/40">
        {/* 임시 데이터: 텔레그램 채널의 주식 관련 요약 내용 */}
        <div className="mb-2">
          <h3 className="text-sm font-bold text-gray-700 mb-1">텔레그램 주식 채널 요약</h3>
          <div className="text-xs text-gray-600">
            <p className="mb-1">
              삼성전자(005930)에 대한 최근 텔레그램 채널 의견은 반도체 수요 증가와 AI 서버 시장 확대로 
              하반기 실적 개선 전망이 긍정적입니다. 특히 HBM 메모리와 파운드리 사업 확장이 주가 상승 
              동력으로 작용할 것으로 보입니다. 다수의 투자자들은 현재 주가가 저평가되어 있다고 판단하며 
              매수 의견을 제시하고 있습니다. 최근 미국 수출 규제 완화 소식도 호재로 작용하고 있습니다.
            </p>
            <p>
              반면 자동차와 관련하여 현대차와 기아의 전기차 전환 속도가 예상보다 빠르게 진행되어 
              올해 생산량 목표 상향 조정이 예상된다는 의견이 다수입니다. 특히 현대차의 아이오닉 시리즈와 
              기아의 EV 시리즈의 판매 호조가 실적에 긍정적 영향을 줄 것으로 전망됩니다.
            </p>
          </div>
        </div>
      </div>
    </div>
  )
}

// 메인 컴포넌트
export default function TelegramSummaryArea() {
  return (
    <Suspense fallback={<div className="telegram-summary-area animate-pulse">
      <div className="h-full bg-gray-200 rounded"></div>
    </div>}>
      <TelegramSummaryAreaContent />
    </Suspense>
  )
}