'use client';
import { useMemo, useState, forwardRef, useEffect, useImperativeHandle, useRef, useCallback } from 'react';
import {
  MaterialReactTable,
  useMaterialReactTable,
  type MRT_ColumnDef,
  type MRT_Row,
} from 'material-react-table';
import { useApp } from "@/contexts/AppContext"
import { Button } from "intellio-common/components/ui/button";
import { IDocument,  IDocumentStatus } from '@/types';  
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import { DocumentStatusBadge } from '@/components/DocumentStatusBadge';
import { createPortal } from 'react-dom';

// 테이블 조작을 위한 유틸리티 함수들
export interface ITableUtils {
  addRow: () => void;
  addColumn: () => void;
  removeRow: (email: string) => void;
  removeColumn: (columnId: string) => void;
  // getTableData: () => IDocument[];
  // getColumnCount: () => number;
}

// 마크다운 스타일 상수 정의
const markdownClassName = `prose dark:prose-invert max-w-none 
  [&>*:first-child]:mt-0 [&>*:last-child]:mb-0
  [&>h1]:mt-3 [&>h1]:mb-1 [&>h1]:text-lg [&>h1]:font-bold
  [&>h2]:mt-2 [&>h2]:mb-1 [&>h2]:text-base [&>h2]:font-semibold
  [&>h3]:mt-1 [&>h3]:mb-1 [&>h3]:text-sm [&>h3]:font-normal
  [&>p]:my-0.5 [&>p]:leading-4 [&>p]:whitespace-pre-line [&>p]:text-xs
  [&>ul]:my-0.5 [&>ul>li]:mt-1 [&>ul>li]:text-xs
  [&>ol]:my-0.5 [&>ol>li]:mt-1 [&>ol>li]:text-xs
  [&>table]:w-full [&>table]:my-2 [&>table]:border-collapse
  [&>table>thead>tr>th]:border [&>table>thead>tr>th]:border-gray-300 [&>table>thead>tr>th]:p-1 [&>table>thead>tr>th]:bg-gray-100 [&>table>thead>tr>th]:text-left [&>table>thead>tr>th]:text-xs
  sm:[&>p]:text-xs sm:[&>ul>li]:text-xs sm:[&>ol>li]:text-xs sm:[&>table>thead>tr>th]:text-xs
  xs:[&>p]:text-[0.65rem] xs:[&>ul>li]:text-[0.65rem] xs:[&>ol>li]:text-[0.65rem] xs:[&>table>thead>tr>th]:text-[0.65rem]`;

