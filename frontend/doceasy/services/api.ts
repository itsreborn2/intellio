const API_BASE_URL = process.env.NEXT_PUBLIC_API_URL
export const API_ENDPOINT = `${API_BASE_URL}/v1`

import * as Types from '@/types/index';
import { format, parseISO } from 'date-fns';
import { ko } from 'date-fns/locale';
//import { IDocument, ITableData, IMessage, ITemplate, IProjectItem, IDocumentUploadResponse } from '@/types';  
import {  ProjectListResponse, IRecentProjectsResponse, ProjectDetail, IUploadProgressCallback, IDocumentUploadResponse, DocumentStatus, Category, ProjectCategory, IProject, DocumentStatusResponse } from '@/types/index';
import { defaultFetchOptions, IApiProject, IApiRecentProjectsResponse } from '@/types/index';
import { IChatRequest, IChatResponse, TableResponse, IDocument, IMessage } from '@/types';

// // 문서 업로드 응답 인터페이스
// export interface IDocumentUploadResponse {
//   success: boolean;              // 업로드 성공 여부
//   project_id: string;           // 프로젝트 ID (UUID)
//   document_ids: string[];       // 업로드된 문서 ID 목록 (UUID[])
//   documents: Array<{
//     id: string
//     filename: string
//     content_type: string
//     status: string
//   }>
//   errors: Array<{
//     filename: string
//     error: string
//   }>
//   failed_uploads: string[]
//   message: string
// }

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
  retention_period: string = 'THIRTY_DAYS'
): Promise<IProject> => {
  console.debug('Creating project with:', { name, description, retention_period })
  
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
    console.debug('Project created successfully:', project)
    
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

export const getProjectList = async (): Promise<ProjectListResponse> => {
  const response = await apiFetch(`${API_ENDPOINT}/projects`, {
    credentials: 'include'
  });

  if (!response.ok) {
    throw new Error('프로젝트 목록을 가져오는데 실패했습니다.');
  }

  return response.json();
};

const sanitizeFileName = (fileName: string): string => {
  // 파일 확장자 분리
  const lastDot = fileName.lastIndexOf('.');
  const name = fileName.substring(0, lastDot);
  const ext = fileName.substring(lastDot);
  
  // 특수문자를 언더스코어로 변경
  const sanitized = name.replace(/[^a-zA-Z0-9가-힣\s-]/g, '_');
  
  return sanitized + ext;
};

export interface IUploadProgressData {
  filename: string
  total_files: number
  processed_files: number
  document?: {
    id: string
    filename: string
    content_type?: string
    status: string
  }
}

export const uploadDocument = async (
  projectId: string, 
  files: File[],
  callbacks?: IUploadProgressCallback
): Promise<void> => {
  try {
    const formData = new FormData()
    files.forEach(file => {
      const sanitizedName = sanitizeFileName(file.name)
      formData.append('files', file, sanitizedName)
    })

    const response = await apiFetch(`${API_ENDPOINT}/documents/projects/${projectId}/upload`, {
      method: 'POST',
      headers: {
        'Accept': 'text/event-stream',
        'X-Requested-With': 'XMLHttpRequest'
      },
      body: formData
    })

    if (!response.ok) {
      if (response.status === 401) {
        window.dispatchEvent(new CustomEvent('sessionExpired'))
        throw new Error('세션이 만료되었습니다. 다시 로그인해주세요.')
      }
      throw new Error(`Upload failed with status ${response.status}`)
    }

    const reader = response.body?.getReader()
    if (!reader) {
      throw new Error('Failed to get response reader')
    }

    const decoder = new TextDecoder()
    let buffer = ''

    while (true) {
      const { done, value } = await reader.read()
      if (done) break

      buffer += decoder.decode(value, { stream: true })
      const lines = buffer.split('\n')
      buffer = lines.pop() || ''

      for (const line of lines) {
        if (line.trim() === '') continue
        if (!line.startsWith('data:')) continue

        try {
          const eventData = line.slice(5).trim() // Remove 'data:' prefix and trim whitespace
          if (!eventData) continue
          try {
            const parsedData = JSON.parse(eventData)
            if (!parsedData.event || !parsedData.data) continue

            switch (parsedData.event) {
              case 'upload_progress':
                callbacks?.onProgress?.(parsedData.data)
                break
              case 'upload_error':
                const errorData = parsedData.data
                callbacks?.onError?.(new Error(errorData.error))
                break
              case 'upload_complete':
                callbacks?.onComplete?.(parsedData.data)
                break
              case 'error':
                const error = parsedData.data
                throw new Error(error.error)
            }
          } catch (e) {
            console.error('Failed to parse SSE data:', e, 'Line:', line)
            continue
          }
        } catch (e) {
          console.error('Failed to parse SSE data:', e, 'Line:', line)
        }
      }
    }
  } catch (error) {
    console.error('Upload failed:', error)
    callbacks?.onError?.(error instanceof Error ? error : new Error(String(error)))
    throw error
  }
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
): Promise<IProject> => {
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

export const searchTable = async (projectId: string, documentIds: string[], query: string): Promise<TableResponse> => {
  try {
    console.log('테이블 검색 요청:', { query, documentIds, mode: 'table' });
    
    const response = await apiFetch(`${API_ENDPOINT}/rag/table/search`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify({
        //user_id,
        project_id : projectId,
        document_ids: documentIds,
        query,
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

export const searchTableStream = async (
  projectId: string, 
  documentIds: string[], 
  query: string,
  callbacks?: {
    onStart?: () => void;
    onProgress?: (data: any) => void;
    onHeader?: (data: any) => void;
    onCell?: (data: any) => void;
    onCompleted?: (data: any) => void;
    onError?: (error: Error) => void;
  }
): Promise<void> => {
  try {
    console.log('테이블 검색 스트리밍 요청:', { query, documentIds, mode: 'table' });
    
    callbacks?.onStart?.();
    
    const response = await apiFetch(`${API_ENDPOINT}/rag/table/search/stream`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'Accept': 'text/event-stream'
      },
      body: JSON.stringify({
        project_id: projectId,
        document_ids: documentIds,
        query,
        mode: 'table'
      }),
      credentials: 'include'
    });

    // 응답 헤더 로깅
    console.log('테이블 스트리밍 응답 헤더:');
    const headers: Record<string, string> = {};
    response.headers.forEach((value, key) => {
      console.log(`${key}: ${value}`);
      headers[key] = value;
    });

    // 콘텐츠 타입 확인
    const contentType = response.headers.get('content-type');
    console.log('응답 콘텐츠 타입:', contentType);
    
    if (!contentType || !contentType.includes('text/event-stream')) {
      console.warn('경고: 응답이 SSE 형식이 아닐 수 있음. 콘텐츠 타입:', contentType);
    }

    if (!response.ok) {
      const errorData = await response.text().catch(() => 'Unknown error');
      throw new Error(`테이블 검색 실패: ${errorData}`);
    }

    if (!response.body) {
      throw new Error('응답 본문이 없습니다');
    }

    const reader = response.body.getReader();
    const decoder = new TextDecoder();
    let buffer = '';

    while (true) {
      const { done, value } = await reader.read();
      
      if (done) {
        // 남은 데이터 처리
        if (buffer.trim()) {
          processData(buffer);
        }
        break;
      }
      
      // 새 데이터를 버퍼에 추가
      buffer += decoder.decode(value, { stream: true });
      
      // 줄바꿈을 기준으로 데이터 처리
      const lines = buffer.split('\n');
      buffer = lines.pop() || ''; // 마지막 라인은 불완전할 수 있으므로 버퍼에 유지
      
      for (const line of lines) {
        if (line.trim()) {
          processData(line);
        }
      }
    }

    function processData(line: string) {
      try {
        // 표준 SSE 이벤트 형식 처리 (event: xxx, data: xxx 형태)
        if (line.startsWith('event:')) {
          // 이벤트 라인 발견, 다음 데이터 라인을 기다립니다.
          console.debug('SSE 이벤트 타입 발견:', line.substring(6).trim());
          return;
        }
        
        // data: 라인 처리
        if (line.startsWith('data:')) {
          let jsonStr = line.substring(5).trim();
          console.debug('SSE 데이터 원본:', jsonStr);
          
          // 간단한 문자열 패턴이면 바로 처리
          if (jsonStr === '[DONE]') {
            return;
          }
          
          try {
            // 1. 기본 전처리: Python -> JavaScript 형식 변환
            jsonStr = jsonStr
              // 속성명의 작은따옴표를 큰따옴표로 변환
              .replace(/'([^']+)':/g, '"$1":')
              // Python 불리언 값 처리 (True -> true, False -> false)
              .replace(/:\s*True(\s*[,}]|$)/g, ': true$1')
              .replace(/:\s*False(\s*[,}]|$)/g, ': false$1');
            
            console.debug('전처리된 JSON 문자열:', jsonStr);
            
            // 2. JSON 파싱 시도
            let eventData;
            try {
              eventData = JSON.parse(jsonStr);
              console.debug('JSON 파싱 성공:', eventData);
            } catch (jsonError) {
              const errorMessage = jsonError instanceof Error ? jsonError.message : String(jsonError);
              console.warn('JSON 파싱 실패:', errorMessage);
              
              // 추가 정제 시도: 이스케이프 처리
              try {
                const cleanedStr = jsonStr
                  .replace(/[\n\r\t]/g, match => {
                    if (match === '\n') return '\\n';
                    if (match === '\r') return '\\r';
                    if (match === '\t') return '\\t';
                    return match;
                  });
                
                eventData = JSON.parse(cleanedStr);
                console.debug('정제 후 JSON 파싱 성공:', eventData);
              } catch (error) {
                console.error('JSON 파싱 최종 실패:', error);
                return;
              }
            }
            
            // 3. 이벤트 타입 결정 및 처리
            // 명시적 이벤트 타입이 있는 경우
            if (eventData.event) {
              handleEvent(eventData.event, eventData.data || eventData);
              return;
            }
            
            // 이벤트 타입이 없는 경우 데이터 구조로 판단
            const eventType = determineEventType(eventData);
            handleEvent(eventType, eventData);
            
          } catch (sseError) {
            console.error('SSE 데이터 처리 실패:', sseError);
          }
          return;
        }
      } catch (e) {
        console.error('데이터 처리 중 오류:', e);
      }
    }
    
    // 이벤트 타입 결정 함수
    function determineEventType(data: any): string {
      // 백엔드 이벤트 구조에 맞춰 타입 결정
      if (data.header_name) return 'header';
      if (data.doc_id && data.content) return 'cell_result';
      if (data.doc_id) return 'cell_processing';
      if (data.message && typeof data.progress === 'number') return 'progress';
      if (data.is_completed || data.completed) return 'completed';
      return 'unknown';
    }

    function handleEvent(eventType: string, eventData: any) {
      console.log(`이벤트 처리: ${eventType}`, eventData);
      
      switch (eventType) {
        case 'header':
          callbacks?.onHeader?.(eventData);
          break;
          
        case 'cell_processing':
        case 'cell_result':
          callbacks?.onCell?.({
            event: eventType,
            ...(eventData.doc_id ? eventData : { doc_id: eventData.data?.doc_id })
          });
          break;
          
        case 'progress':
          callbacks?.onProgress?.(eventData);
          break;
          
        case 'error':
          // 오류 메시지 처리 (다양한 형식 지원)
          const errorMessage = 
            typeof eventData === 'string' ? eventData :
            eventData.message ? eventData.message :
            eventData.error ? eventData.error :
            eventData.detail ? eventData.detail :
            '테이블 분석 중 오류 발생';
          
          callbacks?.onError?.(new Error(errorMessage));
          break;
          
        case 'completed':
          callbacks?.onCompleted?.(eventData);
          break;
          
        case 'unknown':
        default:
          console.warn('알 수 없는 이벤트 타입:', eventType, eventData);
          // 데이터 구조에 따라 적절한 콜백 호출
          if (eventData.header_name) {
            callbacks?.onHeader?.(eventData);
          } else if (eventData.doc_id && eventData.content) {
            callbacks?.onCell?.({
              event: 'cell_result',
              ...eventData
            });
          } else if (eventData.doc_id) {
            callbacks?.onCell?.({
              event: 'cell_processing',
              ...eventData
            });
          } else if (eventData.message) {
            callbacks?.onProgress?.(eventData);
          } else if (eventData.is_completed || eventData.completed) {
            callbacks?.onCompleted?.(eventData);
          }
          break;
      }
    }
  } catch (error) {
    console.error('테이블 검색 중 오류:', error);
    callbacks?.onError?.(error instanceof Error ? error : new Error(String(error)));
    throw error;
  }
};

export async function sendChatMessage(
  projectId: string,
  documentIds: string[],
  message: string
): Promise<IChatResponse> {
  const requestBody: IChatRequest = {
    project_id: projectId,
    document_ids: documentIds,
    message
  };

  const response = await apiFetch(`${API_ENDPOINT}/rag/chat`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
    },
    body: JSON.stringify(requestBody),
  });

  if (!response.ok) {
    throw new Error('채팅 요청 실패');
  }

  // 여기 주석 삭제 금지.
  // 응답 구조
  // End User에게 굳이 청크인 context를 보여줄 필요가 있는가?
  // 그냥 응답으로 answer만 받으면 되는거 아녀?
  // answer : string,
  // context : { 
  //   chunk_id : string[], 
  //   score : number, float
  //   text : string,
  //   document_id : string
  //   chunk_index : number
  // }
  const data: string = await response.json();
  console.log('채팅 응답:', data);

  // // 예시: 응답 데이터 사용
  // if (data.success && data.data.messages) {
  //   console.log('메시지 목록:', data.data.messages);
  // } else if (data.error) {
  //   console.error('에러:', data.error);
  // }

  //return data;
  return {
    role: 'assistant',
    content: data
  }
}



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

