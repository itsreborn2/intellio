import { NextResponse } from 'next/server';

/**
 * 하단 우측 영역 1 API 핸들러
 * 
 * 하단 우측 영역 1에 표시할 데이터를 제공합니다.
 * 현재는 임시 데이터를 반환하지만, 실제 백엔드 연동 시 이 부분을 수정하면 됩니다.
 */
export async function GET() {
  try {
    // 임시 데이터 생성 (예: 인기 종목 데이터)
    const popularStocksData = {
      timestamp: Date.now(),
      popularStocks: [
        {
          id: 1,
          stockCode: "005930",
          stockName: "삼성전자",
          currentPrice: 78500,
          change: 1500,
          changePercent: 1.95,
          volume: 12345678,
          marketCap: 4680000000000
        },
        {
          id: 2,
          stockCode: "000660",
          stockName: "SK하이닉스",
          currentPrice: 156000,
          change: 3000,
          changePercent: 1.96,
          volume: 5678901,
          marketCap: 1134000000000
        },
        {
          id: 3,
          stockCode: "035420",
          stockName: "NAVER",
          currentPrice: 234500,
          change: -2500,
          changePercent: -1.05,
          volume: 1234567,
          marketCap: 385000000000
        },
        {
          id: 4,
          stockCode: "035720",
          stockName: "카카오",
          currentPrice: 67800,
          change: -1200,
          changePercent: -1.74,
          volume: 3456789,
          marketCap: 301000000000
        },
        {
          id: 5,
          stockCode: "051910",
          stockName: "LG화학",
          currentPrice: 567000,
          change: 12000,
          changePercent: 2.16,
          volume: 456789,
          marketCap: 400000000000
        }
      ],
      categories: {
        mostActive: ["005930", "000660", "035420"],
        biggestGainers: ["051910", "000660", "005930"],
        biggestLosers: ["035420", "035720"]
      }
    };

    // 응답 반환
    return NextResponse.json(popularStocksData);
  } catch (error) {
    console.error('하단 우측 영역 1 API 오류:', error);
    
    // 오류 응답 반환
    return NextResponse.json(
      { error: '요청을 처리하는 중 오류가 발생했습니다.' },
      { status: 500 }
    );
  }
}
