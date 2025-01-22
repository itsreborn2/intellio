const API_BASE_URL = process.env.NEXT_PUBLIC_API_URL
const API_ENDPOINT = `${API_BASE_URL}/api/v1`



import * as Types from '@/types/index';

import { format, parseISO } from 'date-fns';

import { ko } from 'date-fns/locale';

//import { IDocument, ITableData, IMessage, ITemplate, IProjectItem, IDocumentUploadResponse } from '@/types';  

import {  ProjectListResponse, IRecentProjectsResponse, ProjectDetail, IUploadProgressCallback, IDocumentUploadResponse, DocumentStatus, Category, ProjectCategory, IProject } from '@/types/index';

import { defaultFetchOptions, IApiProject, IApiRecentProjectsResponse } from '@/types/index';
import { IChatRequest, IChatResponse, TableResponse, IDocument } from '@/types';

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



export const uploadDocument = async (
  projectId: string, 
  files: File | File[],
  callbacks?: IUploadProgressCallback
): Promise<IDocumentUploadResponse> => {
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
    });

    if (!response.ok) {
      const errorData = await response.json().catch(() => null)
      if (response.status === 401) {
        // 세션 만료 처리
        window.dispatchEvent(new CustomEvent('sessionExpired'));
        throw new Error('세션이 만료되었습니다. 다시 로그인해주세요.');
      }
      throw new Error(errorData?.detail || `Upload failed with status ${response.status}`)
    }

    const result: IDocumentUploadResponse = await response.json()
    console.log(`upload result : ${JSON.stringify(result)}`)
    
    if (callbacks?.onComplete) {
      callbacks.onComplete(result)
    }
    
    return result
  } catch (error) {
    console.error('Upload failed:', error)
    if (callbacks?.onError) {
      callbacks.onError(error as Error)
    }
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



// data:Any, return역시 Any, 추후 문제발생 가능성.

export const autosaveProject = async (

  projectId: string, 

  data: any

): Promise<any> => {
  return null;
  // const response = await apiFetch(`${API_ENDPOINT}/projects/${projectId}/autosave`, {
  //   method: 'PUT',
  //   credentials: 'include',
  //   headers: {
  //     'Content-Type': 'application/json',
  //   },
  //   body: JSON.stringify(data),
  // });

  // if (!response.ok) {
  //   throw new Error('Failed to autosave project')
  // }

  // return response.json()
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



export const getRecentProjects = async (): Promise<IRecentProjectsResponse> => {

  try {

    const response = await apiFetch(`${API_ENDPOINT}/projects/recent`, {

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

  await apiFetch(`${API_ENDPOINT}/auth/logout`, {

    method: 'POST',

  });

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
