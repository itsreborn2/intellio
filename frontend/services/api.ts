const API_BASE_URL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000'
const API_ENDPOINT = `${API_BASE_URL}/api/v1`

import { format, parseISO } from 'date-fns';
import { ko } from 'date-fns/locale';

export interface Project {
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
  items: Project[]
}

export interface UploadResponse {
  success: boolean
  project_id: string
  document_ids: string[]
  documents: Array<{
    id: string
    filename: string
    content_type: string
    status: string
  }>
  errors: Array<{
    filename: string
    error: string
  }>
  failed_uploads: string[]
  message: string
}

export interface DocumentStatus {
  id: string
  filename: string
  status: 'UPLOADING' | 'PROCESSING' | 'COMPLETED' | 'FAILED'
  error_message?: string
}

export interface UploadProgressCallback {
  onProgress?: (totalProgress: number) => void;
  onComplete?: (response: UploadResponse) => void;
  onError?: (error: Error) => void;
}

export interface ProjectDetail {
  id: string;
  name: string;
  description?: string;
  documents: Array<{
    id: string;
    filename: string;
    status: string;
    content_type: string;
  }>;
  messages: Array<{
    role: string;
    content: string;
    timestamp: string;
  }>;
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

// API 요청을 위한 기본 설정
const defaultFetchOptions: RequestInit = {
  credentials: 'include',
  headers: {
    'Accept': 'application/json',
    'X-Requested-With': 'XMLHttpRequest'
  }
};

// fetch 함수 래퍼
const apiFetch = async (url: string, options: RequestInit = {}) => {
  try {
    const response = await fetch(url, {
      ...defaultFetchOptions,
      ...options,
      headers: {
        ...defaultFetchOptions.headers,
        ...options.headers,
      }
    });

    if (response.status === 401) {
      // 세션 만료 이벤트 발생
      window.dispatchEvent(new CustomEvent('sessionExpired'));
      throw new Error('세션이 만료되었습니다. 다시 로그인해주세요.');
    }

    return response;
  } catch (error) {
    console.error('API request failed:', error);
    throw error;
  }
};

export const createProject = async (
  name: string, 
  description?: string, 
  retention_period: string = 'FIVE_DAYS'
): Promise<Project> => {
  console.log('Creating project with:', { name, description, retention_period })
  
  try {
    const response = await apiFetch(`${API_ENDPOINT}/projects/`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify({
        name,
        description,
        is_temporary: true,
        retention_period
      }),
    })

    if (!response.ok) {
      const errorData = await response.json().catch(() => null)
      console.error('Project creation failed:', {
        status: response.status,
        statusText: response.statusText,
        errorData
      })
      throw new Error(
        errorData?.detail || 
        `Project creation failed with status ${response.status}: ${response.statusText}`
      )
    }

    const project = await response.json()
    console.log('Project created successfully:', project)
    
    // 프로젝트 생성 이벤트 발생
    const projectCreatedEvent = new CustomEvent('projectCreated', {
      detail: project
    })
    window.dispatchEvent(projectCreatedEvent)
    
    return project
  } catch (error: any) {
    console.error('Project creation request failed:', error)
    throw error
  }
}

export const getProjects = async (): Promise<ProjectListResponse> => {
  const response = await apiFetch(`${API_ENDPOINT}/projects/`, {
    credentials: 'include'  // 쿠키 포함
  })
  
  if (!response.ok) {
    throw new Error('Failed to get projects')
  }

  return response.json()
}

const sanitizeFileName = (fileName: string): string => {
  // 파일 확장자 분리
  const lastDot = fileName.lastIndexOf('.');
  const name = fileName.substring(0, lastDot);
  const ext = fileName.substring(lastDot);
  
  // 특수문자를 언더스코어로 변경
  const sanitized = name.replace(/[^a-zA-Z0-9가-힣\s-]/g, '_');
  
  return sanitized + ext;
};

