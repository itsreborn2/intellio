//////////////////////////////////////////////////////////////
// 프로젝트 목록 관련 인터페이스
//////////////////////////////////////////////////////////////
export interface Category {
  id: string;
  name: string;
  parent_id?: string;
  created_at: string;
}

export interface ProjectCategory {
  id: string;
  project_id: string;
  category_id: string;
}

export interface Template {
  id: string
  name: string
  description: string
}

export interface SidebarProps {
  className?: string;
}

// API 응답의 프로젝트 타입
export interface IApiProject {
  id: string;
  name: string;
  created_at: string;
  updated_at: string;
  is_temporary: boolean;
  category_id?: string;
}

// 프로젝트 관련 인터페이스
export interface IProject {
  id: string
  name: string
  description?: string
  is_temporary: boolean
  retention_period: string
  created_at: string
  updated_at: string
  formatted_date?: string;  // 한국어로 포맷된 날짜
  category_id?: string;  // 카테고리 ID 추가
}

export interface ProjectListResponse {
  total: number
  items: IProject[]
}

// 문서 상태 타입
export type IDocumentStatus = 'UPLOADING' | 'PROCESSING' | 'COMPLETED' | 'FAILED' | 'ERROR'

// 메시지 인터페이스
export interface IMessage {
  role: 'user' | 'assistant'
  content: string
  timestamp?: string
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

// 업로드 진행 상태 콜백 인터페이스
export interface IUploadProgressCallback {
  onProgress?: (totalProgress: number) => void;
  onComplete?: (response: IDocumentUploadResponse) => void;
  onError?: (error: Error) => void;
}

// Table관련되는 인터페이스

export interface TableColumn {
  header: {
    name: string;
    prompt: string;
  };
  cells: {
    doc_id: string;
    content: string;
  }[];
  [key: string]: any;
}

// 응답
export interface TableResponse {
  columns: TableColumn[];
}

export interface ICell {
  docId:string // x축row
  header:string // y축col
  value:string
}
// 문서 관련 인터페이스. 테이블의 row 1개 담당
export interface IDocument {
  id: string
  filename: string
  project_id: string
  status: IDocumentStatus
  content_type?: string
  added_col_context?: Array<ICell> // 추가된 셀. 헤더정보(name), 셀내용
}

// 문서 상태 인터페이스
export interface DocumentStatus {
  id: string
  filename: string
  status: 'UPLOADING' | 'PROCESSING' | 'COMPLETED' | 'FAILED'
  error_message?: string
}

// 문서 업로드 응답 인터페이스
export interface IDocumentUploadResponse {
  success: boolean              // 업로드 성공 여부
  project_id: string           // 프로젝트 ID (UUID)
  document_ids: string[]       // 업로드된 문서 ID 목록 (UUID[])
  documents: Array<IDocument>
  errors: Array<{
    filename: string
    error: string
  }>
  failed_uploads: string[]
  message: string
}

export interface ProjectDetail {
  id: string;
  name: string;
  description?: string;
  documents: IDocument[];
  messages: Array<IMessage>;
  analysis: {
    mode: 'chat' | 'table';
    columns: string[];
    columnPrompts: { [key: string]: string };
    tableData: {
      columns: Array<{
        id: string;
        header: {
          name: string;
          prompt: string;
        };
        cells: Array<{
          doc_id: string;
          content: string;
        }>;
      }>;
    };
  };
  created_at: string;
  updated_at: string;
}

// API 응답 타입 정의
export interface IApiRecentProjectsResponse {
  today: IApiProject[];
  yesterday: IApiProject[];
  four_days_ago: IApiProject[];
  older: IApiProject[];
}

// 최근 프로젝트 응답 타입 정의
export interface IRecentProjectsResponse {
  today: IProject[];
  yesterday: IProject[];
  four_days_ago: IProject[];
  older: IProject[];
}

// API 요청을 위한 기본 설정
export const defaultFetchOptions: RequestInit = {
  credentials: 'include',
  headers: {
    'Accept': 'application/json',
    'X-Requested-With': 'XMLHttpRequest'
  }
};

export interface IChatRequest {
  project_id: string
  document_ids: string[]
  message: string
}

export interface IChatResponse {
  role: 'assistant'
  content: string
  timestamp?: string
}