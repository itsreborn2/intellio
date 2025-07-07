import Hero from "@/components/hero"
import Features from "@/components/features"
import CTA from "@/components/cta"
import Footer from "@/components/footer"

export default function Home() {
  return (
    <div className="relative min-h-screen">
      {/* Background gradients */}
      <div className="pointer-events-none fixed inset-0">
        <div className="absolute inset-0 bg-gradient-to-b from-background via-background/90 to-background" />
        <div className="absolute right-0 top-0 h-[500px] w-[500px] bg-blue-500/10 blur-[100px]" />
        <div className="absolute bottom-0 left-0 h-[500px] w-[500px] bg-purple-500/10 blur-[100px]" />
      </div>

      <div className="relative z-10">
        <Hero />
        {/* Features 컴포넌트가 Hero와 Footer 사이에 위치하도록 조정할 수 있습니다. 
            현재는 Footer가 Hero 바로 다음에 오도록 되어 있습니다. 
            필요시 Features 컴포넌트의 주석을 해제하고 위치를 조정하세요. */}
        {/* <Features /> */}
        <div className="mt-auto"></div> {/* 이 div는 Footer를 하단에 고정하는 역할을 할 수 있습니다. */} 
        <Footer />
      </div>
    </div>
  )
}

