import { NextResponse } from 'next/server';

/**
 * 하단 우측 영역 2 API 핸들러
 * 
 * 하단 우측 영역 2에 표시할 데이터를 제공합니다.
 * 현재는 임시 데이터를 반환하지만, 실제 백엔드 연동 시 이 부분을 수정하면 됩니다.
 */
export async function GET() {
  try {
    // 임시 데이터 생성 (예: 시장 뉴스 데이터)
    const marketNewsData = {
      timestamp: Date.now(),
      news: [
        {
          id: 1,
          title: "삼성전자, 신규 반도체 공장 건설 계획 발표",
          summary: "삼성전자가 평택에 30조원 규모의 신규 반도체 공장 건설 계획을 발표했습니다. 이번 투자는 메모리 반도체 생산 능력 확대를 위한 것으로, 2027년 완공 예정입니다.",
          source: "경제신문",
          publishedAt: Date.now() - 3600000, // 1시간 전
          relatedStocks: ["005930", "000660"],
          sentiment: "positive"
        },
        {
          id: 2,
          title: "미 연준, 금리 동결 결정... 향후 인하 가능성 시사",
          summary: "미국 연방준비제도(Fed)가 기준금리를 현 수준에서 동결하기로 결정했습니다. 다만 인플레이션 안정화에 따라 올해 하반기 금리 인하 가능성을 시사했습니다.",
          source: "글로벌 경제",
          publishedAt: Date.now() - 7200000, // 2시간 전
          relatedStocks: [],
          sentiment: "neutral"
        },
        {
          id: 3,
          title: "LG에너지솔루션, 북미 전기차 배터리 공급 계약 체결",
          summary: "LG에너지솔루션이 북미 주요 전기차 제조사와 대규모 배터리 공급 계약을 체결했습니다. 계약 규모는 약 5조원으로 추정되며, 향후 5년간 안정적인 매출이 기대됩니다.",
          source: "산업뉴스",
          publishedAt: Date.now() - 10800000, // 3시간 전
          relatedStocks: ["373220", "051910"],
          sentiment: "positive"
        },
        {
          id: 4,
          title: "원/달러 환율, 1,300원 선 붕괴... 수출 기업 실적 우려",
          summary: "원/달러 환율이 1,300원 선을 붕괴하며 급등세를 보이고 있습니다. 환율 상승으로 수출 기업들의 실적 악화 우려가 커지고 있으며, 수입 물가 상승에 따른 인플레이션 압력도 우려됩니다.",
          source: "금융정보",
          publishedAt: Date.now() - 14400000, // 4시간 전
          relatedStocks: [],
          sentiment: "negative"
        },
        {
          id: 5,
          title: "네이버, 글로벌 AI 기업과 전략적 제휴 발표",
          summary: "네이버가 글로벌 AI 기업과 전략적 제휴를 맺고 AI 기술 개발 및 서비스 확대에 나섭니다. 이번 제휴를 통해 검색, 커머스 등 주요 서비스에 고도화된 AI 기술을 적용할 예정입니다.",
          source: "IT뉴스",
          publishedAt: Date.now() - 18000000, // 5시간 전
          relatedStocks: ["035420", "035720"],
          sentiment: "positive"
        }
      ]
    };

    // 응답 반환
    return NextResponse.json(marketNewsData);
  } catch (error) {
    console.error('하단 우측 영역 2 API 오류:', error);
    
    // 오류 응답 반환
    return NextResponse.json(
      { error: '요청을 처리하는 중 오류가 발생했습니다.' },
      { status: 500 }
    );
  }
}
