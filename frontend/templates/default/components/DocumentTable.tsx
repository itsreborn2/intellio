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

// 마크다운 렌더링 스타일 정의
const markdownStyles = {
  h1: 'text-2xl font-bold mb-4 mt-6',
  h2: 'text-xl font-bold mb-3 mt-5',
  h3: 'text-lg font-bold mb-2 mt-4',
  p: 'mb-4',
  strong: 'font-bold text-blue-700',
  em: 'italic text-gray-600',
  code: 'px-1 py-0.5 bg-gray-100 rounded text-red-600',
  ul: 'list-disc pl-5 mb-4',
  ol: 'list-decimal pl-5 mb-4',
  li: 'mb-1',
  table: 'min-w-full border-collapse mb-4',
  th: 'border border-gray-300 px-4 py-2 bg-gray-50 font-semibold',
  td: 'border border-gray-300 px-4 py-2',
}

// Cell 컴포넌트 - 마크다운 렌더링 적용
function Cell({ row }: { row: any }) {
  return (
    <div className="p-2">
      <ReactMarkdown 
        remarkPlugins={[remarkGfm]}
        className="prose dark:prose-invert max-w-none 
          [&>*:first-child]:mt-0 [&>*:last-child]:mb-0
          [&>h1]:mt-4 [&>h1]:mb-2 [&>h1]:text-lg [&>h1]:font-bold
          [&>h2]:mt-3 [&>h2]:mb-2 [&>h2]:text-base [&>h2]:font-semibold
          [&>h3]:mt-2 [&>h3]:mb-1.5 [&>h3]:text-sm [&>h3]:font-semibold
          [&>p]:my-3 [&>p]:leading-7 [&>p]:whitespace-pre-line
          [&>ul]:my-3 [&>ul>li]:mt-2
          [&>ol]:my-3 [&>ol>li]:mt-2
          [&>table]:w-full [&>table]:my-4 [&>table]:border-collapse
          [&>table>thead>tr>th]:border [&>table>thead>tr>th]:border-gray-300 [&>table>thead>tr>th]:p-2 [&>table>thead>tr>th]:bg-gray-100 [&>table>thead>tr>th]:text-left
          [&>table>tbody>tr>td]:border [&>table>tbody>tr>td]:border-gray-300 [&>table>tbody>tr>td]:p-2
          [&>table>tbody>tr:nth-child(even)]:bg-gray-50">
        {row.original.content}
      </ReactMarkdown>
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
          baseColumns.push({
            accessorKey: cell.header,
            header: cell.header,
            Cell: ({ row }) => {
              // 해당 row의 added_col_context에서 matching되는 cell의 value를 찾아 표시
              const matchingCell = row.original.added_col_context?.find(
                c => c.header === cell.header
              );
              return (
                <div className="p-2">
                  <ReactMarkdown 
                    remarkPlugins={[remarkGfm]}
                    className="prose dark:prose-invert max-w-none 
                      [&>*:first-child]:mt-0 [&>*:last-child]:mb-0
                      [&>h1]:mt-4 [&>h1]:mb-2 [&>h1]:text-lg [&>h1]:font-bold
                      [&>h2]:mt-3 [&>h2]:mb-2 [&>h2]:text-base [&>h2]:font-semibold
                      [&>h3]:mt-2 [&>h3]:mb-1.5 [&>h3]:text-sm [&>h3]:font-semibold
                      [&>p]:my-3 [&>p]:leading-7 [&>p]:whitespace-pre-line
                      [&>ul]:my-3 [&>ul>li]:mt-2
                      [&>ol]:my-3 [&>ol>li]:mt-2
                      [&>table]:w-full [&>table]:my-4 [&>table]:border-collapse
                      [&>table>thead>tr>th]:border [&>table>thead>tr>th]:border-gray-300 [&>table>thead>tr>th]:p-2 [&>table>thead>tr>th]:bg-gray-100 [&>table>thead>tr>th]:text-left
                      [&>table>tbody>tr>td]:border [&>table>tbody>tr>td]:border-gray-300 [&>table>tbody>tr>td]:p-2
                      [&>table>tbody>tr:nth-child(even)]:bg-gray-50">
                    {matchingCell?.value || ''}
                  </ReactMarkdown>
                </div>
              );
            }
          });
        }
      })
    });
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
        grow: false, // 남은 공간을 채우지 않도록 설정
        muiTableHeadCellProps: {
          sx: { 
            borderRight: 'none',
            backgroundColor: '#f8fafc'
          }
        },
        muiTableBodyCellProps: {
          sx: { 
            borderRight: 'none',
            backgroundColor: '#ffffff'
          }
        }
      },
      'mrt-row-numbers': {
        size: 10, // row number를 출력하는 칼럼만 너비10. 고정
        grow: false, // 남은 공간을 채우지 않도록 설정
        muiTableHeadCellProps: {
          sx: { 
            borderRight: 'none',
            backgroundColor: '#f8fafc'
          }
        },
        muiTableBodyCellProps: {
          sx: { 
            borderRight: 'none',
            backgroundColor: '#ffffff'
          }
        }
      },
    },
    muiTableProps: {
      sx: {
        caption: {
          captionSide: 'top',
        },
        height: '100%', // 상위 컨테이너에 맞춤
        '& .MuiTable-root': {
          borderCollapse: 'separate',
          borderSpacing: 0,
          backgroundColor: '#ffffff',
          boxShadow: '0 1px 3px 0 rgb(0 0 0 / 0.1), 0 1px 2px -1px rgb(0 0 0 / 0.1)'
        },
      },
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
          '& h1': { fontSize: '1.5rem', fontWeight: 'bold', marginBottom: '1rem' },
          '& h2': { fontSize: '1.25rem', fontWeight: 'bold', marginBottom: '0.75rem' },
          '& h3': { fontSize: '1.125rem', fontWeight: 'bold', marginBottom: '0.5rem' },
          '& p': { marginBottom: '1rem' },
          '& strong': { color: 'rgb(29 78 216)', fontWeight: 'bold' },
          '& em': { color: 'rgb(75 85 99)', fontStyle: 'italic' },
          '& code': { backgroundColor: 'rgb(243 244 246)', padding: '0.25rem', borderRadius: '0.25rem', color: 'rgb(220 38 38)' },
          '& ul': { listStyleType: 'disc', paddingLeft: '1.25rem', marginBottom: '1rem' },
          '& ol': { listStyleType: 'decimal', paddingLeft: '1.25rem', marginBottom: '1rem' },
          '& li': { marginBottom: '0.25rem' },
          '& table': { width: '100%', borderCollapse: 'collapse', marginBottom: '1rem' },
          '& th': { borderWidth: '1px', borderColor: 'rgb(209 213 219)', padding: '0.5rem 1rem', backgroundColor: 'rgb(249 250 251)', fontWeight: '600' },
          '& td': { borderWidth: '1px', borderColor: 'rgb(209 213 219)', padding: '0.5rem 1rem' }
        }
      }
    },
    layoutMode: 'grid', //모든 칼럼은 남은 공간을 채우는 형태
    muiTableBodyRowProps: ({ row, table }) => ({
      sx: {
        '&:hover': {
          backgroundColor: '#f1f5f9',
          transition: 'background-color 0.2s ease-in-out'
        },
        height: row.getIsPinned()
          ? `${table.getState().density === 'compact' ? 37 : table.getState().density === 'comfortable' ? 53 : 69}px`
          : undefined,
      },
    }),
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
