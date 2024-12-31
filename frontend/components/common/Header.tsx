"use client"

import { useState, useRef, useEffect } from "react"
import { Settings, User } from "lucide-react"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { useApp } from "@/contexts/AppContext"
import * as api from "@/services/api"

export const Header = ({ className }: { className?: string }) => {
  const { state, dispatch } = useApp()
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
    if (isEditingTitle && titleInputRef.current) {
      titleInputRef.current.focus()
      titleInputRef.current.select() // 텍스트 전체 선택
    }
  }, [isEditingTitle])

  return (
    <div className={`border-b p-4 flex items-center justify-between ${className || ''}`}>
      <div className="flex items-center gap-2">
        {isEditingTitle ? (
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
        )}
      </div>
      <div className="flex items-center gap-2">
        <Button variant="ghost" size="icon" className="h-8 w-8">
          <Settings className="h-4 w-4" />
        </Button>
        <Button variant="ghost" size="icon" className="h-8 w-8">
          <User className="h-4 w-4" />
        </Button>
      </div>
    </div>
  )
}
