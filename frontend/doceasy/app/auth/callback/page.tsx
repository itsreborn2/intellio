// OAuth 콜백 처리 페이지
'use client';

import { Suspense } from 'react';
import { useEffect } from 'react';
import { useRouter, useSearchParams } from 'next/navigation';
import { useAuth } from '@/hooks/useAuth';

// 콜백 처리 컴포넌트
function CallbackContent() {
    const router = useRouter();
    const searchParams = useSearchParams();
    const { login } = useAuth();

    useEffect(() => {
        const handleOAuthCallback = async () => {
            try {
                // response data : user(id,email,provider,name), token
                const code = searchParams.get('code');
                const state = searchParams.get('state');
                
                // OAuth 콜백 처리 요청
                const response = await fetch(
                    `${process.env.NEXT_PUBLIC_API_URL}/api/v1/auth/naver/callback?code=${code}&state=${state}`,
                    {
                        method: 'GET',
                        credentials: 'include',
                    }
                );

                if (!response.ok) {
                    throw new Error('OAuth callback failed');
                }

                const result = await response.json();
                
                if (!result.success) {
                    throw new Error(result.message || 'OAuth callback failed');
                }

                // 로그인 처리
                await login(result.data);

                // 홈페이지로 리다이렉트
                router.push('/');
            } catch (error) {
                console.error('OAuth callback error:', error);
                router.push('/auth/error?message=' + encodeURIComponent('Failed to process OAuth callback'));
            }
        };

        handleOAuthCallback();
    }, [router, searchParams, login]);

    return (
        <div className="flex min-h-screen items-center justify-center">
            <div className="text-center">
                <h1 className="text-2xl font-bold mb-4">로그인 처리 중...</h1>
                <div className="animate-spin rounded-full h-12 w-12 border-t-2 border-b-2 border-blue-500 mx-auto"></div>
            </div>
        </div>
    );
}

// Page 컴포넌트
export default function OAuthCallbackPage() {
    return (
        <Suspense fallback={<div>Loading...</div>}>
            <CallbackContent />
        </Suspense>
    );
}
