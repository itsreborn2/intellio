'use client'

import { Suspense } from 'react'

// 컨텐츠 컴포넌트
function BottomRightArea2Content() {
  return (
    <div className="bottom-right-area-2 bottom-area">
      {/* 하단 우측 영역 2 컨텐츠 */}
      <div className="p-2 h-full overflow-auto border-t border-l border-white/40">
        {/* 임시 데이터: 블로그 요약 내용 */}
        <div className="mb-2">
          <h3 className="text-sm font-bold text-gray-700 mb-1">블로그 요약</h3>
          <div className="text-xs text-gray-600">
            <div className="mb-2 pb-1 border-b border-gray-200">
              <div className="flex justify-between items-center mb-0.5">
                <span className="font-medium">주식고수-J</span>
                <span className="text-xs text-gray-500">2025.03.08</span>
              </div>
              <p className="font-medium mb-0.5">삼성전자, HBM 수요 급등으로 실적 반등 시작되나</p>
              <p>
                삼성전자의 HBM 사업 확대가 실적 턴어라운드의 핵심 포인트가 될 것으로 전망됩니다. 
                NVIDIA와의 협력 강화와 함께 2세대 HBM3E 양산이 계획대로 진행된다면 
                하반기 큰 폭의 실적 개선이 가능할 것입니다. 또한 업데이트된 파운드리 로드맵도 
                주가에 긍정적 요인으로 작용할 전망입니다.
              </p>
            </div>
            
            <div className="mb-2 pb-1 border-b border-gray-200">
              <div className="flex justify-between items-center mb-0.5">
                <span className="font-medium">투자의신</span>
                <span className="text-xs text-gray-500">2025.03.07</span>
              </div>
              <p className="font-medium mb-0.5">현대차, 전기차 판매량 예상치 상회할 듯</p>
              <p>
                현대차의 전기차 판매량이 올해 시장 예상치를 상회할 것으로 보입니다. 
                특히 아이오닉 5와 아이오닉 6의 북미 시장 판매가 호조를 보이고 있으며, 
                신규 모델 출시에 따른 라인업 확대도 기대됩니다. 배터리 기술 고도화와 
                충전 인프라 확대도 긍정적 요인입니다.
              </p>
            </div>
            
            <div>
              <div className="flex justify-between items-center mb-0.5">
                <span className="font-medium">테크애널리스트</span>
                <span className="text-xs text-gray-500">2025.03.05</span>
              </div>
              <p className="font-medium mb-0.5">AI 반도체 시장, 국내기업들 경쟁력은?</p>
              <p>
                글로벌 AI 반도체 시장이 급성장하는 가운데, 국내 기업들의 경쟁력 확보가 시급합니다. 
                삼성전자와 SK하이닉스가 HBM 시장에서 선전하고 있으나, AI 가속기와 같은 핵심 반도체 
                분야에서는 아직 격차가 존재합니다. 정부와 기업의 적극적인 투자와 기술 개발 노력이 
                필요한 시점입니다.
              </p>
            </div>
          </div>
        </div>
      </div>
    </div>
  )
}

// 메인 컴포넌트
export default function BottomRightArea2() {
  return (
    <Suspense fallback={<div className="bottom-right-area-2 bottom-area animate-pulse">
      <div className="h-full bg-gray-200 rounded"></div>
    </div>}>
      <BottomRightArea2Content />
    </Suspense>
  )
}