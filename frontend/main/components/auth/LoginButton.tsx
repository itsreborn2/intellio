"use client"

import { useState, useCallback } from "react"
import { Button } from "../ui/button"

// 로그인 버튼 prop 타입 정의
interface ILoginButtonProps {
  provider: 'google' | 'naver' | 'kakao';
  redirectTo?: 'doceasy' | 'stockeasy' | string;
}

// React Native 환경용 고급 Intent 처리 (참고용)
/*
import { Linking, Platform } from 'react-native';
import { WebBrowser } from 'expo-web-browser';

const handleAdvancedIntent = async (authUrl: string, provider: string) => {
  if (Platform.OS === 'android') {
    try {
      // 1. Chrome Custom Tabs 시도
      const result = await WebBrowser.openBrowserAsync(authUrl, {
        showTitle: true,
        toolbarColor: provider === 'google' ? '#4285f4' : '#03c75a',
        enableBarCollapsing: true,
        showInRecents: true
      });
      
      if (result.type === 'opened') {
        return true;
      }
    } catch (error) {
      console.log('Chrome Custom Tabs 실패, 기본 브라우저 시도');
    }
    
    // 2. 기본 브라우저 시도
    try {
      await Linking.openURL(authUrl);
      return true;
    } catch (error) {
      console.log('시스템 브라우저 호출 실패');
      return false;
    }
  } else if (Platform.OS === 'ios') {
    // iOS SFSafariViewController 사용
    try {
      const result = await WebBrowser.openBrowserAsync(authUrl, {
        presentationStyle: WebBrowser.WebBrowserPresentationStyle.FORM_SHEET,
        controlsColor: provider === 'google' ? '#4285f4' : '#03c75a'
      });
      return result.type === 'opened';
    } catch (error) {
      return false;
    }
  }
  
  return false;
};
*/

