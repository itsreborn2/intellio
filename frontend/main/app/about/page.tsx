export default function AboutPage() {
  return (
    <div className="container mx-auto py-12 px-4 md:px-6">
      <h1 className="text-4xl font-bold tracking-tight text-foreground sm:text-5xl md:text-6xl">
        About Intellio
      </h1>
      <div className="mt-6 prose prose-lg max-w-none text-muted-foreground">
        <h2 className="text-3xl font-semibold tracking-tight text-foreground mt-4">About Us</h2><br/>
        <p className="text-xl font-semibold mt-3 mb-3 text-foreground/90">(주) 인텔리오 – AI와 데이터로 주식 투자의 새로운 길을 열다</p>
        <p>(주) 인텔리오는 10년 이상의 전업투자 경험을 가진 전문가들이 모여 설립한 기업입니다. 단순한 이론이 아닌, 실전에서 검증된 데이터와 AI 기술을 결합하여 투자자들에게 실질적인 도움을 주는 서비스를 제공합니다.</p>

        <h2 className="mt-10 text-3xl font-semibold tracking-tight text-foreground">우리는 누구인가?</h2>
        <p>인텔리오는 오랜 시간 직접 시장에서 투자하며 쌓아온 경험과 데이터를 바탕으로, 개별 투자자들이 보다 효과적으로 시장을 이해하고 대응할 수 있도록 돕기 위해 설립되었습니다. 전통적인 가치투자, 모멘텀 투자뿐만 아니라 AI 기반의 테크노펀더멘탈리스트 방식과 시스템 트레이딩을 활용한 추세 추종 전략 등을 연구하며, 이를 실전에 적용할 수 있는 솔루션을 제공합니다.</p>

        <h2 className="mt-10 text-3xl font-semibold tracking-tight text-foreground">우리가 하는 일</h2>
        <ul className="mt-4 list-disc space-y-3 pl-5 marker:text-sky-400">
          <li><strong>AI 기반 투자 분석 솔루션:</strong> AI를 활용해 투자에 필요한 정보를 자동으로 수집, 분석하고 유의미한 인사이트를 제공합니다.</li>
          <li><strong>주식 시장 데이터 처리 및 시각화:</strong> 시장 데이터를 정리하고 분석하여 투자자들이 빠르게 판단할 수 있도록 지원합니다.</li>
          <li><strong>실전 투자자를 위한 도구 개발:</strong> 단순한 이론이 아닌, 실전 투자에서 활용할 수 있는 다양한 툴과 서비스를 제공합니다.</li>
          <li><strong>RAG 기반 주식 전용 GPT 개발:</strong> 최신 RAG(Retrieval-Augmented Generation) 기술을 활용하여 실시간 데이터와 결합된 맞춤형 주식 분석 AI를 제공합니다. 이를 통해 투자자들은 최신 기업 정보, 재무 데이터, 시장 트렌드를 즉각적으로 분석하고 활용할 수 있습니다.</li>
        </ul>

        <h2 className="mt-10 text-3xl font-semibold tracking-tight text-foreground">차별점</h2>
        <ul className="mt-4 list-disc space-y-3 pl-5 marker:text-sky-400">
          <li><strong>실전 투자 중심 –</strong> 창립 멤버들이 실제로 시장에서 오랜 기간 투자하며 쌓아온 노하우를 기반으로 정보를 제공합니다.</li>
          <li><strong>AI와 데이터 분석 기술 접목 –</strong> 최신 AI 기술을 활용해 투자 판단에 필요한 정보를 신속하고 정확하게 제공합니다.</li>
          <li><strong>자동화된 데이터 수집 및 분석 –</strong> 노코드 및 파이썬 기반의 자동화 솔루션을 활용하여 투자자들이 보다 효율적으로 시장을 분석할 수 있도록 지원합니다.</li>
          <li><strong>RAG 기반 AI 분석 –</strong> 단순한 챗봇이 아닌, 실시간 데이터 검색과 AI 분석을 결합한 주식 전용 GPT를 개발하여 보다 정교한 투자 판단을 지원합니다.</li>
        </ul>

        <h2 className="mt-10 text-3xl font-semibold tracking-tight text-foreground">비전과 목표</h2>
        <p>인텔리오는 단순한 정보 제공을 넘어, 투자자들이 시장에서 지속적으로 성공할 수 있도록 돕는 것을 목표로 합니다. AI와 데이터를 활용하여 보다 정교하고 실용적인 투자 도구를 개발하고, 개별 투자자부터 기관 투자자까지 누구나 쉽게 활용할 수 있는 솔루션을 제공합니다.</p>
        <p>우리는 빠르게 변화하는 금융 시장 속에서, 투자자들이 데이터에 기반한 합리적인 판단을 내릴 수 있도록 지원하며, 궁극적으로는 금융 시장에서의 정보 격차를 해소하는 것을 목표로 합니다.</p>

        <p className="mt-10 text-xl font-semibold text-center text-foreground/90">인텔리오와 함께, AI가 열어주는 새로운 투자 기회를 경험해 보세요!</p>
      
      </div>
    </div>
  );
}
