'use client';

import React from 'react';

/**
 * About 페이지 컴포넌트
 * 스탁이지 서비스에 대한 정보를 제공하는 페이지
 */
const AboutPage: React.FC = () => {
  return (
    <div className="flex-1 p-0 sm:p-2 md:p-4 overflow-auto w-full">
      {/* 메인 콘텐츠 영역 */}
      <div className="w-full max-w-[1280px] mx-auto">
        {/* 섹션 컨테이너 */}
        <div className="mb-2 md:mb-4">
          {/* 내부 컨테이너 */}
          <div className="bg-white rounded-md shadow p-2 md:p-4">
            {/* 콘텐츠 영역 */}
            <div className="bg-white rounded border border-gray-100 p-2 md:p-4 h-auto">
              {/* 제목 영역 */}
              <div className="font-semibold flex items-center mb-6">
                <h1 className="text-lg font-semibold" style={{ color: 'var(--primary-text-color, var(--primary-text-color-fallback))' }}>
                  About 스탁이지
                </h1>
              </div>
              
              {/* 스탁이지 소개 */}
              <div className="mb-6">
                <div className="font-semibold flex items-center mb-2">
                  <h2 className="text-sm md:text-base font-semibold" style={{ color: 'var(--primary-text-color, var(--primary-text-color-fallback))' }}>
                    스탁이지 소개
                  </h2>
                </div>
                <div className="px-2 py-2 bg-gray-50 rounded-md">
                  <p className="text-sm leading-relaxed">
                    스탁이지는 단순한 주식 정보 제공 서비스를 넘어, <strong>풍부한 실전 경험을 갖춘 전업 투자자들</strong>이 직접 개발한 혁신적인 투자 가이드 플랫폼입니다. 저희는 변동성이 큰 시장에서도 꾸준히 수익을 창출할 수 있는 핵심 전략으로, <strong>견고한 가치투자와 역동적인 추세추종을 정교하게 결합한 하이브리드 매매 방식</strong>을 제시합니다.<br/><br/>
                    스탁이지의 근본적인 목표는 명확합니다: <strong>투자 경험이나 지식 수준에 관계없이 누구나 명확한 원칙과 손절 규칙을 준수한다면 주식 시장에서 안정적인 수익을 경험할 수 있도록 실질적인 가이드를 제공</strong>하는 것입니다. 이를 위해 스탁이지는 복잡한 금융 데이터를 직관적으로 시각화하고, AI 기반의 객관적인 분석 정보를 제공하여 사용자가 시장을 더 깊이 이해하고 정보에 입각한 투자 결정을 내릴 수 있도록 지원합니다. RS 랭킹, 정밀 밸류에이션, 심층 추세추종, ETF/섹터 분석 등 스탁이지만의 차별화된 기능들은 이러한 철학을 바탕으로 제공됩니다.<br/><br/>
                    StockEasy는 기존의 복잡한 투자 분석 도구들과 달리, 직관적인 UI와 <strong>국내 최고 수준의 AI 기술력, 그리고 실제 각종 데이터를 기반으로 한 방대한 학습 데이터</strong>를 통해 구축된 독자적인 분석 모델을 자랑합니다. 이를 통해 누구나 쉽게 주식 시장의 본질을 이해하고 효과적인 투자 전략을 수립할 수 있도록 돕습니다.<br/><br/>
                    앞으로 스탁이지는 <strong>국내 최고의 AI 기반 추세추종 및 금융 데이터 딥 리서치 기업</strong>으로 자리매김하여, 모든 투자자가 더 스마트하고 성공적인 투자 여정을 이어갈 수 있도록 끊임없이 진화하고 혁신해 나갈 것입니다.
                  </p>
                  <p className="text-sm leading-relaxed mt-6">
                    스탁이지는 사용자 여러분의 소중한 목소리에 항상 귀 기울이고 있습니다.<br />
                    더 나은 서비스를 위한 제언이나 궁금하신 점이 있다면 언제든지 아래 이메일로 연락 주시기 바랍니다.
                  </p>
                  <p className="text-sm leading-relaxed mt-2">
                    <strong>문의:</strong> <a href="mailto:intellio.korea@gmail.com" className="text-blue-600 hover:underline">intellio.korea@gmail.com</a><br />
                    (주)인텔리오
                  </p>
                </div>
              </div>
              
              {/* 주요 기능 */}
              <div>
                <div className="font-semibold flex items-center mb-2">
                  <h2 className="text-sm md:text-base font-semibold" style={{ color: 'var(--primary-text-color, var(--primary-text-color-fallback))' }}>
                    주요 기능
                  </h2>
                </div>
                <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
                  <div className="bg-gray-50 rounded-md p-3">
                    <h4 className="font-medium text-xs md:text-sm mb-1" style={{ color: 'oklch(0.4 0.03 257.287)' }}>스탁 AI</h4>
                    <p className="text-sm leading-relaxed">
                      스탁이지의 핵심 엔진인 <strong>스탁 AI</strong>는 단순 정보 검색 도구를 넘어, 데이터에 기반한 정교하고 심층적인 투자 분석을 제공하는 당신의 지능형 파트너입니다.<br/><br/>
                      <strong>방대한 학습 데이터와 정교한 분석 에이전트:</strong><br/>
                      스탁 AI는 매일같이 발행되는 <strong>기업의 분기/반기/사업보고서, 주요사항보고서, 지분공시</strong>와 같은 정형 데이터는 물론, 국내외 <strong>산업별 심층 리포트, 경제 뉴스, 시장 분석 자료, 기술 동향 보고서</strong> 등 광범위한 비정형 데이터까지 실시간으로 수집합니다. 이렇게 축적된 방대한 정보는 <strong>다수의 고도화된 분석 에이전트(Analysis Agents)들에 의해 다각도로 정교하게 분석</strong>되어, 단순 키워드 검색으로는 파악하기 어려운 정보 간의 복잡한 연결고리와 숨겨진 맥락까지 명확하게 제시합니다.<br/><br/>
                      <strong>차세대 AI 분석 기술로 구현하는 깊이 있는 통찰력:</strong><br/>
                      일반적인 LLM(거대 언어 모델)이 제공하는 표면적인 정보 요약이나 단순 검색 결과 나열을 뛰어넘습니다. 스탁 AI는 최신 <strong>자연어 처리(NLP)</strong> 기술을 핵심으로 활용하여, 텍스트 이면에 숨겨진 <strong>기업의 사업 전략 변화, 시장 내 경쟁 강도, 신기술 도입에 따른 잠재적 리스크 및 성장 기회, 소비자 반응 및 평판 변화, 거시 경제 지표의 영향</strong> 등을 정밀하게 분석합니다. 이를 통해 투자자는 복잡하고 방대한 자료를 직접 분석하는 시간과 노력을 획기적으로 절감할 수 있습니다.<br/><br/>
                      <strong>신뢰할 수 있는 데이터 기반의 검증된 투자 인사이트:</strong><br/>
                      온라인에 산재한 출처 불명의 정보나 일반적인 의견이 아닌, <strong>실제 기업 활동 데이터, 공시 자료, 검증된 시장 분석 리포트를 기반</strong>으로 한 객관적이고 신뢰도 높은 분석 결과를 제공합니다. 기업의 펀더멘털 변화, 산업 내 경쟁 구도, 신성장 동력 발굴, ESG 경영 현황 등 투자 결정에 필요한 핵심 요소를 다각도로 조명하여, 피상적인 정보에 휘둘리지 않고 <strong>기업과 시장의 본질에 집중한 투자 판단</strong>을 내릴 수 있도록 강력하게 지원합니다.<br/><br/>
                      <strong>투자 결정의 질적 향상 및 새로운 기회 발굴:</strong><br/>
                      스탁 AI가 제공하는 깊이 있는 분석과 통찰력은 투자자가 남들보다 먼저 <strong>숨겨진 유망 투자 기회를 발굴</strong>하고, 예상치 못한 <strong>잠재적 위험 요인을 사전에 인지</strong>하며, 변동성이 큰 시장에서도 <strong>장기적인 관점에서 안정적이고 지속 가능한 포트폴리오를 구축</strong>하는 데 결정적인 도움을 줍니다. 스탁이지는 스탁 AI를 통해 모든 투자자가 정보의 비대칭성을 극복하고, 더 높은 수준의 데이터 기반 투자 전략을 구사할 수 있도록 최선을 다하고 있습니다.
                    </p>
                  </div>
                  <div className="bg-gray-50 rounded-md p-3">
                    <h4 className="font-medium text-xs md:text-sm mb-1" style={{ color: 'oklch(0.4 0.03 257.287)' }}>RS 랭킹</h4>
                    <p className="text-sm leading-relaxed">
                      RS 랭킹은 추세추종 전략의 핵심 지표인 RS(상대강도) 및 MTT(마크 미너비니 트렌드 템플릿) 충족 여부를 종목별로 명확하게 제시합니다. 이와 함께 RS 상위 21개 종목 및 MTT 조건을 만족하는 상위 21개 종목의 차트를 시각적으로 제공하여, 투자자가 시장 주도주를 빠르고 직관적으로 파악할 수 있도록 지원합니다.<br/><br/>
                      스탁이지의 RS 지표는 국내 시장 환경에 최적화된 독자적인 로직으로 정교하게 구성되었습니다. 단순 RS 값뿐만 아니라, RS 1개월, 3개월, 6개월 등 다양한 기간별 RS 수치를 함께 제공하여, 투자자의 다양한 투자 기간 및 전략에 부합하는 맞춤형 데이터 분석을 가능하게 합니다. 이를 통해 사용자는 보다 정교한 매매 타이밍을 포착하고 우량주를 효과적으로 선별하는 데 도움을 받을 수 있습니다.
                    </p>
                  </div>
                  <div className="bg-gray-50 rounded-md p-3">
                    <h4 className="font-medium text-xs md:text-sm mb-1" style={{ color: 'oklch(0.4 0.03 257.287)' }}>추세추종</h4>
                    <p className="text-sm leading-relaxed">
                      스탁이지의 추세추종 기능은 복잡한 시장 상황을 명쾌하게 해석하고 최적의 매매 타이밍 포착을 지원합니다.<br/><br/>
                      먼저, 현재 매매 환경이 유리한지를 직관적인 <strong>'시장 신호등'</strong>과 단기/장기 <strong>'시장 신호'</strong>로 명확히 제시하며, 스탁이지의 독자적인 <strong>'시장 지표 차트'</strong>를 통해 시장의 거시적 위치와 흐름을 정확히 파악하도록 돕습니다.<br/><br/>
                      핵심 종목 발굴을 위해, 시장을 선도하는 <strong>'주도주/주도섹터'</strong>를 식별하고 스탁이지의 엄격한 기준으로 필터링된 <strong>'52주 신고가 주요종목'</strong>을 제공합니다. 특히, 정교한 추세추종 알고리즘에 기반한 <strong>'돌파 리스트'</strong>는 '돌파 임박', '돌파 성공', '돌파 실패' 종목을 명확히 구분하여 실제 돌파 매매 전략 수립에 효과적인 가이드를 제공합니다.<br/><br/>
                      이 모든 정보(종목, 가격, 차트)는 HTS 접속 없이 스탁이지 내에서 바로 확인할 수 있어, 투자자가 번거로움 없이 매매 결정에만 집중하도록 지원합니다.
                    </p>
                  </div>
                  <div className="bg-gray-50 rounded-md p-3">
                    <h4 className="font-medium text-xs md:text-sm mb-1" style={{ color: 'oklch(0.4 0.03 257.287)' }}>ETF/섹터</h4>
                    <p className="text-sm leading-relaxed">
                      ETF/섹터 분석은 시장 내에서 가장 활발한 움직임을 보이는 인더스트리(산업)를 신속하게 식별할 수 있도록 설계되었습니다. 이를 위해 다양한 ETF를 주요 섹터별로 분류하여 제공함으로써, 현재 어떤 섹터가 시장을 주도하고 있는지 한눈에 파악할 수 있도록 합니다.<br/><br/>
                      페이지 하단에서는 현재 가장 강력한 모멘텀을 보이는 섹터와 해당 섹터 내에서 두각을 나타내는 주도주들을 차트와 함께 시각적으로 제시합니다. 더불어, 각 섹터별 ETF 편입 종목들을 RS(상대강도)가 높은 순으로 정렬하여 보여줌으로써, 투자자가 시장의 흐름을 정확히 읽고 유망 종목을 효과적으로 발굴할 수 있도록 지원합니다.
                    </p>
                  </div>
                  <div className="bg-gray-50 rounded-md p-3">
                    <h4 className="font-medium text-xs md:text-sm mb-1" style={{ color: 'oklch(0.4 0.03 257.287)' }}>밸류에이션</h4>
                    <p className="text-sm leading-relaxed">
                      스탁이지의 밸류에이션 기능은 기업의 현재 가치와 미래 성장 잠재력을 정밀하게 분석하여, 투자자가 정보에 기반한 현명한 결정을 내릴 수 있도록 지원합니다.<br/><br/>
                      핵심 재무 지표인 <strong>PER(주가수익비율)</strong>에 대해 현재 수치뿐만 아니라, 증권사 컨센서스를 종합한 <strong>향후 3개년 추정 PER</strong>(<code>2025(E)</code>, <code>2026(E)</code>, <code>2027(E) PER</code>)까지 심층적으로 제공하여 기업의 장기적인 가치 변화를 예측하는 데 도움을 줍니다. 또한, <strong>시가총액</strong>, <strong>업종 분류(대분류, 중분류)</strong> 등 필수 정보를 함께 제시하여 개별 종목 및 시장 전체에 대한 다각적인 이해를 가능하게 합니다.<br/><br/>
                      특히, 각 종목별 <strong>PER 추이</strong>를 시각적인 차트로 제공하여, 과거부터 미래까지의 밸류에이션 변화 흐름을 한눈에 파악할 수 있습니다. 이를 통해 사용자는 저평가된 우량주를 발굴하거나, 특정 종목의 성장 기대감을 가늠하는 등 정교한 투자 전략을 수립할 수 있습니다. 스탁이지는 복잡한 데이터를 명료하게 정리하여, 기업 가치 분석의 효율성과 정확성을 극대화합니다.
                    </p>
                  </div>
                </div>
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
};

export default AboutPage;
