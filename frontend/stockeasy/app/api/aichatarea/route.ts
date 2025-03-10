import { NextResponse } from 'next/server';

/**
 * 채팅 API 핸들러
 * 
 * 클라이언트로부터 메시지와 종목 정보를 받아 처리하고 응답을 반환합니다.
 */
export async function POST(request: Request) {
  try {
    // 요청 본문 파싱
    const body = await request.json();
    const { message, stockInfo } = body;

    // 로그 출력
    console.log('받은 메시지:', message);
    console.log('종목 정보:', stockInfo);

    // 백엔드에서 데이터를 처리하는 로직 구현 필요
    
    // 응답 반환
    return NextResponse.json({
      content: "백엔드 연동 필요",
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
