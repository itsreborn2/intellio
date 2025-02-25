"use client"

import { createContext, useContext, useReducer, useEffect, useRef, useCallback } from 'react'
import { DocumentStatus, IDocumentStatus, IProject, UpdateChatMessagePayload } from '@/types'
import * as api from '@/services/api'
import { IMessage, TableResponse, TableColumn,IDocument, IRecentProjectsResponse } from '@/types'
import * as actionTypes from '@/types/actions'

interface AppState {
  sessionId: string | null
  currentProjectId: string | null
  currentProject: IProject | null
  projectTitle: string
  currentView: 'upload' | 'table' | 'chat'  // 현재 뷰 상태
  documents: { [id: string]: IDocument } // id, IDocument 딕셔너리. 프로젝트에 속한 문서들만. 다른 프로젝트 이동 시 초기화됨.
  messages: IMessage[]
  analysis: {
    mode: 'chat' | 'table'  // 분석 모드 (채팅/테이블)
    columns: string[]
    columnPrompts: { [key: string]: string }
    columnOriginalPrompts: { [key: string]: string }
    tableData: TableResponse
    selectedDocumentIds: string[]
    messages: IMessage[]
    processingColumns: string[]  // 현재 처리 중인 컬럼들
  }
  isAnalyzing: boolean
  lastAutosaved: Date | null
  hasUnsavedChanges: boolean
  recentProjects: IRecentProjectsResponse
  categoryProjects: { [key: string]: any[] }
}

type Action =
  // 전역에 영향을 주는 action
  | { type: typeof actionTypes.SET_INITIAL_STATE }
  | { type: typeof actionTypes.SET_SESSION; payload: string }
  | { type: typeof actionTypes.SET_CURRENT_PROJECT; payload: IProject }
  | { type: typeof actionTypes.SET_VIEW; payload: 'upload' | 'table' | 'chat' }
  | { type: typeof actionTypes.SET_MODE; payload: 'chat' | 'table' }
  
  // Header에서 사용하는 action
  | { type: typeof actionTypes.SET_PROJECT_TITLE; payload:string}

  // Sidebar, ProjectCategory에서 사용하는 action
  | { type: typeof actionTypes.UPDATE_RECENT_PROJECTS; payload: IRecentProjectsResponse }
  | { type: typeof actionTypes.UPDATE_CATEGORY_PROJECTS; payload: { [key: string]: IProject[] } }

  // TableSection에서 사용하는 action
  | { type: typeof actionTypes.ADD_DOCUMENTS; payload: IDocument[] }
  | { type: typeof actionTypes.ADD_CHAT_MESSAGE; payload: IMessage }
  | { type: typeof actionTypes.CLEAR_CHAT_MESSAGE }
  | { type: typeof actionTypes.SET_IS_ANALYZING; payload: boolean }
  | { type: typeof actionTypes.UPDATE_TABLE_DATA; payload: TableResponse }

  // 아직 사용하지 않는 action
  | { type: typeof actionTypes.SELECT_DOCUMENTS; payload: string[] }
  | { type: typeof actionTypes.ADD_COLUMN; payload: string }
  | { type: typeof actionTypes.DELETE_COLUMN; payload: string }
  | { type: typeof actionTypes.UPDATE_DOCUMENT_STATUS; payload: { id: string; status: IDocumentStatus } }
  | { type: typeof actionTypes.UPDATE_TABLE_COLUMNS; payload: any[] }
  | { type: typeof actionTypes.UPDATE_COLUMN_INFO; payload: { oldName: string; newName: string; prompt: string; originalPrompt: string } }
  | { type: typeof actionTypes.ADD_ANALYSIS_COLUMN; payload: { columnName: string; prompt: string; originalPrompt: string } }
  | { type: typeof actionTypes.UPDATE_COLUMN_RESULT; payload: { documentId: string; columnName: string; result: any } }
  | { type: typeof actionTypes.SET_LAST_AUTOSAVED; payload: Date }
  | { type: typeof actionTypes.SET_DOCUMENT_LIST; payload: { [key: string]: IDocument } }
  | { type: typeof actionTypes.UPDATE_CHAT_MESSAGE; payload:UpdateChatMessagePayload }
  | { type: typeof actionTypes.SET_MESSAGES; payload: IMessage[] }

