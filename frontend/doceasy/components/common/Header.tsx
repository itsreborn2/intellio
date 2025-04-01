"use client"

import { useState, useRef, useEffect, Suspense } from "react"
import { User, X, Loader2 } from "lucide-react"
import { Button } from "intellio-common/components/ui/button"
import { Input } from "intellio-common/components/ui/input"
import { useApp } from "@/contexts/AppContext"
import { useAuth, useAuthCheck } from "@/hooks/useAuth"
import * as api from "@/services/api"
import { IProject, ProjectDetail } from '@/types'
import * as actionTypes from '@/types/actions'
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
  DialogDescription,
  DialogPortal,
} from "intellio-common/components/ui/dialog"
import { useRouter } from "next/navigation"

// 모바일 환경 감지 훅
const useIsMobile = () => {
  const [isMobile, setIsMobile] = useState(false);

  useEffect(() => {
    const checkIsMobile = () => {
      setIsMobile(window.innerWidth < 768); // 768px 미만을 모바일로 간주
    };

    // 초기 체크
    checkIsMobile();

    // 리사이즈 이벤트에 대응
    window.addEventListener('resize', checkIsMobile);
    return () => window.removeEventListener('resize', checkIsMobile);
  }, []);

  return isMobile;
};

// 헤더 컨텐츠 컴포넌트
function HeaderContent({ className }: { className?: string }) {
  const router = useRouter()
  const { state, dispatch } = useApp()
  const { user, isAuthenticated, logout } = useAuth()
  const [isEditingTitle, setIsEditingTitle] = useState(false)
  const [editingTitle, setEditingTitle] = useState('')
  const [isLoginDialogOpen, setIsLoginDialogOpen] = useState(false)  // Dialog 상태 추가
  const [isAuthLoading, setIsAuthLoading] = useState(true) // 인증 상태 로딩 상태 추가
  const titleInputRef = useRef<HTMLInputElement>(null)
  const isMobile = useIsMobile();
  
  // 쿠키 기반 인증 상태 확인
  useAuthCheck();

  const handleTitleClick = () => {
    setEditingTitle(state.projectTitle || 'Untitled Project')
    setIsEditingTitle(true)
  }

  const handleTitleChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    setEditingTitle(e.target.value)
  }

  const handleTitleSubmit = async () => {
    // 빈 제목이면 기존 제목으로 복원
    if (editingTitle.trim() === '') {
      setEditingTitle(state.projectTitle || 'Untitled Project')
      setIsEditingTitle(false)
      return
    }
    
    const newTitle = editingTitle.trim()
    
    try {
      // 백엔드로 프로젝트 이름 변경 요청
      if (state.currentProject) {
        await api.updateProjectName(state.currentProject.id, newTitle)
        
        // 프로젝트 정보 다시 가져오기
        const projectInfo = await api.getProjectInfo(state.currentProject.id)
        
        // ProjectDetail을 IProject 형식으로 변환
        const updatedProject: IProject = {
          ...projectInfo,
          is_temporary: state.currentProject.is_temporary,
          retention_period: state.currentProject.retention_period
        }
        
        // 상태 업데이트
        dispatch({ type: actionTypes.SET_PROJECT_TITLE, payload: newTitle })
        dispatch({ type: actionTypes.SET_CURRENT_PROJECT, payload: updatedProject })
        
        // 최근 프로젝트 목록 새로고침
        const recentProjects = await api.getRecentProjects()
        dispatch({ type: actionTypes.UPDATE_RECENT_PROJECTS, payload: recentProjects })
      }
    } catch (error) {
      console.error('프로젝트 이름 변경 실패:', error)
    }
    
    setIsEditingTitle(false)
  }

  const handleTitleBlur = () => {
    handleTitleSubmit()
  }

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter') {
      e.preventDefault()
      handleTitleSubmit()
    } else if (e.key === 'Escape') {
      setIsEditingTitle(false)
      setEditingTitle(state.projectTitle || 'Untitled Project')
    }
  }

  useEffect(() => {
    // 인증 상태가 확인되면 로딩 상태를 false로 설정
    setIsAuthLoading(false)
  }, [isAuthenticated, user])

  useEffect(() => {
    if (isEditingTitle && titleInputRef.current) {
      titleInputRef.current.focus()
      titleInputRef.current.select() // 텍스트 전체 선택
    }
  }, [isEditingTitle])

  return (
    // header 태그로 변경하고 className 통합
    <header className={`p-4 flex items-center justify-between ${className || ''}`}>
      <div className="flex items-center gap-2">
        {isAuthenticated ? (
          isEditingTitle ? (
            <Input
              ref={titleInputRef}
              value={editingTitle}
              onChange={handleTitleChange}
              onBlur={handleTitleBlur}
              onKeyDown={handleKeyDown}
              className="text-base font-semibold"
            />
          ) : (
            <h1 className="text-base font-semibold cursor-pointer" onClick={handleTitleClick}>
              {state.projectTitle || 'Untitled Project'}
            </h1>
          )
        ) : null}
      </div>
      
      {/* 모드 선택 버튼 - ChatSection에서 이동 */}
      <div className="flex items-center gap-2">
        {!isMobile && (
          <div className="flex space-x-2">
            <Button
              variant={state.analysis.mode === 'chat' ? 'default' : 'outline'}
              size="sm"
              onClick={() => {
                dispatch({ type: actionTypes.SET_MODE, payload: 'chat' });
                // 모바일 환경에서는 채팅 탭으로 전환
                if (isMobile && window.dispatchEvent) {
                  window.dispatchEvent(new CustomEvent('switchToTab', { detail: { tab: 'chat' } }));
                }
              }}
              className={`rounded-full text-xs font-medium px-4 ${
                state.analysis.mode === 'chat' 
                  ? 'bg-blue-500 hover:bg-blue-600 text-white' 
                  : 'border-gray-300 dark:border-gray-600 hover:bg-gray-100 dark:hover:bg-gray-700'
              }`}
              disabled={state.isAnalyzing}
            >
              통합분석
            </Button>
            <Button
              variant={state.analysis.mode === 'table' ? 'default' : 'outline'}
              size="sm"
              onClick={() => {
                dispatch({ type: actionTypes.SET_MODE, payload: 'table' });
                // 모바일 환경에서는 테이블 탭으로 전환
                if (isMobile && window.dispatchEvent) {
                  window.dispatchEvent(new CustomEvent('switchToTab', { detail: { tab: 'table' } }));
                }
              }}
              className={`rounded-full text-xs font-medium px-4 ${
                state.analysis.mode === 'table' 
                  ? 'bg-blue-500 hover:bg-blue-600 text-white' 
                  : 'border-gray-300 dark:border-gray-600 hover:bg-gray-100 dark:hover:bg-gray-700'
              }`}
              disabled={state.isAnalyzing}
            >
              {isMobile ? '문서목록' : '개별분석'}
            </Button>
          </div>
        )}
        
        {isMobile && (
          <div className="flex justify-center space-x-4">
            <Button
              variant={state.analysis.mode === 'chat' ? 'default' : 'outline'}
              size="sm"
              onClick={() => {
                dispatch({ type: actionTypes.SET_MODE, payload: 'chat' });
                if (window.dispatchEvent) {
                  window.dispatchEvent(new CustomEvent('switchToTab', { detail: { tab: 'chat' } }));
                }
              }}
              className={`rounded-full text-xs font-medium py-1.5 px-5 ${
                state.analysis.mode === 'chat' 
                  ? 'bg-blue-500 hover:bg-blue-600 text-white' 
                  : 'border-gray-300 dark:border-gray-600 hover:bg-gray-100 dark:hover:bg-gray-700'
              }`}
              disabled={state.isAnalyzing}
            >
              통합분석
            </Button>
            <Button
              variant={state.analysis.mode === 'table' ? 'default' : 'outline'}
              size="sm"
              onClick={() => {
                dispatch({ type: actionTypes.SET_MODE, payload: 'table' });
                if (window.dispatchEvent) {
                  window.dispatchEvent(new CustomEvent('switchToTab', { detail: { tab: 'table' } }));
                }
              }}
              className={`rounded-full text-xs font-medium py-1.5 px-5 ${
                state.analysis.mode === 'table' 
                  ? 'bg-blue-500 hover:bg-blue-600 text-white' 
                  : 'border-gray-300 dark:border-gray-600 hover:bg-gray-100 dark:hover:bg-gray-700'
              }`}
              disabled={state.isAnalyzing}
            >
              문서목록
            </Button>
          </div>
        )}
      </div>
    </header>
  )
}

// 헤더 컴포넌트
export const Header = ({ className }: { className?: string }) => {
  return (
    <Suspense fallback={<div className="h-[56px] bg-background"></div>}>
      <HeaderContent className={className} />
    </Suspense>
  )
}
