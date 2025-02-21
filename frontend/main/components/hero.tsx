import Link from 'next/link';
import { Button } from "@/common/components/ui/button" // Button 컴포넌트 import

const doceasyUrl = process.env.NEXT_PUBLIC_DOCEASY_URL
const stockeasyUrl = process.env.NEXT_PUBLIC_STOCKEASY_URL
console.log('process.env.NEXT_PUBLIC_ENV : ', process.env.NEXT_PUBLIC_ENV)
console.log('process.env.NEXT_PUBLIC_USE_SERVER_FRONTEND : ', process.env.NEXT_PUBLIC_USE_SERVER_FRONTEND)
console.log('doceasy : ', doceasyUrl, ', stockeasy : ', stockeasyUrl)
export default function Hero() {
  return (
    <section className="container relative flex min-h-[calc(100vh-3.5rem)] max-w-screen-2xl flex-col items-center justify-center space-y-8 py-24 text-center md:py-32">
      <div className="absolute inset-0 bg-radial-gradient from-primary to-accent opacity-10 blur-xl"></div>
      <div className="relative space-y-4">
        <h1 className="bg-gradient-to-br from-foreground from-30% via-foreground/90 to-foreground/70 bg-clip-text text-4xl font-bold tracking-tight text-transparent sm:text-5xl md:text-6xl lg:text-7xl">
          Innovate Faster with
          <br />
          Intellio
        </h1>
        <p className="mx-auto max-w-[42rem] leading-normal text-muted-foreground sm:text-xl sm:leading-8">
          가장 빠르고 진보된 AI Power로 업무 자동화와 주식 정보를 전달합니다.
        </p>
      </div>
      <div className="relative flex gap-6">
        <Link href={doceasyUrl}>
          <span className="relative inline-block overflow-hidden rounded-full p-[1.5px]">
            <span className="absolute inset-[-1000%] animate-[spin_2s_linear_infinite] bg-[conic-gradient(from_90deg_at_50%_50%,#393BB2_0%,#E2CBFF_50%,#393BB2_100%)]" />
            <Button size="lg" className="relative rounded-full bg-background px-8 py-4 text-lg font-semibold leading-none tracking-tight inline-flex h-full w-full cursor-pointer items-center justify-center text-foreground hover:bg-accent/10 transition-colors">
              DocEasy
            </Button>
          </span>
        </Link>
        <Link href={stockeasyUrl}>
          <span className="relative inline-block overflow-hidden rounded-full p-[1.5px]">
            <span className="absolute inset-[-1000%] animate-[spin_2s_linear_infinite] bg-[conic-gradient(from_90deg_at_50%_50%,#E2CBFF_0%,#393BB2_50%,#E2CBFF_100%)]" />
            <Button size="lg" className="relative rounded-full bg-background px-8 py-4 text-lg font-semibold leading-none tracking-tight inline-flex h-full w-full cursor-pointer items-center justify-center text-foreground hover:bg-accent/10 transition-colors">
              StockEasy
            </Button>
          </span>
        </Link>
      </div>
    </section>
  )
}

