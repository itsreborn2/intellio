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
import * as api from '@/services/api';
import { DELETE_COLUMN } from '@/types/actions';
import { X, Trash2 } from 'lucide-react';
import { toast } from 'sonner';

// 테이블 조작을 위한 유틸리티 함수들
export interface ITableUtils {
  addRow: () => void;
  addColumn: () => void;
  removeRow: (email: string) => void;
  removeColumn: (columnId: string) => void;
  // getTableData: () => IDocument[];
  // getColumnCount: () => number;
}

// DocumentTable 컴포넌트 props 정의
interface DocumentTableProps {
  onHeaderSelect?: (header: string | null) => void;
  selectedHeader?: string | null;
}

// 마크다운 스타일 상수 정의
const markdownClassName = `prose dark:prose-invert max-w-none 
  [&>*:first-child]:mt-0 [&>*:last-child]:mb-0
  [&>h1]:mt-1 [&>h1]:mb-0 [&>h1]:text-lg [&>h1]:font-bold [&>h1]:text-gray-800
  [&>h2]:mt-1 [&>h2]:mb-0 [&>h2]:text-base [&>h2]:font-semibold [&>h2]:text-gray-700
  [&>h3]:mt-1 [&>h3]:mb-0 [&>h3]:text-sm [&>h3]:font-normal [&>h3]:text-gray-600
  [&>p]:my-0 [&>p]:leading-4 [&>p]:whitespace-pre-line [&>p]:text-xs [&>p]:text-gray-800
  [&>ul]:my-0 [&>ul>li]:mt-0 [&>ul>li]:text-xs [&>ul>li]:text-gray-800
  [&>ol]:my-0 [&>ol>li]:mt-0 [&>ol>li]:text-xs [&>ol>li]:text-gray-800
  [&>table]:w-full [&>table]:my-1 [&>table]:border-collapse
  [&>table>thead>tr>th]:border [&>table>thead>tr>th]:border-gray-300 [&>table>thead>tr>th]:p-0 [&>table>thead>tr>th]:bg-gray-100 [&>table>thead>tr>th]:text-left [&>table>thead>tr>th]:text-xs
  sm:[&>p]:text-xs sm:[&>ul>li]:text-xs sm:[&>ol>li]:text-xs sm:[&>table>thead>tr>th]:text-xs
  xs:[&>p]:text-[0.65rem] xs:[&>ul>li]:text-[0.65rem] xs:[&>ol>li]:text-[0.65rem] xs:[&>table>thead>tr>th]:text-[0.65rem]
  prose-strong:font-bold
  prose-em:text-gray-600 prose-em:italic
  prose-code:text-red-600 prose-code:bg-gray-100 prose-code:px-1 prose-code:rounded`;