export const getRecentProjects = async (): Promise<IRecentProjectsResponse> => {
  try {
    const response = await apiFetch(`${API_ENDPOINT}/projects/recent`, {
      method: 'GET', // 명시적 메서드 지정
      credentials: 'include' // 단순히 브라우저에 저장된 쿠키를 HTTP 요청에 포함시키라는 의미
    });
    // 인증 오류 처리
    if (response.status === 401) {
      console.warn('사용자 인증이 필요합니다.');
      return {
        today: [],
        last_7_days: [],
        last_30_days: []
      };
    }
    if (!response.ok) {
      throw new Error(`Failed to fetch recent projects: ${response.status}`);
    }
    const data: IApiRecentProjectsResponse = await response.json();
   // 날짜 포맷팅
    const formatProjects = (projects: IApiProject[]): IProject[] => {
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
        retention_period: 'THIRTY_DAYS',
        will_be_deleted: project.is_temporary && project.created_at ?
          new Date(project.created_at).getTime() < new Date().getTime() - 30 * 24 * 60 * 60 * 1000 : false
      }));
    };
    
    const result: IRecentProjectsResponse = {
      today: formatProjects(data.today || []),
      last_7_days: formatProjects(data.last_7_days || []),
      last_30_days: formatProjects(data.last_30_days || [])
    };

    return result;
  } catch (error) {
    console.error('Error fetching recent projects:', error);
    return {
      today: [],
      last_7_days: [],
      last_30_days: []
    };
  }
};

