import { NextResponse } from 'next/server';

/**
 * 채팅 API 핸들러
 * 
 * 클라이언트로부터 메시지와 종목 정보를 받아 처리하고 응답을 반환합니다.
 * 현재는 임시 응답을 생성하지만, 실제 백엔드 연동 시 이 부분을 수정하면 됩니다.
 */
export async function POST(request: Request) {
  try {
    // 요청 본문 파싱
    const body = await request.json();
    const { message, stockInfo } = body;

    // 로그 출력
    console.log('받은 메시지:', message);
    console.log('종목 정보:', stockInfo);

    // 응답 생성 (임시 응답)
    let responseContent = '';
    
    if (stockInfo) {
      // 종목 정보가 있는 경우 종목 관련 응답 생성
      responseContent = generateStockResponse(message, stockInfo);
    } else {
      // 일반 질문에 대한 응답 생성
      responseContent = generateGeneralResponse(message);
    }

    // 응답 반환
    return NextResponse.json({
      content: responseContent,
      timestamp: Date.now()
    });
  } catch (error) {
    console.error('채팅 API 오류:', error);
    
    // 오류 응답 반환
    return NextResponse.json(
      { error: '요청을 처리하는 중 오류가 발생했습니다.' },
      { status: 500 }
    );
  }
}

/**
 * 종목 관련 응답 생성 함수
 * 
 * 종목 정보와 메시지를 기반으로 임시 응답을 생성합니다.
 * 실제 백엔드 연동 시 이 함수를 수정하여 실제 데이터를 반환하도록 합니다.
 */
function generateStockResponse(message: string, stockInfo: { stockName: string; stockCode: string }) {
  const { stockName, stockCode } = stockInfo;
  
  // 메시지 내용에 따라 다른 응답 생성
  if (message.includes('가격') || message.includes('시세')) {
    return `${stockName}(${stockCode})의 현재 시세는 다음과 같습니다:\n\n• 현재가: 45,600원\n• 전일대비: ▲ 1,200원 (2.7%)\n• 거래량: 1,245,678주\n• 52주 최고: 51,200원\n• 52주 최저: 32,400원\n\n※ 위 정보는 임시 데이터입니다.`;
  }
  
  if (message.includes('전망') || message.includes('예측') || message.includes('분석')) {
    return `${stockName}(${stockCode})에 대한 시장 전망은 다음과 같습니다:\n\n최근 ${stockName}은(는) 분기별 실적 발표에서 시장 예상치를 상회하는 성과를 보였습니다. 주요 사업 부문의 성장세가 지속되고 있으며, 특히 신규 사업 확장에 따른 긍정적인 효과가 나타나고 있습니다.\n\n애널리스트들은 향후 12개월 동안 주가 상승 가능성을 전망하고 있으며, 목표가는 현재가 대비 15~20% 상승한 수준입니다.\n\n※ 위 정보는 임시 데이터입니다.`;
  }
  
  if (message.includes('재무') || message.includes('실적')) {
    return `${stockName}(${stockCode})의 최근 재무 정보는 다음과 같습니다:\n\n• 매출액: 8조 5,600억원 (전년 대비 12% 증가)\n• 영업이익: 1조 2,300억원 (전년 대비 8% 증가)\n• 순이익: 9,800억원 (전년 대비 15% 증가)\n• EPS: 5,420원\n• PER: 8.41배\n• PBR: 1.2배\n• ROE: 14.2%\n\n※ 위 정보는 임시 데이터입니다.`;
  }
  
  if (message.includes('뉴스') || message.includes('소식')) {
    return `${stockName}(${stockCode}) 관련 최근 주요 뉴스:\n\n1. ${stockName}, 신규 사업 확장 위한 전략적 파트너십 체결\n2. ${stockName}, 해외 시장 진출 가속화... 글로벌 경쟁력 강화\n3. ${stockName}, 친환경 기술 개발에 5년간 1조원 투자 계획 발표\n4. 애널리스트들 "${stockName}, 업황 개선으로 실적 턴어라운드 기대"\n\n※ 위 정보는 임시 데이터입니다.`;
  }
  
  // 기본 응답
  return `${stockName}(${stockCode})에 대한 정보입니다:\n\n${stockName}은(는) 한국 증시에 상장된 기업으로, 주요 사업 영역은 제조업, IT 서비스, 소비재 등 다양한 분야를 포함하고 있습니다. 최근 실적은 안정적인 성장세를 보이고 있으며, 시장에서의 경쟁력을 강화하기 위한 다양한 전략을 추진하고 있습니다.\n\n더 구체적인 정보를 원하시면 '가격', '전망', '재무', '뉴스' 등의 키워드로 질문해 주세요.\n\n※ 위 정보는 임시 데이터입니다.`;
}

/**
 * 일반 질문에 대한 응답 생성 함수
 * 
 * 종목 정보 없이 일반 메시지에 대한 임시 응답을 생성합니다.
 * 실제 백엔드 연동 시 이 함수를 수정하여 실제 데이터를 반환하도록 합니다.
 */
function generateGeneralResponse(message: string) {
  if (message.includes('안녕') || message.includes('반가워')) {
    return '안녕하세요! StockEasy 어시스턴트입니다. 어떤 종목에 대해 알고 싶으신가요?';
  }
  
  if (message.includes('도움') || message.includes('사용법') || message.includes('기능')) {
    return '저는 주식 정보를 제공하는 StockEasy 어시스턴트입니다.\n\n다음과 같은 기능을 제공합니다:\n\n• 종목 검색 및 선택\n• 종목 시세 정보 제공\n• 종목 분석 및 전망 정보\n• 재무 정보 및 주요 지표\n• 관련 뉴스 및 소식\n\n종목을 선택하고 질문을 입력하시면 관련 정보를 제공해 드립니다.';
  }
  
  if (message.includes('추천') || message.includes('좋은 종목')) {
    return '투자 결정은 개인의 투자 성향, 목표, 위험 감수 능력 등을 종합적으로 고려하여 신중하게 이루어져야 합니다. 저는 특정 종목을 추천하거나 투자 조언을 제공하지 않습니다.\n\n다만, 관심 있는 종목에 대한 정보를 검색하여 제공해 드릴 수 있습니다. 어떤 종목에 관심이 있으신가요?';
  }
  
  // 기본 응답
  return '안녕하세요! StockEasy 어시스턴트입니다. 종목을 선택하고 질문을 입력하시면 관련 정보를 제공해 드립니다. 어떤 종목에 관심이 있으신가요?';
}
