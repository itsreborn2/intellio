"use client"

import React, { useRef, useState, useEffect } from "react"
import { Button } from "@/components/ui/button"
import { Checkbox } from "@/components/ui/checkbox"
import {
  Popover,
  PopoverTrigger,
  PopoverContent,
} from "@/components/ui/popover"
import { 
  FileText, 
  Plus, 
  Send, 
  Trash2, 
  Search,
  PenSquare,
  X,
  Share,
  GripHorizontal
} from "lucide-react"
import { useApp } from "@/contexts/AppContext"
import { createProject, uploadDocument } from "@/services/api"
import { Tooltip, Box } from "@mui/material"
import { cn } from "@/lib/utils"
import {
  HoverCard,
  HoverCardContent,
  HoverCardTrigger,
} from "@/components/ui/hover-card"
import { IDocument,  IMessage, ITemplate, IProjectItem, IDocumentUploadResponse, IDocumentStatus } from '@/types';  
import * as actionTypes from '@/types/actions'
import DocumentTable, { ITableUtils } from "./DocumentTable"

// Shadcn Table Components
const Table = React.forwardRef<
  HTMLTableElement,
  React.HTMLAttributes<HTMLTableElement>
>(({ className, ...props }, ref) => (
  <div className="relative w-full overflow-auto">
    <table
      ref={ref}
      className={cn("w-full caption-bottom text-sm border-collapse", className)}
      {...props}
    />
  </div>
))
Table.displayName = "Table"

const TableHeader = React.forwardRef<
  HTMLTableSectionElement,
  React.HTMLAttributes<HTMLTableSectionElement>
>(({ className, ...props }, ref) => (
  <thead ref={ref} className={cn("[&_tr]:border-b bg-gray-200 border-gray-200", className)} {...props} />
))
TableHeader.displayName = "TableHeader"

const TableBody = React.forwardRef<
  HTMLTableSectionElement,
  React.HTMLAttributes<HTMLTableSectionElement>
>(({ className, ...props }, ref) => (
  <tbody
    ref={ref}
    className={cn("", className)}
    {...props}
  />
))
TableBody.displayName = "TableBody"

const TableRow = React.forwardRef<
  HTMLTableRowElement,
  React.HTMLAttributes<HTMLTableRowElement>
>(({ className, ...props }, ref) => (
  <tr
    ref={ref}
    className={cn(
      "border-b border-gray-200 transition-colors hover:bg-muted/50 data-[state=selected]:bg-muted",
      className
    )}
    {...props}
  />
))
TableRow.displayName = "TableRow"

const TableHead = React.forwardRef<
  HTMLTableCellElement,
  React.ThHTMLAttributes<HTMLTableCellElement>
>(({ className, ...props }, ref) => (
  <th
    ref={ref}
    className={cn(
      "h-10 px-2 text-left align-middle font-medium text-muted-foreground border-r border-gray-200 last:border-r-0 [&:has([role=checkbox])]:px-0 [&:has([role=checkbox])]:text-center [&>[role=checkbox]]:translate-y-[2px] [&>[role=checkbox]]:ml-0.5",
      className
    )}
    {...props}
  />
))
TableHead.displayName = "TableHead"

const TableCell = React.forwardRef<
  HTMLTableCellElement,
  React.TdHTMLAttributes<HTMLTableCellElement>
>(({ className, ...props }, ref) => (
  <td
    ref={ref}
    className={cn(
      "p-2 align-middle border-r border-gray-200 last:border-r-0 [&:has([role=checkbox])]:px-0 [&:has([role=checkbox])]:text-center [&>[role=checkbox]]:translate-y-[2px] [&>[role=checkbox]]:ml-0.5",
      className
    )}
    {...props}
  />
))
TableCell.displayName = "TableCell"

// 테이블 컬럼 인터페이스
interface ITableColumn {
  name: string
  key: string
}

// 테이블 행 인터페이스
interface ITableRow {
  id: string
  [key: string]: string
}

// 테이블 데이터 인터페이스
interface ITableData {
  columns: ITableColumn[]
  rows: ITableRow[]
}

const DocumentTitle = ({ fileName }: { fileName: string }) => (
  <div className="bg-muted/90 w-fit px-2 py-1 rounded">
    <span className="text-sm text-muted-foreground">{fileName}</span>
  </div>
)

