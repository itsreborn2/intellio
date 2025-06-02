export default function AboutPage() {
  return (
    <div className="container mx-auto py-12 px-4 md:px-6">
      <h1 className="text-4xl font-bold tracking-tight text-foreground sm:text-5xl md:text-6xl">
        About Intellio
      </h1>
      <div className="mt-6 prose prose-lg max-w-none text-muted-foreground">
        <p>
          Intellio는 최첨단 AI 기술을 활용하여 고객의 비즈니스 성장을 돕는 것을 목표로 합니다.
          저희는 다양한 산업 분야에서 AI 기반 솔루션을 제공하며, 데이터 분석, 업무 자동화, 예측 모델링 등 고객 맞춤형 서비스를 지원합니다.
        </p>
        <p>
          Intellio의 전문가 팀은 다년간의 AI 연구 개발 경험과 실무 적용 노하우를 바탕으로, 고객이 직면한 복잡한 문제를 해결하고 새로운 가치를 창출할 수 있도록 최선을 다하고 있습니다.
          우리는 기술 혁신을 통해 더 나은 미래를 만들어가는 데 기여하고자 합니다.
        </p>
        <h2 className="mt-8 text-2xl font-semibold tracking-tight text-foreground">
          Our Mission
        </h2>
        <p>
          우리의 미션은 AI 기술의 접근성을 높이고, 모든 기업이 AI를 통해 혁신적인 성장을 이룰 수 있도록 지원하는 것입니다.
          고객과의 긴밀한 협력을 통해 최적의 솔루션을 제공하고, 지속 가능한 성공을 함께 만들어갑니다.
        </p>
        <h2 className="mt-8 text-2xl font-semibold tracking-tight text-foreground">
          Our Vision
        </h2>
        <p>
          Intellio는 AI 기술을 선도하는 글로벌 리더가 되어, 인간의 삶을 풍요롭게 하고 사회 발전에 기여하는 것을 비전으로 삼고 있습니다.
          끊임없는 연구와 개발을 통해 미래 기술을 현실로 만들겠습니다.
        </p>
      </div>
    </div>
  );
}
