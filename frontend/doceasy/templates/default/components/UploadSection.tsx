"use client"

import { useCallback, useState, useEffect } from 'react'
import { Upload, FileText, Loader2, AlertCircle, CheckCircle2, Clock } from 'lucide-react'
import { useDropzone } from 'react-dropzone'
import { useApp } from '@/contexts/AppContext'
import { Button } from 'intellio-common/components/ui/button'
import { createProject } from '@/services/api'
import { uploadDocument } from '@/services/api'
import { IDocument, IDocumentStatus, IDocumentUploadResponse, ITableData, TableResponse } from '@/types'
import * as actionTypes from '@/types/actions'
import { UploadProgressDialog } from "intellio-common/components/ui/upload-progress-dialog"
import { IUploadProgressData } from "@/types"
import { useFileUpload } from "@/hooks/useFileUpload"

// 문서 상태 타입 정의
interface DocumentStatus {
  document_id: string
  status: string
  error_message?: string
  is_accessible: boolean
}

// 문서 상태 표시 컴포넌트
const DocumentStatusBadge = ({ status }: { status: string }) => {
  switch (status) {
    case 'COMPLETED':
      return (
        <span className="inline-flex items-center px-2 py-1 text-xs font-medium text-green-700 bg-green-100 rounded-full">
          <CheckCircle2 className="w-3 h-3 mr-1" />
          완료
        </span>
      )
    case 'PROCESSING':
    case 'PARTIAL':
      return (
        <span className="inline-flex items-center px-2 py-1 text-xs font-medium text-blue-700 bg-blue-100 rounded-full">
          <Clock className="w-3 h-3 mr-1" />
          처리중
        </span>
      )
    case 'ERROR':
      return (
        <span className="inline-flex items-center px-2 py-1 text-xs font-medium text-red-700 bg-red-100 rounded-full">
          <AlertCircle className="w-3 h-3 mr-1" />
          오류
        </span>
      )
    default:
      return (
        <span className="inline-flex items-center px-2 py-1 text-xs font-medium text-gray-700 bg-gray-100 rounded-full">
          <Clock className="w-3 h-3 mr-1" />
          대기중
        </span>
      )
  }
}

// 테이블 행 데이터 인터페이스 정의
interface ITableRowData {
  id: string
  Document: string
  Date: string
  "Document Type": string
  status: IDocumentStatus
}

