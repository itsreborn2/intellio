import { useState, useCallback } from 'react'
import { useApp } from '@/contexts/AppContext'
import { createProject, uploadDocument } from '@/services/api'
import { IDocument, IDocumentStatus } from '@/types'
import * as actionTypes from '@/types/actions'

interface UploadProgress {
  isOpen: boolean
  progress: number
  currentFile: string
  processedFiles: number
  totalFiles: number
}

interface UseFileUploadOptions {
  skipChatMessages?: boolean
}

interface UseFileUploadReturn {
  uploadProgress: UploadProgress
  handleFileUpload: (files: File[], projectId?: string, options?: UseFileUploadOptions) => Promise<void>
}

export function useFileUpload(): UseFileUploadReturn {
  const { state, dispatch } = useApp()
  const [uploadProgress, setUploadProgress] = useState<UploadProgress>({
    isOpen: false,
    progress: 0,
    currentFile: '',
    processedFiles: 0,
    totalFiles: 0
  })

  const handleFileUpload = useCallback(async (
    files: File[], 
    existingProjectId?: string,
    options: UseFileUploadOptions = {}
  ) => {
    try {
      // 파일 MIME 타입 로깅
      files.forEach(file => {
        console.log(`파일명: ${file.name}, MIME 타입: ${file.type}`);
      });
      
      let projectId = existingProjectId

      if (!projectId) {
        // 새 프로젝트 생성이 필요한 경우
        dispatch({ type: actionTypes.SET_INITIAL_STATE })
        
        // 프로젝트 이름 설정 - 여러 파일인 경우 '첫번째파일 외 N개' 형식으로
        const projectName = files.length > 1
          ? `${files[0].name.replace(/\.[^/.]+$/, '')} 외 ${files.length - 1}개`
          : files[0].name.replace(/\.[^/.]+$/, '')

        const project = await createProject(projectName, 'Created for document upload')
        projectId = project.id
        
        dispatch({ type: actionTypes.SET_CURRENT_PROJECT, payload: project })
        dispatch({ type: actionTypes.SET_PROJECT_TITLE, payload: projectName})
        window.dispatchEvent(new CustomEvent('projectCreated'))
      }

      // 업로드 진행 상태 초기화
      setUploadProgress({
        isOpen: true,
        progress: 0,
        currentFile: '',
        processedFiles: 0,
        totalFiles: files.length
      })

      await uploadDocument(projectId, files, {
        onProgress: (data) => {
          const progress = (data.processed_files / data.total_files) * 100
          setUploadProgress(prev => ({
            ...prev,
            progress,
            currentFile: data.filename,
            processedFiles: data.processed_files
          }))

          if (data.document) {
            const newDocument: IDocument = {
              id: data.document.id,
              filename: data.document.filename,
              project_id: projectId!,
              status: data.document.status as IDocumentStatus,
              content_type: data.document.content_type
            }
            dispatch({
              type: actionTypes.ADD_DOCUMENTS,
              payload: [newDocument]
            })
          }
        },
        onError: (error) => {
          console.error('Upload error:', error)
          if (!options.skipChatMessages) {
            dispatch({
              type: actionTypes.ADD_CHAT_MESSAGE,
              payload: {
                role: 'assistant',
                content: `업로드 중 오류가 발생했습니다: ${error.message}`
              }
            })
          }
        },
        onComplete: (data) => {
          console.log('Upload complete:', data)
          if (!options.skipChatMessages) {
            dispatch({
              type: actionTypes.ADD_CHAT_MESSAGE,
              payload: {
                role: 'assistant',
                content: `${data.total_processed}개의 문서가 업로드되었습니다.`
              }
            })
          }
          setUploadProgress(prev => ({ ...prev, isOpen: false }))
        }
      })

      if (!existingProjectId && !options.skipChatMessages) {
        // 새 프로젝트인 경우에만 채팅 모드로 전환
        dispatch({ type: actionTypes.SET_VIEW, payload: 'chat' })
      }

    } catch (error) {
      console.error('Upload failed:', error)
      setUploadProgress(prev => ({ ...prev, isOpen: false }))
    }
  }, [dispatch])

  return {
    uploadProgress,
    handleFileUpload
  }
} 