export const uploadDocument = async (
  projectId: string, 
  files: File | File[],
  callbacks?: UploadProgressCallback
): Promise<UploadResponse> => {
  return new Promise(async (resolve, reject) => {
    try {
      const formData = new FormData()
      const fileList = Array.isArray(files) ? files : [files]
      
      fileList.forEach(file => {
        const sanitizedName = sanitizeFileName(file.name)
        formData.append('files', file, sanitizedName)
      })

      const response = await apiFetch(`${API_ENDPOINT}/documents/projects/${projectId}/upload`, {
        method: 'POST',
        headers: {
          'Accept': 'application/json',
          'X-Requested-With': 'XMLHttpRequest'
        },
        body: formData
      })

      if (!response.ok) {
        const errorData = await response.json().catch(() => null)
        if (response.status === 401) {
          // 세션 만료 처리
          window.dispatchEvent(new CustomEvent('sessionExpired'));
          throw new Error('세션이 만료되었습니다. 다시 로그인해주세요.');
        }
        throw new Error(errorData?.detail || `Upload failed with status ${response.status}`)
      }

      const result = await response.json()
      
      if (callbacks?.onComplete) {
        callbacks.onComplete(result)
      }
      
      resolve(result)
    } catch (error) {
      console.error('Upload failed:', error)
      if (callbacks?.onError) {
        callbacks.onError(error as Error)
      }
      reject(error)
    }
  })
}
// api.ts에 추가
export async function getDocumentContent(documentId: string): Promise<string> {
  const response = await apiFetch(`${API_ENDPOINT}/documents/${documentId}/content`);
  return response.text();
}

export const getDocumentStatus = async (documentId: string): Promise<DocumentStatus> => {
  const response = await apiFetch(`${API_ENDPOINT}/documents/${documentId}`, {
    credentials: 'include'  // 쿠키 포함
  })
  
  if (!response.ok) {
    throw new Error('Failed to get document status')
  }

  return response.json()
}

export const updateProjectToPermanent = async (
  projectId: string, 
  categoryId: string
): Promise<Project> => {
  const response = await apiFetch(`${API_ENDPOINT}/projects/${projectId}`, {
    method: 'PUT',
    credentials: 'include',  // 쿠키 포함
    headers: {
      'Content-Type': 'application/json',
    },
    body: JSON.stringify({
      is_temporary: false,
      category_id: categoryId
    }),
  })

  if (!response.ok) {
    throw new Error('Failed to update project')
  }

  return response.json()
}

export const searchTable = async (projectId: string, documentIds: string[], query: string) => {
  try {
    console.log('테이블 검색 요청:', { query, documentIds, mode: 'table' });
    
    const response = await apiFetch(`${API_ENDPOINT}/rag/table/search`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify({
        query,
        document_ids: documentIds,
        mode: 'table'
      }),
      credentials: 'include'
    });

    if (!response.ok) {
      const errorData = await response.json().catch(() => ({}));
      console.error('테이블 검색 실패:', errorData);
      throw new Error(errorData.detail || '테이블 검색 실패');
    }

    const data = await response.json();
    console.log('테이블 검색 응답:', data);

    // 응답 데이터 검증 및 변환
    if (!data || typeof data !== 'object') {
      console.warn('잘못된 응답 데이터 형식:', data);
      return { columns: [] };
    }

    // columns가 없거나 배열이 아닌 경우 빈 배열 반환
    if (!data.columns || !Array.isArray(data.columns)) {
      console.warn('columns 데이터 없음 또는 잘못된 형식:', data);
      return { columns: [] };
    }

    // 응답 데이터를 테이블 형식으로 변환
    return {
      columns: data.columns.map((col: { 
        header?: { 
          name?: string; 
          prompt?: string; 
        }; 
        cells?: Array<{
          doc_id?: string;
          content?: string;
        }>;
      }) => ({
        header: {
          name: col.header?.name || '',
          prompt: col.header?.prompt || ''
        },
        cells: Array.isArray(col.cells) ? col.cells.map((cell: {
          doc_id?: string;
          content?: string;
        }) => ({
          doc_id: cell.doc_id || '',
          content: cell.content || ''
        })) : []
      }))
    };
  } catch (error) {
    console.error('테이블 검색 중 오류:', error);
    throw error;
  }
};

