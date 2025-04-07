'use client';

import { useEffect, useRef, Suspense } from 'react';
import { useRouter, useSearchParams } from 'next/navigation';
import { useAuth } from '@/hooks/useAuth';
import { Loader2 } from 'lucide-react';

// 콜백 처리 로직을 별도의 컴포넌트로 분리
function CallbackHandler() {
    const router = useRouter();
    const searchParams = useSearchParams();
    const { setUser, setToken, login, redirectTo, checkAuthCookie } = useAuth();
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
                
                if (success === 'true' && token && userParam) {
                    try {
                        const decodedUserStr = decodeURIComponent(userParam);
                        console.log('[Callback] 디코딩된 사용자 데이터:', decodedUserStr);
                        
                        try {
                            const userData = JSON.parse(decodedUserStr);
                            console.log('[Callback] 파싱된 사용자 데이터:', userData);

                            // 토큰 및 사용자 정보 설정
                            setToken(token);
                            setUser(userData);
                            
                            // 쿠키 설정 (서브도메인에서 접근 가능하도록)
                            document.cookie = `token=${token}; path=/; domain=.intellio.kr`;

                            // 쿠키에 사용자 정보를 안전하게 저장
                            // JSON 문자열로 변환 후 바로 쿠키에 설정 (중간에 encodeURIComponent 사용)
                            const userDataString = JSON.stringify(userData);
                            document.cookie = `user=${encodeURIComponent(userDataString)}; path=/; domain=.intellio.kr`;

                            // 추가로 login 호출하여 확실하게 인증 상태 설정
                            login(userData);

                            // 쿠키 확인 (백엔드에서 설정한 쿠키가 있는지 확인)
                            checkAuthCookie();

                            // 리디렉션 처리 수정
                            if (redirectTo === 'doceasy' || redirectTo === 'stockeasy') {
                                // 다른 도메인으로 리디렉션
                                window.location.href = `https://${redirectTo}.intellio.kr`;
                            } else {
                                // 메인 사이트 내부 경로로 리디렉션
                                const targetPath = redirectTo || '/';
                                console.log('[Callback] 리디렉션 경로:', targetPath);
                                router.push(targetPath);
                            }
                        } catch (jsonError) {
                            console.error('[Callback] JSON 파싱 오류:', {
                                error: jsonError,
                                receivedData: decodedUserStr
                            });
                            alert('사용자 데이터 처리 중 오류가 발생했습니다.');
                            router.push('/login');
                        }
                    } catch (decodeError) {
                        console.error('[Callback] URL 디코딩 오류:', {
                            error: decodeError,
                            rawUserParam: userParam
                        });
                        alert('사용자 데이터 디코딩 중 오류가 발생했습니다.');
                        router.push('/login');
                    }
                } else if (success === 'false' && error) {
                    const errorMessage = decodeURIComponent(error);
                    console.error('[Callback] 로그인 실패:', {
                        success,
                        error: errorMessage,
                        provider: searchParams.get('provider')
                    });
                    alert(`로그인 실패: ${errorMessage}`);
                    router.push('/login');
                } else {
                    // 쿠키 기반 인증 확인 시도
                    console.log('[Callback] 쿼리 파라미터 없음, 쿠키 확인 시도');
                    checkAuthCookie();
                    
                    // 쿠키 확인 후 리디렉션 처리
                    setTimeout(() => {
                        if (redirectTo === 'doceasy' || redirectTo === 'stockeasy') {
                            window.location.href = `https://${redirectTo}.intellio.kr`;
                        } else {
                            router.push(redirectTo || '/');
                        }
                    }, 1000); // 쿠키 확인을 위한 짧은 지연
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
    }, [searchParams, router, setUser, setToken, login, redirectTo, checkAuthCookie]);

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
                    
                </div>
            }>
                <CallbackHandler />
            </Suspense>
        </div>
    );
} 