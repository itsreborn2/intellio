'use client'

import { Suspense, useEffect, useState } from 'react'
import './globals.css';
//import AIChatArea from './components/AIChatArea';
import AIChatArea from './components/chat/AIChatArea/page';
import { Loader2 } from 'lucide-react'
import { useTokenUsageStore } from '@/stores/tokenUsageStore'
import { useQuestionCountStore } from '@/stores/questionCountStore'
import { isLoggedIn } from './utils/auth'

export default function StockEasyLandingPage() {
  // 토큰 사용량과 질문 개수 스토어 훅
  const { fetchSummary: fetchTokenSummary } = useTokenUsageStore()
  const { fetchSummary: fetchQuestionSummary } = useQuestionCountStore()
  const [loginCheckAttempt, setLoginCheckAttempt] = useState(0)
  
  // 페이지 로드 시 로그인 상태 확인 후 데이터 로드
  useEffect(() => {
    // 첫 로드 시 지연을 준 후 로그인 상태 다시 확인
    const checkLoginWithDelay = setTimeout(() => {
      // 로그인 상태 확인
      const isUserLoggedIn = isLoggedIn()
      //console.log(`홈페이지 로드 (시도 ${loginCheckAttempt + 1}): 로그인 상태 = ${isUserLoggedIn}`)
      
      if (isUserLoggedIn) {
        // 토큰 사용량 요약 정보 가져오기
        fetchTokenSummary('stockeasy', 'month')
        // 질문 개수 요약 정보 가져오기 - 하루 단위로 변경
        fetchQuestionSummary('day', 'day')
      } else if (loginCheckAttempt < 2) {
        // 아직 로그인이 감지되지 않았다면 몇 번 더 시도
        setLoginCheckAttempt(prev => prev + 1)
      }
    }, 1000) // 1초 지연
    
    return () => clearTimeout(checkLoginWithDelay)
  }, [fetchTokenSummary, fetchQuestionSummary, loginCheckAttempt])

  return (
    <div className="flex-1 p-0 sm:p-2 md:p-4 overflow-auto w-full">
      <div className="w-full max-w-[1280px] mx-auto px-0 sm:px-2">
        <Suspense fallback={
          <div className="flex h-full items-center justify-center">
            <Loader2 className="h-10 w-10 animate-spin text-gray-400" />
          </div>
        }>
          <AIChatArea />
        </Suspense>
      </div>
    </div>
  );
}
