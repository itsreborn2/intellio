// OAuth 콜백 처리 페이지
'use client';

import { useEffect } from 'react';
import { useRouter, useSearchParams } from 'next/navigation';
import { useAuth } from '@/hooks/useAuth';
import { IOAuthResponse } from '@/types/auth';

export default function OAuthCallbackPage() {
    const router = useRouter();
    const searchParams = useSearchParams();
    const { login } = useAuth();

    useEffect(() => {
        const handleOAuthCallback = async () => {
            try {
                // URL 파라미터에서 데이터 추출
                const data = searchParams.get('data');
                if (!data) {
                    throw new Error('No data received from OAuth provider');
                }

                // JSON 파싱
                const authData: IOAuthResponse = JSON.parse(decodeURIComponent(data));

                // 로그인 처리
                await login(authData);

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