export const chat = async (
  projectId: string,
  documentIds: string[],// eslint-disable-next-line @typescript-eslint/no-explicit-any
  message: string
): Promise<{ message: string }> => {
  try {
    const response = await apiFetch(`${API_ENDPOINT}/rag/chat`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify({
        project_id: projectId,
        document_ids: documentIds,
        message
      }),
    });

    if (!response.ok) {
      throw new Error('채팅 요청 실패');
    }

    const data = await response.json();
    console.log('채팅 응답:', data);

    if (!data || typeof data.answer !== 'string') {
      console.warn('잘못된 응답 데이터:', data);
      throw new Error('잘못된 응답 형식');
    }

    // answer 필드를 message로 변환하여 반환
    return { message: data.answer };
  } catch (error) {
    console.error('채팅 중 오류:', error);
    throw error;
  }
};

export const autosaveProject = async (
  projectId: string, 
  data: any
): Promise<any> => {
  const response = await apiFetch(`${API_ENDPOINT}/projects/${projectId}/autosave`, {
    method: 'PUT',
    credentials: 'include',
    headers: {
      'Content-Type': 'application/json',
    },
    body: JSON.stringify(data),
  });

  if (!response.ok) {
    throw new Error('Failed to autosave project')
  }

  return response.json()
};

// 세션 관련 API 함수들
export const checkSession = async (): Promise<{
  sessionId: string;
  isLoggedIn: boolean;
  userId?: string;
}> => {
  const response = await apiFetch(`${API_ENDPOINT}/session/check`, {
    credentials: 'include',
    headers: {
      'Cache-Control': 'no-cache',  // 캐시 비활성화
      'Pragma': 'no-cache'
    }
  });

  if (!response.ok) {
    // 세션이 없는 경우 기본값 반환
    if (response.status === 401) {
      return {
        sessionId: '',
        isLoggedIn: false
      };
    }
    throw new Error('Failed to check session');
  }

  return response.json();
};

export const getRecentProjects = async (): Promise<{
  today: Array<{
    id: string;
    title: string;
    name: string;
    created_at: string;
    updated_at: string;
    formatted_date?: string;
    is_temporary: boolean;
    category_id?: string;
    will_be_deleted: boolean;
  }>;
  yesterday: Array<{
    id: string;
    title: string;
    name: string;
    created_at: string;
    updated_at: string;
    formatted_date?: string;
    is_temporary: boolean;
    category_id?: string;
    will_be_deleted: boolean;
  }>;
  four_days_ago: Array<{
    id: string;
    title: string;
    name: string;
    created_at: string;
    updated_at: string;
    formatted_date?: string;
    is_temporary: boolean;
    category_id?: string;
    will_be_deleted: boolean;
  }>;
}> => {
  try {
    const response = await apiFetch(`${API_ENDPOINT}/projects/recent?limit=3`, {
      credentials: 'include'
    })

    if (!response.ok) {
      throw new Error('Failed to fetch recent projects')
    }

    const data = await response.json()
  
    // 날짜 포맷팅
    const formatProjects = (projects: any[]) => {
      return projects.map(project => ({
        id: project.id,
        title: project.name,
        name: project.name,
        created_at: project.created_at,
        updated_at: project.updated_at,
        formatted_date: project.created_at ? 
          format(parseISO(project.created_at), 'PPP', { locale: ko }) : 
          undefined,
        is_temporary: project.is_temporary,
        category_id: project.category_id,
        will_be_deleted: project.is_temporary && project.created_at &&
          new Date(project.created_at).getTime() < new Date().getTime() - 4 * 24 * 60 * 60 * 1000
      }))
    }

    return {
      today: formatProjects(data.today || []),
      yesterday: formatProjects(data.yesterday || []),
      four_days_ago: formatProjects(data.four_days_ago || [])
    }
  } catch (error) {
    console.error('Error fetching recent projects:', error)
    return {
      today: [],
      yesterday: [],
      four_days_ago: []
    }
  }
};

