"use client"

import { useState, useRef, useEffect, Suspense } from "react"
import { Settings, User, X } from "lucide-react"
import { Button } from "intellio-common/components/ui/button"
import { Input } from "intellio-common/components/ui/input"
import { useApp } from "@/contexts/AppContext"
import { useAuth } from "@/hooks/useAuth"
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
import { FontSettings } from "@/components/settings/FontSettings"
import { LoginButton } from "@/components/auth/LoginButton"
import { DropdownMenu, DropdownMenuContent, DropdownMenuItem, DropdownMenuTrigger } from "intellio-common/components/ui/dropdown-menu"
import { Popover, PopoverContent, PopoverTrigger } from "intellio-common/components/ui/popover"
import { useRouter } from "next/navigation"

// 헤더 컨텐츠 컴포넌트
function HeaderContent({ className }: { className?: string }) {
  const router = useRouter()
  const { state, dispatch } = useApp()
  const { user, isAuthenticated, logout } = useAuth()
  const [isEditingTitle, setIsEditingTitle] = useState(false)
  const [editingTitle, setEditingTitle] = useState('')
  const [isLoginDialogOpen, setIsLoginDialogOpen] = useState(false)  // Dialog 상태 추가
  const titleInputRef = useRef<HTMLInputElement>(null)

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

  const handleLogout = async () => {
    await logout();
    // AppContext 상태 초기화
    dispatch({ type: actionTypes.SET_INITIAL_STATE });
    dispatch({ type: actionTypes.SET_PROJECT_TITLE, payload: '' });
    console.log('[Header] 로그아웃 및 상태 초기화 완료');
  }

  useEffect(() => {
    console.log('[Header1] Auth State Updated:', {
      isAuthenticated,
      user,
    })
  }, [isAuthenticated, user])

  useEffect(() => {
    console.log("~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~")
    if (isEditingTitle && titleInputRef.current) {
      titleInputRef.current.focus()
      titleInputRef.current.select() // 텍스트 전체 선택
    }
  }, [isEditingTitle])

  return (
    // header 태그로 변경하고 className 통합
    <header className={`border-b p-4 flex items-center justify-between ${className || ''}`}>
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
      <div className="flex items-center gap-2">
        {/* 사용자 메뉴 */}
        {isAuthenticated && user ? (
          <>
            <span className="text-sm text-gray-600">{user.email}</span>
            <DropdownMenu>
              <DropdownMenuTrigger>
                <div className="inline-flex items-center justify-center w-8 h-8 rounded-md hover:bg-gray-100 cursor-pointer">
                  <User className="h-4 w-4" />
                </div>
              </DropdownMenuTrigger>
              <DropdownMenuContent align="end">
                <DropdownMenuItem onClick={handleLogout}>
                  로그아웃
                </DropdownMenuItem>
              </DropdownMenuContent>
            </DropdownMenu>
          </>
        ) : (
          <div className="flex items-center gap-2">
            <span className="text-sm text-gray-500">로그인이 필요합니다</span>
            <Dialog open={isLoginDialogOpen} onOpenChange={setIsLoginDialogOpen}>
              <DialogTrigger asChild>
                <Button
                  variant="ghost"
                  size="icon"
                  className="h-8 w-8 rounded-md hover:bg-gray-100"
                >
                  <User className="h-4 w-4" />
                </Button>
              </DialogTrigger>
              <DialogContent>
                <DialogHeader>
                  <DialogTitle>로그인 선택</DialogTitle>
                  <DialogDescription>
                    소셜 계정으로 로그인하세요
                  </DialogDescription>
                </DialogHeader>
                <div className="space-y-4">
                  <div className="flex flex-col space-y-2">
                    <LoginButton provider="google" />
                    <LoginButton provider="naver" />
                  </div>
                </div>
              </DialogContent>
            </Dialog>
          </div>
        )}

        <Dialog>
          <DialogTrigger asChild>
            <div className="inline-flex items-center justify-center w-8 h-8 rounded-md hover:bg-gray-100 cursor-pointer">
              <Settings className="h-4 w-4" />
            </div>
          </DialogTrigger>
          <DialogContent>
            <DialogHeader>
              <DialogTitle>설정</DialogTitle>
              <DialogDescription>
                애플리케이션 설정을 변경할 수 있습니다
              </DialogDescription>
            </DialogHeader>
            <FontSettings />
          </DialogContent>
        </Dialog>
      </div>
    </header>
  )
}

// 헤더 컴포넌트
export const Header = ({ className }: { className?: string }) => {
  return (
    <Suspense fallback={<div className="h-[56px] bg-background border-b"></div>}>
      <HeaderContent className={className} />
    </Suspense>
  )
}
