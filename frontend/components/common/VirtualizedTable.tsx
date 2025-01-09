import React, { ReactNode } from "react";
import { getCoreRowModel, useReactTable, ColumnDef } from "@tanstack/react-table";
import { FixedSizeList, ListChildComponentProps } from "react-window";

interface VirtualizedTableProps<T> {
  columns: ColumnDef<T>[];
  data: T[];
}

export const VirtualizedTable = <T,>({ columns, data }: VirtualizedTableProps<T>) => {
  const table = useReactTable({
    data,
    columns,
    getCoreRowModel: getCoreRowModel(),
  });

  const Row = ({ index, style }: ListChildComponentProps) => {
    const row = table.getRowModel().rows[index];
    return (
      <div style={style} className="table-row">
        {row.getVisibleCells().map((cell) => (
          <div className="table-cell">
            {cell.getValue() as ReactNode}
          </div>
        ))}
      </div>
    );
  };

  return (
    <div className="table">
      {/* Header */}
      <div className="table-header">
        {table.getHeaderGroups().map((headerGroup) => (
          <div className="header-row" key={headerGroup.id}>
            {headerGroup.headers.map((column) => (
              <div className="header-cell" key={column.id}>
                
                {typeof column.column.columnDef.header === "function"
                  ? column.column.columnDef.header(column.getContext())
                  : column.column.columnDef.header}
              </div>
            ))}
          </div>
        ))}
      </div>

      {/* Body with Virtualization */}
      <div className="table-body">
        <FixedSizeList
          height={400}
          itemCount={table.getRowModel().rows.length}
          itemSize={50}
          width="100%"
        >
          {Row}
        </FixedSizeList>
      </div>
    </div>
  );
};

export default VirtualizedTable;
