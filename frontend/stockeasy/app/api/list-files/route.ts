import { NextRequest, NextResponse } from 'next/server';
import fs from 'fs';
import path from 'path';

/**
 * 디렉토리 내 파일 목록을 반환하는 API 라우트
 * @param request NextRequest 객체
 * @returns 파일 목록을 담은 JSON 응답
 */
export async function GET(request: NextRequest) {
  try {
    // URL에서 디렉토리 파라미터 가져오기
    const { searchParams } = new URL(request.url);
    const directory = searchParams.get('directory');

    // 디렉토리 파라미터가 없으면 에러 반환
    if (!directory) {
      return NextResponse.json({ error: '디렉토리 파라미터가 필요합니다.' }, { status: 400 });
    }

    // 디렉토리 경로 생성 (public 폴더 내부)
    const dirPath = path.join(process.cwd(), 'public', directory);

    // 디렉토리가 존재하는지 확인
    if (!fs.existsSync(dirPath)) {
      return NextResponse.json({ error: '디렉토리가 존재하지 않습니다.' }, { status: 404 });
    }

    // 디렉토리 내 파일 목록 읽기
    const files = fs.readdirSync(dirPath);

    // CSV 파일만 필터링
    const csvFiles = files.filter(file => file.endsWith('.csv'));

    // 파일 목록 반환
    return NextResponse.json(csvFiles);
  } catch (error) {
    console.error('파일 목록 조회 중 오류 발생:', error);
    return NextResponse.json({ error: '파일 목록을 가져오는 중 오류가 발생했습니다.' }, { status: 500 });
  }
}
