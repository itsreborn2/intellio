import { Button } from "@/components/ui/button"
import Link from 'next/link'; // Link 컴포넌트 import

export default function CTA() {
  return (
    <section className="py-20 bg-primary text-white">
      <div className="container mx-auto text-center">
        <h2 className="text-3xl font-bold mb-6">Ready to Streamline Your Workflow?</h2>
        <p className="text-xl mb-8 max-w-2xl mx-auto">
          Join thousands of teams already using StreamLine to boost their productivity.
        </p>
        <div className="flex justify-center space-x-4"> {/* 버튼들을 flex로 배치 */}
          <Link href="http://localhost:3001"> {/* Doceasy 버튼 링크 */}
            <Button size="lg" variant="secondary">
              Doceasy 바로가기
            </Button>
          </Link>
          <Link href="http://localhost:3002"> {/* Stockeasy 버튼 링크 */}
            <Button size="lg" variant="secondary">
              Stockeasy 바로가기
            </Button>
          </Link>
        </div>
      </div>
    </section>
  )
}
