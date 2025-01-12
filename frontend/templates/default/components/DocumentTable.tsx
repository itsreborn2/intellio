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


// 테이블 조작을 위한 유틸리티 함수들
export interface ITableUtils {
  addRow: () => void;
  addColumn: () => void;
  removeRow: (email: string) => void;
  removeColumn: (columnId: string) => void;
  // getTableData: () => IDocument[];
  // getColumnCount: () => number;
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
        header: 'Title',
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
              return matchingCell?.value || '';
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
    enablePagination: false,
    enableRowPinning: true,
    enableRowSelection: true,
    enableRowNumbers: true,
    enableStickyHeader: true,
    enableFullScreenToggle: false,
    rowPinningDisplayMode: 'select-sticky',
    
    getRowId: (doc) => doc.id,
    displayColumnDefOptions: { // 기본 헤더의 옵션 설정
        'mrt-row-select': {
        size: 10, // 체크박스 컬럼 너비
        grow: false, // 남은 공간을 채우지 않도록 설정
        muiTableHeadCellProps: {
          sx: { borderRight: 'none' }
        },
        muiTableBodyCellProps: {
          sx: { borderRight: 'none' }
        }
      },
      'mrt-row-numbers': {
        size: 10, // row number를 출력하는 칼럼만 너비10. 고정
        grow: false, // 남은 공간을 채우지 않도록 설정
        muiTableHeadCellProps: {
          sx: { borderRight: 'none' }
        },
        muiTableBodyCellProps: {
          sx: { borderRight: 'none' }
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
        },
      },
    },
    muiTablePaperProps: {
      sx: {
        padding: 0,
        margin: 0,
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
        }
      }
    },
    muiTableHeadCellProps: {
      sx: {
        //border: '1px solid rgba(200, 200, 200, 0.4)',
        fontStyle: 'italic',
        fontWeight: 'normal',
        
      },
    },
    muiTableBodyCellProps: {
      sx: {
        //border: '1px solid rgba(180, 180, 180, .5)',
      },
    },

    initialState: {
      rowPinning: {
        //top: ['dmurray@example.com'],
      },
      rowSelection: {
        //'dmurray@example.com': true,
      },
    },
    layoutMode: 'grid', //모든 칼럼은 남은 공간을 채우는 형태
    muiTableBodyRowProps: ({ row, table }) => {
      const { density } = table.getState();
      return {
        sx: {
          height: row.getIsPinned()
            ? `${
                density === 'compact' ? 37 : density === 'comfortable' ? 53 : 69
              }px`
            : undefined,
        },
      };
    },
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
    <div className="space-y-0 mt-4 border-t pt-4">
      <MaterialReactTable table={table} />
    </div>
  );
});

DocumentTable.displayName = "ExampleTable";

export default DocumentTable;
