"use client"

import React from 'react'

interface FileUploadErrorDialogProps {
  isOpen: boolean
  onClose: () => void
  errorMessage: string
}

export function FileUploadErrorDialog({
  isOpen,
  onClose,
  errorMessage
}: FileUploadErrorDialogProps) {
  if (!isOpen) return null
  
  return (
    <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50" onClick={onClose}>
      <div 
        className="bg-white dark:bg-gray-800 p-6 rounded-lg shadow-lg max-w-md w-full mx-4"
        onClick={e => e.stopPropagation()}
      >
        <div className="space-y-4">
          <div className="space-y-2">
            <h2 className="text-xl font-semibold">업로드 오류</h2>
            <p className="text-sm text-gray-500 dark:text-gray-400">
              {errorMessage}
            </p>
          </div>
          
          <div className="flex justify-end pt-4">
            <button
              onClick={onClose}
              className="px-4 py-2 bg-blue-600 hover:bg-blue-700 text-white rounded-md text-sm font-medium transition-colors"
            >
              확인
            </button>
          </div>
        </div>
      </div>
    </div>
  )
} 