const initialState: AppState = {
  sessionId: null,
  currentProjectId: null,
  currentProject: null,
  projectTitle: '',
  currentView: 'upload',
  documents: {},
  messages: [],
  analysis: {
    mode: 'chat',  // 기본값을 chat으로 설정
    columns: ['Document'],
    columnPrompts: {},
    columnOriginalPrompts: {},
    tableData: {
      columns: []
    },
    selectedDocumentIds: [],
    messages: [],
    processingColumns: []
  },
  isAnalyzing: false,
  lastAutosaved: null,
  hasUnsavedChanges: false,
  recentProjects: {
    today: [],
    last_7_days: [],
    last_30_days: []
  },
  categoryProjects: {}
}

const AppContext = createContext<{
  state: AppState
  dispatch: React.Dispatch<Action>
} | undefined>(undefined)

const appReducer = (state: AppState, action: Action): AppState => {
  let newState: AppState;

  switch (action.type) {
    case actionTypes.SET_INITIAL_STATE:
      return {
        ...initialState,
        recentProjects: state.recentProjects // 프로젝트 목록 상태 유지
      }

    case actionTypes.SET_SESSION:
      return {
        ...state,
        sessionId: action.payload
      }

    case actionTypes.SET_CURRENT_PROJECT:
      // 같은 프로젝트인 경우 문서와 분석 데이터를 유지
      if (state.currentProjectId === action.payload.id) {
        return {
          ...state,
          currentProject: action.payload
        }
      }
      
      // 다른 프로젝트로 변경하는 경우 상태 초기화
      return {
        ...state,
        currentProjectId: action.payload.id,
        currentProject: action.payload,
        documents: {},
        messages: [], // 메시지는 useEffect에서 로드됨
        analysis: {
          ...initialState.analysis
        }
      };

    case actionTypes.SET_PROJECT_TITLE:
      console.log(`SET_PROJECT_TITLE: ${action.payload}`)
      return {
        ...state,
        projectTitle: action.payload
        
      }

    case actionTypes.SET_VIEW:
      return {
        ...state,
        currentView: action.payload,
        analysis: {
          ...state.analysis,
          mode: action.payload === 'chat' ? 'chat' : 'table'  // 뷰 변경 시 모드만 변경하고 다른 상태는 유지
        }
      }

    case actionTypes.ADD_DOCUMENTS:
      //payload는 IDocument[] 타입
      // SET_DOCUMENTS_IN_TABLESECTION 는 현재 프로젝트에 속한 문서를 그냥 row 추가하고 땡.하는 역할
      // 나머지는 UPDATE_DATATABLE이던가.. 거기서 
      const newDocuments = action.payload.reduce((acc, doc) => {
        acc[doc.id] = doc;
        return acc;
      }, { ...state.documents });

      // 테이블 데이터가 비어있을 때만 초기화
      let updatedTableData = state.analysis.tableData;

      console.log('SET_DOCUMENTS - 상태 업데이트:', {
        totalDocumentsCount: Object.keys(newDocuments).length,
        currentProjectDocumentsCount: action.payload.filter(doc => doc.project_id === state.currentProjectId).length,
        columnsCount: updatedTableData.columns.length,
        cellsCount: updatedTableData.columns[0]?.cells.length || 0
      });

      return {
        ...state,
        documents: newDocuments,
        analysis: {
          ...state.analysis,
          tableData: updatedTableData,
          selectedDocumentIds: [...new Set([...state.analysis.selectedDocumentIds, ...action.payload.map(doc => doc.id)])]
        }
      };

      break;
    case actionTypes.ADD_CHAT_MESSAGE:
      newState = {
        ...state,
        messages: [...state.messages, {
          ...action.payload,
          timestamp: action.payload.timestamp || new Date().toISOString()
        }],
        hasUnsavedChanges: true
      };
      break;

    case actionTypes.CLEAR_CHAT_MESSAGE:
      newState = {
        ...state,
        messages: []
      };
      break;

    case actionTypes.SET_IS_ANALYZING:
      return {
        ...state,
        isAnalyzing: action.payload
      }

    case actionTypes.SET_MODE:
      // 테이블 모드로 변경 시 현재 프로젝트의 모든 문서를 선택
      const selectedIds = action.payload === 'table' 
        ? Object.values(state.documents)
            .filter(doc => doc.project_id === state.currentProjectId)
            .map(doc => doc.id)
        : state.analysis.selectedDocumentIds;  // 테이블 모드가 아닐 때는 기존 선택 유지

      console.log('SET_MODE 상태:', {
        mode: action.payload,
        currentProjectId: state.currentProjectId,
        documentsCount: Object.keys(state.documents).length,
        selectedIds
      });

      return {
        ...state,
        analysis: {
          ...state.analysis,
          mode: action.payload,
          selectedDocumentIds: selectedIds
        }
      }

    case actionTypes.SELECT_DOCUMENTS:
      // 현재 프로젝트의 문서 ID만 선택 가능
      const validDocumentIds = action.payload.filter(
        id => state.documents[id]?.project_id === state.currentProjectId
      );
      
      return {
        ...state,
        analysis: {
          ...state.analysis,
          selectedDocumentIds: validDocumentIds
        }
      }

    case actionTypes.ADD_COLUMN:    
    // 아직 쓰는데가 없네.
      // 기존 테이블 데이터 유지하면서 새 컬럼 추가       
      const updatedColumnData = state.analysis.tableData.columns.map(row => ({
        ...row,
        [action.payload]: row[action.payload] || row[action.payload] === '' ? row[action.payload] : '내용을 불러오는 중...'
      }))

      // Document 컬럼 다음에 새 컬럼 추가
      const currentColumns = [...state.analysis.columns]
      const documentIndex = currentColumns.indexOf('Document')
      currentColumns.splice(documentIndex + 1, 0, action.payload)

      return {
        ...state,
        analysis: {
          ...state.analysis,
          columns: currentColumns,  // 수정된 컬럼 순서 적용
          tableData: { columns: updatedColumnData }
        }
      }

    case actionTypes.DELETE_COLUMN:
      return {
        ...state,
        analysis: {
          ...state.analysis,
          columns: state.analysis.columns.filter(col => col !== action.payload)
        }
      }

    case actionTypes.UPDATE_TABLE_DATA:
      console.log('[UPDATE_TABLE_DATA] 시작 ----------------');
      console.log('1. 현재 상태:', {
        currentColumns: state.analysis.tableData?.columns || [],
        documents: state.documents,
        currentProjectId: state.currentProjectId
      });

      console.log('2. 받은 payload:', action.payload);

      let initialTableColumns = state.analysis.tableData?.columns || [];
      console.log('3. 초기 테이블 컬럼:', initialTableColumns);

      // Document 칼럼이 없으면 추가
      // if (!initialTableColumns.some(col => col.header.name === 'Document')) {
      //   console.log('4. Document 컬럼 없음 - 새로 추가');
      //   const documentColumn = {
      //     header: {
      //       name: 'Document',
      //       prompt: '문서 이름을 표시합니다'
      //     },
      //     cells: Object.values(state.documents)
      //       .filter(doc => doc.project_id === state.currentProjectId)
      //       .map(doc => ({
      //         doc_id: doc.id,
      //         content: doc.filename
      //       }))
      //   };
      //   console.log('4-1. 생성된 Document 컬럼:', documentColumn);
      //   initialTableColumns = [documentColumn];
      // }

      // 새로운 칼럼 데이터가 있으면 병합
      let finalColumns = initialTableColumns;
      const updatedDocuments = { ...state.documents };
      if (action.payload?.columns?.length > 0) {
        //console.log('5. 새로운 컬럼 데이터 병합 시작');
        //const newColumns = action.payload.columns.filter(col => col.header.name !== 'Document');
        const newColumns = action.payload.columns;
        console.log('5-1. Document 컬럼 제외된 새 컬럼:', newColumns);
        
        // documents 복사본 생성
        

        // 각 컬럼을 순회하면서 해당하는 문서의 added_col_context 업데이트
        newColumns.forEach((column: TableColumn) => {
          // 각 셀을 순회하면서 해당하는 문서 찾기
          column.cells.forEach(cell => {
            const document = updatedDocuments[cell.doc_id];
            if (document) {
              // added_col_context가 없으면 새로 생성
              if (!document.added_col_context) {
                document.added_col_context = [];
              }
　　           // 새로운 cell 데이터 추가
              document.added_col_context.push({
                docId: cell.doc_id,
                header: column.header.name,
                value: cell.content
              });
            }
          });
        });

        // finalColumns = [...initialTableColumns, ...newColumns];
        // console.log('5-2. 최종 병합된 컬럼:', finalColumns);
        // 여기에 요청한 데이터를 넣어줘.

        console.log('5-2. 최종 병합된 컬럼:', finalColumns);
        console.log('5-3. 업데이트된 documents:', updatedDocuments);

      }

      console.log('6. 최종 업데이트될 상태:', {
        columns: finalColumns
      });
      console.log('[UPDATE_TABLE_DATA] 종료 ----------------');

      return {
        ...state,
        documents: updatedDocuments,
        analysis: {
          ...state.analysis,
          tableData: { columns: finalColumns }
        }
      };

    case actionTypes.UPDATE_TABLE_COLUMNS:
      // 서버로부터 받은 새 컬럼 데이터로 테이블 업데이트
      const newColumnsList = action.payload.map((col: any) => col.header.name)
      const existingColumnsList = state.analysis.columns.filter(col => col !== 'Document')
      const mergedColumnsList = [...new Set([...existingColumnsList, ...newColumnsList])]
      
      // 컬럼 프롬프트 업데이트
      const tableColumnPrompts = { ...state.analysis.columnPrompts }
      action.payload.forEach((col: any) => {
        tableColumnPrompts[col.header.name] = col.header.prompt
      })
      
      console.log('UPDATE_TABLE_COLUMNS - 입력:', {
        currentState: state.analysis,
        payload: action.payload,
        newColumns: newColumnsList,
        existingColumns: existingColumnsList,
        mergedColumns: mergedColumnsList,
        columnPrompts: tableColumnPrompts
      })
      
      const tableDataWithNewColumns = state.analysis.tableData.columns.map((row: any) => {
        const newRow = { ...row }
        // 새로운 컬럼의 데이터만 업데이트
        action.payload.forEach((col: any) => {
          const matchingCell = col.cells.find((c: any) => c.doc_id === row.id)
          if (matchingCell) {
            newRow[col.header.name] = matchingCell.content
          } else {
            newRow[col.header.name] = '내용 없음'
          }
        })
        return newRow
      })
      
      return {
        ...state,
        analysis: {
          ...state.analysis,
          columns: ['Document', ...mergedColumnsList],
          columnPrompts: tableColumnPrompts,
          tableData: { columns: tableDataWithNewColumns }
        }
      }

    case actionTypes.UPDATE_COLUMN_INFO:
      const { oldName, newName, prompt, originalPrompt } = action.payload
      return {
        ...state,
        analysis: {
          ...state.analysis,
          columns: state.analysis.columns.map(col => col === oldName ? newName : col),
          columnPrompts: {
            ...state.analysis.columnPrompts,
            [newName]: prompt
          },
          columnOriginalPrompts: {
            ...state.analysis.columnOriginalPrompts,
            [newName]: originalPrompt
          }
        }
      }

    case actionTypes.UPDATE_DOCUMENT_STATUS:
      return {
        ...state,
        documents: {
          ...state.documents,
          [action.payload.id]: {
            ...state.documents[action.payload.id],
            status: action.payload.status as IDocumentStatus
          }
        }
      }

    case actionTypes.ADD_ANALYSIS_COLUMN:
      return state;

    case actionTypes.UPDATE_COLUMN_RESULT:
      const { documentId, columnName, result } = action.payload;
      
      // 테이블 데이터에서 해당 컬럼을 찾아 결과 업데이트
      const existingColumn = state.analysis.tableData.columns.find(
        col => col.header.name === columnName
      );

      let updatedColumns;
      if (existingColumn) {
        // 기존 컬럼이 있으면 결과만 업데이트
        updatedColumns = state.analysis.tableData.columns.map(column => {
          if (column.header.name === columnName) {
            return {
              ...column,
              cells: column.cells.map(cell => 
                cell.doc_id === documentId 
                  ? { ...cell, content: result }
                  : cell
              )
            };
          }
          return column;
        });
      } else {
        // 새로운 컬럼 생성
        const documentColumn = state.analysis.tableData.columns.find(
          col => col.header.name === 'Document'
        );
        
        if (!documentColumn) return state;

        const newColumn = {
          header: {
            name: columnName,
            prompt: state.analysis.columnPrompts[columnName] || ''
          },
          cells: documentColumn.cells.map(docCell => ({
            doc_id: docCell.doc_id,
            content: docCell.doc_id === documentId ? result : ''
          }))
        };

        updatedColumns = [...state.analysis.tableData.columns, newColumn];
      }

      // 컬럼 목록에 새 컬럼 추가
      const updatedColumnsList = state.analysis.columns.includes(columnName)
        ? state.analysis.columns
        : ['Document', ...state.analysis.columns.filter(col => col !== 'Document'), columnName];

      return {
        ...state,
        analysis: {
          ...state.analysis,
          columns: updatedColumnsList,
          tableData: {
            columns: updatedColumns
          }
        }
      };

    case actionTypes.SET_LAST_AUTOSAVED:
      newState = {
        ...state,
        lastAutosaved: action.payload,
        hasUnsavedChanges: false
      };
      break;

    case actionTypes.UPDATE_RECENT_PROJECTS:
      //console.log('UPDATE_RECENT_PROJECTS 액션:', action.payload)
      return {
        ...state,
        recentProjects: action.payload
      }

    case actionTypes.SET_DOCUMENT_LIST:
      return {
        ...state,
        documents: action.payload
      };

    case actionTypes.UPDATE_CATEGORY_PROJECTS:
      return {
        ...state,
        categoryProjects: action.payload
      }

    case actionTypes.UPDATE_CHAT_MESSAGE:
      return {
        ...state,
        messages: state.messages.map(message => 
          message.id === action.payload.id
            ? {
                ...message,
                content: typeof action.payload.content === 'function'
                  ? action.payload.content(message.content)
                  : action.payload.content
              }
            : message
        )
      }
    
    case actionTypes.SET_MESSAGES:
      return {
        ...state,
        messages: action.payload
      };

    default:
      newState = state;
  }

  return newState;
}