export const UploadSection = () => {
  const { state, dispatch } = useApp()
  //const { currentProject } = state
  const [uploadStatus, setUploadStatus] = useState({
    total: 0,
    error: 0,
    failedFiles: [] as string[]
  })
  const [documentStatuses, setDocumentStatuses] = useState<DocumentStatus[]>([])
  const { uploadProgress, handleFileUpload } = useFileUpload()

  // 문서 상태 조회 함수
  const fetchDocumentStatuses = async (documentIds: string[]) => {
    try {
      const response = await fetch('/api/v1/rag/document-status', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          document_ids: documentIds,
        }),
      })
      
      if (!response.ok) {
        throw new Error('문서 상태 조회 실패')
      }
      
      const statuses = await response.json()
      setDocumentStatuses(statuses)
      
    } catch (error) {
      console.error('문서 상태 조회 중 오류:', error)
    }
  }

  // 주기적으로 문서 상태 업데이트
  useEffect(() => {
    const documentIds = documentStatuses
      .filter(status => status.status === 'PROCESSING' || status.status === 'PARTIAL')
      .map(status => status.document_id)
      
    if (documentIds.length > 0) {
      const interval = setInterval(() => {
        fetchDocumentStatuses(documentIds)
      }, 5000) // 5초마다 업데이트
      
      return () => clearInterval(interval)
    }
  }, [documentStatuses])

  const updateUploadStatus = useCallback(
    (
      total: number, 
      error: number, 
      failedFiles: string[]
    ) => {
      setUploadStatus({
        total,
        error,
        failedFiles
      })

      
    }, [dispatch]
  )

  const onDrop = useCallback(async (acceptedFiles: File[]) => {
    await handleFileUpload(acceptedFiles)
  }, [handleFileUpload])

  const { getRootProps, getInputProps, isDragActive } = useDropzone({ 
    onDrop,
    accept: {
      'application/pdf': ['.pdf'],
      'application/msword': ['.doc'],
      'application/vnd.openxmlformats-officedocument.wordprocessingml.document': ['.docx'],
      'text/plain': ['.txt'],
      'application/x-hwp': ['.hwp'],
      'application/x-hwpx': ['.hwpx'],
      'application/vnd.ms-excel': ['.xls'],
      'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet': ['.xlsx'],
      'image/jpeg': ['.jpg', '.jpeg'],
      'image/png': ['.png'],
      'image/gif': ['.gif'],
      'image/tiff': ['.tiff']
    }
  })

  return (
    <>
      <UploadProgressDialog {...uploadProgress} />
      <div className="w-full h-[50vh] flex items-center justify-center p-4">
        <div
          {...getRootProps()}
          className={`w-full h-full max-w-4xl p-8 rounded-lg border-2 border-dashed transition-all duration-200 flex flex-col items-center justify-center cursor-pointer
            ${isDragActive 
              ? 'border-primary bg-primary/10 scale-[0.99] shadow-lg' 
              : 'border-muted-foreground/25 hover:border-primary/50 hover:bg-primary/5'}`}
        >
          <div className="flex flex-col items-center text-center space-y-6">
            <div className={`p-6 rounded-full transition-colors duration-200 ${isDragActive ? 'bg-primary/20' : 'bg-primary/10'}`}>
              <Upload className={`w-8 h-8 transition-colors duration-200 ${isDragActive ? 'text-primary' : 'text-primary/80'}`} />
            </div>
            <div className="space-y-2">
              <h3 className="font-semibold text-xl">문서 업로드</h3>
              <p className="text-sm text-muted-foreground">
                이곳에 문서를 끌어다 놓거나 클릭하여 선택하세요
              </p>
              <p className="text-xs text-muted-foreground mt-2">
                PDF, Word(doc/docx), 한글(hwp/hwpx), 엑셀(xls/xlsx), 이미지(jpg/jpeg/png/gif/tiff), 텍스트(txt)
              </p>
            </div>

            <input {...getInputProps()} />

            {/* 업로드 상태 표시 */}
            {uploadStatus.total > 0 && (
              <div className="mt-4 text-sm">
                <div className="flex items-center space-x-2">
                  <div className="text-green-600">성공: {uploadStatus.total - uploadStatus.error}</div>
                  {uploadStatus.error > 0 && (
                    <div className="text-red-600">
                      실패: {uploadStatus.error}
                      {uploadStatus.failedFiles.length > 0 && (
                        <div className="text-xs mt-1">
                          실패한 파일: {uploadStatus.failedFiles.join(', ')}
                        </div>
                      )}
                    </div>
                  )}
                </div>
                <div className="w-full bg-gray-200 rounded-full h-2 mt-2">
                  <div
                    className="bg-primary rounded-full h-2 transition-all duration-500"
                    style={{
                      width: `${((uploadStatus.total - uploadStatus.error) / uploadStatus.total) * 100}%`
                    }}
                  />
                </div>
              </div>
            )}
            
            {/* 문서 처리 상태 표시 */}
            {documentStatuses.length > 0 && (
              <div className="mt-4">
                <h3 className="text-sm font-medium mb-2">문서 처리 상태</h3>
                <div className="space-y-2">
                  {documentStatuses.map((status) => (
                    <div
                      key={status.document_id}
                      className="flex items-center justify-between p-2 bg-white rounded-lg shadow-sm"
                    >
                      <div className="flex items-center space-x-2">
                        <DocumentStatusBadge status={status.status} />
                        <span className="text-sm text-gray-600">
                          {status.error_message || (status.is_accessible ? '분석 가능' : '처리 중...')}
                        </span>
                      </div>
                    </div>
                  ))}
                </div>
              </div>
            )}
          </div>
        </div>
      </div>
    </>
  )
}
