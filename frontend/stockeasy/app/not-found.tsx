export default function NotFound() {
  return (
    <div className="flex items-center justify-center min-h-screen bg-background">
      <div className="text-center">
        <h2 className="text-3xl font-bold">404</h2>
        <p className="mt-4 text-xl">페이지를 찾을 수 없습니다.</p>
        <p className="mt-2 text-muted-foreground">
          요청하신 페이지가 존재하지 않거나 이동되었습니다.
        </p>
        <a
          href="/"
          className="inline-block mt-8 px-6 py-3 bg-primary text-primary-foreground rounded-md hover:bg-primary/90"
        >
          홈으로 돌아가기
        </a>
      </div>
    </div>
  )
} 