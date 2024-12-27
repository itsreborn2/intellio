"use client"

import { useEffect } from 'react'
import { useSearchParams } from 'next/navigation'
import { DefaultTemplate } from '@/templates/default'
import { useApp } from '@/contexts/AppContext'

export default function Home() {
  const searchParams = useSearchParams()
  const { dispatch } = useApp()
  const templateType = searchParams.get('template') || 'default'

  // 초기 데이터 로드
  useEffect(() => {
    const initializeApp = async () => {
      try {
        // 초기 상태 설정
        dispatch({ type: 'SET_INITIAL_STATE' })
      } catch (error) {
        console.error('Failed to initialize app:', error)
      }
    }

    initializeApp()
  }, [dispatch])

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
