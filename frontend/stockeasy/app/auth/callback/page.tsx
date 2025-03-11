'use client';

import { useEffect, useState } from 'react';
import { useRouter, useSearchParams } from 'next/navigation';
import { useAuth } from '@/hooks/useAuth';
import { Loader2 } from 'lucide-react';

export default function AuthCallbackPage() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const { setUser, setToken, login } = useAuth();
  const [status, setStatus] = useState<'loading' | 'success' | 'error'>('loading');
  const [errorMessage, setErrorMessage] = useState<string>('');

  useEffect(() => {
    const autoLogin = () => {
      try {
        const token = searchParams.get('token');
        const userParam = searchParams.get('user');

        if (!token || !userParam) {
          setStatus('error');
          setErrorMessage('토큰 또는 사용자 정보가 누락되었습니다.');
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
          
          setStatus('success');
          
          // 메인 페이지로 리다이렉션 (페이지 새로고침을 위해 window.location.href 사용)
          setTimeout(() => {
            window.location.href = '/';
          }, 1500);
        } catch (jsonError) {
          console.error('사용자 데이터 파싱 오류:', jsonError);
          setStatus('error');
          setErrorMessage('사용자 데이터 형식이 올바르지 않습니다.');
        }
      } catch (error) {
        console.error('자동 로그인 오류:', error);
        setStatus('error');
        setErrorMessage('자동 로그인 처리 중 오류가 발생했습니다.');
      }
    };

    autoLogin();
  }, [searchParams, router, setUser, setToken, login]);

  return (
    <div className="flex min-h-screen items-center justify-center flex-col">
      {status === 'loading' && (
        <>
          <Loader2 className="h-12 w-12 animate-spin text-primary" />
          <p className="mt-4 text-xl">자동 로그인 처리 중...</p>
        </>
      )}
      
      {status === 'success' && (
        <>
          <div className="text-4xl mb-4">✅</div>
          <p className="text-xl">로그인 성공! 메인 페이지로 이동합니다.</p>
        </>
      )}
      
      {status === 'error' && (
        <>
          <div className="text-4xl mb-4">❌</div>
          <p className="text-xl text-red-500">{errorMessage}</p>
          <button 
            className="mt-4 px-4 py-2 bg-primary text-white rounded-md"
            onClick={() => window.location.href = '/'}
          >
            메인 페이지로 이동
          </button>
        </>
      )}
    </div>
  );
} 