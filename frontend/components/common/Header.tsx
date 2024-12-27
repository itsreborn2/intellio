"use client"

import { useState, useRef, useEffect } from "react"
import { Settings, User } from "lucide-react"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { useApp } from "@/contexts/AppContext"

export const Header = ({ className }: { className?: string }) => {
  const { state, dispatch } = useApp()
  const [isEditingTitle, setIsEditingTitle] = useState(false)
  const titleInputRef = useRef<HTMLInputElement>(null)

  const handleTitleClick = () => {
    setIsEditingTitle(true)
  }

  const handleTitleChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    dispatch({ type: 'SET_PROJECT_TITLE', payload: e.target.value })
  }

  const handleTitleBlur = () => {
    setIsEditingTitle(false)
  }

  useEffect(() => {
    if (isEditingTitle && titleInputRef.current) {
      titleInputRef.current.focus()
    }
  }, [isEditingTitle])

  return (
    <div className={`border-b p-4 flex items-center justify-between ${className || ''}`}>
      <div className="flex items-center gap-2">
        {isEditingTitle ? (
          <Input
            ref={titleInputRef}
            value={state.projectTitle || 'Untitled Project'}
            onChange={handleTitleChange}
            onBlur={handleTitleBlur}
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
