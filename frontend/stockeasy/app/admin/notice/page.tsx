// 1. 관리자 페이지 라우트/파일 생성
// 2. 구글 로그인 세션 확인 및 관리자 이메일 화이트리스트 체크
// 3. 비관리자 접근 시 차단/리다이렉트 처리
// 4. 공지사항 데이터 타입 정의 (title, content, show 등)
// 5. 기존 공지사항 데이터 GET(`/api/notice`)로 불러오기
// 6. 공지사항 작성/수정 UI 구현 (제목, 내용, show, todayOnly 등)
// 7. 저장 버튼 → `/api/notice`로 POST 요청
// 8. 저장 성공/실패 시 토스트 알림
// 9. 저장 후 최신 데이터로 갱신
// 10. 코드/주석 꼼꼼하게 작성 및 정리

'use client';
import React, { useEffect, useState } from 'react';
// import { useSession } from 'next-auth/react';
import { parseCookies } from 'nookies';
import { useRouter } from 'next/navigation';
import { Button } from 'intellio-common/components/ui/button';
import { Input } from 'intellio-common/components/ui/input';
import { Textarea } from '@/components/ui/textarea';
import { Switch } from '@/components/ui/switch';

// 관리자 이메일 화이트리스트
const ADMIN_EMAILS = ['itsreborn2@gmail.com'];

// 공지사항 데이터 타입
interface NoticeData {
  title: string;
  content: string;
  show: boolean;
  todayOnly?: boolean;
  updatedAt?: string;
}

export default function NoticeAdminPage() {
  // 쿠키에서 user 정보 추출 및 관리자 이메일 체크
  const router = useRouter();
  const [isAdmin, setIsAdmin] = useState(false);
  useEffect(() => {
    const cookies = parseCookies();
    let email = '';
    if (cookies.user) {
      try {
        const user = JSON.parse(decodeURIComponent(cookies.user));
        email = user?.email || '';
      } catch {}
    }
    if (ADMIN_EMAILS.includes(email)) setIsAdmin(true);
    else {
      setIsAdmin(false);
      setToast('관리자만 접근 가능합니다.');
      setTimeout(() => router.replace('/'), 1500);
    }
  }, [router]);

  // 공지사항 상태
  const [notice, setNotice] = useState<NoticeData>({
    title: '',
    content: '',
    show: true,
    todayOnly: false,
  });
  const [loading, setLoading] = useState(false);
  const [saving, setSaving] = useState(false);
  const [toast, setToast] = useState<string|null>(null);

  // 2. 관리자 이메일 체크 및 비관리자 접근 차단

  // 5. 기존 공지사항 불러오기
  useEffect(() => {
    setLoading(true);
    fetch('/api/notice')
      .then(res => res.ok ? res.json() : Promise.reject('공지 없음'))
      .then(data => setNotice(data))
      .catch(() => setNotice({ title: '', content: '', show: true, todayOnly: false }))
      .finally(() => setLoading(false));
  }, []);

  // 입력 핸들러
  function handleChange(e: React.ChangeEvent<HTMLInputElement | HTMLTextAreaElement>) {
    const { name, value, type } = e.target as HTMLInputElement;
    setNotice(prev => ({
      ...prev,
      [name]: type === 'checkbox' ? (e.target as HTMLInputElement).checked : value,
    }));
  }
  function handleSwitch(name: keyof NoticeData, value: boolean) {
    setNotice(prev => ({ ...prev, [name]: value }));
  }

  // 저장
  async function handleSave() {
    setSaving(true);
    setToast(null);
    try {
      // credentials: 'include' 옵션을 추가하여 쿠키가 서버로 전달되도록 함
      const res = await fetch('/api/notice', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ ...notice, updatedAt: new Date().toISOString() }),
        credentials: 'include',
      });
      if (!res.ok) throw new Error('저장 실패');
      setToast('공지사항이 저장되었습니다.');
      // 저장 성공 시 최신 데이터로 갱신
      fetch('/api/notice', { credentials: 'include' })
        .then(res => res.ok ? res.json() : Promise.reject('공지 없음'))
        .then(data => setNotice(data));
    } catch {
      setToast('저장에 실패했습니다.');
    } finally {
      setSaving(false);
    }
  }

  if (!isAdmin) return null;
  return (
    <div className="max-w-lg mx-auto mt-10 p-6 bg-white rounded-lg shadow-md border">
      <h1 className="text-2xl font-bold mb-4">공지사항 관리</h1>
      {toast && <div className="mb-4 text-sm text-center text-red-500">{toast}</div>}
      <form onSubmit={e => { e.preventDefault(); handleSave(); }}>
        <label className="block mb-2 font-semibold">제목</label>
        <Input name="title" value={notice.title} onChange={handleChange} required className="mb-4" style={{ borderRadius: 4 }} />
        <label className="block mb-2 font-semibold">내용</label>
        <Textarea name="content" value={notice.content} onChange={handleChange} required rows={5} className="mb-4" style={{ borderRadius: 4 }} />
        {/* 공지 노출/오늘만 노출 스위치 - 활성/비활성 시각 강조 */}
        <div className="flex items-center gap-4 mb-4">
          <span className={notice.show ? 'text-blue-600 font-bold' : 'text-gray-400'}>
            공지 노출
          </span>
          <Switch 
            checked={notice.show} 
            onCheckedChange={(v: boolean) => handleSwitch('show', v)} 
            className={notice.show ? 'bg-blue-500 border-blue-500' : 'bg-gray-200 border-gray-300'}
          />
          <span className={notice.todayOnly ? 'text-blue-600 font-bold' : 'text-gray-400'}>
            오늘만 노출
          </span>
          <Switch 
            checked={notice.todayOnly ?? false} 
            onCheckedChange={(v: boolean) => handleSwitch('todayOnly', v)} 
            className={notice.todayOnly ? 'bg-blue-500 border-blue-500' : 'bg-gray-200 border-gray-300'}
          />
        </div>
        <Button type="submit" disabled={saving || loading} className="w-full">{saving ? '저장 중...' : '저장'}</Button>
      </form>
    </div>
  );
}
