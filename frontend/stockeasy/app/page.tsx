import { Button } from "intellio-common/components/ui/button"

export default function Home() {
  return (
    <main className="min-h-screen bg-gradient-to-b from-gray-900 via-gray-800 to-gray-900 text-white relative overflow-hidden">
      {/* 배경 장식 */}
      <div className="absolute inset-0 overflow-hidden">
        <div className="absolute -inset-[10px] bg-gradient-to-r from-emerald-500/20 via-green-500/20 to-teal-500/20 blur-3xl opacity-30 animate-pulse"></div>
      </div>

      {/* 메인 콘텐츠 */}
      <div className="container mx-auto px-4 py-20 relative z-10">
        <div className="max-w-4xl mx-auto text-center space-y-8">
          {/* 로고 및 타이틀 */}
          <div className="animate-float space-y-6">
            <div className="flex justify-center mb-8">
              <div className="relative">
                <div className="absolute inset-0 bg-gradient-to-r from-emerald-500 to-green-500 blur-xl opacity-50 animate-pulse rounded-full"></div>
                <svg className="w-24 h-24 text-emerald-400 relative" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5}
                    d="M13 7h8m0 0v8m0-8l-8 8-4-4-6 6" />
                </svg>
              </div>
            </div>
            <h1 className="text-7xl font-bold gradient-text tracking-tight">
              StockEasy
            </h1>
            <p className="text-3xl text-gray-300 font-light">
              Intellio Stock & Financial Tools
            </p>
          </div>

          {/* 설명 텍스트 */}
          <div className="mt-12 space-y-6">
            <p className="text-2xl text-gray-300 leading-relaxed">
              혁신적인 AI 기술로 구동되는 차세대 주식 분석 플랫폼이 곧 여러분을 찾아갑니다.
              <br />
              방대한 금융 데이터를 실시간으로 분석하여 더 스마트한 투자 결정을 도와드립니다.
            </p>
          </div>

          {/* 주요 기능 */}
          <div className="grid md:grid-cols-3 gap-8 mt-16">
            {[
              {
                icon: (
                  <svg className="w-10 h-10" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5}
                      d="M9.75 17L9 20l-1 1h8l-1-1-.75-3M3 13h18M5 17h14a2 2 0 002-2V5a2 2 0 00-2-2H5a2 2 0 00-2 2v10a2 2 0 002 2z" />
                  </svg>
                ),
                title: "실시간 AI 분석",
                description: "최신 AI 기술로 실시간 시장 동향을 분석하고 예측합니다"
              },
              {
                icon: (
                  <svg className="w-10 h-10" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5}
                      d="M11 3.055A9.001 9.001 0 1020.945 13H11V3.055z" />
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5}
                      d="M20.488 9H15V3.512A9.025 9.025 0 0120.488 9z" />
                  </svg>
                ),
                title: "포트폴리오 최적화",
                description: "개인화된 포트폴리오 분석으로 최적의 자산 배분을 제안합니다"
              },
              {
                icon: (
                  <svg className="w-10 h-10" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5}
                      d="M9 5H7a2 2 0 00-2 2v12a2 2 0 002 2h10a2 2 0 002-2V7a2 2 0 00-2-2h-2M9 5a2 2 0 002 2h2a2 2 0 002-2M9 5a2 2 0 012-2h2a2 2 0 012 2" />
                  </svg>
                ),
                title: "리스크 관리",
                description: "고도화된 리스크 분석으로 안정적인 투자를 지원합니다"
              }
            ].map((feature, index) => (
              <div key={index} 
                   className="p-8 rounded-2xl bg-gray-800/40 backdrop-blur-lg 
                            hover:bg-gray-700/40 transition-all duration-300
                            border border-gray-700/50 group">
                <div className="text-emerald-400 mb-6 transform group-hover:scale-110 transition-transform duration-300">
                  {feature.icon}
                </div>
                <h3 className="text-2xl font-semibold mb-3">{feature.title}</h3>
                <p className="text-gray-400 text-lg">{feature.description}</p>
              </div>
            ))}
          </div>

          {/* 하단 CTA */}
          <div className="mt-24 space-y-12">
            {/* 리스크 관리 문구 */}
            <p className="text-3xl text-gray-300 font-light">
              고도화된 리스크 분석으로 안정적인 투자를 지원합니다
            </p>
            
            {/* Coming Soon 버튼 */}
            <div className="inline-block scale-125 transform hover:scale-130 transition-transform duration-300">
              <Button
                size="lg"
                className="relative group px-16 py-8 text-3xl font-semibold tracking-wide
                           bg-gradient-to-r from-emerald-500 to-green-500 text-white
                           hover:from-emerald-600 hover:to-green-600
                           shadow-lg hover:shadow-emerald-500/50"
              >
                <span className="relative z-10">Coming Soon</span>
                <div className="absolute inset-0 -z-10 bg-gradient-to-r from-emerald-600/50 to-green-600/50 
                              blur-xl opacity-75 group-hover:opacity-100 transition-all duration-300 rounded-xl">
                </div>
              </Button>
            </div>
          </div>
        </div>
      </div>
    </main>
  )
}