// 1개의 프로젝트를 조회하는 함수
export const getProjectInfo = async (projectId: string): Promise<ProjectDetail> => {
  try {
    const response = await apiFetch(`${API_ENDPOINT}/projects/${projectId}`, {
      credentials: 'include'
    });

    if (!response.ok) {
      throw new Error(`Failed to fetch project: ${response.statusText}`);
    }
    const project:ProjectDetail = await response.json();
    // response.json()
  //   {
  //     "id": "550e8400-e29b-41d4-a716-446655440000",
  //     "name": "프로젝트명",
  //     "description": "설명",
  //     "is_temporary": false,
  //     "created_at": "2025-01-11T12:10:42",
  //     "updated_at": "2025-01-11T12:10:42",
  //     "session_id": "some-session-id",
  //     "user_id": "123e4567-e89b-12d3-a456-426614174000"
  // }
    return project;

  } catch (error) {
    console.error('Error fetching project:', error);
    throw error;
  }
};

// 프로젝트의 문서 목록을 가져옵니다.
// @param projectId 프로젝트 ID
export const getDocumentList = async (projectId: string): Promise<{ [id: string]: IDocument }> => {
  try {
    const response = await apiFetch(`${API_ENDPOINT}/documents/list/${projectId}`, {
      credentials: 'include'
    });
    
    const temp = await response.json();
    //console.log('getDocumentList[temp]:', temp);  // 객체 그대로 출력
    
    // 문서 배열을 key-value 객체로 변환
    const result = temp.items.reduce((acc: { [key: string]: IDocument }, doc: IDocument) => {
      acc[doc.id] = doc;
      return acc;
    
    }, {});

    //console.log(`getDocumentList : `, result)
    return result
  } catch (error) {
    console.error('문서 목록 조회 실패:', error);
    throw error;
  }
};

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
  try {
    const response = await apiFetch(`${API_ENDPOINT}/categories`, {
      method: 'GET', // 명시적 메서드 지정
      credentials: 'include'
    });

    if (!response.ok) {
      const errorData = await response.json().catch(() => ({ detail: '알 수 없는 오류가 발생했습니다.' }));
      console.error('카테고리 조회 실패:', errorData);
      throw new Error(errorData.detail || '카테고리 조회에 실패했습니다.');
    }

    return response.json();
  } catch (error) {
    console.error('카테고리 조회 중 오류 발생:', error);
    throw error;
  }
};