const formatContent = (content: string) => {
  if (!content) return "";
  
  // 특수 태그 처리를 위한 임시 저장소
  const tags: {[key: string]: string[]} = {
    mp: [], // 증가/긍정적 금액
    mn: [], // 감소/부정적 금액
    m: [],  // 기본/중립적 금액
    np: [], // 증가/상승 수치
    nn: [], // 감소/하락 수치
    n: []   // 기본/목표 수치
  };
  
  // 특수 태그를 임시 토큰으로 대체
  let processedContent = content;
  Object.keys(tags).forEach((tag, idx) => {
    const regex = new RegExp(`<${tag}>([^<]+)</${tag}>`, 'g');
    processedContent = processedContent.replace(regex, (match, content) => {
      const token = `__${tag}_${idx}_${tags[tag].length}__`;
      tags[tag].push(content);
      return token;
    });
  });

  // 문장 단위로 분리하고 정리
  const sentences = processedContent.split(/(?<=[.!?])\s+/);
  const formattedSentences = sentences
    .map(sentence => sentence.trim())
    .filter(sentence => sentence)
    .map(sentence => {
      // 마크다운 헤더 처리
      if (sentence.startsWith('# ')) {
        return sentence + '\n';
      }
      
      // 불릿 포인트나 넘버링으로 시작하는 문장 처리
      if (sentence.startsWith('•') || sentence.startsWith('-') || /^\d+[\.\)]/.test(sentence)) {
        return sentence + (sentence.match(/[.!?]$/) ? '' : '.');
      }
      
      // 일반 문장 처리
      return sentence + (sentence.match(/[.!?]$/) ? '' : '.');
    });

  // 내용 구조화
  const sections = [];
  let currentSection = [];
  
  for (let i = 0; i < formattedSentences.length; i++) {
    const sentence = formattedSentences[i];
    
    // 새로운 섹션 시작 여부 확인
    const isNewSection = 
      sentence.startsWith('# ') ||
      sentence.startsWith('> ') ||
      sentence.startsWith('※ ') ||
      sentence.includes(':') || 
      sentence.toLowerCase().includes('요구사항') ||
      sentence.toLowerCase().includes('참고') ||
      sentence.toLowerCase().includes('주의') ||
      (currentSection.length > 0 && isSignificantContextChange(sentence, currentSection[currentSection.length - 1]));

    if (isNewSection) {
      if (currentSection.length > 0) {
        sections.push(currentSection.join('\n'));
        currentSection = [];
      }
      currentSection.push(sentence);
    } else {
      // 불릿 포인트나 넘버링이 있는 경우 새 줄에 추가
      if (sentence.startsWith('•') || sentence.startsWith('-') || /^\d+[\.\)]/.test(sentence.trim())) {
        if (currentSection.length > 0 && !currentSection[currentSection.length - 1].endsWith('\n')) {
          currentSection[currentSection.length - 1] += '\n';
        }
      }
      currentSection.push(sentence);
    }
  }
  
  if (currentSection.length > 0) {
    sections.push(currentSection.join('\n'));
  }

  // 최종 포맷팅
  let formattedContent = sections
    .map(section => section.trim())
    .filter(section => section)
    .join('\n\n');
    
  // 특수 태그 복원
  Object.keys(tags).forEach((tag, idx) => {
    tags[tag].forEach((content, contentIdx) => {
      const token = `__${tag}_${idx}_${contentIdx}__`;
      const tagClass = {
        mp: 'text-blue-600 font-bold',  // 증가/긍정적 금액
        mn: 'text-red-600 font-bold',   // 감소/부정적 금액
        m: 'font-bold',                 // 기본/중립적 금액
        np: 'text-blue-600 font-bold',  // 증가/상승 수치
        nn: 'text-red-600 font-bold',   // 감소/하락 수치
        n: 'font-bold'                  // 기본/목표 수치
      }[tag];
      formattedContent = formattedContent.replace(
        token,
        `<span class="${tagClass}">${content}</span>`
      );
    });
  });

  return formattedContent;
};

