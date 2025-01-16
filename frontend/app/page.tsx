"use client"

import { useEffect } from 'react'
import { useSearchParams } from 'next/navigation'
import { DefaultTemplate } from '@/templates/default'
import { useApp } from '@/contexts/AppContext'
import { useAuth } from '@/hooks/useAuth'
import { IOAuthResponse, IOAuthUser } from '@/types/auth'
import * as actionTypes from '@/types/actions'

export default function Home() {
  const searchParams = useSearchParams()
  const { dispatch } = useApp()
  const { login } = useAuth()
  const templateType = searchParams.get('template') || 'default'

  // 초기 데이터 로드
  useEffect(() => {
    const initializeApp = async () => {
      try {
        // 쿠키에서 사용자 정보와 토큰 가져오기
        const cookies = document.cookie.split(';').reduce((acc, cookie) => {
          const [key, value] = cookie.trim().split('=');
          try {
            acc[key] = JSON.parse(decodeURIComponent(value));
          } catch {
            acc[key] = decodeURIComponent(value);
          }
          return acc;
        }, {} as Record<string, any>);

        // 사용자 정보와 토큰이 있으면 로그인 상태 복원
        if (cookies.user && cookies.token) {
          try {
            // | 를 콤마로 변환
            let cleanedStr = cookies.user.replace(/\|/g, ',');
            // 맨 앞뒤 따옴표 제거
            cleanedStr = cleanedStr.replace(/^"|"$/g, '');
            
            // JSON 파싱 및 결과 확인
            const userData: IOAuthUser = JSON.parse(cleanedStr);
            console.log('userData :', userData);
            
            // IOAuthResponse 형식에 맞게 데이터 구성
            login({
              user: userData,
              token: cookies.token
            });
          } catch (error) {
            console.error('Failed to parse user data:', error);
          }
        }

        // 초기 상태 설정
        dispatch({ type: actionTypes.SET_INITIAL_STATE })
      } catch (error) {
        console.error('Failed to initialize app:', error)
      }
    }

    initializeApp()
  }, [dispatch, login])

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
