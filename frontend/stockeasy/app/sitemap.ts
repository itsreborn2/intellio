import { MetadataRoute } from 'next'

export default function sitemap(): MetadataRoute.Sitemap {
  const baseUrl = process.env.SITE_URL || 'https://stockeasy.intellio.kr'

  // 기본 페이지 URL들
  const routes = [
    '',
    '/rs-rank',
    '/etf-sector',
    '/value',
    // 추가적인 정적 페이지들
  ].map((route) => ({
    url: `${baseUrl}${route}`,
    lastModified: new Date().toISOString(),
    changeFrequency: 'weekly' as const,
    priority: route === '' ? 1 : 0.8,
  }))

  // 동적으로 생성되는 페이지들은 여기에 추가함함
  // 예: 종목 상세 페이지, 포트폴리오 상세 등
  // const stocks = await fetchStocks()
  // const stockRoutes = stocks.map((stock) => ({
  //   url: `${baseUrl}/stocks/${stock.id}`,
  //   lastModified: stock.updatedAt,
  //   changeFrequency: 'daily' as const,
  //   priority: 0.7,
  // }))

  return [
    ...routes,
    // ...stockRoutes,
  ]
} 