// 프로젝트를 카테고리에 추가
export const addProjectToCategory = async (
  projectId: string, 
  categoryId: string
): Promise<IProject> => {
  const response = await apiFetch(
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

  if (!response.ok) {
    const errorData = await response.json().catch(() => null);
    throw new Error(errorData?.detail || `프로젝트를 카테고리에 추가하는데 실패했습니다. 상태 코드: ${response.status}`);
  }

  return response.json();
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

// OAuth 로그인 응답 인터페이스
export interface IOAuthLoginResponse {
  user: {
    id: string;
    email: string;
    name: string;
    provider: string;
  };
  token: string;
}

// OAuth 로그인 처리
export const socialLogin = async (code: string, provider: string): Promise<IOAuthLoginResponse> => {
  const response = await apiFetch(`${API_ENDPOINT}/auth/${provider}/callback`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
    },
    body: JSON.stringify({ code }),
  });
  
  if (!response.ok) {
    throw new Error('Social login failed');
  }
  
  return response.json();
};

// 인증 상태 확인
export const checkAuth = async (): Promise<IOAuthLoginResponse> => {
  const response = await apiFetch(`${API_ENDPOINT}/auth/me`, {
    method: 'GET',
  });
  
  if (!response.ok) {
    throw new Error('Auth check failed');
  }
  
  return response.json();
};

