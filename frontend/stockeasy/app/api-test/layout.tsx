export default function ApiTestLayout({
  children,
}: {
  children: React.ReactNode
}) {
  return (
    <div className="container mx-auto py-4">
      <div className="mb-6">
        <h1 className="text-2xl font-bold text-gray-900 mb-2">
          API 테스트 페이지
        </h1>
        <p className="text-gray-600">
          백엔드 증권 데이터 수집 서비스 API 엔드포인트 테스트
        </p>
      </div>
      {children}
    </div>
  )
} 