"use client"

import { Suspense } from 'react'
import { Progress } from './progress'
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
} from './dialog'

export interface IUploadProgressDialog {
  isOpen: boolean
  progress: number
  currentFile: string
  processedFiles: number
  totalFiles: number
}

// 컨텐츠 컴포넌트
function UploadProgressDialogContent({
  isOpen,
  progress,
  currentFile,
  processedFiles,
  totalFiles
}: IUploadProgressDialog) {
  return (
    <Dialog open={isOpen} modal={true}>
      <DialogContent className="sm:max-w-[425px]">
        <DialogHeader>
          <DialogTitle>문서 업로드 진행 중...</DialogTitle>
          <DialogDescription>
            {processedFiles} / {totalFiles} 파일 처리됨
          </DialogDescription>
        </DialogHeader>
        <div className="grid gap-4 py-4">
          <Progress value={progress} className="w-full" />
          <p className="text-sm text-muted-foreground">
            현재 처리 중: {currentFile}
          </p>
        </div>
      </DialogContent>
    </Dialog>
  )
}

// 메인 컴포넌트
export function UploadProgressDialog(props: IUploadProgressDialog) {
  return (
    <Suspense fallback={<div className="fixed inset-0 z-50 flex items-center justify-center">
      <div className="animate-pulse bg-background p-6 rounded-lg shadow-lg">
        <div className="h-6 bg-gray-200 rounded w-3/4 mb-4"></div>
        <div className="h-4 bg-gray-200 rounded w-full"></div>
      </div>
    </div>}>
      <UploadProgressDialogContent {...props} />
    </Suspense>
  )
} 