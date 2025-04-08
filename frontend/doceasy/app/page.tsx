"use client"

import { Suspense } from 'react'
import { useEffect } from 'react'
import { useSearchParams } from 'next/navigation'
import { DefaultTemplate } from '@/templates/default'
import { useApp } from '@/contexts/AppContext'
import { useAuth } from '@/hooks/useAuth'
import { IOAuthUser } from '@/types/auth'
import * as actionTypes from '@/types/actions'

// 메인 컴포넌트
function HomeContent() {
  const searchParams = useSearchParams()
  const { dispatch } = useApp()
  const { login, setToken } = useAuth()
  const templateType = searchParams.get('template') || 'default'

  // 초기 데이터 로드
  useEffect(() => {
    const initializeApp = async () => {
      try {
        // 쿠키에서 사용자 정보와 토큰 가져오기
        const cookies = document.cookie.split(';').reduce((acc, cookie) => {
          const [key, value] = cookie.trim().split('=');
          if (!value) return acc;
          
          acc[key] = decodeURIComponent(value);
          return acc;
        }, {} as Record<string, any>);

        // 사용자 정보와 토큰이 있으면 로그인 상태 복원
        if (cookies.user && cookies.token) {
          try {
            // 쿠키 값이 따옴표로 감싸진 경우 처리
            let jsonString = cookies.user;
            console.debug('[Page] 원본 사용자 쿠키:', jsonString);
            
            // 이중 따옴표로 감싸진 JSON 문자열인 경우 처리
            if (jsonString.startsWith('"') && jsonString.endsWith('"')) {
              // 바깥쪽 따옴표 제거 및 이스케이프된 따옴표 처리
              jsonString = jsonString.slice(1, -1).replace(/\\"/g, '"');
              console.debug('[Page] 따옴표 제거 후 문자열:', jsonString);
            }
            
            // JSON 파싱 시도
            const userData: IOAuthUser = JSON.parse(jsonString);
            console.debug('[Page] 파싱된 사용자 데이터:', userData);
            
            // 토큰 설정
            setToken(cookies.token);
            // 사용자 정보로 로그인
            login(userData);
          } catch (error) {
            console.error('[Page] 사용자 데이터 파싱 실패:', error);
          }
        }

        // 초기 상태 설정
        dispatch({ type: actionTypes.SET_INITIAL_STATE })
      } catch (error) {
        console.error('Failed to initialize app:', error)
      }
    }

    initializeApp()
  }, [dispatch, login, setToken])

  // 템플릿 타입에 따라 적절한 템플릿 렌더링
  const getTemplate = () => {
    switch (templateType) {
      case 'default':
        return <DefaultTemplate />
      default:
        return <DefaultTemplate />
    }
  }

  return (
    <>
      {getTemplate()}
    </>
  )
}

// Page 컴포넌트
export default function Home() {
  return (
    <Suspense fallback={<div>Loading...</div>}>
      <HomeContent />
    </Suspense>
  )
}
