"use client"

import { createContext, useContext, useReducer, useEffect, useRef, useCallback } from 'react'
import { TableData, Document, Message, DocumentStatus } from '@/types'
import * as api from '@/services/api'

interface TableColumn {
  header: {
    name: string;
    prompt: string;
  };
  cells: {
    doc_id: string;
    content: string;
  }[];
}

interface TableResponse {
  columns: TableColumn[];
}

interface AppState {
  sessionId: string | null
  currentProjectId: string | null
  projectTitle: string
  currentView: 'upload' | 'table' | 'chat'  // 현재 뷰 상태
  documents: {
    [id: string]: Document
  }
  messages: Message[]
  analysis: {
    mode: 'chat' | 'table'  // 분석 모드 (채팅/테이블)
    columns: string[]
    columnPrompts: { [key: string]: string }
    columnOriginalPrompts: { [key: string]: string }
    tableData: TableResponse
    selectedDocumentIds: string[]
    messages: Message[]
    processingColumns: string[]  // 현재 처리 중인 컬럼들
  }
  isAnalyzing: boolean
  lastAutosaved: Date | null
  hasUnsavedChanges: boolean
  recentProjects: {
    today: any[]
    yesterday: any[]
    fourDaysAgo: any[]
    older: any[]
  }
}

type Action =
  | { type: 'SET_INITIAL_STATE' }
  | { type: 'SET_SESSION'; payload: string }
  | { type: 'SET_CURRENT_PROJECT'; payload: string }
  | { type: 'SET_PROJECT_TITLE'; payload: string }
  | { type: 'SET_VIEW'; payload: 'upload' | 'table' | 'chat' }
  | { type: 'SET_DOCUMENTS'; payload: Document[] }
  | { type: 'ADD_MESSAGE'; payload: Message }
  | { type: 'SET_IS_ANALYZING'; payload: boolean }
  | { type: 'SET_MODE'; payload: 'chat' | 'table' }
  | { type: 'SELECT_DOCUMENTS'; payload: string[] }
  | { type: 'ADD_COLUMN'; payload: string }
  | { type: 'DELETE_COLUMN'; payload: string }
  | { type: 'UPDATE_TABLE_DATA'; payload: TableResponse }
  | { type: 'UPDATE_TABLE_COLUMNS'; payload: any[] }
  | { type: 'UPDATE_COLUMN_INFO'; payload: { oldName: string; newName: string; prompt: string; originalPrompt: string } }
  | { type: 'UPDATE_DOCUMENT_STATUS'; payload: { id: string; status: DocumentStatus } }
  | { type: 'ADD_ANALYSIS_COLUMN'; payload: { columnName: string; prompt: string; originalPrompt: string } }
  | { type: 'UPDATE_COLUMN_RESULT'; payload: { documentId: string; columnName: string; result: any } }
  | { type: 'SET_LAST_AUTOSAVED'; payload: Date }
  | { type: 'UPDATE_RECENT_PROJECTS'; payload: { today: any[], yesterday: any[], four_days_ago: any[] } }

const initialState: AppState = {
  sessionId: null,
  currentProjectId: null,
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
    yesterday: [],
    fourDaysAgo: [],
    older: []
  }
}

const AppContext = createContext<{
  state: AppState
  dispatch: React.Dispatch<Action>
} | undefined>(undefined)