// 문맥 변화 감지 함수
const isSignificantContextChange = (currentSentence: string, previousSentence: string) => {
  // 주제어 목록
  const keywords = [
    '구현', '개발', '기능', '설계', '요구', '제약',
    '규칙', '조건', '참고', '주의', '중요', '필수',
    '선택', '옵션', '권장', '금지', '허용', '제한'
  ];
  
  // 이전 문장과 현재 문장의 주제어 포함 여부 비교
  const previousKeywords = keywords.filter(keyword => 
    previousSentence.toLowerCase().includes(keyword)
  );
  const currentKeywords = keywords.filter(keyword => 
    currentSentence.toLowerCase().includes(keyword)
  );
  
  // 주제어가 완전히 다르면 문맥 변화로 판단
  return (
    currentKeywords.length > 0 &&
    previousKeywords.length > 0 &&
    !currentKeywords.some(keyword => previousKeywords.includes(keyword))
  );
};

const CellContent = ({ content, isDocument = false }: { content: string, isDocument?: boolean }) => {
  const formattedContent = formatContent(content);
  
  // 컨텐츠 길이에 따른 카드 크기 계산
  const getCardSize = (content: string) => {
    if (!content) return { width: 300, height: 150 };
    
    const lines = content.split('\n').filter(line => line.trim());
    const maxLineLength = Math.max(...lines.map(line => line.length));
    const lineCount = lines.length;
    
    // 기본 사이즈 계산
    let width = Math.min(Math.max(500, maxLineLength * 8), 1000);  // 최소 500px, 최대 1000px
    let height = Math.min(Math.max(200, lineCount * 24 + 40), 800); // 최소 200px, 최대 800px
    
    return { width, height };
  };
  
  const cardSize = getCardSize(formattedContent);
  
  if (isDocument) {
    return <DocumentTitle fileName={formattedContent} />;
  }

  return (
    <HoverCard>
      <HoverCardTrigger asChild>
        <div className="cursor-help">
          <div className="line-clamp-3 text-sm">
            {formattedContent}
          </div>
        </div>
      </HoverCardTrigger>
      <HoverCardContent
        side="right"
        className="w-[var(--card-width)] max-h-[var(--card-height)] overflow-y-auto"
        style={{
          '--card-width': `${cardSize.width}px`,
          '--card-height': `${cardSize.height}px`,
        } as React.CSSProperties}
      >
        <div className="space-y-1">
          {formattedContent.split('\n').map((line, index) => (
            <div 
              key={index} 
              className={`
                ${/^[•\d]/.test(line.trim()) ? 'pl-4 py-1' : 'py-0.5'}
                ${line.includes(':') ? 'font-semibold py-2' : ''}
                whitespace-pre-wrap break-words
              `}
            >
              {line}
            </div>
          ))}
        </div>
      </HoverCardContent>
    </HoverCard>
  );
};

