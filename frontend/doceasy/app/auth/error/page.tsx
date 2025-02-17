// OAuth 에러 페이지
'use client';

import { Suspense } from 'react';
import { useSearchParams } from 'next/navigation';
import Link from 'next/link';

// 에러 컨텐츠 컴포넌트
function ErrorContent() {
    const searchParams = useSearchParams();
    const errorMessage = searchParams.get('message') || '알 수 없는 오류가 발생했습니다.';

    return (
        <div className="flex min-h-screen items-center justify-center">
            <div className="text-center">
                <h1 className="text-2xl font-bold mb-4">로그인 오류</h1>
                <p className="text-red-500 mb-4">{decodeURIComponent(errorMessage)}</p>
                <Link 
                    href="/"
                    className="text-blue-500 hover:text-blue-700 underline"
                >
                    홈으로 돌아가기
                </Link>
            </div>
        </div>
    );
}

// Page 컴포넌트
export default function OAuthErrorPage() {
    return (
        <Suspense fallback={<div>Loading...</div>}>
            <ErrorContent />
        </Suspense>
    );
}
