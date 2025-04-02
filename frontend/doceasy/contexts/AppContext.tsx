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
  | { type: typeof actionTypes.DELETE_PROJECT; payload: string }

  // TableSection에서 사용하는 action
  | { type: typeof actionTypes.ADD_DOCUMENTS; payload: IDocument[] }
  | { type: typeof actionTypes.ADD_CHAT_MESSAGE; payload: IMessage }
  | { type: typeof actionTypes.CLEAR_CHAT_MESSAGE }
  | { type: typeof actionTypes.SET_IS_ANALYZING; payload: boolean }
  | { type: typeof actionTypes.UPDATE_TABLE_DATA; payload: TableResponse }

  // 아직 사용하지 않는 action
  | { type: typeof actionTypes.SELECT_DOCUMENTS; payload: string[] }
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
  | { type: typeof actionTypes.UPDATE_DOCUMENT_COLUMN; payload: { documentId: string; headerName: string; content: string } }

const initialState: AppState = {
  sessionId: null,
  currentProjectId: null,
  currentProject: null,
  projectTitle: '',
  currentView: 'upload',
  documents: {},
  messages: [],
  analysis: {
    mode: 'table',  // 기본값을 table로 변경
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
          mode: action.payload === 'chat' ? 'chat' : 'table',  // 뷰 변경 시 모드만 변경하고 다른 상태는 유지

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

      // 테이블 모드인데 선택된 문서가 없으면 현재 프로젝트의 모든 문서를 선택
      const finalSelectedIds = (action.payload === 'table' && selectedIds.length === 0)
        ? Object.values(state.documents)
            .filter(doc => doc.project_id === state.currentProjectId)
            .map(doc => doc.id)
        : selectedIds;

      console.log('SET_MODE 상태:', {
        mode: action.payload,
        currentProjectId: state.currentProjectId,
        documentsCount: Object.keys(state.documents).length,
        selectedIds: finalSelectedIds,
        documentsInProject: Object.values(state.documents).filter(doc => doc.project_id === state.currentProjectId).length
      });

      return {
        ...state,
        analysis: {
          ...state.analysis,
          mode: action.payload,
          selectedDocumentIds: finalSelectedIds
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

    case actionTypes.DELETE_COLUMN:
      // 문서의 added_col_context에서 삭제된 컬럼을 제거
      const deletedColumnName = action.payload;
      const updatedDocsAfterDelete = { ...state.documents };
      
      // 모든 문서를 순회하며 added_col_context 업데이트
      Object.keys(updatedDocsAfterDelete).forEach(docId => {
        const doc = updatedDocsAfterDelete[docId];
        if (doc.added_col_context && doc.added_col_context.length > 0) {
          // 해당 컬럼명을 제외한 새로운 배열 생성
          doc.added_col_context = doc.added_col_context.filter(
            col => col.header !== deletedColumnName
          );
        }
      });
      
      console.log(`컬럼 삭제: ${deletedColumnName}`);
      
      return {
        ...state,
        documents: updatedDocsAfterDelete,
        analysis: {
          ...state.analysis,
          columns: state.analysis.columns.filter(col => col !== deletedColumnName),
          // 컬럼 프롬프트도 함께 제거
          columnPrompts: Object.fromEntries(
            Object.entries(state.analysis.columnPrompts).filter(([key]) => key !== deletedColumnName)
          ),
          columnOriginalPrompts: Object.fromEntries(
            Object.entries(state.analysis.columnOriginalPrompts).filter(([key]) => key !== deletedColumnName)
          )
        }
      }

    case actionTypes.UPDATE_TABLE_DATA:

      const bLog = true;

      let initialTableColumns = state.analysis.tableData?.columns || [];
      // 새로운 칼럼 데이터가 있으면 병합
      let finalColumns = [...initialTableColumns]; // 배열을 복제하여 참조 문제 방지

      if (bLog) {
        console.info('[UPDATE_TABLE_DATA] 시작 ----------------');
        console.debug('1. 현재 상태:', {
          currentColumns: state.analysis.tableData?.columns || [],
          documents: state.documents,
          currentProjectId: state.currentProjectId
        });

        console.debug('2. 받은 payload:', action.payload);
        console.debug('3. 초기 테이블 컬럼:', initialTableColumns);
        console.debug('4. 초기화된 finalColumns:', finalColumns);
      }
      
      const updatedDocuments = { ...state.documents };
      
      if (action.payload?.columns?.length > 0) {
        // 스트림 결과는 1개씩 도달, 테이블 히스토리는 전체 문서가 한방에
        const colLen = action.payload.columns.length; 
        const newColumns = action.payload.columns;
        if (bLog) {
          console.debug(`5-0. 새로운 컬럼 데이터 병합 시작 - 컬럼 개수: ${colLen}`);
          console.debug('5-1. 새 컬럼:', newColumns);
        }
        
        // 각 컬럼을 순회하면서 해당하는 문서의 added_col_context 업데이트
        newColumns.forEach((column: TableColumn) => {
          if (bLog) console.debug(`5-1-1. 컬럼:`, column);
          
          // 문서 목록을 순회하면서, 각 문서에 대해 해당 컬럼 추가
          Object.values(updatedDocuments).forEach(document => {
            // 문서에 added_col_context가 없으면 초기화
            if (!document.added_col_context) {
              document.added_col_context = [];
            }
            
            // 해당 문서에 대한 셀 데이터 찾기
            const cell = column.cells.find(cell => cell.doc_id === document.id);
            
            // 헤더와 일치하는 기존 컨텍스트 찾기
            const existingContextIndex = document.added_col_context.findIndex(
              ctx => ctx.header === column.header.name
            );
            
            if (existingContextIndex !== -1) {
              // 기존 컨텍스트가 있으면 값 업데이트
              document.added_col_context[existingContextIndex].value = cell ? cell.content : '분석 중...';
            } else {
              // 헤더만 존재하고, cell이 없으면 여기를 온다.
              // 이런 경우는 사용자 입력에 대한 헤더만 추가된 케이스.
              document.added_col_context.push({
                docId: document.id,
                header: column.header.name,
                value: cell ? cell.content : '분석 중...'
              });
            }
          });
          
          // 기존 셀 처리 로직. TableHis
          column.cells.forEach(cell => {
            const document = updatedDocuments[cell.doc_id];
            if (document) {
              // added_col_context가 없으면 새로 생성
              if (!document.added_col_context) {
                document.added_col_context = [];
              }
              // 새로운 cell 데이터 추가 (이미 위에서 처리했을 수 있음)
              const existingContext = document.added_col_context.find(
                ctx => ctx.header === column.header.name
              );
              
              if (!existingContext) {
                if (bLog) console.debug(`[UPDATE_TABLE_DATA] 새로운 cell 데이터 추가: ${cell.doc_id}, ${column.header.name}, ${cell.content}`);
                document.added_col_context.push({
                  docId: cell.doc_id,
                  header: column.header.name,
                  value: cell.content
                });
              }
            }
            else
            {
              if (bLog) console.debug(`[UPDATE_TABLE_DATA] 기존 문서 없음: ${cell.doc_id}`);
            }
          });
        });

        
        // 새 컬럼들을 순회하며 처리
        newColumns.forEach(newColumn => {
          // 같은 헤더 이름을 가진 컬럼 인덱스 찾기
          const existingColumnIndex = finalColumns.findIndex(
            col => col.header.name === newColumn.header.name
          );
          
          if (existingColumnIndex !== -1) {
            // 같은 이름의 컬럼이 있으면 대체
            if (bLog){
              console.debug(`5-2. 기존 컬럼 [${newColumn.header.name}] 대체 : prompt=${newColumn.header.prompt}`);
              console.debug(`5-2-1. 기존 컬럼:`, finalColumns[existingColumnIndex]);
              console.debug(`5-2-2. 새 컬럼:`, newColumn);
            }
            finalColumns[existingColumnIndex] = newColumn;
          } else {
            // 같은 이름의 컬럼이 없으면 추가
            if (bLog) console.debug(`5-2. 새 컬럼 [${newColumn.header.name}] 추가`);
            finalColumns.push(newColumn);
          }
        });
        
        if (bLog){
          console.debug('5-3. 최종 병합된 컬럼:', finalColumns);
          console.debug('5-4. 업데이트된 documents:', updatedDocuments);
        }
      }

      if (bLog){
        console.debug('6. 최종 업데이트될 상태:', {
          columns: finalColumns
        });
        console.debug('[UPDATE_TABLE_DATA] 종료 ----------------');
      }

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
      // 테이블 모드인 경우 자동으로 모든 문서 선택
      const documentList = action.payload;
      const documentsArray = Object.values(documentList);
      
      // 현재 프로젝트의 문서들만 필터링
      const currentProjectDocIds = documentsArray
        .filter(doc => doc.project_id === state.currentProjectId)
        .map(doc => doc.id);
        
      // 테이블 모드일 때만 문서 선택
      const updatedSelectedDocIds = state.analysis.mode === 'table' 
        ? currentProjectDocIds 
        : state.analysis.selectedDocumentIds;
        
      return {
        ...state,
        documents: documentList,
        analysis: {
          ...state.analysis,
          selectedDocumentIds: updatedSelectedDocIds
        }
      };

    case actionTypes.UPDATE_CATEGORY_PROJECTS:
      return {
        ...state,
        categoryProjects: action.payload
      }

    case actionTypes.UPDATE_CHAT_MESSAGE:
      const { id, content } = action.payload
      return {
        ...state,
        messages: state.messages.map(message => 
          message.id === id 
            ? { 
                ...message, 
                content: typeof content === 'function' 
                  ? content(message.content) 
                  : content 
              } 
            : message
        )
      }

    case actionTypes.SET_MESSAGES:
      return {
        ...state,
        messages: action.payload
      };

    case actionTypes.UPDATE_DOCUMENT_COLUMN:
      const { documentId: docId, headerName: colName, content: cellValue } = action.payload
      const docsWithUpdatedColumn = { ...state.documents }
      
      // 해당 문서 찾기
      const docToUpdate = docsWithUpdatedColumn[docId]
      if (docToUpdate) {
        // added_col_context가 없으면 초기화
        if (!docToUpdate.added_col_context) {
          docToUpdate.added_col_context = []
        }
        
        // 같은 헤더의 기존 컨텍스트 찾기
        const existingContextIndex = docToUpdate.added_col_context.findIndex(
          ctx => ctx.header === colName
        )
        
        if (existingContextIndex !== -1) {
          // 기존 컨텍스트 업데이트
          docToUpdate.added_col_context[existingContextIndex].value = cellValue
        } else {
          // 새 컨텍스트 추가
          docToUpdate.added_col_context.push({
            docId: docId,
            header: colName,
            value: cellValue
          })
        }
      }
      
      return {
        ...state,
        documents: docsWithUpdatedColumn
      }

    case actionTypes.DELETE_PROJECT:
      // 프로젝트 ID로 최근 프로젝트 목록에서 삭제
      const projectId = action.payload;
      const updatedRecentProjects = {
        today: state.recentProjects.today.filter(p => p.id !== projectId),
        last_7_days: state.recentProjects.last_7_days.filter(p => p.id !== projectId),
        last_30_days: state.recentProjects.last_30_days ? state.recentProjects.last_30_days.filter(p => p.id !== projectId) : []
      };
      
      // 현재 선택된 프로젝트가 삭제된 프로젝트인 경우 초기 상태로 리셋
      if (state.currentProjectId === projectId) {
        return {
          ...initialState,
          recentProjects: updatedRecentProjects
        };
      }
      
      return {
        ...state,
        recentProjects: updatedRecentProjects
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
