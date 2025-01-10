'use client';
import { useMemo, useState, forwardRef, useImperativeHandle } from 'react';
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
      console.log(`[DocumentTable] ${doc.filename} : `);
      doc.added_col_context?.forEach((cell) => {
        // 주석 삭제 절대금지
        // 여기는 헤더값을 비교하고 있으면 안넣는데, 백엔드 응답에 따라 동일한 헤더값이 올수도 있다.
        // 그런 경우 헤더값+숫자의 형태로 또 다른 헤더를 넣어줘야한다.
        // 헤더값을 받는 함수를 따로 만들어서 처리해야할듯.
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
  }, [dispatch, documentColContexts]);

  const table = useMaterialReactTable({
    columns,
    data: tableData,
    enablePagination: false,
    enableRowPinning: true,
    enableRowSelection: true,
    enableRowNumbers: true,
    enableStickyHeader: true,
    rowPinningDisplayMode: 'select-sticky',
    getRowId: (doc) => doc.id,
    muiTableHeadCellProps: {
      sx: {
        '&.MuiTableCell-root:first-of-type': {  // 첫 번째 컬럼(인덱스)에만 적용
          width: '30px',  // 원하는 너비로 조정
          maxWidth: '30px',
          padding: '8px'
        }
      }
    },
    initialState: {
      rowPinning: {
        //top: ['dmurray@example.com'],
      },
      rowSelection: {
        //'dmurray@example.com': true,
      },
    },
    muiTableContainerProps: {
      sx: {
        maxHeight: '400px',
      },
    },
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
    <div className="space-y-4 mt-4 border-t pt-4">
      <div className="flex gap-2">
        
        {/* <Button
          //onClick={tableUtils.addColumn}
          className="mb-4 mr-2"
        >
          컬럼 추가 ({countCol})
        </Button>
        <Button
          //onClick={tableUtils.addRow}
          className="mb-4"
        >
          로우 추가 ({countRow})
        </Button> */}
      </div>
      <MaterialReactTable table={table} />
    </div>
  );
});

DocumentTable.displayName = "ExampleTable";

export default DocumentTable;
