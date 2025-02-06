"use client"

import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogDescription } from "./dialog"
import { Progress } from "intellio-common/components/ui/progress"

export interface IUploadProgressDialog {
  isOpen: boolean
  progress: number
  currentFile: string
  processedFiles: number
  totalFiles: number
}

export function UploadProgressDialog({
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