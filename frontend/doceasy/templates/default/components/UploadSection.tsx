"use client"

import { useCallback, useState, useEffect } from 'react'
import { Upload, FileText, Loader2, AlertCircle, CheckCircle2, Clock } from 'lucide-react'
import { useDropzone } from 'react-dropzone'
import { useApp } from '@/contexts/AppContext'
import { Button } from '@/components/ui/button'
import { createProject } from '@/services/api'
import { uploadDocument } from '@/services/api'
import { IDocument, IDocumentStatus, IDocumentUploadResponse, ITableData, TableResponse } from '@/types'
import * as actionTypes from '@/types/actions'

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
  const [uploadStatus, setUploadStatus] = useState({
    total: 0,
    error: 0,
    failedFiles: [] as string[]
  })
  const [documentStatuses, setDocumentStatuses] = useState<DocumentStatus[]>([])

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
    console.log('Files dropped:', acceptedFiles.map(f => f.name))
    
    try {
      // 새로운 프로젝트 생성 전에 상태 초기화
      dispatch({ type: actionTypes.SET_INITIAL_STATE })

      // 첫 번째 파일의 이름을 프로젝트 이름으로 사용
      const projectName = acceptedFiles[0]?.name.replace(/\.[^/.]+$/, '') || 'Untitled Project'

      // 새 프로젝트 생성
      console.log('Creating new project...')
      const project = await createProject(projectName, 'Created for document upload')
      console.log('Created new project:', project)
      
      // 프로젝트 ID와 제목 설정
      dispatch({ type: actionTypes.SET_CURRENT_PROJECT, payload: project })
      dispatch({ type: actionTypes.SET_PROJECT_TITLE, payload: projectName})

      // 사이드바의 프로젝트 목록 갱신을 위해 이벤트 발생
      window.dispatchEvent(new CustomEvent('projectCreated'))

      console.log('Using project ID:', project.id)
      
      try {
        // 초기 상태 설정
        updateUploadStatus(
          acceptedFiles.length, 
          0, 
          []
        )
        // 채팅 메시지로 상태 업데이트
        dispatch({
          type: actionTypes.ADD_CHAT_MESSAGE,
          payload: {
            role: 'assistant',
            content: `문서 업로드를 시작합니다. 총 ${acceptedFiles.length}개의 파일이 업로드됩니다.`
          }
        })
        

        // 모든 파일의 상태를 UPLOADING으로 업데이트하고 테이블에 즉시 추가
        const initialTableData: TableResponse = {
          columns: [{
            header: {
              name: 'Document',
              prompt: '문서 이름을 표시합니다'
            },
            cells: acceptedFiles.map(file => ({
              doc_id: file.name,
              content: file.name
            }))
          }]
        };

        // 테이블 데이터 즉시 업데이트
        dispatch({
          type: actionTypes.UPDATE_TABLE_DATA,
          payload: initialTableData
        })

        // 업로드 섹션에서 채팅 섹션으로 전환
        dispatch({ type: actionTypes.SET_VIEW, payload: 'chat' })

        // 파일 업로드 진행
        console.log(`Uploading ${acceptedFiles.length} files to project ${project.id}`)
        const response:IDocumentUploadResponse = await uploadDocument(project.id, acceptedFiles)
        if(response.success === true)
          console.log('Upload response:[UploadSection1]', response)
        else
          console.warn('Upload response:[UploadSection2]', response)
        

        // 업로드 상태 업데이트
        updateUploadStatus(
          acceptedFiles.length,
          response.errors.length,
          response.failed_uploads || []
        )
        // 채팅 메시지로 상태 업데이트
        dispatch({
          type: actionTypes.ADD_CHAT_MESSAGE,
          payload: {
            role: 'assistant',
            content: `문서 업로드 완료`
          }
        })

        // 업로드가 완료된 이후에는 업로드 성공/실패 여부에 따라 각 문서의 상태를 업데이트 해줘야한다.
        // 새 문서 목록 생성
        const newDocuments:IDocument[] = (response.document_ids || []).map((docId, index) => ({
          id: docId,
          filename: acceptedFiles[index].name,
          project_id: project.id,
          status: 'UPLOADING',
          created_at: new Date().toISOString(),  // 현재 시간을 ISO 문자열로 추가 // 서버에서 생성된 create_at과 다른값일텐데.. 일단 나중에..
          updated_at: new Date().toISOString()   // 현재 시간을 ISO 문자열로 추가
        }));

        // 문서 목록 업데이트
        dispatch({
          type: actionTypes.ADD_DOCUMENTS,
          payload: newDocuments
        });

        // 문서 상태 모니터링 시작
        setDocumentStatuses(
          response.document_ids.map(docId => ({
            document_id: docId,
            status: 'PROCESSING',
            is_accessible: true
          }))
        );

        // 채팅 모드 유지
        dispatch({ type: actionTypes.SET_VIEW, payload: 'chat' })

      } catch (error) {
        console.error('Upload failed:', error)
        // 실패한 파일 이름 목록 생성
        const failedFiles = acceptedFiles.map(file => file.name)
        console.log('Failed files:', failedFiles)
        // 실패한 업로드 상태 업데이트
        updateUploadStatus(
          acceptedFiles.length,
          acceptedFiles.length,
          failedFiles
        )

        // 실패한 파일들의 상태를 ERROR로 업데이트
        const failedTableData: TableResponse = {
          columns: [{
            header: {
              name: 'Document',
              prompt: '문서 이름을 표시합니다'
            },
            cells: failedFiles.map(filename => ({
              doc_id: filename,
              content: filename
            }))
          }]
        };

        dispatch({
          type: actionTypes.UPDATE_TABLE_DATA,
          payload: failedTableData
        })

        throw error
      }
    } catch (error) {
      console.error('Project creation or upload failed:', error)
      throw error
    }
  }, [dispatch])

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
  )
}