// 로그아웃
export const logout = async (): Promise<void> => {
  try {
    const response = await apiFetch(`${API_ENDPOINT}/auth/logout`, {
      method: 'POST',
      credentials: 'include',  // 쿠키를 포함하여 요청
    });
    console.log('[Logout] 상태:', { 
      response: response.status, 
      cookiesBefore: document.cookie 
    });
    
    // 클라이언트 쿠키 삭제 - 도메인 지정
    document.cookie = 'session_id=; expires=Thu, 01 Jan 1970 00:00:00 UTC; path=/; domain=.intellio.kr;';
    document.cookie = 'user=; expires=Thu, 01 Jan 1970 00:00:00 UTC; path=/; domain=.intellio.kr;';
    document.cookie = 'token=; expires=Thu, 01 Jan 1970 00:00:00 UTC; path=/; domain=.intellio.kr;';
    
    console.log('[Logout] 완료:', { cookiesAfter: document.cookie });
  } catch (error) {
    console.error('[Logout] 실패:', error);
    throw error;
  }
};

export async function getTableHistory(projectId: string) {
  try {
    const response = await apiFetch(`${API_ENDPOINT}/table-history/project/${projectId}`, {
      method: 'GET',
      headers: {
        'Content-Type': 'application/json',
      },
      credentials: 'include'
    });

    if (!response.ok) {
      throw new Error('테이블 히스토리를 가져오는데 실패했습니다.');
    }

    return await response.json();
  } catch (error) {
    console.error('테이블 히스토리 요청 실패:', error);
    throw error;
  }
}

