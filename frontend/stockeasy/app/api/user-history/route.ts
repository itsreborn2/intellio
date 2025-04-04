import { NextRequest, NextResponse } from 'next/server';
import fs from 'fs';
import path from 'path';

// 히스토리 아이템 타입 정의
interface HistoryItem {
  id: string;
  stockName: string;
  stockCode?: string;
  prompt: string;
  timestamp: number;
  userId: string;
  responseId?: string;
}

// 데이터 파일 경로
const DATA_DIR = path.join(process.cwd(), 'data');
const HISTORY_FILE = path.join(DATA_DIR, 'user-history.json');

// 데이터 디렉토리 생성 함수
function ensureDataDirExists() {
  if (!fs.existsSync(DATA_DIR)) {
    fs.mkdirSync(DATA_DIR, { recursive: true });
  }
  if (!fs.existsSync(HISTORY_FILE)) {
    fs.writeFileSync(HISTORY_FILE, JSON.stringify([]), 'utf-8');
  }
}

// 히스토리 데이터 읽기 함수
function readHistoryData(): HistoryItem[] {
  ensureDataDirExists();
  try {
    const data = fs.readFileSync(HISTORY_FILE, 'utf-8');
    return JSON.parse(data);
  } catch (error) {
    console.error('히스토리 데이터 읽기 오류:', error);
    return [];
  }
}

// 히스토리 데이터 쓰기 함수
function writeHistoryData(data: HistoryItem[]) {
  ensureDataDirExists();
  try {
    fs.writeFileSync(HISTORY_FILE, JSON.stringify(data, null, 2), 'utf-8');
  } catch (error) {
    console.error('히스토리 데이터 쓰기 오류:', error);
  }
}

// 사용자 히스토리 조회 API
export async function GET(request: NextRequest) {
  try {
    const searchParams = request.nextUrl.searchParams;
    const userId = searchParams.get('userId');

    if (!userId) {
      return NextResponse.json({ error: '사용자 ID가 필요합니다.' }, { status: 400 });
    }

    // 사용자의 히스토리 조회 (최신순으로 정렬, 최대 20개)
    const allHistory = readHistoryData();
    const userHistory = allHistory
      .filter(item => item.userId === userId)
      .sort((a, b) => b.timestamp - a.timestamp)
      .slice(0, 20);

    return NextResponse.json({ history: userHistory });
  } catch (error) {
    console.error('사용자 히스토리 조회 오류:', error);
    return NextResponse.json({ error: '서버 오류가 발생했습니다.' }, { status: 500 });
  }
}

// 사용자 히스토리 저장 API
export async function POST(request: NextRequest) {
  try {
    const body = await request.json();
    const { id, stockName, stockCode, prompt, timestamp, userId, responseId } = body;

    if (!stockName || !prompt || !userId) {
      return NextResponse.json({ error: '필수 정보가 누락되었습니다.' }, { status: 400 });
    }

    // 새 히스토리 아이템 생성
    const newHistoryItem: HistoryItem = {
      id,
      stockName,
      stockCode,
      prompt,
      timestamp,
      userId,
      responseId
    };

    // 기존 히스토리 데이터 읽기
    const historyData = readHistoryData();
    
    // 새 아이템 추가
    historyData.push(newHistoryItem);
    
    // 데이터 저장
    writeHistoryData(historyData);

    return NextResponse.json({ success: true, history: newHistoryItem });
  } catch (error) {
    console.error('히스토리 저장 오류:', error);
    return NextResponse.json({ error: '서버 오류가 발생했습니다.' }, { status: 500 });
  }
}
