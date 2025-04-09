import Navbar from "@/components/navbar"
import Footer from "@/components/footer"
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card"

export default function TermsPage() {
  return (
    <div className="relative min-h-screen">
      {/* 배경 그라디언트 */}
      <div className="pointer-events-none fixed inset-0">
        <div className="absolute inset-0 bg-gradient-to-b from-background via-background/90 to-background" />
        <div className="absolute right-0 top-0 h-[500px] w-[500px] bg-blue-500/10 blur-[100px]" />
        <div className="absolute bottom-0 left-0 h-[500px] w-[500px] bg-purple-500/10 blur-[100px]" />
      </div>

      <div className="relative z-10">
        <Navbar />
        
        <main className="container mx-auto px-4 py-12">
          <Card className="max-w-4xl mx-auto shadow-lg">
            <CardHeader>
              <CardTitle className="text-3xl font-bold">서비스 이용약관</CardTitle>
              <CardDescription>
                인텔리오(Intellio) 서비스 이용에 관한 약관
              </CardDescription>
            </CardHeader>
            <CardContent className="prose max-w-none">
              <div className="space-y-6">
                <section>
                  <h2 className="text-2xl font-semibold">스탁이지 서비스 이용약관</h2>
                  <p className="my-4">
                    안녕하세요.<br />
                    (주)인텔리오의 스탁이지 서비스를 이용해 주셔서 감사합니다. 스탁이지는 기업의 펀더멘탈 데이터를 AI로 분석하고 제공하는 서비스로, 본 약관은 서비스 이용과 관련한 회사와 회원의 권리 및 의무를 규정합니다.
                  </p>
                </section>

                <section>
                  <h3 className="text-xl font-medium">제1조 (목적)</h3>
                  <p>
                    이 약관은 (주)인텔리오(이하 '회사')가 제공하는 닥이지,스탁이지(이하 '서비스')의 이용 조건, 절차, 회원과 회사의 권리 및 책임 등을 정하는 것을 목적으로 합니다.
                  </p>
                </section>

                <section>
                  <h3 className="text-xl font-medium">제2조 (이용계약의 체결)</h3>
                  <p>
                    회원가입 절차를 완료하고 본 약관에 동의하면 이용계약이 성립합니다. 회원은 정확한 정보를 제공해야 하며, 허위 정보 입력 시 서비스 이용이 제한될 수 있습니다.<br />
                    카카오톡 등 외부 플랫폼을 이용한 가입 시에도 본 약관과 개인정보 처리방침에 동의하면 이용계약이 체결됩니다.
                  </p>
                </section>

                <section>
                  <h3 className="text-xl font-medium">제3조 (이용신청 제한)</h3>
                  <p>
                    회사는 다음과 같은 경우 이용 신청을 거절하거나 제한할 수 있습니다.
                  </p>
                  <ol className="list-decimal pl-6">
                    <li>기술적 문제로 인해 원활한 서비스 제공이 어려운 경우</li>
                    <li>만 14세 미만 사용자가 가입을 신청하는 경우</li>
                    <li>서비스의 정상적 운영을 방해할 우려가 있는 경우</li>
                    <li>기타 회사 정책에 따라 이용이 적절하지 않다고 판단되는 경우</li>
                  </ol>
                </section>

                <section>
                  <h3 className="text-xl font-medium">제4조 (회원 탈퇴 및 계약 해지)</h3>
                  <p>
                    회원은 서비스 내 제공되는 탈퇴 기능을 통해 언제든지 이용계약을 해지할 수 있습니다. 탈퇴 후 회원 정보는 관련 법령에 따라 보관되며, 필요하지 않은 정보는 삭제됩니다.
                  </p>
                </section>

                <section>
                  <h3 className="text-xl font-medium">제5조 (서비스 이용 제한 사항)</h3>
                  <p>
                    회원은 다음과 같은 행위를 할 경우 서비스 이용이 제한될 수 있습니다.
                  </p>
                  <ol className="list-decimal pl-6">
                    <li>서비스의 정상적 운영을 방해하는 행위</li>
                    <li>타인의 정보를 무단으로 수집, 이용, 공유하는 행위</li>
                    <li>불법 콘텐츠를 게시하거나 배포하는 행위</li>
                    <li>회사의 사전 동의 없이 서비스를 상업적으로 이용하는 행위</li>
                    <li>서비스의 소스코드를 분석, 수정, 변형하는 행위</li>
                    <li>자동화된 수단을 이용해 데이터를 수집하는 행위</li>
                  </ol>
                </section>

                <section>
                  <h3 className="text-xl font-medium">제6조 (개인정보 보호)</h3>
                  <p>
                    회사는 회원의 개인정보 보호를 최우선으로 하며, 관련된 사항은 스탁이지 개인정보처리방침을 따릅니다.
                  </p>
                </section>

                <section>
                  <h3 className="text-xl font-medium">제7조 (게시물 관리 및 저작권)</h3>
                  <ol className="list-decimal pl-6">
                    <li>회원이 서비스에 게시한 콘텐츠의 저작권은 회원에게 있으며, 회사는 이를 서비스 내에서 노출할 권리를 가집니다.</li>
                    <li>게시물이 타인의 권리를 침해하는 경우, 해당 회원이 이에 대한 책임을 집니다.</li>
                    <li>회사는 서비스 운영 및 홍보 목적으로 게시물을 활용할 수 있으며, 추가적인 상업적 이용이 필요한 경우 사전 동의를 받습니다.</li>
                    <li>법령 위반, 불법 콘텐츠 포함, 명예훼손 등의 문제가 있는 게시물은 사전 통지 없이 삭제될 수 있습니다.</li>
                    <li>본 사이트의 모든 콘텐츠는 저작권법의 보호를 받으며, 무단 사용을 금합니다.</li>
                  </ol>
                </section>

                <section>
                  <h3 className="text-xl font-medium">제8조 (책임 제한)</h3>
                  <ol className="list-decimal pl-6">
                    <li>회사는 서비스 이용으로 인해 발생한 손해에 대해 책임지지 않습니다.</li>
                    <li>회원 간 발생한 분쟁에 회사는 개입할 의무가 없으며, 이로 인해 발생한 피해에 대해서도 책임을 지지 않습니다.</li>
                    <li>서비스 제공 중 발생할 수 있는 오류나 기술적 문제에 대해 회사는 최선을 다해 대응하지만, 이에 따른 손해 배상 책임은 없습니다.</li>
                    <li>이 사이트에서 제공하는 정보는 투자 조언이 아니며, 투자 결정의 책임은 투자자 본인에게 있습니다.</li>
                    <li>본 사이트는 특정 금융 상품에 대한 추천을 제공하지 않습니다.</li>
                  </ol>
                </section>

                <section>
                  <h3 className="text-xl font-medium">제9조 (유료 서비스)</h3>
                  <p>
                    회사는 일부 기능을 유료로 제공할 수 있으며, 이에 대한 세부 사항은 별도의 정책을 통해 안내됩니다.
                  </p>
                </section>

                <section>
                  <h3 className="text-xl font-medium">제10조 (서비스 변경 및 중단)</h3>
                  <ol className="list-decimal pl-6">
                    <li>회사는 서비스 개선을 위해 필요 시 내용을 변경할 수 있으며, 사전 공지합니다.</li>
                    <li>유지보수, 시스템 장애 등의 사유로 서비스가 일시 중단될 수 있으며, 회사는 이에 대한 책임을 지지 않습니다.</li>
                  </ol>
                </section>

                <section>
                  <h3 className="text-xl font-medium">제11조 (기타 조항)</h3>
                  <ol className="list-decimal pl-6">
                    <li>본 약관은 대한민국 법률에 따라 해석되고 적용됩니다.</li>
                    <li>회원이 서비스를 이용하는 과정에서 외부 사이트로 이동하는 경우, 해당 사이트의 이용약관이 적용됩니다.</li>
                    <li>회사는 필요에 따라 본 약관을 개정할 수 있으며, 개정 시 사전 공지합니다.</li>
                  </ol>
                </section>

                <p className="text-sm mt-8 font-medium">
                  본 약관은 2025년 4월10일부터 적용됩니다.
                </p>
              </div>
            </CardContent>
          </Card>
        </main>
        
        <Footer />
      </div>
    </div>
  )
} 