import { NextRequest, NextResponse } from 'next/server';
import { promises as fs } from 'fs';
import path from 'path';
// import { getServerSession } from 'next-auth';
// import { authOptions } from '../../auth/[...nextauth]/authOptions';

// 관리자 이메일 화이트리스트
// 관리자 이메일 목록 (공지사항 관리 권한)
const ADMIN_EMAILS = [
  'itsreborn2@gmail.com',
  'blueslame@gmail.com',
  'plana392@gmail.com',
];

// 저장 경로 (루트 기준)
const NOTICE_DIR = path.join(process.cwd(), 'public', 'requestfile', 'notice');
const NOTICE_FILE = path.join(NOTICE_DIR, 'notice.json');

export async function GET() {
  try {
    const data = await fs.readFile(NOTICE_FILE, 'utf-8');
    return NextResponse.json(JSON.parse(data));
  } catch (err) {
    return NextResponse.json({ error: '공지사항 파일을 찾을 수 없습니다.' }, { status: 404 });
  }
}

export async function POST(req: NextRequest) {
  // 인증: 쿠키에서 user 정보 추출
  // 쿠키 파싱 개선: 여러 쿠키 중 user 쿠키만 정확히 추출
  const cookieHeader = req.headers.get('cookie') || '';
  let userEmail = '';
  let userCookie = '';
  cookieHeader.split(';').forEach((c) => {
    const [key, ...val] = c.trim().split('=');
    if (key === 'user') userCookie = val.join('=');
  });
  if (userCookie) {
    try {
      const userDecoded = decodeURIComponent(userCookie);
      // 양쪽 쌍따옴표 제거 (쿠키가 문자열로 감싸져 있을 때를 대비)
      const cleaned = userDecoded.replace(/^"|"$/g, '');
      const userObj = JSON.parse(cleaned);
      userEmail = userObj?.email || '';
    } catch (e) {
      console.log('user 쿠키 파싱 오류:', e, userCookie);
    }
  }
  // 디버깅용 로그
  console.log('userEmail:', userEmail);
  if (!userEmail || !ADMIN_EMAILS.includes(userEmail)) {
    return NextResponse.json({ error: '권한이 없습니다.' }, { status: 403 });
  }

  try {
    const body = await req.json();
    // 디렉토리 없으면 생성
    await fs.mkdir(NOTICE_DIR, { recursive: true });
    // 파일 저장
    await fs.writeFile(NOTICE_FILE, JSON.stringify(body, null, 2), 'utf-8');
    return NextResponse.json({ success: true });
  } catch (err) {
    return NextResponse.json({ error: '공지사항 저장 실패' }, { status: 500 });
  }
}
