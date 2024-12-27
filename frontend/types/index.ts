export interface Document {
  id: string
  filename: string
  status: DocumentStatus
}

export type DocumentStatus = {
  id: string
  filename: string
  status: 'UPLOADING' | 'PROCESSING' | 'COMPLETED' | 'FAILED' | 'ERROR'
  error_message?: string
}

export interface Message {
  role: 'user' | 'assistant'
  content: string
}

export interface TableData {
  Document: string
  status: 'PROCESSING' | 'COMPLETED' | 'ERROR'
  id: string
}

export interface Template {
  id: string
  name: string
  content: string
}

export interface ProjectItem {
  name: string
  children?: ProjectItem[]
}
