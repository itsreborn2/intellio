'use client';

import { useEffect, useState, Suspense } from 'react';
import { useRouter, useSearchParams } from 'next/navigation';
import { useAuth } from '@/hooks/useAuth';
import { Loader2 } from 'lucide-react';
import { useTokenUsageStore } from '@/stores/tokenUsageStore';
import { useQuestionCountStore } from '@/stores/questionCountStore';

function AutoLoginContent() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const { setUser, setToken, login } = useAuth();
  const [status, setStatus] = useState<'loading' | 'success' | 'error'>('loading');
  const [errorMessage, setErrorMessage] = useState<string>('');
  
  // 토큰 사용량과 질문 개수 스토어 훅
  const { fetchSummary: fetchTokenSummary } = useTokenUsageStore();
  const { fetchSummary: fetchQuestionSummary } = useQuestionCountStore();

  useEffect(() => {
    // 페이지 렌더링 전에 스타일 적용
    document.body.style.backgroundColor = 'white';
    document.body.style.opacity = '0';
    
    const autoLogin = async () => {
      try {
        const token = searchParams.get('token');
        const userParam = searchParams.get('user');

        if (!token || !userParam) {
          setStatus('error');
          setErrorMessage('토큰 또는 사용자 정보가 누락되었습니다.');
          document.body.style.opacity = '1'; // 에러 시에만 화면 표시
          return;
        }

        // 사용자 정보 디코딩
        try {
          const userData = JSON.parse(decodeURIComponent(userParam));
          
          // 쿠키 설정 (서브도메인에서 접근 가능하도록)
          document.cookie = `token=${token}; path=/; domain=.intellio.kr`;
          document.cookie = `auth_token=${token}; path=/; max-age=2592000`; // auth_token 쿠키 추가
          
          // 쿠키에 사용자 정보를 안전하게 저장
          // JSON 문자열로 변환 후 바로 쿠키에 설정 (중간에 encodeURIComponent 사용)
          const userDataString = JSON.stringify(userData);
          document.cookie = `user=${encodeURIComponent(userDataString)}; path=/; domain=.intellio.kr`;
          
          // 상태 업데이트
          setToken(token);
          setUser(userData);
          login(userData);
          
          // 로그인 성공 시 토큰 사용량 정보와 질문 개수 정보 요청
          console.log('자동 로그인 성공, 토큰 사용량 정보 요청');
          try {
            await fetchTokenSummary('stockeasy', 'month');
            await fetchQuestionSummary('day', 'day');
            console.log('토큰 사용량 정보 요청 완료');
          } catch (fetchError) {
            console.error('토큰 사용량 정보 요청 실패:', fetchError);
          }
          
          // 메인 페이지로 이동 (페이지 새로고침을 위해 window.location.href 사용)
          setTimeout(() => {
            window.location.href = '/';
          }, 500); // 정보 요청 후 약간의 지연 추가
        } catch (jsonError) {
          console.error('사용자 데이터 파싱 오류:', jsonError);
          setStatus('error');
          setErrorMessage('사용자 데이터 형식이 올바르지 않습니다.');
          document.body.style.opacity = '1'; // 에러 시에만 화면 표시
        }
      } catch (error) {
        console.error('자동 로그인 오류:', error);
        setStatus('error');
        setErrorMessage('자동 로그인 처리 중 오류가 발생했습니다.');
        document.body.style.opacity = '1'; // 에러 시에만 화면 표시
      }
    };

    autoLogin();
  }, [searchParams, router, setUser, setToken, login, fetchTokenSummary, fetchQuestionSummary]);

  // 에러 상태일 때만 화면을 렌더링
  if (status !== 'error') {
    return null;
  }

  return (
    <div className="flex min-h-screen items-center justify-center flex-col">      
      <div className="text-4xl mb-4">❌</div>
      <p className="text-xl text-red-500">{errorMessage}</p>
      <button 
        className="mt-4 px-4 py-2 bg-primary text-white rounded-md"
        onClick={() => window.location.href = '/'}
      >
        메인 페이지로 이동
      </button>
    </div>
  );
}

export default function AutoLoginPage() {
  return (
    <Suspense fallback={
      <div className="flex min-h-screen items-center justify-center">
        <Loader2 className="h-8 w-8 animate-spin text-primary" />
      </div>
    }>
      <AutoLoginContent />
    </Suspense>
  );
} 