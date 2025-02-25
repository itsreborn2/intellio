"use client"

import React, { useRef, useState, useEffect } from "react"
import { Button } from "intellio-common/components/ui/button"

import { 

  Plus, 

} from "lucide-react"
import { useApp } from "@/contexts/AppContext"
import { useAuth } from "@/hooks/useAuth"

import {
  HoverCard,
  HoverCardContent,
  HoverCardTrigger,
} from "intellio-common/components/ui/hover-card"

import * as actionTypes from '@/types/actions'
import DocumentTable, { ITableUtils } from "./DocumentTable"
import ReactMarkdown from 'react-markdown'
import { useFileUpload } from "@/hooks/useFileUpload"
import { UploadProgressDialog } from "intellio-common/components/ui/upload-progress-dialog"

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
        return sentence;
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
      currentSection.push(sentence);
    }
  }
  
  if (currentSection.length > 0) {
    sections.push(currentSection.join('\n'));
  }

  // 최종 포맷팅 - 이중 줄바꿈을 단일 줄바꿈으로 변경
  let formattedContent = sections
    .map(section => section.trim())
    .filter(section => section)
    .join('\n');
    
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


export const TableSection = () => {
  const { state, dispatch } = useApp()
  const { isAuthenticated } = useAuth()
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
  const { uploadProgress, handleFileUpload } = useFileUpload()

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

  const handleAddDocuments = async (event: React.ChangeEvent<HTMLInputElement>) => {
    const files = event.target.files
    if (!files) return

    try {
      let projectId = state.currentProjectId

      if (!projectId) {
        console.error('No project ID available')
        return
      }

      // 채팅 메시지는 직접 추가하고, useFileUpload에서는 메시지 추가를 건너뜁니다
      dispatch({
        type: actionTypes.ADD_CHAT_MESSAGE,
        payload: {
          role: 'assistant',
          content: `문서 업로드를 시작합니다. 총 ${files.length}개의 파일이 업로드됩니다.`
        }
      });

      await handleFileUpload(Array.from(files), projectId)

      // dispatch({
      //   type: actionTypes.ADD_CHAT_MESSAGE,
      //   payload: {
      //     role: 'assistant',
      //     content: '문서 업로드가 완료되었습니다.'
      //   }
      // });

    } catch (error) {
      console.error('File upload failed:', error)
      dispatch({
        type: actionTypes.ADD_CHAT_MESSAGE,
        payload: {
          role: 'assistant',
          content: `문서 업로드 중 오류가 발생했습니다: ${error instanceof Error ? error.message : '알 수 없는 오류'}`
        }
      });
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
  return (
    <div className="flex-1 flex flex-col h-full overflow-hidden">  
      <UploadProgressDialog {...uploadProgress} />
      <div className="sticky top-0 z-10 bg-background border-b">
        <div className="flex items-center justify-between p-2 gap-2">
          {isAuthenticated && (
            <Button
              variant="outline"
              size="sm"
              className="h-8 px-2 text-xs"
              onClick={() => fileInputRef.current?.click()}
            >
              <Plus className="h-3 w-3 mr-0.5" />
              문서 추가
            </Button>
          )}
          <input
            type="file"
            ref={fileInputRef}
            className="hidden"
            multiple
            onChange={handleAddDocuments}
          />
        </div>
      </div>
      <div className="flex-1 overflow-auto">  
        <DocumentTable ref={tableRef} />
      </div>
    </div>
    
  )
}