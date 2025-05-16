
'use client';

import { usePathname } from 'next/navigation';
import ClientFooter from './ClientFooter';

/**
 * 현재 경로를 확인하여 특정 경로(채팅 페이지)를 제외하고 ClientFooter를 렌더링하는 컴포넌트입니다.
 * AIChatArea 컴포넌트가 주로 사용되는 페이지에서는 푸터를 숨깁니다.
 */
export default function ConditionalFooter() {
  const pathname = usePathname();
  // AIChatArea가 주로 사용되는 페이지 경로 (루트 페이지 '/'로 가정)
  // 만약 다른 경로라면 이 부분을 수정해야 합니다.
  const chatPagePath = '/'; 
  //console.log(`pathname: ${pathname}`);

  // 현재 경로가 채팅 페이지 경로가 아니면 푸터를 렌더링합니다.
  if (pathname !== chatPagePath && !pathname.startsWith("/chat") && !pathname.startsWith("/share_chat")) {
    return <ClientFooter />;
  }

  // 채팅 페이지 경로인 경우 null을 반환하여 푸터를 렌더링하지 않습니다.
  return null;
}