export function AppProvider({ children }: { children: React.ReactNode }) {
  const [state, dispatch] = useReducer(appReducer, initialState)

  // 프로젝트 변경 감지 및 대화 기록 로드
  useEffect(() => {
    if (state.currentProjectId) {
      api.getChatHistory(state.currentProjectId)
        .then(chatHistory => {
          dispatch({
            type: actionTypes.SET_MESSAGES,
            payload: chatHistory
          });
        })
        .catch(error => {
          console.error('대화 기록 로드 실패:', error);
          dispatch({
            type: actionTypes.SET_MESSAGES,
            payload: []
          });
        });
    }
  }, [state.currentProjectId]);

  const saveTimeoutRef = useRef<NodeJS.Timeout | null>(null);

  // 디바운스된 저장 함수
  const debouncedSave = useCallback(async () => {
    if (!state.currentProjectId || !state.hasUnsavedChanges) return;

    try {
      
      // const saveData = {
      //   name: state.projectTitle,
      //   analysis_data: {
      //     mode: state.analysis.mode,
      //     columns: state.analysis.columns,
      //     columnPrompts: state.analysis.columnPrompts,
      //   },
      //   table_data: {
      //     columns: state.analysis.tableData?.columns || []
      //   },
      //   documents: state.documents,
      //   messages: state.messages
      // };

      // await api.autosaveProject(state.currentProjectId, saveData);
      // dispatch({ 
      //   type: actionTypes.SET_LAST_AUTOSAVED, 
      //   payload: new Date() 
      // });

      // console.log('프로젝트 자동 저장 완료:', new Date().toLocaleString());
    } catch (error) {
      console.error('자동 저장 실패:', error);
    }
  }, [state.currentProjectId, state.projectTitle, state.analysis, state.documents, state.messages, state.hasUnsavedChanges]);

  // 변경사항 감지 및 저장 로직
  useEffect(() => {
    if (!state.currentProjectId || !state.hasUnsavedChanges) return;

    // 이전 타이머 취소
    if (saveTimeoutRef.current) {
      clearTimeout(saveTimeoutRef.current);
    }

    // 새로운 타이머 설정 (3초 디바운스)
    saveTimeoutRef.current = setTimeout(debouncedSave, 3000);

    // 컴포넌트 언마운트 시 타이머 정리
    return () => {
      if (saveTimeoutRef.current) {
        clearTimeout(saveTimeoutRef.current);
      }
    };
  }, [state.hasUnsavedChanges, debouncedSave]);

  // 1분마다 변경사항 확인 및 강제 저장
  useEffect(() => {
    if (!state.currentProjectId) return;

    const forceAutosaveInterval = setInterval(() => {
      if (state.hasUnsavedChanges) {
        debouncedSave();
      }
    }, 60 * 1000); // 1분

    return () => clearInterval(forceAutosaveInterval);
  }, [state.currentProjectId, state.hasUnsavedChanges, debouncedSave]);

  return (
    <AppContext.Provider value={{ state, dispatch }}>
      {children}
    </AppContext.Provider>
  )
}

export function useApp() {
  const context = useContext(AppContext)
  if (context === undefined) {
    throw new Error('useApp must be used within an AppProvider')
  }
  return context
}
