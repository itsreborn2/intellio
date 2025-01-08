// 문서 관련 인터페이스
export interface IDocument {
  id: string
  filename: string
  status: IDocumentStatus
  content_type?: string
}


// 문서 상태 타입
export type IDocumentStatus = 'UPLOADING' | 'PROCESSING' | 'COMPLETED' | 'FAILED' | 'ERROR'

// 메시지 인터페이스
export interface IMessage {
  role: 'user' | 'assistant'
  content: string
}

// 테이블 데이터 인터페이스
export interface ITableData {
  Document: string
  status: 'PROCESSING' | 'COMPLETED' | 'ERROR'
  id: string
}

// 템플릿 인터페이스
export interface ITemplate {
  id: string
  name: string
  content: string
}

// 프로젝트 아이템 인터페이스
export interface IProjectItem {
  name: string
  children?: IProjectItem[]
}

// 문서 업로드 응답 인터페이스
export interface IDocumentUploadResponse {
  success: boolean              // 업로드 성공 여부
  project_id: string           // 프로젝트 ID (UUID)
  document_ids: string[]       // 업로드된 문서 ID 목록 (UUID[])
  documents: Array<{
    id: string
    filename: string
    content_type: string
    status: IDocumentStatus
  }>
  errors: Array<{
    filename: string
    error: string
  }>
  failed_uploads: string[]
  message: string
}
