'use client';
import { useMemo, useState, forwardRef, useEffect, useImperativeHandle } from 'react';
import {
  MaterialReactTable,
  useMaterialReactTable,
  type MRT_ColumnDef,
} from 'material-react-table';
import { useApp } from "@/contexts/AppContext"
import { Button } from "@/components/ui/button";
import { IDocument,  IDocumentStatus } from '@/types';  
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';

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
  [&>h1]:mt-4 [&>h1]:mb-2 [&>h1]:text-lg [&>h1]:font-bold
  [&>h2]:mt-3 [&>h2]:mb-2 [&>h2]:text-base [&>h2]:font-semibold
  [&>h3]:mt-1 [&>h3]:mb-1.5 [&>h3]:text-base [&>h3]:font-normal
  [&>p]:my-0.5 [&>p]:leading-6 [&>p]:whitespace-pre-line
  [&>ul]:my-1 [&>ul>li]:mt-2
  [&>ol]:my-1 [&>ol>li]:mt-2
  [&>table]:w-full [&>table]:my-4 [&>table]:border-collapse
  [&>table>thead>tr>th]:border [&>table>thead>tr>th]:border-gray-300 [&>table>thead>tr>th]:p-2 [&>table>thead>tr>th]:bg-gray-100 [&>table>thead>tr>th]:text-left
  [&>table>tbody>tr>td]:border [&>table>tbody>tr>td]:border-gray-300 [&>table>tbody>tr>td]:p-2
  [&>table>tbody>tr:nth-child(even)]:bg-gray-50`;

// 마크다운 셀 컴포넌트
function MarkdownCell({ content }: { content: string }) {
  const [isExpanded, setIsExpanded] = useState(false);
  
  return (
    <div 
      className="py-1 px-2 transition-all duration-200 cursor-pointer"
      onDoubleClick={() => setIsExpanded(!isExpanded)}
    >
      <div 
        className={`${
          !isExpanded 
            ? "overflow-hidden text-ellipsis max-h-[3.0em] relative after:content-[''] after:absolute after:bottom-0 after:right-0 after:left-0 after:h-6 after:bg-gradient-to-t after:from-white" 
            : ""
        }`}
      >
        <ReactMarkdown 
          remarkPlugins={[remarkGfm]}
          className={`${markdownClassName} leading-6`}
        >
          {content}
        </ReactMarkdown>
      </div>
    </div>
  );
}

const DocumentTable = forwardRef<ITableUtils>((props, ref) => {
  const { state, dispatch } = useApp()
  const [showAgeColumn, setShowAgeColumn] = useState(true);
  const [countCol, setCountCol] = useState(0);
  const [countRow, setCountRow] = useState(0);
  // 굳이 제어할 필요가 있나?
  // state로 알아서 업데이트하면 되잖아..??
  
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
        accessorKey: 'filename',
        header: 'Document',
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
        console.log(`[DocumentTable] ${doc.filename} : `);
        console.log(`[DocumentTable] col`, cell);
        if (!baseColumns.some(col => col.accessorKey === cell.header)) {
          console.log(`[DocumentTable] col 변경 : ` , cell)
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

    // Document 컬럼의 크기를 조절 (추가된 컬럼이 있을 때만)
    if (addedColumnsCount > 0) {
      baseColumns[0] = {
        ...baseColumns[0],
        size: 200,  // Document 컬럼 너비 500px로 고정
        grow: false // 남은 공간을 차지하지 않도록 설정
      };

      // Document 컬럼 이후의 컬럼들에 대해 균등한 너비 설정
      for (let i = 1; i < baseColumns.length; i++) {
        baseColumns[i] = {
          ...baseColumns[i],
          size: undefined, // 자동으로 크기 조절되도록
          grow: true      // 남은 공간을 균등하게 차지
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
    enableColumnOrdering: false, // 컬럼 순서 변경 비활성화
    enableGlobalFilter: false, // 전역 검색 비활성화
    enableColumnFilters: false, // 컬럼 필터 비활성화
    enableFilters: false, // 필터 비활성화
    enableColumnActions: false, // 컬럼 액션 버튼 비활성화
    enableHiding: false, // 컬럼 숨기기 비활성화
    enableDensityToggle: false, // 밀도 토글 비활성화
    enableFullScreenToggle: false, // 전체화면 토글 비활성화
    enableTopToolbar: false, // 상단 툴바 비활성화
    enablePagination: false, // 페이지네이션 비활성화
    enableBottomToolbar: false, // 하단 툴바 비활성화
    positionToolbarAlertBanner: 'none', // 알림 배너 비활성화
    getRowId: (doc) => doc.id,
    displayColumnDefOptions: {
      'mrt-row-select': {
        size: 10, // 체크박스 컬럼 너비
        grow: false // 남은 공간을 채우지 않도록 설정
      },
      'mrt-row-numbers': {
        size: 10, // row number를 출력하는 칼럼만 너비10. 고정
        grow: false // 남은 공간을 채우지 않도록 설정
      },
    },
    muiTableProps: {
      sx: {
        caption: {
          backgroundColor: '#ffffff',
        },
        // 테이블 스타일링
        '& .MuiTableBody-root': {
          backgroundColor: '#ffffff',
          boxShadow: '0 1px 3px 0 rgb(0 0 0 / 0.1), 0 1px 2px -1px rgb(0 0 0 / 0.1)'
        },
      },
    },
    muiTableHeadProps: {
      sx: {
        '& tr': {
          height: '48px' // 헤더 높이 고정
        }
      }
    },
    muiTableBodyProps: {
      sx: {
        '& tr': {
          // 추가 컬럼이 없을 때만 고정 높이 적용
          height: columns.length === 1 ? '48px' : 'auto'
        }
      }
    },
    muiTablePaperProps: {
      sx: {
        padding: 0,
        margin: 0,
        backgroundColor: 'transparent',
        boxShadow: 'none',
        '& .MuiTableContainer-root': {
          padding: 0
        }
      }
    },
    muiTableContainerProps: {
      sx: { 
        height: '100%',
        maxHeight: '100%',
        overflow: 'auto',
        padding: 0,
        '& .MuiTable-root': {
          margin: 0
        },
        '&::-webkit-scrollbar': {
          width: '8px',
          height: '8px'
        },
        '&::-webkit-scrollbar-track': {
          backgroundColor: '#f1f1f1'
        },
        '&::-webkit-scrollbar-thumb': {
          backgroundColor: '#888',
          borderRadius: '4px',
          '&:hover': {
            backgroundColor: '#555'
          }
        }
      }
    },
    muiTableHeadCellProps: {
      sx: {
        backgroundColor: '#f8fafc',
        color: '#1e293b',
        fontWeight: '600',
        fontSize: '0.875rem',
        padding: '12px 16px',
        borderBottom: '2px solid #e2e8f0',
        '&:hover': {
          backgroundColor: '#f1f5f9'
        }
      },
    },
    muiTableBodyCellProps: {
      sx: {
        padding: '1rem',
        verticalAlign: 'top',
        '& .prose': {
          maxWidth: 'none',
          '& h1': { fontSize: '1rem', fontWeight: 'bold', marginBottom: '0.5rem' },
          '& h2': { fontSize: '1rem', fontWeight: 'bold', marginBottom: '0.5rem' },
          '& h3': { fontSize: '1rem', fontWeight: 'bold', marginBottom: '0.5rem' },
          '& p': { marginBottom: '0.5rem' },
          '& strong': { color: 'rgb(29 78 216)', fontWeight: 'bold' },
          '& em': { color: 'rgb(75 85 99)', fontStyle: 'italic' },
          '& code': { backgroundColor: 'rgb(243 244 246)', padding: '0.25rem', borderRadius: '0.25rem', color: 'rgb(220 38 38)' },
          '& ul': { listStyleType: 'disc', paddingLeft: '1.25rem', marginBottom: '0.5rem' },
          '& ol': { listStyleType: 'decimal', paddingLeft: '1.25rem', marginBottom: '0.5rem' },
          '& li': { marginBottom: '0.25rem' },
          '& table': { width: '100%', borderCollapse: 'collapse', marginBottom: '0.5rem' },
          '& th': { borderWidth: '1px', borderColor: 'rgb(209 213 219)', padding: '0.5rem 1rem', backgroundColor: 'rgb(249 250 251)', fontWeight: '600' },
          '& td': { borderWidth: '1px', borderColor: 'rgb(209 213 219)', padding: '0.5rem 1rem' }
        },
        '&:hover': {
          backgroundColor: '#f8fafc',
          cursor: 'pointer',
        },
      }
    },
    muiTableBodyRowProps: {
      hover: false,
      sx: {
        '&:hover': {
          backgroundColor: 'transparent',
        },
      },
    },
    layoutMode: 'grid', //모든 칼럼은 남은 공간을 채우는 형태
  });

  // 테이블 유틸리티 함수들
  // const tableUtils: ITableUtils = {
  //   addRow: () => setCountRow(prev => prev + 1),
  //   addColumn: () => setCountCol(prev => prev + 1),
  //   removeRow: (docid) => {
  //     const newData = tableData.filter(doc => doc.id !== docid);
  //     setCountRow(prev => Math.max(0, prev - 1));
  //   },
  //   removeColumn: (columnId) => {
  //     setCountCol(prev => Math.max(0, prev - 1));
  //   },
  //   // getTableData: () => tableData,
  //   // getColumnCount: () => countCol
  // };

  // ref로 테이블 유틸리티 함수들 노출
  //useImperativeHandle(ref, () => tableUtils);

  return (
    <div className="space-y-0 mt-0 rounded-lg bg-white">
      <MaterialReactTable table={table} />
    </div>
  );
});

DocumentTable.displayName = "ExampleTable";

export default DocumentTable;
