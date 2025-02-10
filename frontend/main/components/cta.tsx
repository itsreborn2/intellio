import { Button } from "@/components/ui/button"

export default function CTA() {
  return (
    <section className="border-t">
      <div className="container flex flex-col items-center gap-4 py-24 text-center md:py-32">
        <h2 className="font-bold text-3xl leading-[1.1] sm:text-3xl md:text-5xl">
          AI 업무 자동화 & 주식 데이터 컨설팅
        </h2>
        <p className="max-w-[42rem] leading-normal text-muted-foreground sm:text-xl sm:leading-8">
          가장 앞선 AI 기술을 적용하여 소규모 업무 자동화 부터 주식시장의 트랜드 데이터까지.
          늘 진보된 기술만을 제안드립니다.
        </p>
        <Button size="lg" className="mt-4">
          업무 자동화 문의
        </Button>
      </div>
    </section>
  )
}