// 마크다운 셀 컴포넌트
function MarkdownCell({ content }: { content: string }) {
  const [isExpanded, setIsExpanded] = useState(false);
  const [needsScroll, setNeedsScroll] = useState(false);
  const [isHovering, setIsHovering] = useState(false);
  const contentRef = useRef<HTMLDivElement>(null);
  const containerRef = useRef<HTMLDivElement>(null);
  const [position, setPosition] = useState({ top: 0, left: 0, width: 0 });
  const tableRef = useRef<HTMLElement | null>(null);
  const [contentHeight, setContentHeight] = useState(0); // contentHeight 상태 추가
  
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
  
  // 내용 높이 확인 및 스크롤 필요 여부 업데이트
  const checkContentHeight = useCallback(() => {
    if (contentRef.current && containerRef.current) {
      const scrollHeight = contentRef.current.scrollHeight;
      const clientHeight = contentRef.current.clientHeight;
      setContentHeight(scrollHeight); // 실제 컨텐츠 높이 저장
      setNeedsScroll(scrollHeight > clientHeight && scrollHeight > 60); // 60px 기준으로 스크롤 필요 여부 판단
    }
  }, [content]);

  const maxHeight = isExpanded ? `${contentHeight}px` : '60px'; // Max height is 60px when collapsed

  // 브라우저 영역 내에 포털이 표시되도록 위치 계산
  const calculateSafePosition = useCallback((rect: DOMRect) => {
    const padding = 20; // 화면 가장자리로부터의 최소 여백
    const headerHeight = 36; // 테이블 헤더의 높이
    const minPopupWidth = 400; // 팝업창의 최소 너비
    
    // DocumentTable의 위치 정보 가져오기
    let tableTop = 0;
    if (tableRef.current) {
      const tableRect = tableRef.current.getBoundingClientRect();
      tableTop = tableRect.top;
    }
    
    const minTopPadding = Math.max(headerHeight + 10, tableTop); // 헤더 높이 + 추가 여백 또는 테이블 상단 중 큰 값
    const viewportWidth = window.innerWidth;
    const viewportHeight = window.innerHeight;
    const expandedWidth = Math.max(minPopupWidth, rect.width + 40); // 확장 시 너비 (최소 300px)
    const estimatedHeight = Math.min(rect.height * 5, 500); // 예상 높이 (최대 500px)
    
    // 기본 위치 (셀의 중앙에서 시작)
    let top = rect.top;
    let left = rect.left;
    
    // 너무 작은 칼럼인 경우 팝업이 셀 중앙에서 시작하도록 조정
    if (rect.width < minPopupWidth) {
      left = Math.max(padding, rect.left - (minPopupWidth - rect.width) / 2);
    }
    
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
      top = Math.max(minTopPadding, rect.top - estimatedHeight); // 셀 위에 간격 없이 표시
      
      // 계산된 위치가 테이블 상단보다 작으면 조정
      if (top < minTopPadding) {
        // 위쪽에도 충분한 공간이 없으면 테이블 헤더 아래에 표시
        top = minTopPadding;
      }
    } else {
      // 하단에 충분한 공간이 있으면 셀 아래에 표시
      top = rect.bottom; // 셀 아래에 표시
    }
    
    return { top, left, width: Math.max(minPopupWidth - 40, rect.width) }; // 최소 너비 보장 (padding 40px 고려)
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
  
  // 아이콘 클릭 이벤트 핸들러
  const handleIconClick = useCallback((e: React.MouseEvent) => {
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
        ${isHovering ? 'bg-gray-50' : ''}
      `}
      style={{
        userSelect: 'none',
        maxHeight: isExpanded ? '500px' : '60px', // 축소 시 최대 높이를 60px로 증가
        width: isExpanded ? `${position.width}px` : '100%',
        top: isExpanded ? `${position.top}px` : undefined,
        left: isExpanded ? `${position.left}px` : undefined,
        padding: isExpanded ? '10px' : '0px', // 확장 시에만 패딩 적용
        position: isExpanded ? 'fixed' : 'relative', // 확장 시 position 변경
      }}
      onDoubleClick={handleDoubleClick}
      onMouseEnter={() => setIsHovering(true)}
      onMouseLeave={() => setIsHovering(false)}
    >
      {/* 내부 스크롤 가능한 컨테이너 */}
      <div
        className="overflow-y-auto overflow-x-hidden"
        style={{
          maxHeight: isExpanded ? '480px' : '60px', // 내부 컨텐츠 최대 높이도 동기화
          width: '100%',
          scrollbarWidth: 'thin',
          scrollbarColor: 'rgb(203 213 225) transparent' // Tailwind gray-300
        }}
      >
        <div 
          ref={contentRef}
          style={{
            userSelect: 'none', // 텍스트 선택 비활성화
            width: '100%',
            boxSizing: 'border-box', // 패딩 포함 계산
            paddingRight: needsScroll && !isExpanded ? '0px' : '0', // 스크롤 필요시 우측 패딩 제거 (기존 스크롤바 공간)
            margin: '0' // 기본 마진 제거
          }}
        >
          <ReactMarkdown remarkPlugins={[remarkGfm]} className={markdownClassName}>
            {content}
          </ReactMarkdown>
        </div>
      </div>
      
      {/* UI 요소들을 위한 절대 위치 컨테이너 */}
      {/* 이 요소들은 스크롤과 무관하게 항상 고정된 위치에 표시됨 */}
      <div className="absolute inset-0 pointer-events-none">
        {/* 스크롤 표시를 위한 UI - 고정 위치 */}
        {needsScroll && (
          <div className="absolute left-0 bottom-0 px-1 py-0.5">
            <span className="text-[9px] text-gray-500">↓</span>
          </div>
        )}
        
        {/* 셀 확장 버튼 - 항상 고정된 위치, 내용 위에 겹침 */}
        <div 
          className="absolute right-0 bottom-0 z-20 flex items-center bg-white bg-opacity-70 px-1 py-0.5 rounded-tl cursor-pointer hover:bg-gray-100 pointer-events-auto"
          onClick={handleIconClick}
          title="클릭하여 자세히 보기"
          data-tooltip-delay="100"
        >
          <span className="text-[9px] text-blue-500 italic">
            <svg 
              xmlns="http://www.w3.org/2000/svg" 
              width="12" 
              height="12" 
              viewBox="0 0 24 24" 
              fill="none" 
              stroke="currentColor" 
              strokeWidth="2" 
              strokeLinecap="round" 
              strokeLinejoin="round" 
              className="inline-block"
            >
              <circle cx="11" cy="11" r="8"></circle>
              <line x1="21" y1="21" x2="16.65" y2="16.65"></line>
              <line x1="11" y1="8" x2="11" y2="14"></line>
              <line x1="8" y1="11" x2="14" y2="11"></line>
            </svg>
          </span>
        </div>
      </div>
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
          width: `${Math.max(300, Math.min(position.width + 40, window.innerWidth - 40))}px`, // 최소 너비 300px 보장
          maxHeight: `${Math.min(500, window.innerHeight - Math.max(position.top, 20) - 20)}px`, // 높이 제한 개선
          minHeight: '100px',
          padding: '8px',       // 패딩 줄임 (12px → 8px)
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
            width: `${Math.max(250, Math.min(window.innerWidth - 20, position.width + 20))}px`, // 모바일에서도 최소 너비 250px 보장
            padding: '4px',     // 모바일 패딩 더 줄임 (8px → 4px)
            left: `${Math.max(10, Math.min(position.left, window.innerWidth - Math.max(250, position.width + 20) - 10))}px`
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
            boxSizing: 'border-box',
            position: 'relative',
            paddingBottom: '20px' // 닫기 버튼을 위한 공간 확보 (26px → 20px)
          }}
        >
          <ReactMarkdown remarkPlugins={[remarkGfm]} className={markdownClassName}>
            {content}
          </ReactMarkdown>
          <div className="absolute bottom-0 right-0">
            <span 
              className="text-[10px] text-gray-500 bg-gray-100 px-2 py-0.5 rounded cursor-pointer hover:bg-gray-200"
              onClick={handleCollapseClick}
            >
              닫기
            </span>
          </div>
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

const DocumentTable = forwardRef<ITableUtils, DocumentTableProps>((props, ref) => {
  const { state, dispatch } = useApp()
  const [showAgeColumn, setShowAgeColumn] = useState(true);
  const [countCol, setCountCol] = useState(0);
  const [countRow, setCountRow] = useState(0);
  const [selectedHeader, setSelectedHeader] = useState<string | null>(null);

  // 부모로부터 받은 헤더 선택 상태와 동기화
  useEffect(() => {
    if (props.selectedHeader !== undefined) {
      setSelectedHeader(props.selectedHeader);
    }
  }, [props.selectedHeader]);

  // 헤더 선택 시 부모에게 알림
  const handleHeaderSelection = useCallback((headerId: string) => {
    const newHeaderState = selectedHeader === headerId ? null : headerId;
    setSelectedHeader(newHeaderState);
    if (props.onHeaderSelect) {
      props.onHeaderSelect(newHeaderState);
    }
  }, [props.onHeaderSelect, selectedHeader]);

  const tableData = useMemo(() => {
    // 기본 데이터
    const baseData: IDocument[] = []
    //console.log(`[DocumentTable] documents length: ${Object.keys(state.documents).length}`)
    // documents에 있는 내용 업데이트.
    // document가 추가될때. 즉 row가 1개 늘어나야할때 호출됨. 문서 업로드 / 문서 추가 시
    const additionalData = Object.values(state.documents).map((document) => ({
      ...document
    }));
    console.debug(`[DocumentTable] documents 변경 : ` , additionalData)

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
        header: "문서이름",
        enableSorting: true, // Document 컬럼만 정렬 활성화
        Cell: ({ row }: { row: MRT_Row<IDocument> }) => {
          const document = row.original;
          const status = document.status;
          
          // 파일명 길이 확인 (긴 파일명 여부 체크)
          const isLongFilename = document.filename.length > 25;
          
          // 상태에 따른 색상 클래스 결정
          let colorClass = '';
          if (status === 'ERROR') {
            colorClass = 'doc-filename-error';
          } else if (status === 'PROCESSING' || status === 'PARTIAL' || status === 'UPLOADING' || status === 'UPLOADED') {
            colorClass = 'doc-filename-processing';
          }

          return (
            <div className="doc-filename-cell">
              <div className="doc-filename-container">
                <p 
                  className={`doc-filename-text text-sm ${isLongFilename ? 'doc-filename-long' : 'doc-filename-short'} ${colorClass}`}
                  title={document.filename}
                >
                  {document.filename}
                </p>
              </div>
              
              {status !== 'COMPLETED' && (
                <div className="doc-status-container">
                  <DocumentStatusBadge status={status} />
                </div>
              )}
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
            enableSorting: false, // 추가 컬럼은 정렬 비활성화
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

    // 문서이름 컬럼 설정 조정
    baseColumns[0] = {
      ...baseColumns[0],
      size: 300, 
      grow: false, 
      minSize: 120, 
      maxSize: 250, 
      muiTableHeadCellProps: {
        sx: {
          // 모바일 특정 스타일 제거 (전역 설정 사용)
        }
      },
      muiTableBodyCellProps: {
        sx: {
          // 모바일 특정 스타일 제거 (전역 설정 사용)
        }
      }
    };

    // Document 컬럼의 크기를 조절 (추가된 컬럼이 있을 때만)
    if (addedColumnsCount > 0) {
      baseColumns[0] = {
        ...baseColumns[0],
        size: undefined, 
        grow: false, 
        minSize: 120, 
        maxSize: 250, 
        // muiTableHeadCellProps와 muiTableBodyCellProps는 위에서 이미 제거했으므로 여기서는 불필요
      };

      // Document 컬럼 이후의 컬럼들에 대해 균등한 너비 설정 및 모바일 스타일 제거
      for (let i = 1; i < baseColumns.length; i++) {
        baseColumns[i] = {
          ...baseColumns[i],
          size: undefined, 
          grow: true,      
          minSize: 180,    
          maxSize: 300,    
          muiTableHeadCellProps: {
            sx: {
              // 모바일 특정 스타일 제거 (전역 설정 사용)
            }
          },
          muiTableBodyCellProps: {
            sx: {
             // 모바일 특정 스타일 제거 (전역 설정 사용)
            }
          }
        };
      }
    }
    
    // 칼럼이 5개를 초과하면 테이블에 가로 스크롤 적용
    const hasHorizontalScroll = baseColumns.length > 5; // 체크박스 컬럼까지 포함해서 총 6개 이상
    console.debug(`[DocumentTable] 총 컬럼 수: ${baseColumns.length}, 가로 스크롤: ${hasHorizontalScroll}`);
    
    // Document 컬럼을 고정 설정
    if (hasHorizontalScroll && baseColumns.length > 0) {
      // Document 컬럼 스티키 설정
      baseColumns[0] = {
        ...baseColumns[0],
        muiTableHeadCellProps: {
          align: 'left',
          sx: {
            position: 'sticky',
            left: '30px', // 체크박스 컬럼 너비
            zIndex: 2,
            backgroundColor: 'rgb(238, 238, 250) !important', // 기본 배경색 유지
            // 기존 스타일 유지...
            '&::after': {
              content: '""',
              position: 'absolute',
              right: 0,
              top: 0,
              bottom: 0,
              width: '1px',
              backgroundColor: '#ccc',
              boxShadow: '2px 0 5px rgba(0,0,0,0.1)',
            },
          }
        },
        muiTableBodyCellProps: {
          align: 'left',
          sx: {
            position: 'sticky',
            left: '30px', // 체크박스 컬럼 너비
            zIndex: 1,
            backgroundColor: 'white', // 배경색 일관성 유지
             // 기존 스타일 유지...
            '&::after': {
              content: '""',
              position: 'absolute',
              right: 0,
              top: 0,
              bottom: 0,
              width: '1px',
              backgroundColor: '#ccc',
              boxShadow: '2px 0 5px rgba(0,0,0,0.1)',
            },
          }
        }
      };
    }
    
    return baseColumns;
  }, [dispatch, documentColContexts, state.documents]); // 의존성 배열은 그대로 유지

  // 칼럼 수에 따라 테이블 너비 계산 (기존 로직 유지)
  const calculateTableWidth = useMemo(() => {
    const totalColumns = columns.length; 
    const checkboxColWidth = 30; 
    const documentColWidth = 250; 
    const additionalColWidth = 200; 
    const additionalColumns = Math.max(0, totalColumns - 2);
    
    if (totalColumns <= 5) {
      return '100%';
    } else {
      const calculatedWidth = checkboxColWidth + documentColWidth + (additionalColumns * additionalColWidth);
      return Math.max(1200, calculatedWidth) + 'px';
    }
  }, [columns.length]);

  // 칼럼이 5개를 초과하는지 여부 계산 (기존 로직 유지)
  const hasHorizontalScroll = useMemo(() => columns.length > 5, [columns.length]);
  
  // 칼럼 삭제 핸들러 (기존 로직 유지)
  const handleDeleteColumn = async (columnId: string) => {
    if (!columnId || columnId === 'filename') return;
    
    try {
      const projectId = state.currentProjectId;
      if (!projectId) return;
      
      const response = await api.deleteColumn(projectId, columnId);
      
      if (response.success) {
        dispatch({
          type: DELETE_COLUMN,
          payload: columnId
        });
        toast.success(`${columnId} 컬럼이 삭제되었습니다.`);
        if (props.onHeaderSelect) {
          props.onHeaderSelect(null);
        }
        setSelectedHeader(null);
      } else {
        toast.error("컬럼 삭제에 실패했습니다.");
      }
    } catch (error) {
      console.error("컬럼 삭제 중 오류가 발생했습니다:", error);
      toast.error("컬럼 삭제 중 오류가 발생했습니다.");
    }
  };
  
  // 헤더 위치 계산을 위한 함수 (기존 로직 유지)
  const getHeaderPosition = useCallback(() => {
    if (!selectedHeader) return { left: '0px' };
    
    const baseWidth = 40 + 250; 
    const selectedIndex = columns.findIndex(col => col.accessorKey === selectedHeader);
    
    if (selectedIndex <= 0) return { left: '40px' }; 
    
    const avgColumnWidth = 200;
    const estimatedLeft = baseWidth + ((selectedIndex - 1) * avgColumnWidth);
    const maxLeft = typeof window !== 'undefined' ? window.innerWidth - 200 : 1000;
    
    return {
      left: `${Math.min(estimatedLeft, maxLeft)}px`
    };
  }, [selectedHeader, columns]);

  const table = useMaterialReactTable({
    columns,
    data: tableData,
    enableRowSelection: true,
    enableMultiRowSelection: true,
    enableColumnResizing: false, // 크기 조정 비활성화 유지
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
    enableSorting: true, 
    positionToolbarAlertBanner: 'none',
    getRowId: (doc) => doc.id,
    defaultColumn: {
      minSize: 30, 
      maxSize: 500, 
      size: 30,    
    },
    displayColumnDefOptions: {
      'mrt-row-select': {
        size: 30,
        grow: false,
        maxSize: 30,
        minSize: 30,
        muiTableHeadCellProps: {
          sx: {
            padding: '0',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            width: '30px', // 고정 너비
            height: '42px', // 헤더 행 높이 고정
            '& .Mui-TableHeadCell-Content': { 
              display: 'flex',
              justifyContent: 'center', // 내부 div 수평 중앙 정렬
              alignItems: 'center',     // 내부 div 수직 중앙 정렬
              width: '100%',            // 내부 div 너비 100%
              height: '100%',           // 내부 div 높이 100%
            },
            '&:hover': { // 마우스 오버 시 배경색 변경
              backgroundColor: '#858B9D !important'
            },
          }
        },
        muiTableBodyCellProps: {
          sx: {
            padding: '0',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            width: '30px', // 고정 너비
            height: '69px', // 본문 행 높이 고정
          }
        }
      }
    },
    // 전역 헤더 셀 스타일
    muiTableHeadCellProps: ({ column }) => {
      const props: any = {
        sx: {
          padding: '0px 10px',
          backgroundColor: 'rgb(238, 238, 250) !important', // 기본 배경색 유지
          borderRight: '1px solid #e2e8f0',
          borderBottom: '2px solid #e2e8f0',
          fontWeight: 600,
          color: '#1e293b',
          fontSize: '0.875rem', // 14px로 변경
          whiteSpace: 'nowrap',
          display: 'flex',
          alignItems: 'center',
          height: '42px', // 데스크톱 높이 42px로 고정
          '&:hover': { // 마우스 오버 시 배경색 변경
            backgroundColor: 'rgba(0, 0, 0, 0.04) !important'
          },
          // 모바일 특정 스타일 제거 (전역 설정 사용)
          '@media (max-width: 767px)': {
            minHeight: '34px', // 모바일 최소 높이 34px
            fontSize: '0.8rem', // 모바일 폰트 크기 13px
          },
          // .MuiBox-root 스타일 통합 (기존 유지)
          '& .MuiBox-root': {
            display: 'flex',
            alignItems: 'center',
            height: '100%'
          },
          '& .MuiTableHeadCell-Content': {
            display: 'flex',
            alignItems: 'center',
            height: '100%'
          },
          '& .MuiTableHeadCell-Content-Labels': {
            display: 'flex',
            alignItems: 'center',
            height: '100%'
          },
          '& .MuiTableHeadCell-Content-Wrapper': {
            display: 'flex',
            alignItems: 'center',
            height: '100%'
          }
        }
      };
      
      // mrt-row-select 컬럼 특별 처리 (기존 유지)
      if (column.id === 'mrt-row-select') {
        props.sx.padding = '0 !important';
        props.sx.display = 'flex !important';
        props.sx.alignItems = 'center !important';
        props.sx.justifyContent = 'center !important';
        // 체크박스 헤더 셀의 폰트 크기는 전역 설정을 따르므로 별도 지정 불필요
        return props;
      }
      
      // 선택 가능한 헤더 처리 (filename 제외, 기존 로직 유지)
      if (column.id !== 'filename') {
        props.onClick = () => {
          handleHeaderSelection(column.id);
        };
        
        props.children = (
          <div 
            style={{ 
              display: 'flex', 
              alignItems: 'center',
              // justifyContent: 'space-between', // 스타일 제거
              width: '100%' 
            }}
          >
            {/* header 텍스트는 전역 fontSize 적용 */}
            <span>{column.columnDef.header}</span> 
            {/* 휴지통 아이콘 - 항상 표시되도록 조건 제거 */}
            <Trash2 
              size={14} // 아이콘 크기는 유지
              className="text-gray-500 hover:text-red-500 ml-2 cursor-pointer flex-shrink-0" // 줄어들지 않도록 flex-shrink-0 추가
              onClick={(e) => {
                e.stopPropagation(); // 헤더 선택 이벤트 전파 방지
                handleDeleteColumn(column.id); // 삭제할 컬럼 ID 전달 (handleDeleteColumn 함수 시그니처 확인 필요)
              }}
            />
          </div>
        );
        
        props.sx.cursor = 'pointer';
        props.sx.backgroundColor = selectedHeader === column.id 
          ? 'rgb(186, 230, 253) !important' 
          : 'rgb(219, 227, 228) !important'; // 선택되지 않은 헤더 기본 배경색
        props.sx['&:hover'] = {
          backgroundColor: selectedHeader === column.id 
            ? 'rgb(186, 230, 253) !important' 
            : 'rgba(0, 0, 0, 0.04) !important' // 선택되지 않은 헤더 hover 배경색
        };
      } else {
        // filename 컬럼 처리 (기존 유지)
        props.sx['&:hover'] = {
          backgroundColor: 'rgba(0, 0, 0, 0.04) !important'
        };
      }
      
      return props;
    },
     // 전역 바디 셀 스타일 추가
    muiTableBodyCellProps: {
      sx: {
        paddingTop: '0.5rem',     // 상단 패딩 명시적 설정
        paddingBottom: '0.5rem',  // 하단 패딩 명시적 설정
        paddingRight: '0.5rem',   // 오른쪽 패딩 증가
        fontSize: '0.875rem', // 14px로 설정
        borderRight: '1px solid #e2e8f0',
        verticalAlign: 'top',      // 셀 내용을 상단에 정렬
        color: '#000000',          // 글자색 변경 (검정)
        minHeight: '69px',         // 최소 높이 59px에서 69px로 증가
        maxHeight: 'none',         // 최대 높이 제한 제거
        overflow: 'visible',       // 셀 자체는 오버플로우 숨김 처리하여 높이 고정
        whiteSpace: 'normal',      // 텍스트가 줄바꿈되도록 설정
        
        // 모바일 환경에서 셀 조정
        '@media (max-width: 640px)': {
          paddingTop: '0.35rem',  // 모바일 상단 패딩 명시적 설정
          paddingBottom: '0.35rem', // 모바일 하단 패딩 명시적 설정
          fontSize: '0.8rem', // 13px로 설정
          minHeight: '59px',      // 모바일 최소 높이도 50px에서 59px로 증가
        },
        
        // 마크다운 스타일링 - 이 스타일을 포탈에도 적용
        '& .prose': {
          maxWidth: 'none',
          fontSize: '0.875rem', // 14px로 설정
          '& h1': { fontSize: '0.9rem', fontWeight: 'bold', marginBottom: '0.25rem' },
          '& h2': { fontSize: '0.85rem', fontWeight: 'bold', marginBottom: '0.25rem' },
          '& h3': { fontSize: '0.8rem', fontWeight: 'bold', marginBottom: '0.25rem' },
          '& p': { marginBottom: '0.25rem', fontSize: '0.875rem', lineHeight: '1.2' },
          '& strong': { color: 'rgb(29 78 216)', fontWeight: 'bold' },
          '& em': { color: 'rgb(75 85 99)', fontStyle: 'italic' },
          '& code': { backgroundColor: 'rgb(243 244 246)', padding: '0.15rem', borderRadius: '0.25rem', color: 'rgb(220 38 38)', fontSize: '0.875rem' },
          '& ul': { listStyleType: 'disc', paddingLeft: '1rem', marginBottom: '0.25rem' },
          '& ol': { listStyleType: 'decimal', paddingLeft: '1rem', marginBottom: '0.25rem' },
          '& li': { marginBottom: '0.15rem', fontSize: '0.875rem', lineHeight: '1.2' },
          '& table': { width: '100%', borderCollapse: 'collapse', marginBottom: '0.25rem', fontSize: '0.875rem' },
          '& th': { borderWidth: '1px', borderColor: 'rgb(209 213 219)', padding: '0.25rem 0.5rem', backgroundColor: 'rgb(249 250 251)', fontWeight: 600, fontSize: '0.875rem' },
          '& td': { borderWidth: '1px', borderColor: 'rgb(209 213 219)', padding: '0.25rem 0.5rem', fontSize: '0.875rem' },
          // 모바일 환경에서 마크다운 스타일 조정
          '@media (max-width: 640px)': {
            fontSize: '0.8rem', // 13px로 설정
            '& h1': { fontSize: '0.85rem' }, // 헤딩 크기 유지 또는 약간 줄임
            '& h2': { fontSize: '0.8rem' },
            '& h3': { fontSize: '0.75rem' },
            '& p': { fontSize: '0.8rem', lineHeight: '1.2' }, // 본문 폰트 크기 조정
            '& li': { fontSize: '0.8rem', lineHeight: '1.2' }, // 목록 폰트 크기 조정
            '& code': { fontSize: '0.8rem' }, // 코드 폰트 크기 조정
            '& th': { fontSize: '0.8rem', padding: '0.15rem 0.3rem' }, // 테이블 헤더 폰트/패딩 조정
            '& td': { fontSize: '0.8rem', padding: '0.15rem 0.3rem' } // 테이블 셀 폰트/패딩 조정
          }
        },
        '&:hover': {
          backgroundColor: 'rgba(0, 0, 0, 0.04)',
          cursor: 'pointer',
        },
        
        // Document 칼럼 셀 스타일 (filename)
        '&[data-column-id="filename"]': {
          height: 'auto',
          minHeight: '30px',
          maxHeight: 'none',
          padding: '4px 2px',      // 패딩 더 줄임
          overflow: 'visible',
          
          // Document 칼럼 내 파일명 컨테이너
          '& .filename-container': {
            padding: '2px 0',      // 패딩 줄임
          },
          
          // Document 칼럼 내 파일명 문단 공통 스타일
          '& p': {
            margin: 0,
            maxWidth: '100%',
            lineHeight: 1.2,
            paddingTop: '2px',
            paddingBottom: '2px',
            width: '100%',
            textAlign: 'left',
          },
          
          // 길이가 짧은 파일명 (한 줄로 표시)
          '& p.short-filename': {
            whiteSpace: 'nowrap',
            overflow: 'hidden',
            textOverflow: 'ellipsis',
          },
          
          // 길이가 긴 파일명 (여러 줄로 표시)
          '& p.long-filename': {
            whiteSpace: 'normal',
            wordBreak: 'break-all',
            wordWrap: 'break-word',
            overflowWrap: 'break-word',
            hyphens: 'auto',
          },
          
          // 상태 배지 위치 조정
          '& .status-badge': {
            marginTop: '2px',
            flexShrink: 0,
            display: 'inline-flex',
          },
          
          // 모바일 환경에서 Document 칼럼 내 파일명 스타일 조정
          '@media (max-width: 640px)': {
            '& span:first-of-type': { // ':first-child' 대신 ':first-of-type' 사용
              fontSize: '0.8rem', // 모바일 폰트 크기 13px
              lineHeight: 1.2,
              '&.doc-filename-long': {
                maxHeight: '3.6em', // 모바일 최대 3줄
              }
            }
          }
        }
      }
    },
    muiTableBodyRowProps: ({ row }) => ({
      sx: {
        ...(row.getIsSelected() && {
          backgroundColor: '#ABABAB !important', // 선택된 행 배경색
          '&:hover': {
            backgroundColor: '#ABABAB !important', // 선택된 행 호버 시 배경색 유지
          },
        }),
        ...(!row.getIsSelected() && {
          '&:hover': {
            backgroundColor: 'rgba(0, 0, 0, 0.04) !important', // 선택되지 않은 행 hover 배경색 추가
          },
        }),
      },
    }),
    muiTableHeadRowProps: {
      sx: {
        backgroundColor: '#F4F4F4', // 배경색 변경
        '& .MuiTableCell-root': {
          color: '#000000', // 글자색 변경 (검정)
          fontWeight: 'normal', // 글자 굵기 일반으로 변경
        },
      },
    },
    muiSelectCheckboxProps: { // Prop 이름 수정: muiTableCheckboxProps -> muiSelectCheckboxProps
      sx: {
        '&.Mui-checked': {
          color: '#ABABAB', // 체크박스 자체 색상
          '.MuiSvgIcon-root': { fill: '#ABABAB !important' } // 아이콘 색상 변경 (!important 추가)
        },
        '&.MuiCheckbox-indeterminate': { // 중간 상태 추가
          color: '#ABABAB', // 체크박스 자체 색상
          '.MuiSvgIcon-root': { fill: '#ABABAB !important' } // 아이콘 색상
        },
      },
    },
    muiSelectAllCheckboxProps: { // Prop 이름 수정: muiTableCheckboxProps -> muiSelectAllCheckboxProps
      sx: {
        '&.Mui-checked': {
          color: '#ABABAB', // 체크박스 자체 색상
          '.MuiSvgIcon-root': { fill: '#ABABAB !important' } // 아이콘 색상 변경 (!important 추가)
        },
        '&.MuiCheckbox-indeterminate': { // 중간 상태 추가
          color: '#ABABAB', // 체크박스 자체 색상
          '.MuiSvgIcon-root': { fill: '#ABABAB !important' } // 아이콘 색상
        },
      },
    },
    layoutMode: 'grid', //모든 칼럼은 남은 공간을 채우는 형태
  });

  return (
    <div className="w-full overflow-hidden relative" style={{ height: 'auto', maxHeight: '100%', display: 'flex', flexDirection: 'column' }}>
      {/* 삭제 버튼 제거 */}
      
      <style jsx global>{`
        /* 스크롤바 스타일 설정 - 모든 스크롤바에 적용 */
        * {
          scrollbar-width: thin; /* Firefox용 */
          scrollbar-color: rgba(133, 139, 157, 0.3) transparent; /* Firefox용 */
          -webkit-overflow-scrolling: touch; /* iOS 스크롤 성능 향상 */
        }
        
        /* Webkit 기반 브라우저(크롬, 사파리, 에지 등)용 스크롤바 스타일 */
        *::-webkit-scrollbar {
          width: 6px; /* 세로 스크롤바 너비 */
          height: 6px; /* 가로 스크롤바 높이 */
        }
        
        *::-webkit-scrollbar-track {
          background: transparent; /* 스크롤바 트랙 배경 */
        }
        
        *::-webkit-scrollbar-thumb {
          background-color: rgba(133, 139, 157, 0.3); /* 스크롤바 색상 */
          border-radius: 3px; /* 스크롤바 모서리 반경 */
          border: none; /* 테두리 제거 */
        }
        
        *::-webkit-scrollbar-thumb:hover {
          background-color: rgba(133, 139, 157, 0.5); /* 호버 시 스크롤바 색상 */
        }
        
        /* 모바일 환경에서도 동일한 스크롤바 스타일 적용 */
        @media (max-width: 767px) {
          * {
            scrollbar-width: thin; /* Firefox용 */
            scrollbar-color: rgba(133, 139, 157, 0.3) transparent; /* Firefox용 */
            -webkit-overflow-scrolling: touch; /* iOS 스크롤 성능 향상 */
          }
          
          *::-webkit-scrollbar {
            width: 4px; /* 모바일에서는 조금 더 작게 */
            height: 4px;
          }
          
          *::-webkit-scrollbar-thumb {
            background-color: rgba(133, 139, 157, 0.3);
            border-radius: 2px;
          }
        }
        
        /* 헤더 셀 스타일 직접 조정 */
        .MuiTableHead-root {
          background-color: #F4F4F4 !important;
        }
        
        /* 테이블 행 테두리 스타일 완전히 제거 */
        .MuiTableBody-root .MuiTableRow-root {
          border: none !important;
          box-shadow: none !important;
          outline: none !important;
          height: auto !important; /* 행 높이 자동 설정 */
          min-height: 70px !important; /* 최소 높이 증가 */
          max-height: none !important; /* 최대 높이 제한 제거 */
          overflow: visible !important; /* 내용이 보이도록 오버플로우 보이게 설정 */
        }
        
        /* 테이블 셀 사이에만 약간의 구분선 추가 */
        .MuiTableBody-root .MuiTableCell-root {
          border-bottom: 1px solid rgba(194, 190, 190, 0.3) !important;
          border-top: none !important;
          border-left: none !important;
          border-right: none !important;
          padding: 0.4rem !important; /* 셀 패딩 증가 */
          height: auto !important; /* 셀 높이 자동 설정 */
          max-height: none !important; /* 셀 최대 높이 제한 제거 */
          overflow: visible !important; /* 내용이 보이도록 오버플로우 보이게 설정 */
        }
        
        /* 마지막 셀의 오른쪽 테두리 제거 */
        .MuiTableBody-root .MuiTableCell-root:last-child {
          border-right: none !important;
        }
        
        /* 마지막 행의 하단 테두리 제거 */
        .MuiTableBody-root .MuiTableRow-root:last-child .MuiTableCell-root {
          border-bottom: none !important;
        }
        
        /* 테이블 전체 테두리 제거 */
        .MuiTable-root {
          border: none !important;
        }
        
        /* 모바일 환경에서 테이블 행 높이 조정 */
        @media (max-width: 640px) {
          .MuiTableBody-root .MuiTableRow-root {
            min-height: 60px !important;
          }
        }
        
        /* 툴팁 딜레이 줄이기 */
        [title]:hover::after {
          content: attr(title);
          position: absolute;
          bottom: 100%;
          left: 50%;
          transform: translateX(-50%);
          background-color: rgba(0, 0, 0, 0.8);
          color: white;
          padding: 2px 6px;
          border-radius: 3px;
          font-size: 10px;
          white-space: nowrap;
          z-index: 100;
          transition-delay: 0.1s !important;
          transition-duration: 0.1s !important;
        }
        
        /* 툴팁 딜레이 속성이 있는 경우 */
        [data-tooltip-delay="100"]:hover::after {
          transition-delay: 0.1s !important;
        }
        
        .MuiTableHead-root .MuiTableCell-root {
          display: flex !important;
          align-items: center !important;
          height: 42px !important; /* 데스크톱 높이 42px로 고정 */
          padding: 0 10px !important;
          borderRight: none !important;
        }
        
        /* 마지막 헤더 셀은 오른쪽 테두리 제외 */
        .MuiTableHead-root .MuiTableCell-root:last-child {
          borderRight: none !important;
        }
        
        /* 헤더 셀 호버 상태 */
        .MuiTableHead-root .MuiTableCell-root:hover {
          background-color: 'rgba(0, 0, 0, 0.04) !important';
        }
        
        /* 모바일 환경에서 헤더 셀 조정 */
        @media (max-width: 640px) {
          .MuiTableHead-root .MuiTableCell-root {
            height: 34px !important; /* 모바일에서도 헤더 높이 유지 */
            padding: 0 5px !important;
            font-size: 0.8rem !important;
          }
        }
        
        
        
        /* 헤더 셀 내부 컴포넌트 스타일 조정 */
        .MuiTableHead-root .MuiTableCell-root > div {
          display: flex !important;
          align-items: center !important;
          height: 100% !important; /* 헤더 내부 요소 높이 자동 설정 */
        }
        
        /* 헤더 셀 텍스트 스타일 조정 */
        .MuiTableHead-root .MuiTableCell-root span {
          display: flex !important;
          align-items: center !important;
          height: 100% !important; /* 헤더 내부 요소 높이 자동 설정 */
          line-height: 1 !important;
          padding-top: 0 !important;
          padding-bottom: 0 !important;
          margin-top: 0 !important;
          margin-bottom: 0 !important;
        }
        
        /* 헤더 셀 내부 모든 요소 수직 중앙 정렬 */
        .MuiTableHead-root .MuiTableCell-root * {
          vertical-align: middle !important;
        }
        
        /* Material React Table 특정 클래스 타겟팅 */
        .mrt-thead-cell-content, 
        .mrt-thead-cell-content-wrapper, 
        .mrt-thead-cell-content-labels,
        .mrt-header-cell-text,
        .mrt-header-cell-content {
          display: flex !important;
          align-items: center !important;
          height: 100% !important; /* 헤더 내부 요소 높이 자동 설정 */
          justify-content: flex-start !important; /* 좌측 정렬 */
        }
        
        /* 문서이름 컨텐츠 정렬 추가 조정 */
        .MuiTableCell-head[data-index="1"] .mrt-header-cell-content,
        .MuiTableCell-head[data-index="1"] .mrt-header-cell-text,
        .MuiTableCell-head .Mui-TableHeadCell-Content,
        .MuiTableCell-head .Mui-TableHeadCell-Content-Labels,
        .MuiTableCell-head .Mui-TableHeadCell-Content-Wrapper {
          display: flex !important;
          align-items: center !important;
          height: 100% !important;
          line-height: 1 !important; /* 줄간격 조정 */
        }
        
        /* 문서이름 텍스트 자체 정렬 */
        .MuiTableCell-head .Mui-TableHeadCell-Content-Wrapper {
          padding-top: 0 !important;
          padding-bottom: 0 !important;
          margin-top: 0 !important;
          margin-bottom: 0 !important;
        }
        
        /* 헤더 내 버튼 상하 중앙 정렬 */
        .MuiTableHead-root button {
          display: inline-flex !important;
          align-items: center !important;
          justify-content: center !important;
          gap: 2px !important;
          white-space: nowrap !important;
          border-radius: 0.375rem !important;
          font-size: 0.875rem !important;
          font-weight: 500 !important;
          height: 2rem !important; /* h-8 */
          width: 2rem !important; /* w-8 */
          border: 1px solid !important;
          background-color: var(--background, white) !important;
          position: relative !important;
          transition: all 0.1s !important;
        }
        
        /* 헤더 내 버튼 상하 중앙 정렬 */
        .MuiTableHead-root button svg {
          pointer-events: none !important;
          height: 1rem !important; /* size-4 */
          width: 1rem !important; /* size-4 */
          flex-shrink: 0 !important;
        }
        
        /* 버튼 호버 상태 */
        .MuiTableHead-root button:hover {
          background-color: var(--accent, #f4f4f4) !important;
          color: var(--accent-foreground, #333) !important;
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
          height: 100% !important; /* 헤더 높이에 맞춰 100% */
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
          height: '100%' !important;
          padding: 0 !important;
        }
        
        /* 체크박스 셀 내부 모든 요소 중앙 정렬 */
        .mrt-row-select-cell *, 
        .mrt-row-select-head-cell * {
          display: flex !important;
          justify-content: center !important;
          align-items: center !important;
        }
        
        /* 테이블 본문 셀의 우측 테두리 강화 */
        .MuiTableBody-root .MuiTableCell-root {
          borderRight: '1px solid #e2e8f0' !important;
        }
        
        /* 마지막 칼럼은 오른쪽 테두리 제외 */
        .MuiTableBody-root .MuiTableCell-root:last-child {
          borderRight: none !important;
        }
        
        /* 테이블 행 높이 자동 조정 */
        .MuiTableBody-root .MuiTableRow-root {
          height: auto !important;
          min-height: 70px !important; /* 행 높이 증가 */
        }
        
        /* 모바일 환경에서 테이블 행 높이 조정 */
        @media (max-width: 640px) {
          .MuiTableBody-root .MuiTableRow-root {
            min-height: 60px !important;
          }
        }
        
        /* Document 칼럼 셀 스타일 */
        .doc-filename-cell {
          overflow: hidden;
          width: 100%;
        }
        
        /* 파일명 컨테이너 스타일 */
        .doc-filename-container {
          padding: 4px 0;
          width: 100%;
        }
        
        /* 파일명 텍스트 기본 스타일 */
        .doc-filename-text {
          margin: 0;
          padding: 2px 0;
          font-size: 0.875rem; // 14px로 설정
          font-weight: 500;
          line-height: 1.2;
          width: 100%;
          text-align: left;
        }
        
        /* 짧은 파일명 (한 줄) 스타일 */
        .doc-filename-short {
          white-space: nowrap;
          overflow: hidden;
          text-overflow: ellipsis;
        }
        
        /* 긴 파일명 (여러 줄) 스타일 */
        .doc-filename-long {
          white-space: normal;
          word-break: break-all;
          word-wrap: break-word;
          overflowWrap: 'break-word',
          hyphens: 'auto',
        },
        
        /* 상태 배지 컨테이너 */
        .doc-status-container {
          margin-top: 4px;
        }
        
        /* 파일명 텍스트 색상 (에러) */
        .doc-filename-error {
          color: #ef4444;
        }
        
        /* 파일명 텍스트 색상 (처리 중) */
        .doc-filename-processing {
          color: #9ca3af;
        }
        
        /* 패딩과 마진 최소화하여 컨텐츠 영역 최대화 */
        .MuiTableBody-root .MuiTableCell-root {
          padding: 0.4rem !important;
        }
        
        /* 모든 셀 내부 요소의 마진 제거 */
        .MuiTableBody-root .MuiTableCell-root > div {
          margin: 0 !important;
          width: 100% !important;
          max-width: 100% !important;
          padding: 0 !important;
          max-height: none !important; /* 셀 내부 div 최대 높이 제한 제거 */
          overflow: visible !important; /* 내용이 보이도록 오버플로우 보이게 설정 */
        }
        
        /* MUI 테이블 셀 컨텐츠 최대화 */
        .MuiTableCell-body {
          padding: 3px !important;
        }
        
        /* 셀 내부의 p 태그 패딩 제거 및 높이 제한 */
        .MuiTableBody-root .MuiTableCell-root p {
          margin: 0 !important;
          padding: 0 !important;
          line-height: 1.2 !important;
          max-height: none !important; /* 셀 내부 p 태그 최대 높이 제한 제거 */
          overflow: visible !important; /* 내용이 보이도록 오버플로우 보이게 설정 */
        }
        
        /* 파일명 텍스트 패딩 축소 */
        .doc-filename-text {
          padding: 0 !important;
          margin: 0 !important;
        }
        
        /* 파일명 컨테이너 패딩 축소 */
        .doc-filename-container {
          padding: 0 !important;
        }
        
        /* 상태 배지 컨테이너 마진 축소 */
        .doc-status-container {
          margin-top: 2px !important;
        }
        
        /* MarkdownCell 내 컨텐츠 패딩 축소 */
        .MuiTableBody-root .prose {
          margin: 0 !important;
          padding: 0 !important;
          max-height: none !important; /* prose 컨텐츠 최대 높이 제한 제거 */
          overflow: visible !important; /* 내용이 보이도록 오버플로우 보이게 설정 */
        }
        
        /* prose 내부 요소들의 마진 축소 */
        .MuiTableBody-root .prose > * {
          margin-top: 1px !important;
          margin-bottom: 1px !important;
        }
        
        /* 마크다운 스타일 복원 */
        .MuiTableBody-root .prose,
        body > div > div > div .prose {
          max-width: none !important;
          font-size: 0.875rem !important;
        }
        
        /* 제목 스타일 */
        .MuiTableBody-root .prose h1,
        body > div > div > div .prose h1 { 
          font-size: 0.9rem !important; 
          font-weight: bold !important; 
          margin-bottom: 0.25rem !important;
          margin-top: 0.5rem !important;
          color: #333 !important;
        }
        
        .MuiTableBody-root .prose h2,
        body > div > div > div .prose h2 { 
          font-size: 0.85rem !important; 
          font-weight: bold !important; 
          margin-bottom: 0.25rem !important;
          margin-top: 0.5rem !important;
          color: #444 !important;
        }
        
        .MuiTableBody-root .prose h3,
        body > div > div > div .prose h3 { 
          font-size: 0.8rem !important; 
          font-weight: bold !important; 
          margin-bottom: 0.25rem !important;
          margin-top: 0.25rem !important;
          color: #555 !important;
        }
        
        /* 단락 스타일 */
        .MuiTableBody-root .prose p,
        body > div > div > div .prose p { 
          margin-bottom: 0.25rem !important; 
          font-size: 0.875rem !important; 
          line-height: 1.2 !important;
          color: #333 !important;
        }
        
        /* 강조 스타일 */
        .MuiTableBody-root .prose strong,
        body > div > div > div .prose strong { 
          font-weight: bold !important;
        }
        
        /* 이탤릭 스타일 */
        .MuiTableBody-root .prose em,
        body > div > div > div .prose em { 
          color: rgb(75 85 99) !important; 
          font-style: italic !important;
        }
        
        /* 코드 스타일 */
        .MuiTableBody-root .prose code,
        body > div > div > div .prose code { 
          background-color: rgb(243 244 246) !important; 
          padding: 0.15rem !important; 
          border-radius: 0.25rem !important; 
          color: rgb(220 38 38) !important; 
          font-size: 0.875rem !important;
        }
        
        /* 리스트 스타일 */
        .MuiTableBody-root .prose ul,
        body > div > div > div .prose ul { 
          list-style-type: disc !important; 
          padding-left: 1rem !important; 
          margin-bottom: 0.25rem !important;
        }
        
        .MuiTableBody-root .prose ol,
        body > div > div > div .prose ol { 
          list-style-type: decimal !important; 
          padding-left: 1rem !important; 
          margin-bottom: 0.25rem !important;
        }
        
        .MuiTableBody-root .prose li,
        body > div > div > div .prose li { 
          margin-bottom: 0.15rem !important; 
          font-size: 0.875rem !important; 
          line-height: 1.2 !important;
          color: #333 !important;
        }
        
        /* 테이블 스타일 */
        .MuiTableBody-root .prose table,
        body > div > div > div .prose table { 
          width: 100% !important; 
          border-collapse: collapse !important; 
          margin-bottom: 0.25rem !important; 
          font-size: 0.875rem !important;
        }
        
        .MuiTableBody-root .prose th,
        body > div > div > div .prose th { 
          border-width: px !important; 
          border-color: rgb(209 213 219) !important; 
          padding: 0.25rem 0.5rem !important; 
          background-color: rgb(249 250 251) !important; 
          font-weight: 600 !important; 
          font-size: 0.875rem !important;
          color: #333 !important;
        }
        
        .MuiTableBody-root .prose td,
        body > div > div > div .prose td { 
          border-width: 1px !important; 
          border-color: rgb(209 213 219) !important; 
          padding: 0.25rem 0.5rem !important; 
          font-size: 0.875rem !important;
          color: #333 !important;
        }
        
        /* 모바일 환경에서 마크다운 스타일 조정 */
        @media (max-width: 640px) {
          .MuiTableBody-root .prose h1,
          body > div > div > div .prose h1 { 
            font-size: 0.85rem !important;
          }
          
          .MuiTableBody-root .prose h2,
          body > div > div > div .prose h2 { 
            font-size: 0.8rem !important;
          }
          
          .MuiTableBody-root .prose h3,
          body > div > div > div .prose h3 { 
            font-size: 0.75rem !important;
          }
          
          .MuiTableBody-root .prose p,
          .MuiTableBody-root .prose li,
          body > div > div > div .prose p,
          body > div > div > div .prose li { 
            font-size: 0.8rem !important;
          }
          
          .MuiTableBody-root .prose code,
          body > div > div > div .prose code { 
            font-size: 0.8rem !important;
          }
          
          .MuiTableBody-root .prose th,
          .MuiTableBody-root .prose td,
          body > div > div > div .prose th,
          body > div > div > div .prose td { 
            font-size: 0.8rem !important;
            padding: 0.15rem 0.3rem !important;
          }
        }
        
        /* 칼럼 리사이징 관련 커서 스타일 제거 */
        .mrt-header-cell-resizer {
          display: none !important;
          cursor: default !important;
          width: 0 !important;
          pointer-events: none !important;
        }
        
        /* 칼럼 리사이저 관련 모든 요소 숨김 */
        .mrt-column-resize-handle, 
        .mrt-column-resize-handle-left, 
        .mrt-column-resize-handle-right {
          display: none !important;
          width: 0 !important;
          opacity: 0 !important;
          pointer-events: none !important;
        }
        
        /* 헤더 셀 호버 시 리사이징 관련 시각적 힌트 제거 */
        .MuiTableCell-root:hover .mrt-header-cell-resizer,
        .MuiTableCell-root:hover .mrt-column-resize-handle {
          display: none !important;
          width: 0 !important;
          opacity: 0 !important;
        }
        
        /* 헤더 셀 경계에 마우스를 올렸을 때 커서 스타일 */
        .MuiTableHead-root .MuiTableCell-root {
          cursor: default !important;
        }
        
        /* 칼럼 경계 호버 시 스타일 제거 */
        .MuiTableCell-root:hover {
          cursor: default !important;
        }
        
        /* 모든 정렬 아이콘 숨김 (기본값) */
        .MuiTableHead-root .MuiTableCell-root .mrt-sorting-icons {
          opacity: 0 !important;
          visibility: hidden !important;
          display: none !important;
        }
        
        /* Document 컬럼(filename)에만 정렬 아이콘 표시 */
        .MuiTableHead-root .MuiTableCell-root[data-column-id="filename"] .mrt-sorting-icons {
          opacity: 1 !important;
          visibility: visible !important;
          display: flex !important;
          margin-left: 4px !important;
        }
        
        /* 정렬 아이콘 크기 조정 */
        .MuiTableHead-root .MuiTableCell-root[data-column-id="filename"] .mrt-sorting-icons svg {
          width: 14px !important;
          height: 14px !important;
        }
        
        /* 정렬 버튼 스타일 개선 */
        .MuiTableHead-root .MuiTableCell-root[data-column-id="filename"] .mrt-sorting-icon {
          color: #666 !important;
        }
        
        /* 활성화된 정렬 아이콘 강조 */
        .MuiTableHead-root .MuiTableCell-root[data-column-id="filename"] .mrt-sorting-icon-active {
          color: #1976d2 !important;
        }
        
        /* 모바일 환경에서 정렬 아이콘 조정 */
        @media (max-width: 640px) {
          .MuiTableHead-root .MuiTableCell-root[data-column-id="filename"] .mrt-sorting-icons svg {
            width: 12px !important;
            height: 12px !important;
          }
        }
        
        /* Document 컬럼 헤더 스타일 (정렬 가능 표시) */
        .MuiTableHead-root .MuiTableCell-root[data-column-id="filename"] {
          cursor: pointer !important; /* 정렬 가능함을 표시하는 커서 */
          color: #1e293b !important; /* 색상 강조 */
          font-weight: 600 !important; /* 굵기 강조 */
        }
        
        /* Document 컬럼 헤더 호버 효과 */
        .MuiTableHead-root .MuiTableCell-root[data-column-id="filename"]:hover {
          background-color: 'rgba(0, 0, 0, 0.04) !important';
        }
        
        /* Document 컬럼 헤더와 정렬 아이콘 배치 */
        .MuiTableHead-root .MuiTableCell-root[data-column-id="filename"] .mrt-header-content {
          display: flex !important;
          align-items: center !important;
          justify-content: flex-start !important;
        }
        
        /* Document 컬럼(filename)에만 정렬 아이콘 표시 */
        .MuiTableHead-root .MuiTableCell-root[data-column-id="filename"] .mrt-sorting-icons {
          opacity: 1 !important;
          visibility: visible !important;
          display: flex !important;
          margin-left: 4px !important;
          align-items: center !important;
        }
        
        /* 정렬되지 않은 다른 컬럼 헤더 */
        .MuiTableHead-root .MuiTableCell-root:not([data-column-id="filename"]) {
          cursor: default !important; /* 정렬 불가능 표시 */
        }
        
        /* 테이블 헤더 폰트를 기본 앱 폰트로 상속 */
        .MuiTableHead-root .MuiTableCell-root {
          font-family: inherit !important;
        }
        
        /* 모바일 및 데스크탑에서의 테이블 스크롤 동작 개선 */
        @media (max-width: 767px) {
          .MuiPaper-root {
            height: 100% !important;
            flex: 1 !important;
          }
          .MuiTableContainer-root {
            overflow-y: visible !important; /* 내부 스크롤 제거 */
            max-height: none !important; /* 높이 제한 제거 */
            -webkit-overflow-scrolling: touch !important; /* iOS 스크롤 성능 향상 */
          }
          
          /* 모바일에서 스크롤바 터치 영역 확대 */
          .MuiTableContainer-root::-webkit-scrollbar {
            width: 4px !important;
            height: 4px !important;
          }
        }
        
        /* 데스크탑 환경에서 테이블 스크롤 동작 최적화 */
        @media (min-width: 768px) {
          /* 테이블 컨테이너가 가변적으로 화면에 맞게 확장되도록 설정 */
          .MuiPaper-root {
            height: 100% !important; /* 테이블 컨테이너 높이를 부모 요소에 맞게 설정 */
            display: flex !important;
            flex-direction: column !important;
            overflow: hidden !important;
            flex: 1 !important; /* 부모 요소의 공간을 모두 차지하도록 설정 */
          }
          
          /* 테이블 헤더 영역 고정 */
          .MuiTableHead-root {
            position: sticky !important;
            top: 0 !important;
            z-index: 2 !important;
            background-color: white !important;
          }
          
          /* 테이블 본문 영역 스크롤 최적화 */
          .MuiTableContainer-root {
            flex: 1 !important;
            overflow: auto !important;
            /* 스크롤이 필요할 때만 스크롤바 표시 */
            overflow-y: auto !important;
            height: auto !important; /* 고정 높이 제거 */
            max-height: calc(100vh - 200px) !important; /* 화면 크기에 따라 가변적인 최대 높이 설정 */
          }
          
          /* 테이블 자체가 컨테이너를 채우도록 설정 */
          .MuiTable-root {
            height: auto !important; /* 테이블 높이 자동 설정 */
            min-height: auto !important; /* 최소 높이 제한 제거 */
            table-layout: fixed !important; /* 테이블 레이아웃 고정 */
          }
        }
      `}</style>
      <MaterialReactTable table={table} />
    </div>
  );
});

DocumentTable.displayName = "DocEasyTable";

export default DocumentTable;