const appReducer = (state: AppState, action: Action): AppState => {
  let newState: AppState;

  switch (action.type) {
    case 'SET_INITIAL_STATE':
      return {
        ...initialState,
        recentProjects: state.recentProjects // 프로젝트 목록 상태 유지
      }

    case 'SET_SESSION':
      return {
        ...state,
        sessionId: action.payload
      }

    case 'SET_CURRENT_PROJECT':
      return {
        ...state,
        currentProjectId: action.payload
      }

    case 'SET_PROJECT_TITLE':
      newState = {
        ...state,
        projectTitle: action.payload,
        hasUnsavedChanges: true,
        // 현재 프로젝트의 제목이 최근 프로젝트 목록에 있으면 즉시 업데이트
        recentProjects: {
          ...state.recentProjects,
          today: state.recentProjects.today.map(project => 
            project.id === state.currentProjectId 
              ? { ...project, title: action.payload }
              : project
          ),
          yesterday: state.recentProjects.yesterday.map(project => 
            project.id === state.currentProjectId 
              ? { ...project, title: action.payload }
              : project
          ),
          fourDaysAgo: state.recentProjects.fourDaysAgo.map(project => 
            project.id === state.currentProjectId 
              ? { ...project, title: action.payload }
              : project
          )
        }
      };
      break;

    case 'SET_VIEW':
      return {
        ...state,
        currentView: action.payload,
        analysis: {
          ...state.analysis,
          mode: action.payload === 'chat' ? 'chat' : 'table'  // 뷰 변경 시 모드만 변경하고 다른 상태는 유지
        }
      }

    case 'SET_DOCUMENTS':
      const newDocuments = action.payload.reduce((acc, doc) => {
        acc[doc.id] = doc;
        return acc;
      }, { ...state.documents });

      // 테이블 데이터가 비어있을 때만 초기화
      let updatedTableData = state.analysis.tableData;
      if (!updatedTableData.columns || updatedTableData.columns.length === 0) {
        const documentCells = action.payload
          .filter(doc => doc.project_id === state.currentProjectId)
          .map(doc => ({
            doc_id: doc.id,
            content: doc.filename
          }));

        updatedTableData = {
          columns: documentCells.length > 0 ? [
            {
              header: {
                name: 'Document',
                prompt: '문서 이름을 표시합니다'
              },
              cells: documentCells
            }
          ] : []
        };
      } else {
        // Document 칼럼의 cells만 업데이트
        const documentColumn = updatedTableData.columns.find(col => col.header.name === 'Document');
        if (documentColumn) {
          const existingDocIds = new Set(documentColumn.cells.map(cell => cell.doc_id));
          const newCells = action.payload
            .filter(doc => doc.project_id === state.currentProjectId && !existingDocIds.has(doc.id))
            .map(doc => ({
              doc_id: doc.id,
              content: doc.filename
            }));
          
          documentColumn.cells = [...documentColumn.cells, ...newCells];
        }
      }

      console.log('SET_DOCUMENTS - 상태 업데이트:', {
        documentsCount: Object.keys(newDocuments).length,
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

    case 'ADD_MESSAGE':
      newState = {
        ...state,
        messages: [...state.messages, action.payload],
        hasUnsavedChanges: true
      };
      break;

    case 'SET_IS_ANALYZING':
      return {
        ...state,
        isAnalyzing: action.payload
      }

    case 'SET_MODE':
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

    case 'SELECT_DOCUMENTS':
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

    case 'ADD_COLUMN':    
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

    case 'DELETE_COLUMN':
      return {
        ...state,
        analysis: {
          ...state.analysis,
          columns: state.analysis.columns.filter(col => col !== action.payload)
        }
      }

    case 'UPDATE_TABLE_DATA':
      console.log('UPDATE_TABLE_DATA - 이전 상태:', {
        currentColumns: state.analysis.tableData?.columns || [],
        newColumns: action.payload?.columns
      });

      let initialTableColumns = state.analysis.tableData?.columns || [];

      // Document 칼럼이 없으면 추가
      if (!initialTableColumns.some(col => col.header.name === 'Document')) {
        const documentColumn = {
          header: {
            name: 'Document',
            prompt: '문서 이름을 표시합니다'
          },
          cells: Object.values(state.documents)
            .filter(doc => doc.project_id === state.currentProjectId)
            .map(doc => ({
              doc_id: doc.id,
              content: doc.filename
            }))
        };
        initialTableColumns = [documentColumn];
      }

      // 새로운 칼럼 데이터가 있으면 병합
      if (action.payload?.columns?.length > 0) {
        const newColumns = action.payload.columns.filter(col => col.header.name !== 'Document');

        // 각 새로운 컬럼에 대해 모든 문서의 셀 데이터 확인
        newColumns.forEach(newCol => {
          const existingCol = initialTableColumns.find(col => col.header.name === newCol.header.name);
          if (existingCol) {
            // 기존 컬럼이 있으면 셀 데이터 업데이트
            newCol.cells.forEach(newCell => {
              const existingCellIndex = existingCol.cells.findIndex(cell => cell.doc_id === newCell.doc_id);
              if (existingCellIndex !== -1) {
                existingCol.cells[existingCellIndex] = newCell;
              } else {
                existingCol.cells.push(newCell);
              }
            });
          } else {
            // 새로운 컬럼 추가
            const documentColumn = initialTableColumns[0];
            newCol.cells = documentColumn.cells.map(docCell => {
              const matchingCell = newCol.cells.find(cell => cell.doc_id === docCell.doc_id);
              return matchingCell || { doc_id: docCell.doc_id, content: '' };
            });
            initialTableColumns.push(newCol);
          }
        });
      }

      console.log('UPDATE_TABLE_DATA - 업데이트된 상태:', {
        initialTableColumns
      });

      return {
        ...state,
        analysis: {
          ...state.analysis,
          tableData: {
            columns: initialTableColumns
          }
        }
      };

    case 'UPDATE_TABLE_COLUMNS':
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

    case 'UPDATE_COLUMN_INFO':
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

    case 'UPDATE_DOCUMENT_STATUS':
      return {
        ...state,
        documents: {
          ...state.documents,
          [action.payload.id]: {
            ...state.documents[action.payload.id],
            status: action.payload.status
          }
        }
      }

    case 'ADD_ANALYSIS_COLUMN':
      return state;

    case 'UPDATE_COLUMN_RESULT':
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

    case 'SET_LAST_AUTOSAVED':
      newState = {
        ...state,
        lastAutosaved: action.payload,
        hasUnsavedChanges: false
      };
      break;

    case 'UPDATE_RECENT_PROJECTS':
      return {
        ...state,
        recentProjects: {
          today: action.payload.today,
          yesterday: action.payload.yesterday,
          fourDaysAgo: action.payload.four_days_ago,
          older: []
        }
      }

    default:
      newState = state;
  }

  return newState;
}

export function AppProvider({ children }: { children: React.ReactNode }) {
  const [state, dispatch] = useReducer(appReducer, initialState);
  const saveTimeoutRef = useRef<NodeJS.Timeout | null>(null);

  // 디바운스된 저장 함수
  const debouncedSave = useCallback(async () => {
    if (!state.currentProjectId || !state.hasUnsavedChanges) return;

    try {
      const saveData = {
        name: state.projectTitle,
        analysis_data: {
          mode: state.analysis.mode,
          columns: state.analysis.columns,
          columnPrompts: state.analysis.columnPrompts,
        },
        table_data: {
          columns: state.analysis.tableData?.columns || []
        },
        documents: state.documents,
        messages: state.messages
      };

      await api.autosaveProject(state.currentProjectId, saveData);
      dispatch({ 
        type: 'SET_LAST_AUTOSAVED', 
        payload: new Date() 
      });

      console.log('프로젝트 자동 저장 완료:', new Date().toLocaleString());
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