export async function updateProjectName(projectId: string, newName: string): Promise<IProject> {
  try {
    const response = await apiFetch(`${API_ENDPOINT}/projects/${projectId}`, {
      method: 'PUT',  // PATCH에서 PUT으로 변경
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify({
        name: newName,
      }),
    });

    if (!response.ok) {
      throw new Error('프로젝트 이름 업데이트 실패');
    }

    const data = await response.json();
    return data;
  } catch (error) {
    console.error('프로젝트 이름 업데이트 중 오류 발생:', error);
    throw error;
  }
}

export async function sendChatMessage_streaming(
  projectId: string,
  documentIds: string[],
  message: string
): Promise<Response> {
  const requestBody: IChatRequest = {
    project_id: projectId,
    document_ids: documentIds,
    message
  }

  const response = await apiFetch(`${API_ENDPOINT}/rag/chat`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      'Accept': 'text/event-stream',
    },
    body: JSON.stringify(requestBody),
  })

  if (!response.ok) {
    throw new Error('채팅 요청 실패')
  }

  return response
}

export async function updateCategory(
  categoryId: string, 
  data: { name: string }
): Promise<Category> {
  const response = await apiFetch(
    `${API_ENDPOINT}/categories/${categoryId}`,
    {
      method: 'PUT',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify(data),
    }
  );

  if (!response.ok) {
    throw new Error('카테고리 업데이트 실패');
  }

  return response.json();
}

// 프로젝트 삭제
export const deleteProject = async (projectId: string): Promise<void> => {
  try {
    // 카테고리 라우터를 통한 프로젝트 삭제
    const response = await apiFetch(`${API_ENDPOINT}/categories/projects/${projectId}`, {
      method: 'DELETE',
    });

    if (!response.ok) {
      const errorData = await response.json().catch(() => ({}));
      throw new Error(errorData.detail || '프로젝트 삭제 실패');
    }
  } catch (error) {
    console.error('프로젝트 삭제 중 오류 발생:', error);
    throw error;
  }
}

export async function stopChatMessageGeneration(
  projectId: string
): Promise<void> {
  const response = await apiFetch(`${API_ENDPOINT}/rag/chat/stop`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
    },
    body: JSON.stringify({ project_id: projectId }),
  })

  if (!response.ok) {
    throw new Error('메시지 생성 중지 요청 실패')
  }
}

export async function getChatHistory(projectId: string): Promise<IMessage[]> {
  const response = await apiFetch(`${API_ENDPOINT}/rag/chat/history/${projectId}`);
  if (!response.ok) {
    throw new Error('대화 기록 조회 실패');
  }
  return response.json();
}


export async function getDocumentUploadStatus(documentIds: string[]): Promise<DocumentStatusResponse[]> {
  console.log('getDocumentUploadStatus', documentIds)
  const response = await apiFetch(`${API_ENDPOINT}/rag/document-status`, {
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
  
  const statuses: DocumentStatusResponse[] = await response.json()
  return statuses
}

