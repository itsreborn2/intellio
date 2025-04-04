import { NextRequest, NextResponse } from 'next/server';
import fs from 'fs';
import path from 'path';

// 분석 결과 타입 정의
interface AnalysisResult {
  id: string;
  content: string;
  stockName: string;
  stockCode?: string;
  prompt: string;
  timestamp: number;
  userId?: string;
}

// 데이터 파일 경로
const DATA_DIR = path.join(process.cwd(), 'data');
const ANALYSIS_FILE = path.join(DATA_DIR, 'analysis-results.json');

// 데이터 디렉토리 생성 함수
function ensureDataDirExists() {
  if (!fs.existsSync(DATA_DIR)) {
    fs.mkdirSync(DATA_DIR, { recursive: true });
  }
  if (!fs.existsSync(ANALYSIS_FILE)) {
    fs.writeFileSync(ANALYSIS_FILE, JSON.stringify([]), 'utf-8');
  }
}

// 분석 결과 데이터 읽기 함수
function readAnalysisData(): AnalysisResult[] {
  ensureDataDirExists();
  try {
    const data = fs.readFileSync(ANALYSIS_FILE, 'utf-8');
    return JSON.parse(data);
  } catch (error) {
    console.error('분석 결과 데이터 읽기 오류:', error);
    return [];
  }
}

// 분석 결과 데이터 쓰기 함수
function writeAnalysisData(data: AnalysisResult[]) {
  ensureDataDirExists();
  try {
    fs.writeFileSync(ANALYSIS_FILE, JSON.stringify(data, null, 2), 'utf-8');
  } catch (error) {
    console.error('분석 결과 데이터 쓰기 오류:', error);
  }
}

// 분석 결과 조회 API
export async function GET(request: NextRequest) {
  try {
    const searchParams = request.nextUrl.searchParams;
    const responseId = searchParams.get('responseId');

    if (!responseId) {
      return NextResponse.json({ error: '분석 결과 ID가 필요합니다.' }, { status: 400 });
    }

    // 분석 결과 조회
    const allResults = readAnalysisData();
    const result = allResults.find(item => item.id === responseId);

    if (!result) {
      return NextResponse.json({ error: '분석 결과를 찾을 수 없습니다.' }, { status: 404 });
    }

    return NextResponse.json({ result: result.content });
  } catch (error) {
    console.error('분석 결과 조회 오류:', error);
    return NextResponse.json({ error: '서버 오류가 발생했습니다.' }, { status: 500 });
  }
}

// 분석 결과 저장 API
export async function POST(request: NextRequest) {
  try {
    const body = await request.json();
    const { id, content, stockName, stockCode, prompt, timestamp, userId } = body;

    if (!id || !content || !stockName || !prompt) {
      return NextResponse.json({ error: '필수 정보가 누락되었습니다.' }, { status: 400 });
    }

    // 새 분석 결과 아이템 생성
    const newAnalysisResult: AnalysisResult = {
      id,
      content,
      stockName,
      stockCode,
      prompt,
      timestamp,
      userId
    };

    // 기존 분석 결과 데이터 읽기
    const analysisData = readAnalysisData();
    
    // 이미 존재하는 ID가 있는지 확인
    const existingIndex = analysisData.findIndex(item => item.id === id);
    
    if (existingIndex !== -1) {
      // 기존 분석 결과 업데이트
      analysisData[existingIndex] = newAnalysisResult;
    } else {
      // 새 분석 결과 추가
      analysisData.push(newAnalysisResult);
    }
    
    // 데이터 저장
    writeAnalysisData(analysisData);

    return NextResponse.json({ success: true, result: newAnalysisResult });
  } catch (error) {
    console.error('분석 결과 저장 오류:', error);
    return NextResponse.json({ error: '서버 오류가 발생했습니다.' }, { status: 500 });
  }
}
