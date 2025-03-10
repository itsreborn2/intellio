import { NextResponse } from 'next/server';

/**
 * 하단 좌측 영역 API 핸들러
 * 
 * 하단 좌측 영역에 표시할 데이터를 제공합니다.
 * 현재는 임시 데이터를 반환하지만, 실제 백엔드 연동 시 이 부분을 수정하면 됩니다.
 */
export async function GET() {
  try {
    // 임시 데이터 생성 (예: 시장 동향 데이터)
    const marketTrendData = {
      timestamp: Date.now(),
      trends: [
        {
          id: 1,
          sector: "IT/반도체",
          change: 2.1,
          volume: 1254789,
          topGainers: ["삼성전자", "SK하이닉스", "LG전자"],
          topLosers: ["네이버", "카카오"]
        },
        {
          id: 2,
          sector: "금융",
          change: -0.8,
          volume: 987654,
          topGainers: ["KB금융", "신한지주"],
          topLosers: ["하나금융", "우리금융", "미래에셋증권"]
        },
        {
          id: 3,
          sector: "제약/바이오",
          change: 1.5,
          volume: 754321,
          topGainers: ["셀트리온", "삼성바이오로직스", "SK바이오사이언스"],
          topLosers: ["한미약품"]
        },
        {
          id: 4,
          sector: "화학",
          change: -1.2,
          volume: 543210,
          topGainers: ["LG화학"],
          topLosers: ["롯데케미칼", "SK이노베이션", "S-Oil"]
        },
        {
          id: 5,
          sector: "자동차",
          change: 0.7,
          volume: 432109,
          topGainers: ["현대차", "기아"],
          topLosers: ["현대모비스"]
        }
      ]
    };

    // 응답 반환
    return NextResponse.json(marketTrendData);
  } catch (error) {
    console.error('하단 좌측 영역 API 오류:', error);
    
    // 오류 응답 반환
    return NextResponse.json(
      { error: '요청을 처리하는 중 오류가 발생했습니다.' },
      { status: 500 }
    );
  }
}
