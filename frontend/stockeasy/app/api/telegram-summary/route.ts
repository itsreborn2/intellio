import { NextResponse } from 'next/server';

/**
 * 텔레그램 요약 API 핸들러
 * 
 * 텔레그램 채널에서 수집된 주식 관련 정보를 요약하여 제공합니다.
 * 현재는 임시 데이터를 반환하지만, 실제 백엔드 연동 시 이 부분을 수정하면 됩니다.
 */
export async function GET() {
  try {
    // 임시 데이터 생성
    const summaryData = {
      timestamp: Date.now(),
      summaries: [
        {
          id: 1,
          source: "주식 정보 채널",
          timestamp: Date.now() - 3600000, // 1시간 전
          content: "삼성전자, 신규 메모리 칩 생산 라인 확장 발표. 향후 5년간 10조원 투자 계획.",
          sentiment: "positive"
        },
        {
          id: 2,
          source: "마켓 인사이트",
          timestamp: Date.now() - 7200000, // 2시간 전
          content: "KOSPI, 미국 고용지표 호조에 상승 마감. 외국인 매수세 유입 지속.",
          sentiment: "positive"
        },
        {
          id: 3,
          source: "글로벌 마켓 뉴스",
          timestamp: Date.now() - 10800000, // 3시간 전
          content: "미 연준, 금리 동결 결정. 향후 금리 인하 가능성 시사에 시장 긍정적 반응.",
          sentiment: "neutral"
        },
        {
          id: 4,
          source: "테크 스톡 알리미",
          timestamp: Date.now() - 14400000, // 4시간 전
          content: "애플, 신규 AI 기능 탑재한 iOS 업데이트 발표. 관련 부품 공급사 주가 상승.",
          sentiment: "positive"
        },
        {
          id: 5,
          source: "금융 뉴스 속보",
          timestamp: Date.now() - 18000000, // 5시간 전
          content: "원/달러 환율, 1,300원 선 붕괴. 수출 기업 실적 전망 악화 우려.",
          sentiment: "negative"
        }
      ]
    };

    // 응답 반환
    return NextResponse.json(summaryData);
  } catch (error) {
    console.error('텔레그램 요약 API 오류:', error);
    
    // 오류 응답 반환
    return NextResponse.json(
      { error: '요청을 처리하는 중 오류가 발생했습니다.' },
      { status: 500 }
    );
  }
}