// 마크다운 셀 컴포넌트
function MarkdownCell({ content }: { content: string }) {
  const [isExpanded, setIsExpanded] = useState(false);
  const [needsScroll, setNeedsScroll] = useState(false);
  const contentRef = useRef<HTMLDivElement>(null);
  const containerRef = useRef<HTMLDivElement>(null);
  const [position, setPosition] = useState({ top: 0, left: 0, width: 0 });
  const tableRef = useRef<HTMLElement | null>(null);
  
  // 컴포넌트 마운트 시 테이블 요소 찾기
  useEffect(() => {
    // DocumentTable 컴포넌트의 최상위 div 찾기
    const findTableContainer = () => {
      if (containerRef.current) {
        let element: HTMLElement | null = containerRef.current;
        // 상위 요소를 탐색하며 DocumentTable의 최상위 div 찾기
        while (element && !element.classList.contains('w-full') && !element.classList.contains('h-full')) {
          element = element.parentElement;
        }
        tableRef.current = element;
      }
    };
    
    findTableContainer();
  }, []);
  
  // 컨텐츠 높이 체크하여 스크롤이 필요한지 확인
  const checkContentHeight = useCallback(() => {
    if (contentRef.current && containerRef.current) {
      const contentHeight = contentRef.current.scrollHeight;
      const containerHeight = containerRef.current.clientHeight;
      setNeedsScroll(contentHeight > containerHeight);
    }
  }, []);
  
  // 브라우저 영역 내에 포털이 표시되도록 위치 계산
  const calculateSafePosition = useCallback((rect: DOMRect) => {
    const padding = 20; // 화면 가장자리로부터의 최소 여백
    const headerHeight = 36; // 테이블 헤더의 높이
    
    // DocumentTable의 위치 정보 가져오기
    let tableTop = 0;
    if (tableRef.current) {
      const tableRect = tableRef.current.getBoundingClientRect();
      tableTop = tableRect.top;
    }
    
    const minTopPadding = Math.max(headerHeight + 10, tableTop); // 헤더 높이 + 추가 여백 또는 테이블 상단 중 큰 값
    const viewportWidth = window.innerWidth;
    const viewportHeight = window.innerHeight;
    const expandedWidth = rect.width + 40; // 확장 시 추가되는 너비
    const estimatedHeight = Math.min(rect.height * 5, 500); // 예상 높이 (최대 500px)
    
    // 기본 위치 (원래 셀 위치)
    let top = rect.top;
    let left = rect.left;
    
    // 오른쪽 경계 확인 및 조정
    if (left + expandedWidth > viewportWidth - padding) {
      left = Math.max(padding, viewportWidth - expandedWidth - padding);
    }
    
    // 왼쪽 경계 확인 및 조정
    if (left < padding) {
      left = padding;
    }
    
    // 하단 경계 확인 및 조정
    const bottomSpace = viewportHeight - rect.bottom - padding;
    if (estimatedHeight > bottomSpace) {
      // 하단에 충분한 공간이 없으면 셀 바로 위에 표시
      top = Math.max(minTopPadding, rect.top - estimatedHeight); // 셀 위에 간격 없이 표시 (2px 제거)
      
      // 계산된 위치가 테이블 상단보다 작으면 조정
      if (top < minTopPadding) {
        // 위쪽에도 충분한 공간이 없으면 테이블 헤더 아래에 표시
        top = minTopPadding;
      }
    } else {
      // 하단에 충분한 공간이 있으면 셀 아래에 표시
      top = rect.bottom; // 셀 아래에 간격 없이 표시 (2px 제거)
    }
    
    return { top, left, width: rect.width };
  }, []);
  
  // 확장/축소 토글 함수
  const toggleExpand = useCallback(() => {
    if (!isExpanded && containerRef.current) {
      // 확장 전에 원래 위치와 크기 저장 및 안전한 위치 계산
      const rect = containerRef.current.getBoundingClientRect();
      setPosition(calculateSafePosition(rect));
    }
    setIsExpanded(prevState => !prevState);
  }, [isExpanded, calculateSafePosition]);
  
  // 더블클릭 이벤트 핸들러
  const handleDoubleClick = useCallback((e: React.MouseEvent) => {
    // 기본 더블클릭 동작(텍스트 선택) 방지
    e.preventDefault();
    e.stopPropagation();
    toggleExpand();
  }, [toggleExpand]);
  
  // 컨텐츠나 확장 상태가 변경될 때 높이 체크
  useEffect(() => {
    // 약간의 지연을 두고 높이 체크 (렌더링 완료 후)
    const timer = setTimeout(checkContentHeight, 50);
    return () => clearTimeout(timer);
  }, [content, isExpanded, checkContentHeight]);
  
  // 브라우저 크기가 변경될 때 위치 재계산
  useEffect(() => {
    if (isExpanded && containerRef.current) {
      const handleResize = () => {
        const rect = containerRef.current?.getBoundingClientRect();
        if (rect) {
          setPosition(calculateSafePosition(rect));
        }
      };
      
      window.addEventListener('resize', handleResize);
      return () => window.removeEventListener('resize', handleResize);
    }
  }, [isExpanded, calculateSafePosition]);
  
  // ESC 키를 누르면 확장 상태에서 축소 상태로 전환
  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.key === 'Escape' && isExpanded) {
        setIsExpanded(false);
      }
    };
    
    window.addEventListener('keydown', handleKeyDown);
    return () => window.removeEventListener('keydown', handleKeyDown);
  }, [isExpanded]);
  
  // 접기 버튼 클릭 핸들러
  const handleCollapseClick = useCallback((e: React.MouseEvent) => {
    e.stopPropagation();
    setIsExpanded(false);
  }, []);
  
  // 기본 셀 렌더링
  const normalCell = (
    <div 
      ref={containerRef}
      className={`
        transition-all duration-300 cursor-pointer text-xs relative
        ${needsScroll ? 'overflow-y-auto overflow-x-hidden' : 'overflow-visible'}
      `}
      style={{
        userSelect: 'none',
        maxHeight: '55px',
        width: '100%',
        paddingTop: '0.125rem',
        paddingBottom: '0.125rem',
        paddingLeft: '4px',
        paddingRight: '0px',
        scrollbarWidth: 'thin',
        scrollbarColor: '#cbd5e1 transparent'
      }}
      onDoubleClick={handleDoubleClick}
    >
      <style jsx>{`
        /* 웹킷 기반 브라우저용 스크롤바 스타일 */
        div::-webkit-scrollbar {
          width: 1px;
          height: 1px;
          position: absolute;
          right: 0;
        }
        div::-webkit-scrollbar-track {
          background: transparent;
        }
        div::-webkit-scrollbar-thumb {
          background: #cbd5e1;
          border-radius: 0;
        }
        div::-webkit-scrollbar-thumb:hover {
          background: #94a3b8;
        }
        /* 스크롤바가 필요할 때만 표시 */
        div::-webkit-scrollbar {
          display: auto;
        }
        div:not(:hover)::-webkit-scrollbar-thumb {
          background: transparent;
        }
        div:hover::-webkit-scrollbar-thumb {
          background: #cbd5e1;
        }
        /* 스크롤 이동 버튼 제거 */
        div::-webkit-scrollbar-button {
          display: none;
        }
        
        /* 모바일 환경에서 스크롤바 조정 */
        @media (max-width: 640px) {
          div::-webkit-scrollbar {
            width: 0.5px;
            height: 0.5px;
          }
        }
      `}</style>
      <div 
        ref={contentRef}
        style={{
          userSelect: 'none',
          width: '100%',
          boxSizing: 'border-box',
          paddingRight: '0'
        }}
      >
        <ReactMarkdown 
          remarkPlugins={[remarkGfm]}
          className={`${markdownClassName} leading-4 text-xs prose-strong:text-blue-700 prose-em:text-gray-600 prose-code:text-red-600 prose-code:bg-gray-100`}
        >
          {content}
        </ReactMarkdown>
      </div>
      {needsScroll && (
        <div className="text-right mt-1 mr-0">
          <span className="text-[9px] text-gray-400 italic">↓</span>
        </div>
      )}
    </div>
  );
  
  // 확장된 셀 렌더링 (포털 사용) - 스타일 통일
  const expandedCell = isExpanded && typeof window !== 'undefined' ? createPortal(
    <div 
      className="fixed inset-0 bg-black bg-opacity-20 z-40 flex items-center justify-center"
      onClick={() => setIsExpanded(false)}
    >
      <div 
        className="bg-white rounded shadow-md overflow-y-auto overflow-x-hidden z-50"
        style={{
          position: 'absolute',
          top: `${position.top}px`,
          left: `${position.left}px`,
          width: `${Math.min(position.width + 40, window.innerWidth - 40)}px`, // 너비가 화면을 넘지 않도록
          maxHeight: `${Math.min(500, window.innerHeight - Math.max(position.top, 20) - 20)}px`, // 높이 제한 개선
          minHeight: '100px',
          padding: '12px',
          transition: 'all 0.3s ease',
          scrollbarWidth: 'thin',
          scrollbarColor: '#cbd5e1 transparent',
          zIndex: 50,
          // 확장된 셀이 위쪽에 표시될 때와 아래쪽에 표시될 때 그림자 방향 조정
          boxShadow: position.top < (containerRef.current?.getBoundingClientRect().top || 0)
            ? '0 4px 12px rgba(0, 0, 0, 0.15)' // 셀 위에 표시될 때
            : '0 -4px 12px rgba(0, 0, 0, 0.15)', // 셀 아래에 표시될 때
          // 모바일 환경에서 조정
          ...(window.innerWidth <= 640 && {
            width: `${Math.min(window.innerWidth - 20, position.width + 20)}px`,
            padding: '8px',
            left: `${Math.max(10, Math.min(position.left, window.innerWidth - (position.width + 20) - 10))}px`
          })
        }}
        onClick={(e) => e.stopPropagation()}
      >
        <style jsx>{`
          /* 웹킷 기반 브라우저용 스크롤바 스타일 */
          div::-webkit-scrollbar {
            width: 2px;
            height: 2px;
            position: absolute;
            right: 0;
          }
          div::-webkit-scrollbar-track {
            background: transparent;
          }
          div::-webkit-scrollbar-thumb {
            background: #cbd5e1;
            border-radius: 1px;
          }
          div::-webkit-scrollbar-thumb:hover {
            background: #94a3b8;
          }
          /* 스크롤 이동 버튼 제거 */
          div::-webkit-scrollbar-button {
            display: none;
          }
          
          /* 모바일 환경에서 스크롤바 조정 */
          @media (max-width: 640px) {
            div::-webkit-scrollbar {
              width: 1px;
              height: 1px;
            }
          }
        `}</style>
        <div 
          style={{
            userSelect: 'text',
            width: '100%',
            boxSizing: 'border-box'
          }}
        >
          <ReactMarkdown 
            remarkPlugins={[remarkGfm]}
            className={`${markdownClassName} leading-4 text-xs prose-strong:text-blue-700 prose-em:text-gray-600 prose-code:text-red-600 prose-code:bg-gray-100`}
          >
            {content}
          </ReactMarkdown>
        </div>
        <div className="text-right mt-2 text-xs text-gray-500">
          <span 
            className="text-[10px] italic bg-gray-100 px-2 py-0.5 rounded cursor-pointer hover:bg-gray-200"
            onClick={handleCollapseClick}
          >
            클릭하여 접기
          </span>
        </div>
      </div>
    </div>,
    document.body
  ) : null;
  
  return (
    <>
      {normalCell}
      {expandedCell}
    </>
  );
}