export const LoginButton: React.FC<ILoginButtonProps> = ({ provider, redirectTo = '/' }) => {
  const [isLoading, setIsLoading] = useState(false);

  // 네이버 앱 감지
  const isNaverApp = (): boolean => {
    if (typeof window === 'undefined') return false;
    return /NAVER|NaverApp/i.test(window.navigator.userAgent);
  };

  // Chrome Custom Tabs Intent URI 생성
  const createCustomTabsIntent = (url: string, provider: string): string => {
    // Provider별 테마 색상
    const getToolbarColor = (provider: string): string => {
      switch (provider) {
        case 'google': return '4285f4';
        case 'naver': return '03c75a';
        case 'kakao': return 'fee500';
        default: return '000000';
      }
    };

    const toolbarColor = getToolbarColor(provider);
    
    // Chrome Custom Tabs Intent URI 구성
    const baseIntent = 'intent://';
    const urlWithoutProtocol = url.replace(/^https?:\/\//, '');
    const intentParams = [
      'Intent',
      'scheme=https',
      'package=com.android.chrome',
      `S.customtabs.intent.extra.COLOR_SCHEME=${toolbarColor}`,
      'S.customtabs.intent.extra.TITLE_VISIBILITY=1',
      'S.customtabs.intent.extra.ENABLE_URLBAR_HIDING=true',
      'S.customtabs.intent.extra.TOOLBAR_COLOR=' + parseInt(toolbarColor, 16),
      'end'
    ].join(';');
    
    return `${baseIntent}${urlWithoutProtocol}#${intentParams}`;
  };

  // 다양한 브라우저 호출 방법들
  const openInExternalBrowser = (url: string) => {
    const userAgent = window.navigator.userAgent;
    
    // 1. Chrome 브라우저 우선 시도 (Android)
    if (/Android/i.test(userAgent)) {
      const chromeIntent = `intent://${url.replace(/^https?:\/\//, '')}#Intent;scheme=https;package=com.android.chrome;end`;
      try {
        window.location.href = chromeIntent;
        return true;
      } catch (e) {
        console.log('Chrome Intent 실패:', e);
      }
    }

    // 2. 다양한 브라우저 스킴 시도 (네이버 제외)
    const browserSchemes = [
      `samsung://internet?url=${encodeURIComponent(url)}`,      // Samsung Internet 우선
      `firefox://open-url?url=${encodeURIComponent(url)}`,
      `googlechrome://navigate?url=${encodeURIComponent(url)}`,
      `opera-http://${url.replace(/^https?:\/\//, '')}`
    ];

    for (const scheme of browserSchemes) {
      try {
        window.location.href = scheme;
        // 각 시도 간격을 두어 성공 여부 확인
        setTimeout(() => {
          // 만약 여전히 현재 페이지에 있다면 다음 방법 시도
          if (document.visibilityState === 'visible') {
            return false;
          }
        }, 500);
        return true;
      } catch (e) {
        console.log(`브라우저 스킴 실패 (${scheme}):`, e);
      }
    }

    // 3. 최종 폴백: 일반 window.open
    try {
      const newWindow = window.open(url, '_blank', 'noopener,noreferrer');
      if (newWindow) {
        return true;
      }
    } catch (e) {
      console.log('window.open 실패:', e);
    }

    // 4. 마지막 수단: 현재 탭에서 이동
    window.location.href = url;
    return true;
  };

  // 강력한 시스템 브라우저 호출 (네이버 앱 대응)
  const handleOAuth = useCallback(() => {
    // 브라우저 환경에서 절대 URL 생성
    let backendUrl: string;
    
    if (typeof window !== 'undefined') {
      // 프로덕션 환경인지 확인
      const isProduction = process.env.NEXT_PUBLIC_ENV === 'production';
      
      if (isProduction) {
        // 프로덕션: https://intellio.kr/api 사용
        backendUrl = `${window.location.origin}/api`;
      } else {
        // 개발: localhost:8000 직접 사용
        backendUrl = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000/api';
      }
    } else {
      console.log('서버 환경');
      // 서버 환경에서는 환경변수 또는 기본값 사용
      backendUrl = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000/api';
    }
    
    const oauthUrl = `${backendUrl}/v1/auth/${provider}/login?redirectTo=${redirectTo}`;
    
    console.log('OAuth URL:', oauthUrl); // 디버깅용
    
    // 네이버 앱에서의 특별 처리 (외부 브라우저 호출)
    if (isNaverApp()) {
      openInExternalBrowser(oauthUrl);
      return;
    }
    
    // 일반적인 처리 - 모든 환경에서 단순 이동 (네이버 앱 제외)
    window.location.href = oauthUrl;
  }, [provider, redirectTo]);

  // 모바일 기기 감지
  const isMobileDevice = (): boolean => {
    if (typeof window === 'undefined') return false;
    
    return /Android|webOS|iPhone|iPad|iPod|BlackBerry|IEMobile|Opera Mini/i.test(
      window.navigator.userAgent
    );
  };

  // 메인 로그인 처리 함수
  const handleLogin = () => {
    if (isLoading) return; // 중복 클릭 방지
    
    setIsLoading(true);
    
    try {
      // 간단한 OAuth 처리 (이미 Intent 효과)
      handleOAuth();
    } catch (error) {
      console.error('로그인 오류:', error);
      setIsLoading(false);
    }
  };

  // 제공자별 버튼 스타일 설정
  const getButtonStyle = () => {
    switch (provider) {
      case 'kakao':
        return 'bg-[#FEE500] text-black hover:bg-[#E6CF00]';
      case 'google':
        return 'bg-white text-black border border-gray-300 hover:bg-gray-100';
      case 'naver':
        return 'bg-[#03C75A] text-white hover:bg-[#02B350]';
      default:
        return '';
    }
  };

  // 제공자별 버튼 텍스트
  const getButtonText = () => {
    if (isLoading) return '로그인 중...';
    return `${provider.charAt(0).toUpperCase() + provider.slice(1)}로 로그인`;
  };

  return (
    <div className="relative">
      <Button
        className={`w-full mb-2 ${getButtonStyle()} ${isLoading ? 'opacity-75' : ''}`}
        onClick={handleLogin}
        disabled={isLoading}
      >
        <div className="flex items-center justify-center gap-2">
          {isLoading && (
            <svg className="animate-spin h-4 w-4" viewBox="0 0 24 24">
              <circle
                className="opacity-25"
                cx="12"
                cy="12"
                r="10"
                stroke="currentColor"
                strokeWidth="4"
                fill="none"
              />
              <path
                className="opacity-75"
                fill="currentColor"
                d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"
              />
            </svg>
          )}
          <span>{getButtonText()}</span>
        </div>
      </Button>
      
      {/* Intent 방식 상태 표시 */}
      {/* {!isLoading && (
        <div className="text-xs text-center space-y-1">
          {isNaverApp() ? (
            <div className="space-y-1">
              <div className="text-purple-600 flex items-center justify-center gap-1">
                <span>🎨</span>
                <span>Chrome Custom Tabs로 안전 로그인</span>
              </div>
              <div className="text-gray-500 text-[10px]">
                네이버 앱에서 외부 브라우저로 안전하게 로그인합니다
              </div>
            </div>
          ) : isMobileDevice() ? (
            <div className="text-green-600 flex items-center justify-center gap-1">
              <span>🔄</span>
              <span>시스템 브라우저로 안전 로그인</span>
            </div>
          ) : (
            <div className="text-blue-600 flex items-center justify-center gap-1">
              <span>🌐</span>
              <span>새 탭에서 안전하게 로그인</span>
            </div>
          )}
        </div>
      )} */}
    </div>
  );
}; 