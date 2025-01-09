"use client"

import { useState, useRef, useEffect } from "react"
import { Settings, User } from "lucide-react"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { useApp } from "@/contexts/AppContext"
import { useAuth } from "@/hooks/useAuth"
import * as api from "@/services/api"
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
  DialogDescription,
} from "@/components/ui/dialog"
import { FontSettings } from "@/components/settings/FontSettings"
import { LoginButton } from "@/components/auth/LoginButton"
import { DropdownMenu, DropdownMenuContent, DropdownMenuItem, DropdownMenuTrigger } from "@/components/ui/dropdown-menu"
import { Popover, PopoverContent, PopoverTrigger } from "@/components/ui/popover"

export const Header = ({ className }: { className?: string }) => {
  const { state, dispatch } = useApp()
  const auth = useAuth()
  const { isAuthenticated, name, email, logout } = auth
  const [isEditingTitle, setIsEditingTitle] = useState(false)
  const [editingTitle, setEditingTitle] = useState('')
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
    dispatch({ type: 'SET_PROJECT_TITLE', payload: newTitle })
    setIsEditingTitle(false)

    // 현재 프로젝트가 있을 때만 저장
    if (state.currentProjectId) {
      try {
        // 프로젝트 상태 저장
        await api.autosaveProject(state.currentProjectId, {
          title: newTitle,
          documents: state.documents,
          messages: state.messages,
          analysis: state.analysis,
          currentView: state.currentView
        });
      } catch (error) {
        console.error('프로젝트 저장 실패:', error)
      }
    }
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
    //setEditingTitle(state.projectTitle || 'Untitled Project')
    console.log('[Header1] Auth State Updated:', {
      isAuthenticated: auth.isAuthenticated,
      name: auth.name,
      email: auth.email,
      token: auth.token,
      provider: auth.provider
    })
  }, [auth])

  useEffect(() => {
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
              className="text-lg font-semibold"
            />
          ) : (
            <h1 className="text-lg font-semibold cursor-pointer" onClick={handleTitleClick}>
              {state.projectTitle || 'Untitled Project'}
            </h1>
          )
        ) : null}
      </div>
      <div className="flex items-center gap-2">
        {/* 사용자 메뉴 */}
        {isAuthenticated ? (
          <>
            <span className="text-sm text-gray-600">{email}</span>
            <DropdownMenu>
              <DropdownMenuTrigger>
                <div className="inline-flex items-center justify-center w-8 h-8 rounded-md hover:bg-gray-100 cursor-pointer">
                  <User className="h-4 w-4" />
                </div>
              </DropdownMenuTrigger>
              <DropdownMenuContent align="end">
                <DropdownMenuItem onClick={logout}>
                  로그아웃
                </DropdownMenuItem>
              </DropdownMenuContent>
            </DropdownMenu>
          </>
        ) : (
          <div className="flex items-center gap-2">
            <span className="text-sm text-gray-500">로그인이 필요합니다</span>
            <Dialog>
              <DialogTrigger>
                <div className="inline-flex items-center justify-center w-8 h-8 rounded-md hover:bg-gray-100 cursor-pointer">
                  <User className="h-4 w-4" />
                </div>
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
                    <LoginButton provider="kakao" />
                  </div>
                </div>
              </DialogContent>
            </Dialog>
          </div>
        )}

        <Dialog>
          <DialogTrigger>
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
