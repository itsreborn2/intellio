'use client';
import { Suspense } from 'react';
import { useMemo, useState, forwardRef, useImperativeHandle } from 'react';
import {
  MaterialReactTable,
  useMaterialReactTable,
  type MRT_ColumnDef,
} from 'material-react-table';
import { Button } from "intellio-common/components/ui/button"

export type Person = {
  idx3123:number;
  firstName: string;
  lastName: string;
  email: string;
  city: string;
  state: string;
  age: number; 
  [key: string]: any;  // 동적필드
};

// 테이블 조작을 위한 유틸리티 함수들
export interface ITableUtils {
  addRow: () => void;
  addColumn: () => void;
  removeRow: (email: string) => void;
  removeColumn: (columnId: string) => void;
  getTableData: () => Person[];
  getColumnCount: () => number;
}

// 테이블 컴포넌트를 별도로 분리
const TableComponent = forwardRef<ITableUtils>((props, ref) => {
  const [initAllData, doInitAllData] = useState(false);
  const [countCol, setCountCol] = useState(0);
  const [countRow, setCountRow] = useState(0);
  //const [data, setData] = useState<Person[]>([]);  

  // 동적 데이터 생성
  const tableData = useMemo(() => {
    if(initAllData) {
      //setData([]); 
      return [];
    }
    
    // 기본 데이터
    const baseData: Person[] = [
      {
        idx3123:1,
        firstName: 'dylan',
        lastName: 'Murray',
        email: 'dmurray@example.com',
        city: 'East Daphne',
        state: 'Kentucky',
        age: 25
      },
      {
        idx3123:2,
        firstName: 'Raquel',
        lastName: 'Kohler',
        email: 'rkohler@example.com',
        city: 'Columbus',
        state: 'Ohio',
        age: 24
      },
      {
        idx3123:3,
        firstName: 'Ervin',
        lastName: 'Reinger',
        email: 'ereinger@mailinator.com',
        city: 'South Linda',
        state: 'West Virginia',
        age: 35
      },
      {
        idx3123:4,
        firstName: 'Brittany',
        lastName: 'McCullough',
        email: 'bmccullough@example.com',
        city: 'Lincoln',
        state: 'Nebraska',
        age: 29
      },
      {
        idx3123:5,
        firstName: 'Branson',
        lastName: 'Frami',
        email: 'bframi@example.com',
        city: 'Charleston',
        state: 'South Carolina',
        age: 32
      },
    ];


    // countRow만큼 추가 데이터 생성
    const additionalData = Array.from({ length: countRow }).map((_, index) => ({
      idx3123:index+5,
      firstName: `User${index}`,
      lastName: `LastName${index}`,
      email: `user${index}@example.com`,
      city: `City${index}`,
      state: `State${index}`,
      age: Math.floor(Math.random() * 40) + 20, // 20-60세 사이 랜덤 나이
      // 동적 필드들 추가
      ...Object.fromEntries(
        Array.from({ length: countCol }).map((_, colIndex) => [
          `DynamicHeader_${colIndex}`,
          (index + 1) * (Math.floor(Math.random() * 5) + 1)
        ])
      )
    }));

    const result = [...baseData, ...additionalData];
    //setData(result); 
    return result;
  }, [countRow, countCol, initAllData]);

  const columns = useMemo<MRT_ColumnDef<Person>[]>(() => {
    const baseColumns: MRT_ColumnDef<Person>[] = [
      
      {
        accessorKey: 'firstName',
        header: 'First Name',
      },
      {
        accessorKey: 'lastName',
        header: 'Last Name',
        
      },
      {
        accessorKey: 'email',
        header: 'Email',
      },
      // {
      //   accessorKey: 'city',
      //   header: 'City',
      // },
    ];


    
    // count만큼 동적 컬럼 추가
    Array.from({ length: countCol }).forEach((_, index) => {
      baseColumns.push({
        accessorKey: `DynamicHeader_${index}`,
        header: `dynamicHeader_${index}`,
        Cell: ({ cell }) => (index + 1) * (Math.floor(Math.random() * 5) + 1)
      });
    });

    return baseColumns;
  },
  [initAllData, countCol]
  );


  

  const table = useMaterialReactTable({
    columns,
    data: tableData,
    enablePagination: false,
    enableRowPinning: true,
    enableRowNumbers: true,
    enableRowSelection: true,
    enableStickyHeader: true,
    rowPinningDisplayMode: 'select-sticky',
    getRowId: (row: Person) => row.email,
    // state: {
    //   isLoading: data.length === 0 && initAllData, 
    // },
    displayColumnDefOptions: {
      'mrt-row-numbers': {
        size: 20, 
        grow: false, 
      },
    },
    muiTableProps: {
      sx: {
        border: '1px solid rgba(0, 0, 255, .5)',
        height: '100%', 
        overflow: 'auto', 
        caption: {
          captionSide: 'top',
        },
        '& .MuiTable-root': {
        borderCollapse: 'separate',
        borderSpacing: 0,
      },
      },
      
    },
    muiTableContainerProps: {
      sx: { 
         maxHeight: 'calc(100vh - 120px)', 
       height: '100%', 
         overflow: 'auto', 
      // display: 'flex',
      // flexDirection: 'column',
      // '& .MuiTable-root': {
      //   flex: 1,
      //   minHeight: 0
      // }
      }
    },
    muiTableHeadCellProps: {
      sx: {
        border: '3px solid rgba(255, 81, 81, .5)',
        fontStyle: 'italic',
        fontWeight: 'normal',
      },
    },
    muiTableBodyCellProps: {
      sx: {
        border: '1px solid rgba(81, 81, 81, .5)',
      },
    },
    initialState: {
      rowPinning: {
        top: [],
      },
      
    },
    
    layoutMode: 'grid',
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
  const tableUtils: ITableUtils = {
    addRow: () => setCountRow(prev => prev + 1),
    addColumn: () => setCountCol(prev => prev + 1),
    removeRow: (email) => {
      //const newData = tableData.filter(row => row.email !== email);
      setCountRow(prev => Math.max(0, prev - 1));
    },
    removeColumn: (columnId) => {
      setCountCol(prev => Math.max(0, prev - 1));
    },
    getTableData: () => tableData,
    getColumnCount: () => countCol
  };

  // ref로 테이블 유틸리티 함수들 노출
  useImperativeHandle(ref, () => tableUtils);

  return (
    <div className="space-y-4">
      <Button 
        onClick={() => doInitAllData(!initAllData)}
        className="mb-4 mr-2"
      >
        테이블 초기화
      </Button>
      <Button
        onClick={tableUtils.addColumn}
        className="mb-4 mr-2"
      >
        컬럼 추가 ({countCol})
      </Button>
      <Button
        onClick={tableUtils.addRow}
        className="mb-4"
      >
        로우 추가 ({countRow})
      </Button>
      <MaterialReactTable table={table} />
    </div>
  );
});

// Page 컴포넌트
export default function TestPage() {
  return (
    <Suspense fallback={<div>Loading...</div>}>
      <TableComponent />
    </Suspense>
  );
}