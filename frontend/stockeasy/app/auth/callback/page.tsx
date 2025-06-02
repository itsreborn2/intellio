'use client';

import { useEffect, useState, Suspense } from 'react';
import { useRouter, useSearchParams } from 'next/navigation';
import { useAuth } from '@/hooks/useAuth';
import { Loader2 } from 'lucide-react';

function AuthCallbackContent() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const { setUser, login, checkAuth } = useAuth();
  const [status, setStatus] = useState<'loading' | 'success' | 'error'>('loading');
  const [errorMessage, setErrorMessage] = useState<string>('');

  useEffect(() => {
    const autoLogin = async () => {
      try {
        const success = searchParams.get('success');
        const token = searchParams.get('token');
        const userParam = searchParams.get('user');
        const error = searchParams.get('error');

        console.log('[Stockeasy Callback] 상태:', { success, token, userParam, error });

        if (success === 'true' && userParam) {
          try {
            const decodedUserStr = decodeURIComponent(userParam);
            console.log('[Stockeasy Callback] 디코딩된 사용자 데이터:', decodedUserStr);
            
            const userData = JSON.parse(decodedUserStr);
            console.log('[Stockeasy Callback] 파싱된 사용자 데이터:', userData);

            // 사용자 정보 설정 (쿠키는 백엔드에서 이미 설정됨)
            setUser(userData);
            login(userData);

            // 백엔드에서 쿠키를 설정했으므로 인증 상태 다시 확인
            await checkAuth();
            
            setStatus('success');
            
            // 메인 페이지로 리다이렉션
            setTimeout(() => {
              window.location.href = '/';
            }, 1500);
          } catch (parseError) {
            console.error('[Stockeasy Callback] 사용자 데이터 파싱 오류:', parseError);
            setStatus('error');
            setErrorMessage('사용자 데이터 형식이 올바르지 않습니다.');
          }
        } else if (error) {
          console.error('[Stockeasy Callback] 인증 오류:', error);
          setStatus('error');
          setErrorMessage(`로그인 오류: ${error}`);
        } else {
          console.error('[Stockeasy Callback] 잘못된 콜백 파라미터');
          setStatus('error');
          setErrorMessage('로그인 정보가 올바르지 않습니다.');
        }
      } catch (error) {
        console.error('[Stockeasy Callback] 처리 중 오류:', error);
        setStatus('error');
        setErrorMessage('자동 로그인 처리 중 오류가 발생했습니다.');
      }
    };

    autoLogin();
  }, [searchParams, router, setUser, login, checkAuth]);

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

export default function AuthCallbackPage() {
  return (
    <Suspense fallback={
      <div className="flex min-h-screen items-center justify-center">
        <Loader2 className="h-12 w-12 animate-spin text-primary" />
        <p className="ml-4">로딩 중...</p>
      </div>
    }>
      <AuthCallbackContent />
    </Suspense>
  );
} 