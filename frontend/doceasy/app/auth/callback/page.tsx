// OAuth 콜백 처리 페이지
'use client';

import { useEffect, useRef, Suspense } from 'react';
import { useRouter, useSearchParams } from 'next/navigation';
import { useAuth } from '@/hooks/useAuth';
import { toast } from 'sonner';
import { LoadingSpinner } from '@/components/ui/loading';

// 콜백 처리 로직을 별도의 컴포넌트로 분리
function CallbackHandler() {
    const router = useRouter();
    const searchParams = useSearchParams();
    const { setUser, setToken } = useAuth();
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

                            // 쿠키 설정 (서브도메인에서 접근 가능하도록)
                            document.cookie = `token=${token}; path=/; domain=.intellio.kr`;
                            
                            // 쿠키에 사용자 정보를 안전하게 저장
                            // JSON 문자열로 변환 후 바로 쿠키에 설정 (중간에 encodeURIComponent 사용)
                            const userDataString = JSON.stringify(userData);
                            document.cookie = `user=${encodeURIComponent(userDataString)}; path=/; domain=.intellio.kr`;

                            setToken(token);
                            setUser(userData);

                            toast.success('로그인이 완료되었습니다.');
                            router.push('/');
                            router.refresh();
                        } catch (jsonError) {
                            console.error('[Callback] JSON 파싱 오류:', {
                                error: jsonError,
                                receivedData: decodedUserStr
                            });
                            toast.error('사용자 데이터 처리 중 오류가 발생했습니다.');
                        }
                    } catch (decodeError) {
                        console.error('[Callback] URL 디코딩 오류:', {
                            error: decodeError,
                            rawUserParam: userParam
                        });
                        toast.error('사용자 데이터 디코딩 중 오류가 발생했습니다.');
                    }
                } else if (success === 'false' && error) {
                    const errorMessage = decodeURIComponent(error);
                    console.error('[Callback] 로그인 실패:', {
                        success,
                        error: errorMessage,
                        provider: searchParams.get('provider')
                    });
                    toast.error(`로그인 실패: ${errorMessage}`);
                } else {
                    console.error('[Callback] 잘못된 응답:', {
                        success,
                        token: token ? '존재' : '없음',
                        userParam: userParam ? '존재' : '없음',
                        error
                    });
                    toast.error('잘못된 접근입니다.');
                }
            } catch (error) {
                console.error('Callback 처리 중 오류:', error);
                toast.error('로그인 처리 중 오류가 발생했습니다.');
                //router.push('/auth/login');
            } finally {
                isProcessing.current = false;
            }
        };

        handleCallback();
    }, [searchParams, router, setUser, setToken]);

    return (
        <div className="text-center">
            <LoadingSpinner size="lg" />
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
                    <LoadingSpinner size="lg" />
                    
                </div>
            }>
                <CallbackHandler />
            </Suspense>
        </div>
    );
}
