import { create } from 'zustand'
import { IQuestionCountSummary } from '@/types'
import * as api from '@/services/api'
import { isLoggedIn } from '@/app/utils/auth'

interface QuestionCountState {
  // 질문 개수 요약 정보
  summary: IQuestionCountSummary | null
  // 로딩 상태
  isLoading: boolean
  // 오류 상태
  error: string | null
  
  // 액션들
  setSummary: (summary: IQuestionCountSummary | null) => void
  setIsLoading: (isLoading: boolean) => void
  setError: (error: string | null) => void
  
  // 질문 개수 요약 정보 조회
  fetchSummary: (period?: string, groupBy?: string | null) => Promise<void>
}

// 질문 개수 스토어 생성
export const useQuestionCountStore = create<QuestionCountState>((set) => ({
  // 초기 상태
  summary: null,
  isLoading: false,
  error: null,
  
  // 상태 설정 함수들
  setSummary: (summary) => set({ summary }),
  setIsLoading: (isLoading) => set({ isLoading }),
  setError: (error) => set({ error }),
  
  // 질문 개수 요약 정보 조회
  fetchSummary: async (period = 'month', groupBy = 'day') => {
    try {
      // 로그인 상태가 아니면 API 호출하지 않음
      if (!isLoggedIn()) {
        set({ summary: null, isLoading: false });
        return;
      }
      
      set({ isLoading: true, error: null });
      const data = await api.getQuestionCountSummary(period, groupBy);
      set({ summary: data, isLoading: false });
    } catch (error) {
      console.error('질문 개수 요약 정보 조회 실패:', error);
      set({ 
        isLoading: false, 
        error: error instanceof Error ? error.message : '질문 개수 요약 정보 조회 중 오류가 발생했습니다.' 
      });
    }
  }
})) 