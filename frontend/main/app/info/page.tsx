// frontend/main/app/info/page.tsx

// frontend/main/app/info/page.tsx

export default function InfoPage() {
 
  // Helper function to create Notion image URLs
  const getNotionImageUrl = (fileId: string, filename: string, blockId?: string) => {
    const s3Path = `https%3A%2F%2Fs3.us-west-2.amazonaws.com%2Fsecure.notion-static.com%2F${fileId}%2F${encodeURIComponent(filename)}`;
    // blockId가 있으면 사용하고, 없으면 fileId를 사용 (일부 이전 URL 패턴 호환)
    const idForQuery = blockId || fileId; 
    return `https://www.notion.so/image/${s3Path}?table=block&id=${idForQuery}&cache=v2`;
  };

  const notionContentHtml = `
    <h2 class="text-3xl font-bold mt-0 mb-6">스탁이지(StockEasy)</h2>
    <p>스탁이지(StockEasy)는 주식 전문 AI 어시스턴트로, 국내 주식 시장에 특화된 정보를 제공합니다.</p>
    <p>전업 투자자 3인으로 구성된 (주)인텔리오(Intellio)에서 개발하였으며, RAG(Retrieval Augmented Generation) 기술을 활용하여 신뢰도 높은 답변을 제공합니다.</p>
    <p>이제 주식 리서치는 주식 AI 스탁이지를 이용하세요.</p>
    <p>당신의 리서치 시간을 줄여줍니다.</p>
    
    <h3 class="text-2xl font-semibold mt-8 mb-4">스탁이지의 주요 특징</h3>
    <ul>
      <li>국내 주식 특화 : 챗GPT, 제미나이, 퍼블렉시티 등 일반 LLM과 달리, 국내 주식 시장에 초점을 맞춘 분석과 정보를 체크하여 투자자가 원하는 정보를 제공합니다.</li>
      <li>증권사 챗봇 차별화 : HTS, MTS에 있는 단순 챗봇의 대답과는 다른 수준의 정보를 제공합니다.</li>
      <li>다양한 투자 전략 지원 : 추세추종, 상대강도(RS), 주도섹터 및 주도주, 밸류에이션 등 실전 투자에 필요한 다양한 정보를 제공합니다.</li>
      <li>시각화된 데이터 제공 : 차트와 테이블을 통해 투자자들이 쉽게 이해하고 활용할 수 있도록 정보를 제공합니다.</li>
      <li>오픈 베타 서비스 : 현재 오픈 베타중으로, 사용자 피드백을 반영하여 지속적으로 개선되고 있습니다.</li>
    </ul>
    
    <br />
<img src="https://zealous-spice-207.notion.site/image/attachment%3A2d814dfe-7821-4065-b3a6-3bf8cde26b76%3Aimage.png?table=block&id=201a7c3f-6a64-80d6-bf37-cdf43bf469e4&cache=v2" alt="스탁이지 서비스 소개 이미지 1" />
<br />
    <br />
<img src="https://zealous-spice-207.notion.site/image/attachment%3A5e0148c8-2b53-4cef-81e3-2b485d8e0909%3Aimage.png?table=block&id=201a7c3f-6a64-80ea-a180-f50cdafe14b0&cache=v2" alt="스탁이지 서비스 소개 이미지 2" />
<br />
    
    <p>구글 ID를 통해 스탁이지에 가입이 가능합니다.</p>
    <p>하루에 10개의 질문 기회를 드리며 매일 자정에 초기화 됩니다.</p>

    <h2 class="text-3xl font-bold mt-10 mb-6"><strong>스탁 AI</strong></h2>
    <p>스탁이지의 핵심 엔진인 <strong>스탁 AI</strong>는 단순 정보 검색 도구를 넘어, 데이터에 기반한 정교하고 심층적인 투자 분석을 제공하는 지능형 파트너입니다.</p>
    <p><strong>방대한 학습 데이터와 정교한 분석 에이전트:</strong></p>
    <p>스탁 AI는 매일같이 발행되는 <strong>기업의 분기/반기/사업보고서, 주요사항보고서, 지분공시</strong> 와 같은 정형 데이터는 물론, 국내외<strong>산업별 심층 리포트, 경제 뉴스, 시장 분석 자료, 기술 동향 보고서</strong> 등 광범위한 비정형 데이터까지 실시간으로 수집합니다. 이렇게 축적된 방대한 정보는<strong>다수의 고도화된 분석 에이전트(Analysis Agents)들에 의해 다각도로 정교하게 분석</strong>되어, 단순 키워드 검색으로는 파악하기 어려운 정보 간의 복잡한 연결고리와 숨겨진 맥락까지 명확하게 제시합니다.</p>
    <p><strong>차세대 AI 분석 기술로 구현하는 깊이 있는 통찰력:</strong></p>
    <p>일반적인 LLM(거대 언어 모델)이 제공하는 표면적인 정보 요약이나 단순 검색 결과 나열을 뛰어넘습니다. 스탁 AI는 최신<strong>자연어 처리(NLP)</strong>기술을 핵심으로 활용하여, 텍스트 이면에 숨겨진<strong>기업의 사업 전략 변화, 시장 내 경쟁 강도, 신기술 도입에 따른 잠재적 리스크 및 성장 기회, 소비자 반응 및 평판 변화, 거시 경제 지표의 영향</strong>등을 정밀하게 분석합니다. 이를 통해 투자자는 복잡하고 방대한 자료를 직접 분석하는 시간과 노력을 획기적으로 절감할 수 있습니다.</p>
    <br />
<img src="https://zealous-spice-207.notion.site/image/attachment%3A9518a227-f50f-4189-a348-768bcbcdc0f1%3A%EC%A2%85%EB%AA%A9.jpg?table=block&id=1d6a7c3f-6a64-8092-94e9-d4f04db749c3&cache=v2" alt="스탁 AI 종목 분석 예시" />
<br />
    <p>종목을 먼저 선택하시고 질문을 하시면 됩니다.</p>
    <br />
<img src="https://zealous-spice-207.notion.site/image/attachment%3A341ff589-88fe-44f4-ae1e-c1a0e035f169%3Aimage.png?table=block&id=201a7c3f-6a64-80ff-9448-e5b445340b79&cache=v2" alt="스탁 AI 질문 입력창" />
<br />
    <br />
<img src="https://zealous-spice-207.notion.site/image/attachment%3Af3d04a63-ed4e-4dbd-930d-ec67251f32b4%3Aimage.png?table=block&id=201a7c3f-6a64-808a-9b2d-f6b92f92d5f9&cache=v2" alt="스탁 AI 답변 예시" />
<br />
    <p >질문에 따라서 평균 2분 정도의 시간이 소요 됩니다.</p>
    <br />
<img src="https://zealous-spice-207.notion.site/image/attachment%3Ad961dd3a-8b45-4c1e-8214-292b99d36385%3Aimage.png?table=block&id=201a7c3f-6a64-80f1-b5ed-cc39653fc9be&cache=v2" alt="스탁 AI 답변 상세 기능" />
<br />
    <p>우측 상단에 공유 버튼을 누르시면 답변을 쉽게 공유할수 있는 링크 주소가 생성이 됩니다.</p>
    <p>PDF 버튼은 PDF 파일로 저장할수 있는 기능이며</p>
    <p>말버튼 옆 숫자는 하루에 답변할수 있는 횟수 입니다.</p>
    <br />
<img src="https://zealous-spice-207.notion.site/image/attachment%3A934e1534-6780-4748-8f72-ed23bc536ce1%3Aimage.png?table=block&id=201a7c3f-6a64-806b-bdb5-f655ef7133a0&cache=v2" alt="스탁 AI 아이콘 설명" />
<br />
    <p>화면 상단 로보트 모양의 아이콘 “스탁 AI”를 누르면 초기화로 돌아가며 다시 종목을 선택하고 질문할수 있습니다.</p>
    <p>시계모양의 아이콘 “검색 히스토리”는 최근 채팅 내역을 날짜순으로 보여줍니다.</p>
    <p>선택시 과거 답변을 다시 확인하실수 있습니다.</p>

    <h2 class="text-3xl font-bold mt-10 mb-6">추세추종</h2>
    <p>스탁이지의 추세추종 기능은 복잡한 시장 상황을 명쾌하게 해석하고 최적의 매매 타이밍 포착을 지원합니다.</p>
    <p>먼저, 현재 매매 환경이 유리한지를 직관적인<strong>'시장 신호등'</strong>과 단기/장기<strong>'시장 신호'</strong>로 명확히 제시하며, 스탁이지의 독자적인<strong>'시장 지표 차트'</strong>를 통해 시장의 거시적 위치와 흐름을 정확히 파악하도록 돕습니다.</p>
    <p>핵심 종목 발굴을 위해, 시장을 선도하는<strong>'주도주/주도섹터'</strong>를 식별하고 스탁이지의 엄격한 기준으로 필터링된<strong>'52주 신고가 주요종목'</strong>을 제공합니다. 특히, 정교한 추세추종 알고리즘에 기반한<strong>'돌파 리스트'</strong>는 '돌파 임박', '돌파 성공', '돌파 실패' 종목을 명확히 구분하여 실제 돌파 매매 전략 수립에 효과적인 가이드를 제공합니다.</p>
    <p>이 모든 정보(종목, 가격, 차트)는 HTS 접속 없이 스탁이지 내에서 바로 확인할 수 있어, 투자자가 번거로움 없이 매매 결정에만 집중하도록 지원합니다.</p>
    <br />
<img src="https://zealous-spice-207.notion.site/image/attachment%3A9f0a16a0-3572-4b85-9d6b-0b8fd3f9ff39%3Aimage.png?table=block&id=201a7c3f-6a64-8084-9d86-e82227c1de64&cache=v2" alt="추세추종 - 시장 신호등 및 시장 지표 차트" />
<br />
    <p>시장신호등은 시장의 매수/매도 타이밍, 위험신호 등을 직관적으로 색상으로 시각화해서 투자자에게 알려주는 서비스 입니다.</p>
    <p>복잡한 차트나 지표를 해석하기 어려운 투자자들에게 직관적이고 빠른 의사 결정을 할수 있도록 해줍니다.</p>
    <br />
    <p>빨간불 : 약함, 위험경고 (약세장)</p>
    <p>노란불 : 중립, 관망 (횡보장)</p>
    <p>초록불 : 강함, 투자기회 (강세장)</p>
    <br />
    <p>스탁이지에서는 단기/장기 두가지 뷰를 제공하고 있으며 “시장지표” 탭을 통해 구체적으로 확인도 가능합니다.</p>
    <br />
<img src="https://zealous-spice-207.notion.site/image/attachment%3Ae929ce64-840c-444d-823a-2b53f3717022%3Aimage.png?table=block&id=201a7c3f-6a64-802d-b380-d76055f6558f&cache=v2" alt="추세추종 - 52주 신고가 주요종목" />
<br />
    <br />
<img src="https://zealous-spice-207.notion.site/image/attachment%3A78b43826-f4f2-4fcc-9c29-b1ffc85b7a19%3Aimage.png?table=block&id=201a7c3f-6a64-80e1-ae18-d2a5cecf254b&cache=v2" alt="추세추종 - 신규 관심 섹터 예시" />
<br />
    
   
    <p>주도 섹터 및 주도주 현황을 통해 현재 시장의 주도섹터 주도주를 파악할수 있습니다.</p>
    <p>단순 오늘의 주도섹터 주도주가 아니라 실제로 상승 후 추세를 유지하고 있는 섹터 중에서도 RS가 높은 상위 6개 섹터와 종목을 체크해서 보여줍니다.</p>
    <p>매매에 도움이 될수 있도록 가중평균 RS(12개월)과 RS(1개월)의 흐름 MTT(마크미너비니 템플릿)에 부합되는 종목인지 표시해주며 차트 탭을 통해 주도종목들의 차트를 바로 확인할 수 있습니다.</p>
    <br />
<img src="https://zealous-spice-207.notion.site/image/attachment%3A22754210-528a-47bd-aa30-272eb41fc604%3Aimage.png?table=block&id=201a7c3f-6a64-8058-a897-d757ed7fb0cb&cache=v2" alt="추세추종 - 주도 섹터 및 주도주 현황" />
<br />
    
    <p>신규 관심 섹터는 포지션을 새로 구축하는 섹터로 바닥권에서 다시 상승하는 추세를 보여주는 섹터로 아직은 추세가 없지만 앞으로 지켜볼 섹터를 표시해줍니다.</p>
    <br />
<img src="https://zealous-spice-207.notion.site/image/attachment%3A61dfc3a2-1bbf-41c4-aa04-c07f898222e0%3Aimage.png?table=block&id=201a7c3f-6a64-807e-a522-ff67dc9fe1eb&cache=v2" alt="추세추종 - 신규 관심 섹터" />
<br />
    
    <p>52주 신고가 주요 종목은 내부로직을 통해 52주 신고가 전 종목을 보여주는것이 아니라 그중에서도 관심을 가져볼만한 종목으로 압축시켜서 표시해줍니다.</p>
    <p>차트 탭을 누르면 해당 종목들의 차트를 확인하실 수 있습니다.</p>
    <p>이때 주도섹터 주도주와 52주 신고가 주요종목에 겹치는 경우 추세가 강하다라고 판별할수 있습니다.</p>
    <br />
<img src="https://zealous-spice-207.notion.site/image/attachment%3A17210812-847a-44d6-b978-e453c522254b%3Aimage.png?table=block&id=201a7c3f-6a64-8072-9a0f-cdd59c8f2284&cache=v2" alt="추세추종 - 52주 신고가 주요 종목" />
<br />
    <p>스탁이지 돌파 리스트는 내부 로직에 의해 돌파에 임박(돌파에서 3% 근접) 한 종목을 보여줍니다.</p>
    <p>돌파 성공은 당일 돌파 가격 이상으로 안착한 종목이며 돌파 실패는 당일 돌파 했지만 다시 하락한 종목들입니다. </p>
    <p>해당 돌파는 거래량과 인더스트리액션등을 감안하지 않고 단순 가격에 의한 돌파 체크 입니다.</p>
    <p>차트탭을 누르면 해당 종목들의 차트가 나오며 돌파 라인도 표시해줍니다.</p>
    <p>실제 매매에 적용할경우 꼭 돌파시 거래량과 인더스트리 액션을 체크하시기 바랍니다.</p>
    <p>또한 돌파 성공과 스쾃 등의 횟수로도 포지션 조절에 도움을 받을수 있습니다.  </p>
    <p>추세추종 관련 매매에 대해서 좀 더 공부를 하고 싶은 분은 “손실은 짧게 수익은 길게” 저자 깡토의 책을 참고하시기 바랍니다.</p>

    <h2 class="text-3xl font-bold mt-10 mb-6"><strong>RS 순위</strong></h2>
    <p>RS 랭킹은 추세추종 전략의 핵심 지표인 RS(상대강도) 및 MTT(마크 미너비니 트렌드 템플릿) 충족 여부를 종목별로 명확하게 제시합니다. 이와 함께 RS 상위 21개 종목 및 MTT 조건을 만족하는 상위 21개 종목의 차트를 시각적으로 제공하여, 투자자가 시장 주도주를 빠르고 직관적으로 파악할 수 있도록 지원합니다.</p>
    <p>스탁이지의 RS 지표는 국내 시장 환경에 최적화된 독자적인 로직으로 정교하게 구성되었습니다. 단순 RS 값뿐만 아니라, RS 1개월, 3개월, 6개월 등 다양한 기간별 RS 수치를 함께 제공하여, 투자자의 다양한 투자 기간 및 전략에 부합하는 맞춤형 데이터 분석을 가능하게 합니다. 이를 통해 사용자는 보다 정교한 매매 타이밍을 포착하고 우량주를 효과적으로 선별하는 데 도움을 받을 수 있습니다.</p>
    <br />
<img src="https://zealous-spice-207.notion.site/image/attachment%3A301508aa-bf4b-47e1-95df-74c284c78c16%3Aimage.png?table=block&id=201a7c3f-6a64-80af-a06b-cfc3cb389e01&cache=v2" alt="RS 순위 차트 예시" />
<br />
    <p>RS순위 페이지 는 RS(상대강도)에 대한 표시 입니다</p>
    <p>RS(Relative Strength)는 특정 종목의 주가 수익률이 시장 전체의 수익률과 비교해서 얼마나 강한지 백분률로 표시한 지표 입니다.</p>
    <p>현재 스탁이지에서는 시가총액 2000억 미만은 제외하였습니다.</p>
    <p>기존 RS는 가중평균으로 계산하였고 개월을 추가하여 흐름을 파악하기 쉽게 하였습니다.</p>
    <p>MTT(마크미너비니템플릿)으로 조건에 부합하는 종목들을 체크하였습니다.</p>
    <p>우측 상단에 검색을 통해 보유한 종목의 RS를 확인하실수 있습니다 </p>
    <p>시총 2000억 미만을 제외한것은 스몰캡은 슬리피지로 인해서 인베스트 대상이지 추세추종 트레이딩 대상이 될수가 없어서 제외 했습니다.</p>

    <h2 class="text-3xl font-bold mt-10 mb-6"><strong>ETF 섹터</strong></h2>
    <p>ETF/섹터 분석은 시장 내에서 가장 활발한 움직임을 보이는 인더스트리(산업)를 신속하게 식별할 수 있도록 설계되었습니다. 이를 위해 다양한 ETF를 주요 섹터별로 분류하여 제공함으로써, 현재 어떤 섹터가 시장을 주도하고 있는지 한눈에 파악할 수 있도록 합니다.</p>
    <p>페이지 하단에서는 현재 가장 강력한 모멘텀을 보이는 섹터와 해당 섹터 내에서 두각을 나타내는 주도주들을 차트와 함께 시각적으로 제시합니다. 더불어, 각 섹터별 ETF 편입 종목들을 RS(상대강도)가 높은 순으로 정렬하여 보여줌으로써, 투자자가 시장의 흐름을 정확히 읽고 유망 종목을 효과적으로 발굴할 수 있도록 지원합니다.</p>
    <br />
<img src="https://zealous-spice-207.notion.site/image/attachment%3A395fc1d5-9ad7-447c-a5ea-3ea4d899ec2d%3Aimage.png?table=block&id=201a7c3f-6a64-8026-8a7d-c11d9d3e64e4&cache=v2" alt="ETF 섹터 차트 예시" />
<br />
    <p>ETF/섹터 페이지는 한눈에 시장의 흐름을 파악하기 위한 용도 입니다.</p>
    <p>어떤 섹터들이 강하고 약한지 포지션 날짜와 20일 이격, 등락률을 통해 섹터의 강함을 판단하고</p>
    <p>대표종목들의 RS를 통해 전반적인 자금의 흐름을 체크할수 있습니다.</p>
    <p>하단에는 산업별 주도ETF 차트도 볼수 있습니다.</p>

    <h2 class="text-3xl font-bold mt-10 mb-6"><strong>밸류에이션</strong></h2>
   
    <p>스탁이지의 밸류에이션 기능은 기업의 현재 가치와 미래 성장 잠재력을 정밀하게 분석하여, 투자자가 정보에 기반한 현명한 결정을 내릴 수 있도록 지원합니다.</p>
    <p>핵심 재무 지표인<strong>PER(주가수익비율)</strong>에 대해 현재 수치뿐만 아니라, 증권사 컨센서스를 종합한<strong>향후 3개년 추정 PER</strong>(E)까지 심층적으로 제공하여 기업의 장기적인 가치 변화를 예측하는 데 도움을 줍니다. 또한,<strong>시가총액</strong>,<strong>업종 분류(대분류, 중분류)</strong>등 필수 정보를 함께 제시하여 개별 종목 및 시장 전체에 대한 다각적인 이해를 가능하게 합니다.</p>
    <br />
<img src="https://zealous-spice-207.notion.site/image/attachment%3A75c87bc2-48bf-4ccd-8db1-b0f4373a3cf2%3Aimage.png?table=block&id=201a7c3f-6a64-8060-ae0e-c1c5bdfeabbe&cache=v2" alt="밸류에이션 차트 예시" />
<br />
    <p>밸류에이션 페이지는 애널리스트들이 추정한 컨센서스 기준으로 최근 3년치의 PER 를 제공합니다.</p>
    <p>애널리스트 추정치가 없을 경우 공백입니다.</p>
    <p>멀티플 등의 (PEER 그룹 PER)를 체크하실때 사용하시면 됩니다.</p>
    <p>원하시는 종목명이나 종목코드를 넣어서 검색해서 분류를 확인하고 분류를 선택하면 동일한 분류의 종목들이 정렬되서 나옵니다.</p>
    <p>이상으로 간단한 스탁이지의 기능 소개를 마칩니다.</p>

    <h2 class="text-3xl font-bold mt-10 mb-6"><strong>활용 방법</strong></h2>
    <p>시장 신호등을 먼저 확인하고 주도섹터 / 주도주를 체크 합니다.</p>
    <p>이때 ETF 페이지에서 자금의 흐름을 확인하고 RS페이지에서 주도주들의 RS를 체크 합니다.</p>
    <p>차트를 확인하고 돌파 리스트 체크해서 관심 종목을 정리 합니다.</p>
    <p>스탁 AI 페이지에서 해당 종목에 대해서 궁금한 점을 질문을 해서 펀더멘탈도 체크합니다.</p>
    <p>마지막 밸류에이션 페이지에서 그 섹터의 평균 밸류를 체크 합니다.</p>
    <p>이제 실전 매매에서 돌파 할때 거래량이 터졌는지, 인더스트리 액션이 있는지를 확인 후 추세를 따라 갑니다.</p>
    <p>스탁이지는 오픈베타 서비스 중이며 지속적으로 개발중에 있습니다.</p>
    <p>아직 스탁 AI 어시스턴트에서 수급/밸류에이션/기술적분석 등등 포함하지 못했습니다. 앞으로 추가할 예정이며 국내 시장 뿐만 아니라 향 후 글로벌 시장도 진입 예정입니다.</p>
    <p>적극적인 사용과 과도한 주변 홍보 압도적 고맙습니다.</p>
    <p>특히 블로그 포스팅과 함께 답변링크 공유는 참 감사합니다. </p>
    <p>언제나 궁금하시거나 좋은 의견 있으시면 깡토의 블로그나 <a href="mailto:intellio.korea@gmail.com">intellio.korea@gmail.com</a> 으로 메일 주세요.</p>
    <p>감사합니다.</p>
  `;

  return (
    <div className="flex flex-col min-h-screen bg-background">
      <div className="container mx-auto px-4 pt-8 pb-16 flex-grow">

        <article
  className="prose prose-sm sm:prose lg:prose-lg xl:prose-xl max-w-none dark:prose-invert text-left prose-headings:text-left prose-h1:text-left prose-h2:text-left prose-h3:text-left prose-h4:text-left prose-h5:text-left prose-h6:text-left prose-p:text-left prose-li:text-left prose-blockquote:text-left prose-strong:text-[oklch(0.372_0.044_257.287)] prose-a:text-blue-600 dark:prose-a:text-blue-400 prose-li:my-1 prose-img:rounded-lg prose-img:shadow-lg prose-img:max-w-[90%] prose-img:h-auto prose-img:mx-auto prose-img:my-6 prose-blockquote:bg-gray-50 prose-blockquote:border-l-4 prose-blockquote:border-blue-400 prose-blockquote:p-4 prose-blockquote:italic prose-hr:my-8 prose-hr:border-t prose-hr:border-gray-300 prose-ul:list-disc prose-ul:list-inside prose-ul:ml-6 prose-ul:mb-2 prose-ol:list-decimal prose-ol:list-inside prose-ol:ml-6 prose-ol:mb-2 prose-p:leading-relaxed prose-p:mb-4 prose-section:mb-10 prose-h1:text-4xl prose-h1:font-extrabold prose-h1:mb-8 prose-h2:text-2xl prose-h2:font-bold prose-h2:mb-4 prose-h2:text-[oklch(0.372_0.044_257.287)] prose-h3:text-xl prose-h3:font-semibold prose-h3:mb-2 prose-h3:text-[oklch(0.372_0.044_257.287)] prose-section:mb-10 prose-a:underline prose-a:decoration-blue-400 prose-a:font-medium prose-a:hover:text-blue-700 prose-a:transition-colors prose-a:duration-200"
  dangerouslySetInnerHTML={{ __html: notionContentHtml }}
/>
<br />

      </div>
    </div>
  );
}

