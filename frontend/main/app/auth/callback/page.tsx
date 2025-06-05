'use client';

import { useEffect, useRef, Suspense } from 'react';
import { useRouter, useSearchParams } from 'next/navigation';
import { useAuth } from '@/hooks/useAuth';
import { Loader2 } from 'lucide-react';

// 콜백 처리 로직을 별도의 컴포넌트로 분리
function CallbackHandler() {
    const router = useRouter();
    const searchParams = useSearchParams();
    const { setUser, login, redirectTo, checkAuth } = useAuth();
    const isProcessing = useRef(false);

    useEffect(() => {
        if (!searchParams) return;

        const handleCallback = async () => {
            if (isProcessing.current) return;
            isProcessing.current = true;

            try {
                const success = searchParams.get('success');
                const token = searchParams.get('token');
                const userParam = searchParams.get('user');
                const error = searchParams.get('error');
                console.log('[Callback] 상태:', { success, token, userParam, error });
                
                if (success === 'true' && userParam) {
                    try {
                        const decodedUserStr = decodeURIComponent(userParam);
                        console.log('[Callback] 디코딩된 사용자 데이터:', decodedUserStr);
                        
                        try {
                            const userData = JSON.parse(decodedUserStr);
                            console.log('[Callback] 파싱된 사용자 데이터:', userData);

                            // 사용자 정보 설정 (쿠키는 백엔드에서 이미 설정됨)
                            setUser(userData);
                            login(userData);

                            // 백엔드에서 쿠키를 설정했으므로 인증 상태 다시 확인
                            await checkAuth();

                            // 리디렉션 처리
                            if (redirectTo === 'doceasy' || redirectTo === 'stockeasy') {
                                // 다른 도메인으로 리디렉션
                                const domain_url = process.env.NEXT_PUBLIC_ENV === 'production' ? 'https://' : 'http://';
                                let service_url;
                                
                                if (process.env.NEXT_PUBLIC_ENV === 'production') {
                                    service_url = `${redirectTo}.intellio.kr`;
                                } else {
                                    // 개발 환경에서는 localhost 포트 사용
                                    if (redirectTo === 'doceasy') service_url = `localhost:3010`;
                                    else if (redirectTo === 'stockeasy') service_url = `localhost:3020`;
                                }
                                
                                console.log('[Callback] 서비스 리디렉션:', `${domain_url}${service_url}`);
                                // 쿠키가 자동으로 전달되므로 토큰 파라미터 불필요
                                window.location.href = `${domain_url}${service_url}`;
                            } else {
                                // 메인 사이트 내부 경로로 리디렉션
                                const targetPath = redirectTo || '/';
                                console.log('[Callback] 리디렉션 경로:', targetPath);
                                router.push(targetPath);
                            }
                        } catch (parseError) {
                            console.error('[Callback] 사용자 데이터 파싱 오류:', parseError);
                            alert('사용자 정보를 처리하는 중 오류가 발생했습니다.');
                            router.push('/login');
                        }
                    } catch (decodeError) {
                        console.error('[Callback] 사용자 데이터 디코딩 오류:', decodeError);
                        alert('사용자 정보를 디코딩하는 중 오류가 발생했습니다.');
                        router.push('/login');
                    }
                } else if (error) {
                    console.error('[Callback] 인증 오류:', error);
                    alert(`로그인 오류: ${error}`);
                    router.push('/login');
                } else {
                    console.error('[Callback] 잘못된 콜백 파라미터');
                    alert('로그인 정보가 올바르지 않습니다.');
                    router.push('/login');
                }
            } catch (error) {
                console.error('Callback 처리 중 오류:', error);
                alert('로그인 처리 중 오류가 발생했습니다.');
                router.push('/login');
            } finally {
                isProcessing.current = false;
            }
        };

        handleCallback();
    }, [searchParams, router, setUser, login, redirectTo, checkAuth]);

    return (
        <div className="text-center">
            <Loader2 className="h-8 w-8 animate-spin mx-auto" />
            <p className="mt-4 text-muted-foreground">로그인 처리 중...</p>
        </div>
    );
}

// 메인 페이지 컴포넌트
export default function AuthCallback() {
    return (
        <div className="flex min-h-screen items-center justify-center">
            <Suspense fallback={
                <div className="text-center">
                    <Loader2 className="h-8 w-8 animate-spin mx-auto" />
                    <p className="mt-4 text-muted-foreground">로딩 중...</p>
                </div>
            }>
                <CallbackHandler />
            </Suspense>
        </div>
    );
} 