export const TableSection = () => {
  const { state, dispatch } = useApp()
  const [selectedRows, setSelectedRows] = useState<number[]>([])
  const [selectedCells, setSelectedCells] = useState<{ row: number; col: string }[]>([])
  const [selectionMode, setSelectionMode] = useState<'row' | 'cell'>('row')
  const [selectionStart, setSelectionStart] = useState<{ row: number; col: string } | null>(null)
  const [isSelecting, setIsSelecting] = useState(false)
  const [columns, setColumns] = useState(["Document"])
  const [columnOrder, setColumnOrder] = useState<string[]>(["Document"])
  const [columnToDelete, setColumnToDelete] = useState<string | null>(null)
  const [columnWidths, setColumnWidths] = useState<{ [key: string]: number }>({})
  const [draggedColumn, setDraggedColumn] = useState<string | null>(null)
  const fileInputRef = useRef<HTMLInputElement>(null)
  const tableRef = useRef<ITableUtils>(null);

  // 컬럼 상태 동기화
  useEffect(() => {
    if (state.analysis.tableData?.columns) {
      const columnNames = state.analysis.tableData.columns.map(col => col.header.name);
      setColumns(columnNames);
      
      // Document 컬럼을 첫 번째로, 새 컬럼은 Document 다음에, 나머지 컬럼들은 그 뒤에 배치
      const documentIndex = columnNames.indexOf("Document");
      if (documentIndex !== -1) {
        const documentColumn = "Document";
        const existingColumns = columnOrder.filter(name => name !== "Document" && columnNames.includes(name));
        const newColumns = columnNames.filter(name => 
          name !== "Document" && !columnOrder.includes(name)
        );
        
        const reorderedColumns = [
          documentColumn,
          ...newColumns,
          ...existingColumns
        ];
        
        setColumnOrder(reorderedColumns);
      } else {
        setColumnOrder(columnNames);
      }
    }
  }, [state.analysis.tableData]);

  const handleFileUpload = async (event: React.ChangeEvent<HTMLInputElement>) => {
    const files = event.target.files
    if (!files) return

    try {
      let projectId = state.currentProjectId
      if (!projectId) {
        const project = await createProject('Temporary Project', 'Created for document upload')
        projectId = project.id
        dispatch({ type: actionTypes.SET_CURRENT_PROJECT, payload: projectId })
        
        // 프로젝트 생성 이벤트 발생
        window.dispatchEvent(new CustomEvent('projectCreated'))
      }
      
      dispatch({
        type: actionTypes.ADD_CHAT_MESSAGE,
        payload: {
          role: 'assistant',
          content: `문서 업로드를 시작합니다. 총 ${files.length}개의 파일이 업로드됩니다.`
        }
      })

      const response: IDocumentUploadResponse = await uploadDocument(projectId, Array.from(files))
      console.log('Upload response[TableSection]:', response)
      
      
      // 1. 문서 상태 업데이트
      const documents: IDocument[] = response.documents.map(doc => ({
        id: doc.id,
        filename: doc.filename,
        project_id: doc.project_id,
        status: doc.status,
        content_type: doc.content_type
      }));
      console.log('Created document[TableSection], dispatch(\'SET_DOCUMENTS_IN_TABLESECTION\', payload) : ', documents)
    

      dispatch({
        type: actionTypes.ADD_DOCUMENTS,
        payload: documents
      });
      console.log(`2. 테이블 데이터 초기화 - Document 컬럼 추가. 현재프로젝트 : ${state.currentProjectId}`)
      // export interface TableColumn {
      //   header: {
      //     name: string;
      //     prompt: string;
      //   };
      //   cells: {
      //     doc_id: string;
      //     content: string;
      //   }[];
      //   [key: string]: any;
      // }
      
      // export interface TableResponse {
      //   columns: TableColumn[];
      // }
      // 2. 테이블 데이터 초기화 - Document 컬럼 추가
      if (documents.length > 0) {
        // const tableData  = {
        //   columns: [{
        //     header: {
        //       name: 'Document',
        //       prompt: '문서 이름을 표시합니다'
        //     },
        //     cells: documents.map(doc => ({
        //       doc_id: doc.id,
        //       content: doc.filename
        //     }))
        //   }]
        // }
        // console.log(`2-1. tableData : ${tableData}`)
        // dispatch({
        //   type: actionTypes.UPDATE_TABLE_DATA,
        //   payload: tableData
        // })

        console.log('3. 분석 모드를 테이블로 변경')
        // 3. 분석 모드를 테이블로 변경
        dispatch({
          type: actionTypes.SET_VIEW,
          payload: 'table'
        })
      }
      console.log('ADD_MESSAGE')
      // 기존 메시지 dispatch
      dispatch({
        type: actionTypes.ADD_CHAT_MESSAGE,
        payload: {
          role: 'assistant',
          content: `문서 추가 완료`
        }
      })

    } catch (error) {
      console.error('Failed to upload documents:', error)
    }
      
  }

  const toggleRowSelection = (id: number) => {
    setSelectedRows(prev =>
      prev.includes(id) ? prev.filter(rowId => rowId !== id) : [...prev, id]
    )
  }

  const handleDragStart = (e: React.DragEvent<HTMLTableHeaderCellElement>, column: string) => {
    setDraggedColumn(column)
  }

  const handleDragOver = (e: React.DragEvent<HTMLTableHeaderCellElement>, column: string) => {
    e.preventDefault()
  }

  const handleDragEnd = () => {
    setDraggedColumn(null)
  }

  const handleResizeStart = (e: React.MouseEvent<HTMLDivElement>, column: string) => {
    const tableHead = e.currentTarget.parentElement
    if (!tableHead) return;  // 조기 반환으로 null 체크
    
    const table = tableHead.parentElement
    const columnWidth = tableHead.style.width
    const startX = e.clientX
    const startWidth = parseInt(columnWidth)

    const mouseMoveHandler = (e: MouseEvent) => {
      const newWidth = startWidth + (e.clientX - startX)
      tableHead.style.width = `${newWidth}px`
    }

    const mouseUpHandler = () => {
      document.removeEventListener('mousemove', mouseMoveHandler)
      document.removeEventListener('mouseup', mouseUpHandler)
      setColumnWidths(prev => ({ ...prev, [column]: parseInt(tableHead.style.width) }))
    }

    document.addEventListener('mousemove', mouseMoveHandler)
    document.addEventListener('mouseup', mouseUpHandler)
  }

  const handleDeleteColumn = (column: string) => {
    setColumnToDelete(column)
    setColumns(prev => prev.filter(col => col !== column))
    setColumnOrder(prev => prev.filter(col => col !== column))
  }

  const deleteSelectedRows = () => {
    // implement delete logic here
  }

  const handleCellMouseDown = (rowIndex: number, column: string) => {
    if (column === 'Document') return // Document 컬럼은 선택 제외
    
    setSelectionMode('cell')
    setIsSelecting(true)
    setSelectionStart({ row: rowIndex, col: column })
    setSelectedCells([{ row: rowIndex, col: column }])
  }

  const handleCellMouseEnter = (rowIndex: number, column: string) => {
    if (!isSelecting || !selectionStart || column === 'Document') return

    const startRow = Math.min(selectionStart.row, rowIndex)
    const endRow = Math.max(selectionStart.row, rowIndex)
    const startColIndex = columnOrder.indexOf(selectionStart.col)
    const endColIndex = columnOrder.indexOf(column)
    const minColIndex = Math.min(startColIndex, endColIndex)
    const maxColIndex = Math.max(startColIndex, endColIndex)

    const newSelectedCells = []
    for (let row = startRow; row <= endRow; row++) {
      for (let colIndex = minColIndex; colIndex <= maxColIndex; colIndex++) {
        const col = columnOrder[colIndex]
        if (col !== 'Document') {
          newSelectedCells.push({ row, col })
        }
      }
    }
    setSelectedCells(newSelectedCells)
  }

  const handleCellMouseUp = () => {
    setIsSelecting(false)
    setSelectionStart(null)
  }

  useEffect(() => {
    const handleMouseUp = () => {
      setIsSelecting(false)
      setSelectionStart(null)
    }

    window.addEventListener('mouseup', handleMouseUp)
    return () => window.removeEventListener('mouseup', handleMouseUp)
  }, [])

  // 선택된 셀에 대한 컨텍스트 메뉴
  const handleContextMenu = (e: React.MouseEvent) => {
    e.preventDefault()
    if (selectedCells.length > 0) {
      // 여기에 컨텍스트 메뉴 로직 추가
    }
  }

  // useEffect(() => {
  //   const tableHead = document.querySelector('thead');
  //   if (!tableHead) return;  // tableHead가 null이 함수 종료

  //   // 이후 tableHead 사용하는 코드...
  //   tableHead.addEventListener('dragover', handleDragOver);
  //   tableHead.addEventListener('drop', handleDrop);
    
  //   return () => {
  //     if (tableHead) {  // cleanup에서도 null 체크
  //       tableHead.removeEventListener('dragover', handleDragOver);
  //       tableHead.removeEventListener('drop', handleDrop);
  //     }
  //   };
  // }, [handleDragOver, handleDrop]);

  return (
    <div className="flex-1 flex flex-col overflow-hidden">
      <div className="sticky top-0 z-10 bg-background border-b">
        <div className="flex items-center justify-between p-2 gap-2">
          <Button
            variant="outline"
            size="sm"
            className="h-8 px-2 text-xs"
            onClick={() => fileInputRef.current?.click()}
          >
            <Plus className="h-3 w-3 mr-0.5" />
            문서 추가
          </Button>
          <input
            type="file"
            ref={fileInputRef}
            className="hidden"
            multiple
            onChange={handleFileUpload}
          />
        </div>
      </div>

      <div className="flex-1 relative">  {/* overflow-auto 제거 */}
        <DocumentTable ref={tableRef} />
        {/*
        <div className="overflow-x-auto overflow-y-auto max-h-[calc(100vh-200px)] relative">
           예전에 쓰던 테이블.
          <div className="flex flex-col gap-4">
            <Table className="w-full border-collapse table-fixed">
              <colgroup>
                <col className="w-[40px] min-w-[40px] max-w-[40px]" />
                {columnOrder.map((colName) => (
                  <col key={colName} className="w-auto" />
                ))}
              </colgroup>
              <TableHeader>
                <TableRow className="border-b">
                  <TableHead className="w-[40px] min-w-[40px] max-w-[40px] p-2 bg-muted/50">
                    <div className="flex items-center justify-center">
                      {state.analysis.tableData?.columns?.[0]?.cells?.length > 0 && (
                        <Checkbox
                          checked={selectedRows.length > 0}
                          onCheckedChange={(checked) => {
                            if (checked) {
                              const allRows = state.analysis.tableData?.columns?.[0]?.cells?.map((_, index) => index) || [];
                              setSelectedRows(allRows);
                            } else {
                              setSelectedRows([]);
                            }
                          }}
                        />
                      )}
                    </div>
                  </TableHead>
                  {columnOrder.map((colName) => {
                    const column = state.analysis.tableData?.columns?.find(col => col.header.name === colName);
                    if (!column) return null;
                    return (
                      <TableHead
                        key={colName}
                        className={`p-2 bg-muted/50 ${
                          colName === "Document" ? "sticky left-[40px] z-20 bg-muted/50" : ""
                        }`}
                      >
                        {state.analysis.tableData?.columns?.[0]?.cells?.length > 0 && (
                          <div className="flex items-center justify-center text-center">
                            <span className="font-medium">{colName}</span>
                          </div>
                        )}
                      </TableHead>
                    );
                  })}
                </TableRow>
              </TableHeader>
              <TableBody>
                {state.analysis.tableData?.columns?.[0]?.cells?.map((cell, rowIndex) => (
                  <TableRow
                    key={cell.doc_id}
                    className={`group border-b hover:bg-muted/30 ${
                      selectedRows.includes(rowIndex) ? "bg-muted/50" : ""
                    }`}
                  >
                    <TableCell className="w-[40px] min-w-[40px] max-w-[40px] p-2">
                      <div className="flex items-center justify-center">
                        <div className="relative group/row">
                          <span className="text-sm text-muted-foreground group-hover/row:invisible absolute top-1/2 left-1/2 -translate-x-1/2 -translate-y-1/2">
                            {rowIndex + 1}
                          </span>
                          <div className="invisible group-hover/row:visible">
                            <Checkbox
                              checked={selectedRows.includes(rowIndex)}
                              onCheckedChange={(checked) => {
                                if (checked) {
                                  setSelectedRows([...selectedRows, rowIndex]);
                                } else {
                                  setSelectedRows(selectedRows.filter(row => row !== rowIndex));
                                }
                              }}
                            />
                          </div>
                        </div>
                      </div>
                    </TableCell>
                    {columnOrder.map((colName) => {
                      const column = state.analysis.tableData?.columns?.find(col => col.header.name === colName);
                      if (!column) return null;
                      return (
                        <TableCell
                          key={colName}
                          onClick={() => {
                            if (colName !== "Document") {
                              const isSelected = selectedCells.some(
                                (selectedCell) =>
                                  selectedCell.row === rowIndex && selectedCell.col === colName
                              );
                              if (isSelected) {
                                setSelectedCells(selectedCells.filter(
                                  (cell) => !(cell.row === rowIndex && cell.col === colName)
                                ));
                              } else {
                                setSelectedCells([...selectedCells, { row: rowIndex, col: colName }]);
                              }
                            }
                          }}
                          className={`p-2 cursor-pointer ${
                            colName === "Document"
                              ? "sticky left-[40px] z-20 bg-background"
                              : ""
                          } ${
                            selectedCells.some(
                              (selectedCell) =>
                                selectedCell.row === rowIndex && selectedCell.col === colName
                            )
                              ? "bg-muted/80"
                              : ""
                          } ${
                            colName !== "Document" ? "hover:bg-muted/30" : ""
                          }`}
                        >
                          <CellContent 
                            content={column.cells[rowIndex]?.content || ''} 
                            isDocument={colName === "Document"}
                          />
                        </TableCell>
                      );
                    })}
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          </div>
          
         
        </div>
        */}
      </div>

      {selectedRows.length > 0 && (
        <div className="absolute bottom-4 left-1/2 transform -translate-x-1/2 bg-background shadow-lg rounded-lg p-4 flex items-center gap-4">
          <span className="text-sm text-muted-foreground">{selectedRows.length}개의 행이 선택됨</span>
          <Button variant="destructive" size="sm" onClick={deleteSelectedRows}>
            <Trash2 className="h-4 w-4 mr-2" />
            선택 행 삭제
          </Button>
          <Button variant="outline" size="sm" onClick={() => setSelectedRows([])}>
            <X className="h-4 w-4 mr-2" />
            선택 취소
          </Button>
        </div>
      )}
    </div>
  )
}