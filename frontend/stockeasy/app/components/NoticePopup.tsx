// 공지사항 팝업 컴포넌트
// - 카드형 UI, 오늘 하루/1주일 안보기 버튼, localStorage 연동
// - Shadcn UI, Tailwind 사용
// - 공지 데이터 타입: { title, content, show, todayOnly, updatedAt }

'use client';
import React, { useEffect, useState } from 'react';

interface NoticeData {
  title: string;
  content: string;
  show: boolean;
  todayOnly?: boolean;
  updatedAt?: string;
}

interface NoticePopupProps {
  notice: NoticeData;
  onClose: () => void;
}

// localStorage 키
const LS_KEY = 'stockeasy_notice_hide_until';
const LS_ID_KEY = 'stockeasy_notice_last_id';

export function NoticePopup({ notice, onClose }: NoticePopupProps) {
  const [hide, setHide] = useState(false);

  // 공지 ID: updatedAt + title 조합
  const noticeId = `${notice.updatedAt ?? ''}_${notice.title}`;

  // 오늘 날짜(YYYY-MM-DD)
  function todayStr() {
    return new Date().toISOString().slice(0, 10);
  }

  // 1주일 뒤 날짜(YYYY-MM-DD)
  function weekLaterStr() {
    const d = new Date();
    d.setDate(d.getDate() + 7);
    return d.toISOString().slice(0, 10);
  }

  // localStorage에 숨김 정보 저장
  function hideFor(dateStr: string) {
    localStorage.setItem(LS_KEY, dateStr);
    localStorage.setItem(LS_ID_KEY, noticeId);
    setHide(true);
    onClose();
  }

  // 렌더 조건: show=false 이거나 숨김 설정이면 렌더X
  useEffect(() => {
    if (!notice.show) return setHide(true);
    const hideUntil = localStorage.getItem(LS_KEY);
    const lastId = localStorage.getItem(LS_ID_KEY);
    // 공지 ID가 바뀌면 무조건 노출
    if (lastId !== noticeId) {
      localStorage.removeItem(LS_KEY);
      localStorage.setItem(LS_ID_KEY, noticeId);
      setHide(false);
      return;
    }
    // 숨김 기간 체크
    if (hideUntil && todayStr() <= hideUntil) setHide(true);
    else setHide(false);
  }, [notice, noticeId]);

  if (hide) return null;

  // 항상 최상위(z-9999)로 팝업이 뜨도록 z-index 강화 및 fixed 적용
  return (
    <div className="fixed inset-0 z-[9999] flex items-center justify-center bg-black/40 px-2 sm:px-0">
      <div className="bg-white rounded-xl shadow-xl w-full max-w-md sm:max-w-md md:max-w-lg p-4 sm:p-6 relative animate-fadeIn mx-auto"
        style={{ minWidth: 0 }}>
        <button
          className="absolute top-2 right-2 sm:top-3 sm:right-3 text-gray-400 hover:text-gray-600 text-2xl sm:text-xl"
          onClick={onClose}
          aria-label="닫기"
        >
          ×
        </button>
        <h2 className="text-lg sm:text-xl font-bold mb-2 break-words">{notice.title}</h2>
        <div
          className="text-sm sm:text-base mb-4 whitespace-pre-line break-words
            max-h-[50vh] overflow-y-auto sm:max-h-none sm:overflow-visible"
        >
          {notice.content}
        </div>
        <div className="flex flex-col sm:flex-row gap-2 justify-end">
          <button
            onClick={() => hideFor(todayStr())}
            className="px-3 py-2 rounded bg-gray-200 hover:bg-gray-300 text-xs sm:text-sm"
          >
            오늘 하루 안보기
          </button>
          <button
            onClick={() => hideFor(weekLaterStr())}
            className="px-3 py-2 rounded bg-gray-200 hover:bg-gray-300 text-xs sm:text-sm"
          >
            1주일 동안 안보기
          </button>
        </div>
      </div>
    </div>
  );
}
