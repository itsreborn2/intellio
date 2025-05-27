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

  // 강력한 시스템 브라우저 호출 (네이버 앱 대응)
  const handleOAuth = useCallback(() => {
    const backendUrl = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000/api';
    const oauthUrl = `${backendUrl}/v1/auth/${provider}/login?redirectTo=${redirectTo}`;
    
    // 네이버 앱에서의 특별 처리 (Chrome Custom Tabs 우선)
    if (isNaverApp()) {
      // Chrome Custom Tabs Intent URI 생성
      const customTabsUrl = createCustomTabsIntent(oauthUrl, provider);
      
      try {
        // 1순위: Chrome Custom Tabs Intent
        window.location.href = customTabsUrl;
        
        // 1초 후 폴백 실행 (Custom Tabs 실패 시)
        setTimeout(() => {
          // 2순위: 간단한 Chrome 호출
          const simpleChrome = `googlechrome://navigate?url=${encodeURIComponent(oauthUrl)}`;
          window.location.href = simpleChrome;
          
          // 1초 후 최종 폴백
          setTimeout(() => {
            // 3순위: 일반 브라우저
            window.location.href = oauthUrl;
          }, 1000);
        }, 500);
        
        return;
      } catch (error) {
        // 즉시 폴백: 일반 브라우저 호출
        window.location.href = oauthUrl;
        return;
      }
    }
    
    // 일반적인 처리
    if (isMobileDevice()) {
      // 모바일: 새 탭으로 열기 + 추가 옵션
      const newWindow = window.open(
        oauthUrl, 
        '_blank', 
        'noopener,noreferrer,width=400,height=600,scrollbars=yes,resizable=yes'
      );
      
      // 팝업 차단 시 현재 탭에서 이동
      if (!newWindow || newWindow.closed) {
        window.location.href = oauthUrl;
      }
    } else {
      // 데스크톱: 현재 탭에서 이동
      window.location.href = oauthUrl;
    }
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
      {!isLoading && (
        <div className="text-xs text-center space-y-1">
          {isNaverApp() ? (
            <div className="text-purple-600 flex items-center justify-center gap-1">
              <span>🎨</span>
              <span>Chrome Custom Tabs로 안전 로그인</span>
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
      )}
    </div>
  );
}; 