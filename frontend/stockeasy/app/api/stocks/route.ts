import { NextResponse } from 'next/server';
import fs from 'fs';
import path from 'path';
import Papa from 'papaparse';

// CSV 파일에서 종목 리스트를 가져오는 API 라우트
export async function GET() {
  try {
    // 로컬 CSV 파일 경로 (새 경로로 변경)
    const filePath = path.join(process.cwd(), 'public', 'Stocklist.csv');
    
    console.log('CSV 파일 경로:', filePath);
    
    // CSV 파일 존재 확인
    if (!fs.existsSync(filePath)) {
      console.error('CSV 파일이 존재하지 않습니다:', filePath);
      return NextResponse.json({ error: 'CSV 파일이 존재하지 않습니다' }, { status: 404 });
    }
    
    // CSV 파일 읽기
    const fileContent = fs.readFileSync(filePath, 'utf-8');
    
    // 디버깅을 위한 로그
    console.log('CSV 파일 내용 일부:', fileContent.substring(0, 200));
    console.log('CSV 파일 크기:', fileContent.length, '바이트');
    
    // CSV 파싱
    const results = Papa.parse(fileContent, {
      header: true,
      skipEmptyLines: true
    });
    
    console.log('파싱된 데이터 샘플:', results.data.slice(0, 3));
    console.log('데이터 총 개수:', results.data.length);
    
    // 중복 제거를 위한 Set 생성
    const uniqueStocks = new Set();
    
    // 종목 데이터 추출 (종목명(종목코드) 형식으로 변경)
    const stockOptions = results.data
      .filter((row: any) => row.종목명 && row.종목코드) // 종목명과 종목코드가 있는 행만 필터링
      .filter((row: any) => {
        // 중복 제거 (같은 종목코드는 한 번만 포함)
        if (uniqueStocks.has(row.종목코드)) {
          return false;
        }
        uniqueStocks.add(row.종목코드);
        return true;
      })
      .map((row: any) => ({
        value: row.종목코드, // 값은 종목코드로 설정
        label: `${row.종목명}(${row.종목코드})` // 라벨은 종목명(종목코드)로 설정
      }));
    
    console.log('추출된 종목 수:', stockOptions.length);
    console.log('종목 샘플:', stockOptions.slice(0, 5));
    
    // 결과 반환
    return NextResponse.json(stockOptions);
  } catch (error) {
    console.error('종목 리스트 가져오기 오류:', error);
    return NextResponse.json({ error: '종목 리스트를 가져올 수 없습니다.' }, { status: 500 });
  }
}

/**
 * Google Drive 파일 프록시 API
 * 클라이언트에서 CORS 문제 없이 Google Drive 파일에 접근할 수 있도록 중계 역할을 함
 * 
 * @param request POST 요청 (fileId를 포함한 JSON 본문)
 * @returns CSV 파일 내용 또는 오류 응답
 */
export async function POST(request: Request) {
  try {
    // 요청 본문에서 fileId 추출
    const { fileId } = await request.json();
    
    if (!fileId) {
      console.error('fileId가 제공되지 않았습니다.');
      return NextResponse.json(
        { error: 'fileId가 필요합니다.' },
        { status: 400 }
      );
    }
    
    console.log('Google Drive 파일 ID:', fileId);
    
    // Google Drive 공유 링크에서 직접 다운로드 URL로 변환
    // 공유 링크 형식: https://drive.google.com/file/d/{fileId}/view?usp=sharing
    // 다운로드 링크 형식: https://drive.google.com/uc?export=download&id={fileId}
    const downloadUrl = `https://drive.google.com/uc?export=download&id=${fileId}`;
    
    // 대체 URL 형식들 (필요시 주석 해제하여 사용)
    // const downloadUrl = `https://drive.usercontent.google.com/download?id=${fileId}&export=download&authuser=0`;
    // const downloadUrl = `https://docs.google.com/uc?export=download&id=${fileId}`;
    
    console.log('서버에서 Google Drive 파일 다운로드 시도:', downloadUrl);
    
    try {
      // AbortController를 사용하여 타임아웃 구현
      const controller = new AbortController();
      const timeoutId = setTimeout(() => controller.abort(), 5000); // 5초 타임아웃
      
      // 서버 측에서 Google Drive 파일 요청 (CORS 제한 없음)
      const response = await fetch(downloadUrl, {
        // 추가 옵션으로 요청 시도
        headers: {
          'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
        },
        redirect: 'follow', // 리다이렉트 자동 처리
        signal: controller.signal, // AbortController 연결
      });
      
      // 타임아웃 해제
      clearTimeout(timeoutId);
      
      console.log('Google Drive 응답 상태:', response.status, response.statusText);
      console.log('Google Drive 응답 헤더:', JSON.stringify(Object.fromEntries(response.headers.entries())));
      
      if (!response.ok) {
        console.error('Google Drive 파일 다운로드 실패:', response.status, response.statusText);
        return NextResponse.json(
          { error: `Google Drive 파일 다운로드 실패: ${response.status} ${response.statusText}` },
          { status: response.status }
        );
      }
      
      // 파일 내용 가져오기
      const fileContent = await response.text();
      console.log('파일 내용 일부:', fileContent.substring(0, 100));
      
      // CSV 파일 내용 반환
      return new NextResponse(fileContent, {
        headers: {
          'Content-Type': 'text/csv; charset=utf-8',
        },
      });
    } catch (fetchError) {
      console.error('Google Drive 파일 가져오기 오류 (상세):', fetchError);
      
      // 로컬 파일 사용 시도 (대체 방법)
      try {
        console.log('로컬 CSV 파일 사용 시도...');
        // 로컬 파일 경로 수정 - public 폴더 내의 RS_Result.csv 파일 사용
        const filePath = path.join(process.cwd(), 'public', 'RS_Result.csv');
        
        if (!fs.existsSync(filePath)) {
          console.error('로컬 CSV 파일이 존재하지 않습니다:', filePath);
          throw new Error('로컬 CSV 파일이 존재하지 않습니다');
        }
        
        const fileContent = fs.readFileSync(filePath, 'utf-8');
        console.log('로컬 파일 내용 일부:', fileContent.substring(0, 100));
        
        return new NextResponse(fileContent, {
          headers: {
            'Content-Type': 'text/csv; charset=utf-8',
          },
        });
      } catch (localError) {
        console.error('로컬 파일 가져오기 오류:', localError);
        throw new Error('Google Drive 및 로컬 파일 모두 가져오기 실패');
      }
    }
  } catch (error: any) {
    console.error('Google Drive 프록시 오류 (전체):', error);
    return NextResponse.json(
      { error: `파일을 가져오는 중 오류가 발생했습니다: ${error.message || '알 수 없는 오류'}` },
      { status: 500 }
    );
  }
}
