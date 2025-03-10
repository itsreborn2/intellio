import { NextResponse } from 'next/server';

/**
 * 하단 중앙 영역 API 핸들러
 * 
 * 하단 중앙 영역에 표시할 데이터를 제공합니다.
 * 현재는 임시 데이터를 반환하지만, 실제 백엔드 연동 시 이 부분을 수정하면 됩니다.
 */
export async function GET() {
  try {
    // 임시 데이터 생성 (예: 시장 지표 데이터)
    const marketIndicatorsData = {
      timestamp: Date.now(),
      indicators: [
        {
          id: 1,
          name: "KOSPI",
          value: 2756.23,
          change: 15.78,
          changePercent: 0.58,
          trend: "up",
          volume: 1234567890
        },
        {
          id: 2,
          name: "KOSDAQ",
          value: 876.45,
          change: -3.21,
          changePercent: -0.36,
          trend: "down",
          volume: 987654321
        },
        {
          id: 3,
          name: "원/달러",
          value: 1298.50,
          change: -2.30,
          changePercent: -0.18,
          trend: "down"
        },
        {
          id: 4,
          name: "국고채 3년",
          value: 3.45,
          change: 0.05,
          changePercent: 1.47,
          trend: "up"
        },
        {
          id: 5,
          name: "WTI",
          value: 78.65,
          change: 1.23,
          changePercent: 1.59,
          trend: "up"
        }
      ],
      marketSummary: {
        advancers: 458,
        decliners: 387,
        unchanged: 55,
        tradingVolume: 12345678901,
        tradingValue: 9876543210123
      }
    };

    // 응답 반환
    return NextResponse.json(marketIndicatorsData);
  } catch (error) {
    console.error('하단 중앙 영역 API 오류:', error);
    
    // 오류 응답 반환
    return NextResponse.json(
      { error: '요청을 처리하는 중 오류가 발생했습니다.' },
      { status: 500 }
    );
  }
}
