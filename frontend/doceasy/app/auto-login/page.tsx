'use client';

import { useEffect, useState, Suspense } from 'react';
import { useRouter, useSearchParams } from 'next/navigation';
import { useAuth } from '../../hooks/useAuth';
import { Loader2 } from 'lucide-react';

function AutoLoginContent() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const { setUser, setToken, login } = useAuth();
  const [status, setStatus] = useState<'loading' | 'success' | 'error'>('loading');
  const [errorMessage, setErrorMessage] = useState<string>('');

  useEffect(() => {
    // 페이지 렌더링 전에 스타일 적용
    document.body.style.backgroundColor = 'white';
    document.body.style.opacity = '0';
    
    const autoLogin = () => {
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
          document.cookie = `user=${userParam}; path=/; domain=.intellio.kr`;
          
          // 상태 업데이트
          setToken(token);
          setUser(userData);
          login(userData);
          
          // 즉시 메인 페이지로 이동 (화면 표시 없이)
          window.location.href = '/';
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
  }, [searchParams, router, setUser, setToken, login]);

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