const DocumentTable = forwardRef<ITableUtils>((props, ref) => {
  const { state, dispatch } = useApp()
  const [showAgeColumn, setShowAgeColumn] = useState(true);
  const [countCol, setCountCol] = useState(0);
  const [countRow, setCountRow] = useState(0);
  
  const tableData = useMemo(() => {
    // 기본 데이터
    const baseData: IDocument[] = []
    //console.log(`[DocumentTable] documents length: ${Object.keys(state.documents).length}`)
    // documents에 있는 내용 업데이트.
    // document가 추가될때. 즉 row가 1개 늘어나야할때 호출됨. 문서 업로드 / 문서 추가 시
    const additionalData = Object.values(state.documents).map((document) => ({
      ...document
    }));
    console.log(`[DocumentTable] documents 변경 : ` , additionalData)

    return [...baseData, ...additionalData];
  }, [state.documents]);

  const documentColContexts = useMemo(() => 
    Object.values(state.documents).map(doc => doc.added_col_context),
    [state.documents]
  );

  const columns = useMemo<MRT_ColumnDef<IDocument>[]>(() => {
    // 여기는 column가 추가되어야할때 호출됨. Table모드에서 프롬프트 입력 시.
    const baseColumns: MRT_ColumnDef<IDocument>[] = [
      {
        id: "filename",
        accessorKey: "filename",
        header: "Document",
        Cell: ({ row }: { row: MRT_Row<IDocument> }) => {
          const document = row.original;
          const status = document.status;
          
          // 상태에 따른 파일명 색상 설정
          const filenameColorClass = status === 'ERROR' 
            ? 'text-red-500' 
            : (status === 'PROCESSING' || status === 'PARTIAL' || status === 'UPLOADING' || status === 'UPLOADED') 
              ? 'text-gray-400' 
              : 'text-foreground';

          return (
            <div className="flex items-center gap-1 w-full overflow-hidden">
              <span className={`${filenameColorClass} truncate flex-1 text-xs font-medium`}>{document.filename}</span>
              <DocumentStatusBadge status={status} />
            </div>
          );
        },
      },
    ];
    
    // 추가된 컬럼 수를 추적
    let addedColumnsCount = 0;
    
    Object.values(state.documents).forEach((doc) => {
      
      doc.added_col_context?.forEach((cell) => {
        // 주석 삭제 절대금지
        // 여기는 헤더값을 비교하고 있으면 안넣는데, 백엔드 응답에 따라 동일한 헤더값이 올수도 있다.
        // 그런 경우 헤더값+숫자의 형태로 또 다른 헤더를 넣어줘야한다.
        // 헤더값을 받는 함수를 따로 만들어서 처리해야할듯.
        //console.debug(`[DocumentTable] ${doc.filename} : col : `, cell);
        if (!baseColumns.some(col => col.accessorKey === cell.header)) {
          console.debug(`[DocumentTable] col 변경 : ` , cell)
          addedColumnsCount++;
          baseColumns.push({
            accessorKey: cell.header,
            header: cell.header,
            grow: true, // 새로 추가되는 컬럼들은 남은 공간을 균등하게 차지
            Cell: ({ row }) => {
              // 해당 row의 added_col_context에서 matching되는 cell의 value를 찾아 표시
              const matchingCell = row.original.added_col_context?.find(
                c => c.header === cell.header
              );
              return <MarkdownCell content={matchingCell?.value || ''} />;
            }
          });
        }
      })
    });

    baseColumns[0] = {
      ...baseColumns[0],
      size: 300, // 고정 크기 대신 상대적 크기 사용
      grow: false, // 남은 공간을 차지하지 않도록 설정
      minSize: 120, // 최소 크기 축소 (150 -> 120)
      maxSize: 250, // 최대 크기 유지
      muiTableHeadCellProps: {
        sx: {
          // 모바일에서 더 작은 크기로 조정
          '@media (max-width: 640px)': {
            minWidth: '100px',
            maxWidth: '150px',
          }
        }
      },
      muiTableBodyCellProps: {
        sx: {
          // 모바일에서 더 작은 크기로 조정
          '@media (max-width: 640px)': {
            minWidth: '100px',
            padding: '0.25rem',
            fontSize: '0.7rem'
          }
        }
      }
    };

    // Document 컬럼의 크기를 조절 (추가된 컬럼이 있을 때만)
    if (addedColumnsCount > 0) {
      baseColumns[0] = {
        ...baseColumns[0],
        size: undefined, // 고정 크기 대신 상대적 크기 사용
        grow: false, // 남은 공간을 차지하지 않도록 설정
        minSize: 120, // 최소 크기 축소 (150 -> 120)
        maxSize: 250, // 최대 크기 유지
        muiTableHeadCellProps: {
          sx: {
            // 모바일에서 더 작은 크기로 조정
            '@media (max-width: 640px)': {
              minWidth: '100px',
              maxWidth: '150px',
            }
          }
        },
        muiTableBodyCellProps: {
          sx: {
            // 모바일에서 더 작은 크기로 조정
            '@media (max-width: 640px)': {
              minWidth: '100px',
              padding: '0.25rem',
              fontSize: '0.7rem'
            }
          }
        }
      };

      // Document 컬럼 이후의 컬럼들에 대해 균등한 너비 설정
      for (let i = 1; i < baseColumns.length; i++) {
        baseColumns[i] = {
          ...baseColumns[i],
          size: undefined, // 자동으로 크기 조절되도록
          grow: true,      // 남은 공간을 균등하게 차지
          minSize: 80,     // 최소 크기 축소 (100 -> 80)
          maxSize: 500,    // 최대 크기 유지
          muiTableHeadCellProps: {
            sx: {
              // 모바일에서 더 작은 크기로 조정
              '@media (max-width: 640px)': {
                minWidth: '80px',
                padding: '0.25rem',
                fontSize: '0.7rem'
              }
            }
          },
          muiTableBodyCellProps: {
            sx: {
              // 모바일에서 더 작은 크기로 조정
              '@media (max-width: 640px)': {
                minWidth: '80px',
                padding: '0.25rem',
                fontSize: '0.7rem'
              }
            }
          }
        };
      }
    }
    
    return baseColumns;
  }, [dispatch, documentColContexts, state.documents]);

  const table = useMaterialReactTable({
    columns,
    data: tableData,
    enableRowSelection: true,
    enableMultiRowSelection: true,
    enableColumnResizing: true,
    enableStickyHeader: true,
    enableStickyFooter: false,
    enableColumnVirtualization: false,
    enableTableHead: true,
    enableTableFooter: false,
    enableColumnOrdering: false,
    enableGlobalFilter: false,
    enableColumnFilters: false,
    enableFilters: false,
    enableColumnActions: false,
    enableHiding: false,
    enableDensityToggle: false,
    enableFullScreenToggle: false,
    enableTopToolbar: false,
    enablePagination: false,
    enableBottomToolbar: false,
    positionToolbarAlertBanner: 'none',
    getRowId: (doc) => doc.id,
    defaultColumn: {
      minSize: 30,  // 최소 크기 조정
      maxSize: 500, // 최대 크기 제한 (800 -> 500)
      size: 30,    // 기본 크기 조정
    },
    displayColumnDefOptions: {
      'mrt-row-select': {
        size: 30,  // 체크박스 컬럼 크기 축소 (40 -> 30)
        grow: false,
        maxSize: 30,  // 최대 크기도 제한
        minSize: 30,  // 최소 크기도 제한
        muiTableHeadCellProps: {
          align: 'center',
          sx: {
            padding: '0 !important',
          },
        },
        muiTableBodyCellProps: {
          align: 'center',
          sx: {
            padding: '0 !important',
          },
        },
      },
      'mrt-row-numbers': {
        size: 40,
        grow: false
      },
    },
    muiTableProps: {
      sx: {
        tableLayout: 'fixed', // 'auto' -> 'fixed'로 변경하여 테이블 너비 제어
        width: '100%',
        maxWidth: '100%', // 최대 너비 제한 추가
        maxHeight: '100%',
        borderCollapse: 'separate',  // 테이블 경계선 분리
        borderSpacing: 0,  // 경계선 간격 없음
        // 모바일 환경에서 폰트 크기 조정
        '@media (max-width: 640px)': {
          fontSize: '0.7rem',
        }
      },
    },
    muiTableHeadProps: {
      sx: {
        '& tr': {
          height: '36px',  // 헤더 행 높이 축소
          '& th': {
            verticalAlign: 'middle',  // 헤더 셀 내용 수직 중앙 정렬
            lineHeight: '1',  // 라인 높이 조정
            paddingTop: '0',  // 상단 패딩 제거
            paddingBottom: '0'  // 하단 패딩 제거
          },
          // 모바일 환경에서 헤더 높이 조정
          '@media (max-width: 640px)': {
            height: '30px',
          }
        },
        position: 'sticky',
        top: 0,
        zIndex: 10,
        backgroundColor: '#f80000 !important'
      }
    },
    muiTableBodyProps: {
      sx: {
        '& tr': {
          height: columns.length === 1 ? '36px' : 'auto',  // 본문 행 높이 축소
          maxHeight: '60px',  // 최대 높이 제한
          borderBottom: '1px solid #e2e8f0',  // 행 하단 경계선 추가
          // 모바일 환경에서 행 높이 조정
          '@media (max-width: 640px)': {
            height: columns.length === 1 ? '30px' : 'auto',
            maxHeight: '50px',
          }
        }
      }
    },
    muiTablePaperProps: {
      sx: {
        padding: 0,
        margin: 0,
        backgroundColor: 'transparent',
        boxShadow: 'none',
        maxHeight: '100%',
        overflow: 'hidden',
        display: 'flex',
        flexDirection: 'column',
      }
    },
    muiTableContainerProps: {
      sx: { 
        height: 'auto',
        maxHeight: '100%',
        overflow: 'auto',
        flex: 1,
        width: '100%', // 너비 100% 설정
        maxWidth: '100%', // 최대 너비 제한
        // 스크롤바 스타일
        '&::-webkit-scrollbar': {
          width: '4px',
          height: '4px',
          // 모바일에서 더 작은 스크롤바
          '@media (max-width: 640px)': {
            width: '2px',
            height: '2px',
          }
        },
        '&::-webkit-scrollbar-track': {
          backgroundColor: '#f1f1f1'
        },
        '&::-webkit-scrollbar-thumb': {
          backgroundColor: '#888',
          borderRadius: '2px',
          '&:hover': {
            backgroundColor: '#555'
          }
        },
        '&::-webkit-scrollbar-button': {
          display: 'none'
        },
        // 내부 테이블 스타일링
        '& .MuiTable-root': {
          margin: 0,
          width: '100%',
          maxWidth: '100%', // 최대 너비 제한 추가
          borderCollapse: 'separate',
          borderSpacing: 0,
          border: '1px solid #e2e8f0'  // 테이블 전체 테두리 추가
        },
        // 헤더 스타일링
        '& .MuiTableHead-root': {
          position: 'sticky',
          top: 0,
          zIndex: 2,
          backgroundColor: '#f80000 !important',
          boxShadow: '0 1px 2px rgba(0, 0, 0, 0.05)'  // 헤더에 미세한 그림자 추가
        },
        // 헤더 셀 직접 스타일링
        '& .MuiTableHead-root .MuiTableCell-root': {
          display: 'flex',
          alignItems: 'center',
          height: '36px',
          padding: '0 10px',
          // 모바일 환경에서 헤더 셀 조정
          '@media (max-width: 640px)': {
            height: '30px',
            padding: '0 5px',
          }
        }
      }
    },
    muiTableHeadCellProps: {
      sx: {
        padding: '0px 10px',  // 상하 패딩 제거, 좌우 패딩 유지
        backgroundColor: '#f80000 !important',
        borderRight: '1px solid #e2e8f0',
        borderBottom: '2px solid #e2e8f0',
        fontWeight: 600,
        color: '#1e293b',
        fontSize: '0.8rem',
        whiteSpace: 'nowrap',
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'flex-start',
        height: '36px',
        '&:hover': {
          backgroundColor: '#ff3333 !important'
        },
        // 모바일 환경에서 헤더 셀 조정
        '@media (max-width: 640px)': {
          padding: '0px 5px',
          fontSize: '0.7rem',
          height: '30px',
        },
        '&.mrt-row-select-head-cell': {
          padding: '0 !important',
          display: 'flex !important',
          alignItems: 'center !important',
          justifyContent: 'center !important',
        },
        '& .MuiBox-root': {  // Material UI Box 컴포넌트 스타일링
          display: 'flex',
          alignItems: 'center',
          height: '100%'
        },
        '& .Mui-TableHeadCell-Content': {
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'flex-start',
          height: '100%'
        },
        '& .Mui-TableHeadCell-Content-Labels': {
          display: 'flex',
          alignItems: 'center',
          height: '100%'
        },
        '& .Mui-TableHeadCell-Content-Wrapper': {
          display: 'flex',
          alignItems: 'center',
          height: '100%'
        }
      },
    },
    muiTableBodyCellProps: {
      sx: {
        padding: '0.5rem',
        paddingRight: '0.25rem', // 오른쪽 패딩 줄임
        fontSize: '0.75rem',
        borderRight: '1px solid #e2e8f0',
        verticalAlign: 'top',  // 셀 내용을 상단에 정렬
        color: '#334155',  // 텍스트 색상 개선
        height: '59px', // 셀 높이 고정
        maxHeight: '59px', // 최대 높이 제한
        overflow: 'visible', // 셀 자체는 오버플로우 허용 (내부 컨텐츠가 스크롤 처리)
        
        // 모바일 환경에서 셀 조정
        '@media (max-width: 640px)': {
          padding: '0.25rem',
          fontSize: '0.7rem',
          height: '50px',
          maxHeight: '50px',
        },
        
        // 마크다운 스타일링 - 이 스타일을 포탈에도 적용
        '& .prose': {
          maxWidth: 'none',
          fontSize: '0.75rem',
          '& h1': { fontSize: '0.9rem', fontWeight: 'bold', marginBottom: '0.25rem' },
          '& h2': { fontSize: '0.85rem', fontWeight: 'bold', marginBottom: '0.25rem' },
          '& h3': { fontSize: '0.8rem', fontWeight: 'bold', marginBottom: '0.25rem' },
          '& p': { marginBottom: '0.25rem', fontSize: '0.75rem', lineHeight: '1.2' },
          '& strong': { color: 'rgb(29 78 216)', fontWeight: 'bold' },
          '& em': { color: 'rgb(75 85 99)', fontStyle: 'italic' },
          '& code': { backgroundColor: 'rgb(243 244 246)', padding: '0.15rem', borderRadius: '0.25rem', color: 'rgb(220 38 38)', fontSize: '0.75rem' },
          '& ul': { listStyleType: 'disc', paddingLeft: '1rem', marginBottom: '0.25rem' },
          '& ol': { listStyleType: 'decimal', paddingLeft: '1rem', marginBottom: '0.25rem' },
          '& li': { marginBottom: '0.15rem', fontSize: '0.75rem', lineHeight: '1.2' },
          '& table': { width: '100%', borderCollapse: 'collapse', marginBottom: '0.25rem', fontSize: '0.75rem' },
          '& th': { borderWidth: '1px', borderColor: 'rgb(209 213 219)', padding: '0.25rem 0.5rem', backgroundColor: 'rgb(249 250 251)', fontWeight: '600', fontSize: '0.75rem' },
          '& td': { borderWidth: '1px', borderColor: 'rgb(209 213 219)', padding: '0.25rem 0.5rem', fontSize: '0.75rem' },
          // 모바일 환경에서 마크다운 스타일 조정
          '@media (max-width: 640px)': {
            fontSize: '0.7rem',
            '& h1': { fontSize: '0.85rem' },
            '& h2': { fontSize: '0.8rem' },
            '& h3': { fontSize: '0.75rem' },
            '& p': { fontSize: '0.7rem' },
            '& li': { fontSize: '0.7rem' },
            '& code': { fontSize: '0.7rem' },
            '& th': { fontSize: '0.7rem', padding: '0.15rem 0.3rem' },
            '& td': { fontSize: '0.7rem', padding: '0.15rem 0.3rem' }
          }
        },
        '&:hover': {
          backgroundColor: 'f80000',
          cursor: 'pointer',
        },
        // Document 칼럼 셀 내부 요소가 셀 너비를 초과하지 않도록 설정
        '&[data-column-id="filename"]': {
          '& > div': {
            width: '100%',
            maxWidth: '100%',
            overflow: 'hidden'
          }
        }
      }
    },
    muiTableBodyRowProps: ({ row }) => {
      const document = row?.original as IDocument;
      const isCompleted = document?.status === 'COMPLETED';
      
      return {
        hover: false,
        sx: {
          opacity: isCompleted ? 1 : 0.5,
          pointerEvents: isCompleted ? 'auto' : 'none',
          backgroundColor: isCompleted ? 'transparent' : '#f5f5f5',
          '&:hover': {
            backgroundColor: isCompleted ? 'transparent' : '#f5f5f5',
          },
        }
      };
    },
    layoutMode: 'grid', //모든 칼럼은 남은 공간을 채우는 형태
  });



  return (
    <div className="w-full h-full overflow-hidden">
      <style jsx global>{`
        /* 헤더 셀 스타일 직접 조정 */
        .MuiTableHead-root {
          background-color:rgb(219, 227, 228) !important;
        }
        
        .MuiTableHead-root .MuiTableCell-root {
          background-color: rgb(219, 227, 228) !important;
          display: flex !important;
          align-items: center !important;
          height: 36px !important;
          padding: 0 10px !important;
          border-right: 2px solid #e2e8f0 !important;
        }
        
        /* 마지막 헤더 셀은 오른쪽 테두리 제외 */
        .MuiTableHead-root .MuiTableCell-root:last-child {
          border-right: none !important;
        }
        
        /* 헤더 셀 호버 상태 */
        .MuiTableHead-root .MuiTableCell-root:hover {
          background-color: rgb(200, 226, 228) !important;
        }
        
        /* 모바일 환경에서 헤더 셀 조정 */
        @media (max-width: 640px) {
          .MuiTableHead-root .MuiTableCell-root {
            height: 30px !important;
            padding: 0 5px !important;
            font-size: 0.7rem !important;
          }
        }
        
        
        
        /* 헤더 셀 내부 컴포넌트 스타일 조정 */
        .MuiTableHead-root .MuiTableCell-root > div {
          display: flex !important;
          align-items: center !important;
          height: 100% !important;
        }
        
        /* 헤더 셀 텍스트 스타일 조정 */
        .MuiTableHead-root .MuiTableCell-root span {
          display: flex !important;
          align-items: center !important;
          height: 100% !important;
          line-height: 1 !important;
        }
        
        /* 헤더 셀 내부 모든 요소 수직 중앙 정렬 */
        .MuiTableHead-root .MuiTableCell-root * {
          vertical-align: middle !important;
        }
        
        /* Material React Table 특정 클래스 타겟팅 */
        .mrt-thead-cell-content, 
        .mrt-thead-cell-content-wrapper, 
        .mrt-thead-cell-content-labels,
        .mrt-header-cell-text {
          display: flex !important;
          align-items: center !important;
          height: 100% !important;
        }
        
        /* 체크박스 크기 축소 */
        .MuiCheckbox-root {
          padding: 0 !important;
          margin: 0 !important;
        }
        
        /* 체크박스 아이콘 크기 축소 */
        .MuiCheckbox-root svg {
          width: 18px !important;
          height: 18px !important;
        }
        
        /* 모바일 환경에서 체크박스 아이콘 크기 더 축소 */
        @media (max-width: 640px) {
          .MuiCheckbox-root svg {
            width: 16px !important;
            height: 16px !important;
          }
        }
        
        /* 체크박스 셀 공통 스타일 */
        .mrt-row-select-cell,
        .mrt-row-select-head-cell {
          width: 30px !important;
          max-width: 30px !important;
          min-width: 30px !important;
          padding: 0 !important;
          display: flex !important;
          justify-content: center !important;
          align-items: center !important;
        }
        
        /* 모바일 환경에서 체크박스 셀 크기 조정 */
        @media (max-width: 640px) {
          .mrt-row-select-cell,
          .mrt-row-select-head-cell {
            width: 24px !important;
            max-width: 24px !important;
            min-width: 24px !important;
          }
        }
        
        /* 체크박스 셀 내부 컨테이너 스타일 */
        .mrt-row-select-cell > div,
        .mrt-row-select-head-cell > div {
          width: 100% !important;
          height: 100% !important;
          display: flex !important;
          justify-content: center !important;
          align-items: center !important;
          padding: 0 !important;
          margin: 0 !important;
        }
        
        /* 체크박스 컴포넌트 자체 스타일 */
        .mrt-row-select-cell .MuiCheckbox-root,
        .mrt-row-select-head-cell .MuiCheckbox-root {
          display: flex !important;
          justify-content: center !important;
          align-items: center !important;
          padding: 0 !important;
          margin: 0 !important;
          position: relative !important;
          left: 0 !important;
          top: 0 !important;
          transform: none !important;
        }
        
        /* 체크박스 내부 요소 스타일 */
        .MuiCheckbox-root input,
        .MuiCheckbox-root svg {
          margin: 0 auto !important;
        }
        
        /* 헤더 체크박스 특별 처리 */
        .MuiTableHead-root .mrt-row-select-head-cell .Mui-TableHeadCell-Content {
          display: flex !important;
          justify-content: center !important;
          align-items: center !important;
          width: 100% !important;
          height: 100% !important;
          padding: 0 !important;
        }
        
        /* 체크박스 셀 내부 모든 요소 중앙 정렬 */
        .mrt-row-select-cell *, 
        .mrt-row-select-head-cell * {
          display: flex !important;
          justify-content: center !important;
          align-items: center !important;
        }
        
        /* Document 칼럼 셀 내부 요소 너비 제한 */
        .MuiTableBody-root .MuiTableCell-root[data-column-id="filename"] > div {
          width: 100% !important;
          max-width: 100% !important;
          overflow: hidden !important;
        }
        
        /* Document 칼럼 내 파일명 너비 제한 */
        .MuiTableBody-root .MuiTableCell-root[data-column-id="filename"] .truncate {
          max-width: calc(100% - 24px) !important; /* 상태 배지 너비와 간격을 고려한 값 */
        }
        
        /* 모바일 환경에서 Document 칼럼 내 파일명 너비 제한 조정 */
        @media (max-width: 640px) {
          .MuiTableBody-root .MuiTableCell-root[data-column-id="filename"] .truncate {
            max-width: calc(100% - 20px) !important; /* 상태 배지 너비와 간격을 고려한 값 */
            font-size: 0.7rem !important;
          }
        }
        
        /* 테이블 너비 제한 */
        .MuiTable-root {
          width: 100% !important;
          max-width: 100% !important;
        }
        
        /* 테이블 셀 너비 제한 */
        .MuiTableCell-root {
          max-width: 100% !important;
          overflow: hidden !important;
        }
        
        /* 모바일 환경에서 테이블 셀 조정 */
        @media (max-width: 640px) {
          .MuiTableBody-root .MuiTableCell-root {
            padding: 0.25rem !important;
            font-size: 0.7rem !important;
          }
        }
        
        /* 리액트 포탈 마크다운 스타일 통일 */
        body > div > div > div .prose,
        .MuiTableBody-root .prose {
          max-width: none !important;
          font-size: 0.75rem !important;
        }
        
        body > div > div > div .prose h1,
        .MuiTableBody-root .prose h1 { 
          font-size: 0.9rem !important; 
          font-weight: bold !important; 
          margin-bottom: 0.25rem !important;
          margin-top: 0.5rem !important;
        }
        
        body > div > div > div .prose h2,
        .MuiTableBody-root .prose h2 { 
          font-size: 0.85rem !important; 
          font-weight: bold !important; 
          margin-bottom: 0.25rem !important;
          margin-top: 0.5rem !important;
        }
        
        body > div > div > div .prose h3,
        .MuiTableBody-root .prose h3 { 
          font-size: 0.8rem !important; 
          font-weight: bold !important; 
          margin-bottom: 0.25rem !important;
          margin-top: 0.25rem !important;
        }
        
        body > div > div > div .prose p,
        .MuiTableBody-root .prose p { 
          margin-bottom: 0.25rem !important; 
          font-size: 0.75rem !important; 
          line-height: 1.2 !important;
        }
        
        /* 모바일 환경에서 포탈 마크다운 스타일 조정 */
        @media (max-width: 640px) {
          body > div > div > div .prose h1,
          .MuiTableBody-root .prose h1 { 
            font-size: 0.85rem !important;
          }
          
          body > div > div > div .prose h2,
          .MuiTableBody-root .prose h2 { 
            font-size: 0.8rem !important;
          }
          
          body > div > div > div .prose h3,
          .MuiTableBody-root .prose h3 { 
            font-size: 0.75rem !important;
          }
          
          body > div > div > div .prose p,
          body > div > div > div .prose li,
          .MuiTableBody-root .prose p,
          .MuiTableBody-root .prose li { 
            font-size: 0.7rem !important;
          }
        }
        
        body > div > div > div .prose strong,
        .MuiTableBody-root .prose strong { 
          color: rgb(29 78 216) !important; 
          font-weight: bold !important;
        }
        
        body > div > div > div .prose em,
        .MuiTableBody-root .prose em { 
          color: rgb(75 85 99) !important; 
          font-style: italic !important;
        }
        
        body > div > div > div .prose code,
        .MuiTableBody-root .prose code { 
          background-color: rgb(243 244 246) !important; 
          padding: 0.15rem !important; 
          border-radius: 0.25rem !important; 
          color: rgb(220 38 38) !important; 
          font-size: 0.75rem !important;
        }
        
        body > div > div > div .prose ul,
        .MuiTableBody-root .prose ul { 
          list-style-type: disc !important; 
          padding-left: 1rem !important; 
          margin-bottom: 0.25rem !important;
        }
        
        body > div > div > div .prose ol,
        .MuiTableBody-root .prose ol { 
          list-style-type: decimal !important; 
          padding-left: 1rem !important; 
          margin-bottom: 0.25rem !important;
        }
        
        body > div > div > div .prose li,
        .MuiTableBody-root .prose li { 
          margin-bottom: 0.15rem !important; 
          font-size: 0.75rem !important; 
          line-height: 1.2 !important;
        }
        
        body > div > div > div .prose table,
        .MuiTableBody-root .prose table { 
          width: 100% !important; 
          border-collapse: collapse !important; 
          margin-bottom: 0.25rem !important; 
          font-size: 0.75rem !important;
        }
        
        body > div > div > div .prose th,
        .MuiTableBody-root .prose th { 
          border-width: 1px !important; 
          border-color: rgb(209 213 219) !important; 
          padding: 0.25rem 0.5rem !important; 
          background-color: rgb(249 250 251) !important; 
          font-weight: 600 !important; 
          font-size: 0.75rem !important;
        }
        
        body > div > div > div .prose td,
        .MuiTableBody-root .prose td { 
          border-width: 1px !important; 
          border-color: rgb(209 213 219) !important; 
          padding: 0.25rem 0.5rem !important; 
          font-size: 0.75rem !important;
        }
        
        /* 모바일 환경에서 테이블 조정 */
        @media (max-width: 640px) {
          body > div > div > div .prose table,
          body > div > div > div .prose th,
          body > div > div > div .prose td,
          .MuiTableBody-root .prose table,
          .MuiTableBody-root .prose th,
          .MuiTableBody-root .prose td { 
            font-size: 0.65rem !important;
            padding: 0.15rem 0.3rem !important;
          }
        }
        
        /* 모든 스크롤바 이동 버튼 제거 */
        *::-webkit-scrollbar-button {
          display: none !important;
        }
        
        /* 테이블 본문 셀의 우측 테두리 강화 */
        .MuiTableBody-root .MuiTableCell-root {
          border-right: 1px solid #e2e8f0 !important;
        }
        
        /* 마지막 칼럼은 오른쪽 테두리 제외 */
        .MuiTableBody-root .MuiTableCell-root:last-child {
          border-right: none !important;
        }
      `}</style>
      <MaterialReactTable table={table} />
    </div>
  );
});

DocumentTable.displayName = "DocEasyTable";

export default DocumentTable;