export const getProject = async (projectId: string): Promise<ProjectDetail> => {
  try {
    const response = await apiFetch(`${API_ENDPOINT}/projects/${projectId}`, {
      credentials: 'include'
    });

    if (!response.ok) {
      throw new Error(`Failed to fetch project: ${response.statusText}`);
    }

    const project = await response.json();
    return project;
  } catch (error) {
    console.error('Error fetching project:', error);
    throw error;
  }
};

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

// 카테고리 생성
export const createCategory = async (name: string, parent_id?: string): Promise<Category> => {
  try {
    const response = await apiFetch(`${API_ENDPOINT}/categories`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify({ 
        name, 
        parent_id,
        type: "PERMANENT"  // type 명시적 추가
      }),
    });

    if (!response.ok) {
      const errorData = await response.json().catch(() => ({}));
      throw new Error(errorData.detail || '폴더 생성에 실패했습니다.');
    }

    return response.json();
  } catch (error) {
    console.error('Category creation failed:', error);
    throw error;
  }
};

// 카테고리 목록 조회
export const getCategories = async (): Promise<Category[]> => {
  const response = await apiFetch(`${API_ENDPOINT}/categories`, {
    credentials: 'include'
  });

  if (!response.ok) {
    throw new Error('Failed to fetch categories');
  }

  return response.json();
};

// 프로젝트를 카테고리에 추가
export const addProjectToCategory = async (
  projectId: string, 
  categoryId: string
): Promise<Project> => {
  return apiFetch(
    `${API_ENDPOINT}/categories/${categoryId}/projects`,
    {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json'
      },
      body: JSON.stringify({
        project_id: projectId
      })
    }
  );
}

// 카테고리의 프로젝트 목록 조회
export const getCategoryProjects = async (categoryId: string) => {
  const response = await fetch(`${API_ENDPOINT}/categories/${categoryId}/projects`, {
    method: 'GET',
    headers: {
      'Content-Type': 'application/json',
    },
    credentials: 'include'
  })

  if (!response.ok) {
    throw new Error('카테고리 프로젝트 조회 실패')
  }

  return response.json()
}

// 카테고리 삭제 함수 수정
export const deleteCategory = async (categoryId: string): Promise<void> => {
  try {
    /* // 먼저 카테고리에 속한 프로젝트들의 카테고리 연결을 해제
    const projects = await getCategoryProjects(categoryId);
    
    // 각 프로젝트의 카테고리 연결 해제
    for (const project of projects) {
      await apiFetch(`${API_ENDPOINT}/categories/${categoryId}/projects/${project.id}`, {
        method: 'DELETE',
        headers: {
          'Content-Type': 'application/json',
        }
      });
    } */
    //const data = await getCategories();
    //console.log('before delete, category : ',data);
    // 그 다음 카테고리 삭제
    const url = `${API_ENDPOINT}/categories/${categoryId}`;
    console.log('Category deletion URL: ', url);
    const response = await apiFetch(url, {
      method: 'DELETE',
      headers: {
        'Content-Type': 'application/json',
      }
    });

    if (!response.ok) {
      console.log('not ok return');
      const errorData = await response.json().catch(() => ({}));
      throw new Error(errorData.detail || '폴더 삭제에 실패했습니다.');
    }
  } catch (error) {
    console.error('Category deletion failed:', error);
    throw error;
  }
};
