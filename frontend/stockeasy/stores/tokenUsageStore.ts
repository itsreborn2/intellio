import { create } from 'zustand'
import { ITokenUsageSummary, ITokenUsageDetail } from '@/types'
import * as api from '@/services/api'
import { isLoggedIn } from '@/app/utils/auth'

interface TokenUsageState {
  // 토큰 사용량 요약 정보
  summary: ITokenUsageSummary | null
  // 토큰 사용량 상세 정보
  detail: ITokenUsageDetail | null
  // 로딩 상태
  isLoading: boolean
  // 오류 상태
  error: string | null
  
  // 액션들
  setSummary: (summary: ITokenUsageSummary | null) => void
  setDetail: (detail: ITokenUsageDetail | null) => void
  setIsLoading: (isLoading: boolean) => void
  setError: (error: string | null) => void
  
  // 토큰 사용량 요약 정보 조회
  fetchSummary: (projectType?: string, period?: string) => Promise<void>
  // 토큰 사용량 상세 정보 조회
  fetchDetail: (
    projectType?: string,
    tokenType?: string | null,
    startDate?: string | null,
    endDate?: string | null,
    groupBy?: string[] | null
  ) => Promise<void>
}

// 토큰 사용량 스토어 생성
export const useTokenUsageStore = create<TokenUsageState>((set) => ({
  // 초기 상태
  summary: null,
  detail: null,
  isLoading: false,
  error: null,
  
  // 상태 설정 함수들
  setSummary: (summary) => set({ summary }),
  setDetail: (detail) => set({ detail }),
  setIsLoading: (isLoading) => set({ isLoading }),
  setError: (error) => set({ error }),
  
  // 토큰 사용량 요약 정보 조회
  fetchSummary: async (projectType = 'stockeasy', period = 'day') => {
    try {
      // 로그인 상태가 아니면 API 호출하지 않음
      if (!isLoggedIn()) {
        set({ summary: null, isLoading: false });
        return;
      }
      
      set({ isLoading: true, error: null });
      const data = await api.getTokenUsageSummary(projectType, period);
      set({ summary: data, isLoading: false });
    } catch (error) {
      console.error('토큰 사용량 요약 정보 조회 실패:', error);
      set({ 
        isLoading: false, 
        error: error instanceof Error ? error.message : '토큰 사용량 요약 정보 조회 중 오류가 발생했습니다.' 
      });
    }
  },
  
  // 토큰 사용량 상세 정보 조회
  fetchDetail: async (
    projectType = 'stockeasy',
    tokenType = null,
    startDate = null,
    endDate = null,
    groupBy = null
  ) => {
    try {
      // 로그인 상태가 아니면 API 호출하지 않음
      if (!isLoggedIn()) {
        set({ detail: null, isLoading: false });
        return;
      }
      
      set({ isLoading: true, error: null });
      const data = await api.getTokenUsageDetail(projectType, tokenType, startDate, endDate, groupBy);
      set({ detail: data, isLoading: false });
    } catch (error) {
      console.error('토큰 사용량 상세 정보 조회 실패:', error);
      set({ 
        isLoading: false, 
        error: error instanceof Error ? error.message : '토큰 사용량 상세 정보 조회 중 오류가 발생했습니다.' 
      });
    }
  }
})) 