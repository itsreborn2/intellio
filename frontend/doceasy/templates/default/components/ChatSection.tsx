"use client"

import { useState, useEffect, useRef, useCallback, useMemo } from 'react'
import { Send, Square, Maximize2, Minimize2 } from 'lucide-react'
import { Button } from 'intellio-common/components/ui/button'
import { Input } from 'intellio-common/components/ui/input'
import { useApp } from '@/contexts/AppContext'
import { searchTable, searchTableStream, sendChatMessage, sendChatMessage_streaming, stopChatMessageGeneration, API_ENDPOINT } from '@/services/api'
import { IMessage, IChatResponse, TableResponse } from '@/types/index'
import * as actionTypes from '@/types/actions'
import ReactMarkdown from 'react-markdown'
import remarkGfm from 'remark-gfm'
import remarkBreaks from 'remark-breaks'
import React from 'react'
import { Plus } from 'lucide-react';
import cn from 'classnames';

// 모바일 환경 감지 훅
const useIsMobile = () => {
  const [isMobile, setIsMobile] = useState(false);

  useEffect(() => {
    const checkIsMobile = () => {
      setIsMobile(window.innerWidth < 768); // 768px 미만을 모바일로 간주
    };

    // 초기 체크
    checkIsMobile();

    // 리사이즈 이벤트에 대응
    window.addEventListener('resize', checkIsMobile);
    return () => window.removeEventListener('resize', checkIsMobile);
  }, []);

  return isMobile;
};

// 테이블 분석 진행 상태 컴포넌트
const TableAnalysisProgress = React.memo(function TableAnalysisProgress({
  streamingState
}: {
  streamingState: {
    isStreaming: boolean;
    headerName: string | null;
    processingDocIds: string[];
    completedDocIds: string[];
  }
}) {
  if (!streamingState.isStreaming) return null;

  return (
    <div className="fixed bottom-24 right-8 bg-white dark:bg-gray-900 rounded-xl p-4 z-50 max-w-xs">
      <div className="flex flex-col space-y-3">
        <h4 className="font-semibold text-sm text-gray-800 dark:text-gray-200">
          {streamingState.headerName ? `'${streamingState.headerName}' 분석 중` : '문서 분석 중'}
        </h4>
        
        <div className="space-y-2">
          <div className="flex justify-between text-xs">
            <span className="text-gray-600 dark:text-gray-400">진행 중:</span>
            <span className="font-medium text-gray-800 dark:text-gray-200">{streamingState.processingDocIds.length}</span>
          </div>
          <div className="flex justify-between text-xs">
            <span className="text-gray-600 dark:text-gray-400">완료:</span> 
            <span className="font-medium text-gray-800 dark:text-gray-200">{streamingState.completedDocIds.length}</span>
          </div>
          
          {/* 프로그레스 바 */}
          <div className="w-full bg-gray-200 dark:bg-gray-700 rounded-full h-2 mt-1">
            <div 
              className="bg-blue-500 h-2 rounded-full transition-all duration-300"
              style={{ 
                width: `${streamingState.processingDocIds.length + streamingState.completedDocIds.length === 0 
                  ? 5 // 아직 문서 처리 전에는 5%로 표시
                  : Math.floor((streamingState.completedDocIds.length / 
                     (streamingState.processingDocIds.length + streamingState.completedDocIds.length)) * 100)}%` 
              }}
            ></div>
          </div>
        </div>
      </div>
    </div>
  );
});

class StreamingMarkdownHandler {
  processChunk(data: string, dispatch: any, tempMessageId: string): void {
    if (!data || data === '[DONE]') return;

    // 줄바꿈 문자 처리
    const processedData = data
          .replace(/\r\n/g, '\n')  // CRLF를 LF로 변환
          .replace(/\r/g, '\n')    // CR을 LF로 변환
          .replace(/\\n/g, '\n');  // 이스케이프된 \n을 실제 개행문자로 변환

    //console.log('processedData :', processedData)
    dispatch({
      type: actionTypes.UPDATE_CHAT_MESSAGE,
      payload: {
        id: tempMessageId,
        content: (prevContent: string) => prevContent + processedData
      }
    });
  }

  reset(): void {
    // 필요한 경우 상태 초기화
  }
}

interface ChatSectionProps {
  onUploadButtonClick?: () => void;
  isMobile?: boolean; // isMobile prop 추가
}

export const ChatSection: React.FC<ChatSectionProps> = ({ onUploadButtonClick, isMobile }) => { // isMobile prop 받기
  const { state, dispatch } = useApp()
  const [input, setInput] = useState('')
  const [streamingMessageId, setStreamingMessageId] = useState<string | null>(null)
  const [isGenerating, setIsGenerating] = useState(false)
  const messagesEndRef = useRef<HTMLDivElement>(null)
  const inputRef = useRef<HTMLInputElement>(null)
  const messageCountRef = useRef(0)
  const isMobileValue = useIsMobile();
  
  // 테이블 스트리밍 상태
  const [tableStreamingState, setTableStreamingState] = useState<{
    isStreaming: boolean;
    headerName: string | null;
    processingDocIds: string[];
    completedDocIds: string[];
  }>({
    isStreaming: false,
    headerName: null,
    processingDocIds: [],
    completedDocIds: [],
  });

  // 고유한 메시지 ID 생성 함수
  const generateMessageId = useCallback(() => {
    messageCountRef.current += 1
    return `${Date.now()}-${messageCountRef.current}`
  }, [])

  const handleStopGeneration = useCallback(async () => {
    if (!state.currentProjectId) return
    
    try {
      await stopChatMessageGeneration(state.currentProjectId)
      setIsGenerating(false)
      setStreamingMessageId(null)
    } catch (error) {
      console.error('메시지 생성 중지 중 오류:', error)
    }
  }, [state.currentProjectId])

  const handleSubmit = useCallback(async (e: React.FormEvent) => {
    e.preventDefault()
    if (!input.trim()) return

    const currentInput = input
    setInput('')

    // 분석 시작 상태 설정
    dispatch({ type: actionTypes.SET_IS_ANALYZING, payload: true })
    setIsGenerating(true)

    // 사용자 메시지 추가
    const userMessageId = generateMessageId()
    dispatch({
      type: actionTypes.ADD_CHAT_MESSAGE,
      payload: {
        id: userMessageId,
        role: 'user',
        content: currentInput,
        timestamp: new Date().toISOString()
      }
    })

    if (state.analysis.mode === 'table') {
      if (!state.currentProjectId || !state.analysis.selectedDocumentIds.length) {
        console.warn('프로젝트 ID 또는 선택된 문서가 없습니다', {
          projectId: state.currentProjectId,
          selectedDocumentIds: state.analysis.selectedDocumentIds
        })
        dispatch({ type: actionTypes.SET_IS_ANALYZING, payload: false })
        
        // 오류 메시지 추가
        dispatch({
          type: actionTypes.ADD_CHAT_MESSAGE,
          payload: {
            role: 'assistant',
            content: '분석할 문서가 선택되지 않았습니다. 문서를 선택하신 후 질문해주세요.'
          }
        });
        setIsGenerating(false);
        return
      }

      console.debug('테이블 검색 시작:', {
        mode: state.analysis.mode,
        projectId: state.currentProjectId,
        documentIds: state.analysis.selectedDocumentIds,
        query: currentInput
      })

      try {
        // 스트리밍 상태 초기화
        setTableStreamingState({
          isStreaming: true,
          headerName: null,
          processingDocIds: [],
          completedDocIds: [],
        });

        // 응답 메시지 ID 생성
        const assistantMessageId = generateMessageId();

        // 초기 메시지 추가 - 분석 중 상태
        dispatch({
          type: actionTypes.ADD_CHAT_MESSAGE,
          payload: {
            id: assistantMessageId,
            role: 'assistant',
            content: '테이블 데이터를 분석 중입니다...',
            timestamp: new Date().toISOString()
          }
        });

        // 스트리밍 API 호출
        // console.log('searchTableStream 함수 호출 직전', {
        //   projectId: state.currentProjectId,
        //   documentIds: state.analysis.selectedDocumentIds,
        //   query: currentInput
        // });
        
        // 테이블 데이터 초기화
        let tableData: TableResponse = { columns: [] };
        
        // 콜백 기반으로 searchTableStream 호출
        await searchTableStream(
          state.currentProjectId,
          state.analysis.selectedDocumentIds,
          currentInput,
          {
            onStart: () => {
              console.debug('테이블 검색 스트리밍 시작');
            },
            onHeader: (data) => {
              console.debug('헤더 이벤트 처리:', data);
              // 헤더 정보 저장
              setTableStreamingState(prev => ({
                ...prev,
                headerName: data.header_name
              }));
              
              // 테이블 데이터 초기화 및 헤더 설정
              tableData = {
                columns: [{
                  header: {
                    name: data.header_name,
                    prompt: data.prompt
                  },
                  cells: []
                }]
              };
              
              // 분석 시작 메시지 업데이트
              dispatch({
                type: actionTypes.UPDATE_CHAT_MESSAGE,
                payload: {
                  id: assistantMessageId,
                  content: `**${data.header_name}** 컬럼을 생성하고 있습니다. 결과가 준비되는 대로 표시됩니다...`
                }
              });

              // 테이블 데이터를 상태에 업데이트
              dispatch({
                type: actionTypes.UPDATE_TABLE_DATA,
                payload: tableData
              });
            },
            onCell: (data) => {
              // 이벤트 타입 자체가 cell_processing 또는 cell_result일 수 있음
              const eventType = data.event || '';
              
              if (eventType === 'cell_processing' || (data.doc_id && !data.content)) {
                // 처리 중인 문서 추가
                setTableStreamingState(prev => ({
                  ...prev,
                  processingDocIds: [...prev.processingDocIds, data.doc_id]
                }));
              } else if (eventType === 'cell_result' || (data.doc_id && data.content)) {
                // 결과 셀 데이터 추가
                if (tableData.columns[0] && data.content) {
                  const headerName = tableData.columns[0].header.name;

                  // 테이블 데이터에 셀 추가
                  tableData.columns[0].cells.push({
                    doc_id: data.doc_id,
                    content: data.content
                  });
                  
                  // 문서 데이터의 added_col_context 업데이트를 위한 액션 디스패치\
                  console.debug('searchTableStream[onCell][UPDATE_DOCUMENT_COLUMN]:', tableData)
                  dispatch({
                    type: actionTypes.UPDATE_DOCUMENT_COLUMN,
                    payload: {
                      documentId: data.doc_id,
                      headerName: headerName,
                      content: data.content
                    }
                  });
                  
                  // 처리 상태 업데이트
                  setTableStreamingState(prev => ({
                    ...prev,
                    processingDocIds: prev.processingDocIds.filter(id => id !== data.doc_id),
                    completedDocIds: [...prev.completedDocIds, data.doc_id]
                  }));
                  
                  // // 테이블 데이터 업데이트
                  // console.log('searchTableStream[onCell][UPDATE_TABLE_DATA] :', tableData)
                  // dispatch({
                  //   type: actionTypes.UPDATE_TABLE_DATA,
                  //   payload: tableData
                  // });
                }
              }
            },
            onProgress: (data) => {
              // 진행 상황 메시지 업데이트
              if (tableData.columns[0]?.header?.name) {
                dispatch({
                  type: actionTypes.UPDATE_CHAT_MESSAGE,
                  payload: {
                    id: assistantMessageId,
                    content: `**${tableData.columns[0].header.name}** 컬럼 분석 중: ${data.message}`
                  }
                });
              }
            },
            onError: (error) => {
              console.error('테이블 분석 오류:', error);
              // 오류 메시지 표시
              dispatch({
                type: actionTypes.UPDATE_CHAT_MESSAGE,
                payload: {
                  id: assistantMessageId,
                  content: `테이블 분석 중 오류가 발생했습니다: ${error.message}`
                }
              });
            },
            onCompleted: (data) => {
              console.debug('완료 이벤트 처리:', data);
              // 완료 상태 표시
              setTableStreamingState(prev => ({
                ...prev,
                isStreaming: false
              }));
              
              // 헤더 이름 확인 (데이터 구조가 다양할 수 있음)
              const headerName = data.header_name || 
                (tableData.columns[0]?.header?.name) || 
                '새로운';
              
              // 완료 메시지로 업데이트
              dispatch({
                type: actionTypes.UPDATE_CHAT_MESSAGE,
                payload: {
                  id: assistantMessageId,
                  content: `**${headerName}** 컬럼이 추가되었습니다. 테이블을 확인해주세요.`
                }
              });
            }
          }
        );

      } catch (error) {
        console.error('테이블 분석 중 오류:', error)
        
        // 오류 메시지 추가
        dispatch({
          type: actionTypes.ADD_CHAT_MESSAGE,
          payload: {
            role: 'assistant',
            content: `죄송합니다. 분석 중 오류가 발생했습니다: ${error instanceof Error ? error.message : '알 수 없는 오류'}`
          }
        });
        
      } finally {
        // 스트리밍 상태 초기화
        setTableStreamingState({
          isStreaming: false,
          headerName: null,
          processingDocIds: [],
          completedDocIds: [],
        });
        
        dispatch({ type: actionTypes.SET_IS_ANALYZING, payload: false })
        setIsGenerating(false)
      }
    } else {
      const streamingHandler = new StreamingMarkdownHandler();
      const tempMessageId = generateMessageId();

      try {
        const docIds = Object.values(state.documents).map(doc => doc.id)
        console.debug('doc ids : ', docIds)
        
        try {
          // 초기 빈 메시지 추가
          dispatch({
            type: actionTypes.ADD_CHAT_MESSAGE,
            payload: {
              id: tempMessageId,
              role: 'assistant',
              content: '',
              timestamp: new Date().toISOString()
            }
          });

          setStreamingMessageId(tempMessageId);

          const response = await sendChatMessage_streaming(
            state.currentProjectId!,
            docIds,
            currentInput
          );

          if (!response.ok) {
            throw new Error('채팅 요청 실패');
          }

          const reader = response.body?.getReader();
          if (!reader) throw new Error('Reader not available');

          const decoder = new TextDecoder();

          while (true) {
            const { value, done } = await reader.read();
            if (done) {
              setStreamingMessageId(null);
              setIsGenerating(false);
              break;
            }

            const chunk = decoder.decode(value);
            //console.log('chunk :', chunk)
            //const content = chunk.substring(chunk.indexOf('data:') + 5);
            const content = chunk.substring(16).slice(0, -4);
            
            //const lines = content.split('\r\n');
            const lines = content.split('data: ').slice(1);
            console.debug('lines :', lines)

            for (const line of lines) {

              if (line.trim() === '[DONE]') {
                setStreamingMessageId(null);
                setIsGenerating(false);
                break;
              }
              streamingHandler.processChunk(line, dispatch, tempMessageId);

            }
          }

        } catch (error) {
          setStreamingMessageId(null);
          setIsGenerating(false);
          console.error('채팅 중 오류:', error);
          dispatch({
            type: actionTypes.ADD_CHAT_MESSAGE,
            payload: {
              role: 'assistant',
              content: '죄송합니다. 응답을 생성하는 중에 오류가 발생했습니다.'
            }
          });
        } finally {
          streamingHandler.reset();
          dispatch({ type: actionTypes.SET_IS_ANALYZING, payload: false });
          setStreamingMessageId(null);
          setIsGenerating(false);
        }
      } catch (error) {
        setStreamingMessageId(null);
        setIsGenerating(false)
        console.error('채팅 중 오류:', error);
        dispatch({
          type: actionTypes.ADD_CHAT_MESSAGE,
          payload: {
            role: 'assistant',
            content: '죄송합니다. 응답을 생성하는 중에 오류가 발생했습니다.'
          }
        });
      }
    }
  }, [input, state.analysis.mode, state.currentProjectId, state.analysis.selectedDocumentIds, dispatch, generateMessageId]);

  const handleInputChange = useCallback((e: React.ChangeEvent<HTMLInputElement>) => {
    setInput(e.target.value)
  }, []);

  const handleKeyDown = useCallback((e: React.KeyboardEvent<HTMLInputElement>) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      handleSubmit(e);
    }
  }, [handleSubmit]);

  // 메시지 렌더링 최적화
  const renderMessages = useMemo(() => {
    return state.messages.map((message) => (
      <ChatMessage 
        key={message.id || `${message.timestamp}-${message.role}`} 
        message={message} 
        isStreaming={message.id === streamingMessageId}
      />
    ));
  }, [state.messages, streamingMessageId]);

  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' })
  }

  useEffect(() => {
    scrollToBottom()
  }, [state.messages])

  return (
    <div className="relative h-full flex flex-col bg-background dark:bg-gray-900">
      {/* 메시지 컨테이너 */}
      <div 
        id="chat-container" 
        className={`overflow-y-auto ${isMobile ? 'px-3 py-4 pt-14' : 'px-4 py-6'} bg-background 
          scrollbar-thin scrollbar-thumb-gray-300 dark:scrollbar-thumb-gray-600 
          scrollbar-track-transparent hover:scrollbar-thumb-gray-400 dark:hover:scrollbar-thumb-gray-500`}
        style={{ height: `calc(100%)` }}
      >
        <div className="flex flex-col max-w-3xl mx-auto w-full">
          {renderMessages}
          <div ref={messagesEndRef} />
        </div>
      </div>

      {/* 입력 영역 */}
      <div 
        className={`${
          isMobile 
            ? 'fixed bottom-0 left-0 right-0 z-[1000] p-2.5 bg-background dark:bg-gray-900 border-t border-gray-200 dark:border-gray-800' 
            : 'fixed bottom-0 left-0 right-0 z-[10] bg-background dark:bg-gray-900 border-gray-200 dark:border-gray-800'
        }`}
        style={{ height: isMobile ? '56px' : '50px' }}
      >
        <form onSubmit={handleSubmit} className="flex max-w-3xl mx-auto w-full px-0 relative">
          {/* 텍스트 입력 영역 wrapper (position: relative 유지) */} 
          <div className="w-full relative flex items-center gap-2"> 
            {/* Plus 아이콘: 데스크탑에서는 input 안에 absolute, 모바일에서는 input 옆에 static. 버튼 스타일 추가 */} 
            <div 
              className={cn(
                "cursor-pointer text-gray-500 hover:text-gray-700 dark:text-gray-400 dark:hover:text-gray-200",
                "p-1 rounded-md hover:bg-gray-100 dark:hover:bg-gray-800", // 버튼 스타일 및 hover 효과
                !isMobileValue && "absolute left-2 top-1/2 transform -translate-y-1/2 z-10", // 데스크탑: absolute 위치 조정 (left-3 -> left-2)
                isMobileValue && "ml-1" // 모바일: 왼쪽 여백 조정 (ml-3 -> ml-1)
              )}
              onClick={onUploadButtonClick}
            >
              <Plus className="h-4 w-4" />
            </div>
            
            {/* Input: 데스크탑에서만 왼쪽 패딩 추가 */} 
            <Input
              className={cn(
                "flex-1 w-full rounded-md pr-12",
                isMobileValue ? "px-3 py-1.5 text-sm h-10" : "py-2.5 h-11 pl-10", // 데스크탑: pl-10 유지
                "bg-white border-gray-200 dark:border-gray-700 focus-visible:ring-[#10A37F] shadow-sm"
              )}
              placeholder={isGenerating 
                ? "응답 중..." 
                : (state.analysis.mode === 'table' 
                  ? (isMobileValue ? "질문을 입력하세요..." : "개별 분석을 위한 질문을 입력하세요...") 
                  : "메시지를 입력하세요...")}
              value={input}
              onChange={handleInputChange}
              onKeyDown={handleKeyDown}
              disabled={isGenerating || state.isAnalyzing}
              ref={inputRef}
            />
            <div className="absolute right-2 top-1/2 transform -translate-y-1/2">
              {isGenerating ? (
                <Button 
                  type="button" 
                  variant="destructive" 
                  size="sm"
                  onClick={handleStopGeneration}
                  disabled={state.analysis.mode === 'table' && tableStreamingState.isStreaming}
                  className={cn("rounded-full bg-red-500 hover:bg-red-600", isMobileValue ? 'h-8 w-8 p-0' : 'h-9 w-9 p-0')}
                >
                  <Square className={cn(isMobileValue ? 'h-3.5 w-3.5' : 'h-4 w-4')} />
                </Button>
              ) : (
                <Button 
                  type="submit" 
                  variant="ghost"
                  size="icon"
                  disabled={!input.trim() || isGenerating || state.isAnalyzing}
                  className={cn(isMobileValue ? 'h-8 w-8' : 'h-9 w-9')}
                >
                  <Send className={cn(isMobileValue ? 'h-3.5 w-3.5' : 'h-4 w-4')} />
                </Button>
              )}
            </div>
          </div>
        </form>
      </div>

      {/* 테이블 모드 분석 진행 상태 표시 */}
      <TableAnalysisProgress streamingState={tableStreamingState} />

      {/* 타이핑 애니메이션 스타일 */}
      <style jsx global>{`
        .typing .cursor {
          display: inline-block;
          width: 6px;
          height: 16px;
          background-color: currentColor;
          margin-left: 2px;
          animation: blink 1s infinite;
        }
        
        @keyframes blink {
          0%, 50% { opacity: 1; }
          51%, 100% { opacity: 0; }
        }
        
        /* 스크롤바 스타일링 - tailwind-scrollbar 플러그인이 없을 경우 대비 */
        .scrollbar-thin::-webkit-scrollbar {
          width: 6px;
        }
        
        .scrollbar-thumb-gray-300::-webkit-scrollbar-thumb {
          background-color: #d1d5db;
          border-radius: 9999px;
        }
        
        .dark .scrollbar-thumb-gray-600::-webkit-scrollbar-thumb {
          background-color: #4b5563;
        }
        
        .scrollbar-track-transparent::-webkit-scrollbar-track {
          background-color: transparent;
        }
        
        .hover\:scrollbar-thumb-gray-400:hover::-webkit-scrollbar-thumb {
          background-color: #9ca3af;
        }
        
        .dark .hover\:scrollbar-thumb-gray-500:hover::-webkit-scrollbar-thumb {
          background-color: #6b7280;
        }
        
        /* 모바일에서 커서 크기 조정 */
        @media (max-width: 767px) {
          .typing .cursor {
            width: 4px;
            height: 14px;
          }
        }
      `}</style>
    </div>
  )
}

// ChatMessage 컴포넌트를 메모이제이션
const ChatMessage = React.memo(function ChatMessage({ message, isStreaming }: { message: IMessage; isStreaming?: boolean }) {
  const contentRef = useRef<HTMLDivElement>(null);
  const [isLongContent, setIsLongContent] = useState(false);

  useEffect(() => {
    if (contentRef.current) {
      const { scrollHeight, clientHeight, scrollWidth, clientWidth } = contentRef.current;
      setIsLongContent(scrollHeight > clientHeight || scrollWidth > clientWidth);
    }
  }, [message.content]);

  return (
    <div className={`flex flex-col ${message.role === 'assistant' ? 'mb-2 md:mb-6' : 'mb-2 md:mb-3'} w-full`}>
      <div className={`flex items-start ${
        message.role === 'assistant' && !message.isStatusMessage // 상태 메시지는 assistant 역할이지만 user처럼 오른쪽에 정렬될 수 있음
          ? `mr-auto max-w-6xl`
          : `ml-auto max-w-4xl` // 사용자 메시지 및 상태 메시지
      }`}>
        {/* 사용자 메시지 스타일 */}
        {message.role === 'user' && (
          <div className="rounded-md px-4 py-2.5 bg-[#3F424A] text-white">
            <div 
              ref={contentRef}
              className={`overflow-hidden ${isStreaming ? 'typing' : ''}`}
            >
              <ReactMarkdown 
                remarkPlugins={[remarkGfm, remarkBreaks]}
                skipHtml={true}
                unwrapDisallowed={true}
                className={`prose max-w-none markdown text-sm md:text-base
                    [&>h3]:font-semibold [&>h3]:mt-3 [&>h3]:mb-1.5
                    [&>p]:leading-relaxed [&>p]:mt-0 [&>p]:mb-1
                    [&>ul]:mt-0 [&>ul]:mb-2 [&>ul]:pl-4
                    [&>li]:leading-relaxed
                    [&>p:only-child]:m-0
                    [&>h3]:text-white [&>p]:text-white [&>li]:text-white
                `}
                components={{ text: ({node, ...props}) => <>{props.children}</> }}
              >
                {message.content}
              </ReactMarkdown>
              {isStreaming && <span className="cursor blink-cursor" />}
            </div>
          </div>
        )}

        {/* 상태 메시지 스타일 */}
        {message.isStatusMessage && (
          <div className="rounded-md px-4 py-2.5 bg-[#D8EFE9] text-[#3F424A]">
             <div 
              ref={contentRef}
              className={`overflow-hidden ${isStreaming ? 'typing' : ''}`}
            >
              <ReactMarkdown 
                remarkPlugins={[remarkGfm, remarkBreaks]}
                skipHtml={true}
                unwrapDisallowed={true}
                className={`prose max-w-none markdown text-sm md:text-base
                    [&>p]:leading-relaxed [&>p]:mt-0 [&>p]:mb-1
                    [&>p:only-child]:m-0
                    [&>p]:text-[#3F424A] // 상태 메시지 텍스트 색상 적용
                `}
                components={{ text: ({node, ...props}) => <>{props.children}</> }}
              >
                {message.content}
              </ReactMarkdown>
              {/* 상태 메시지는 스트리밍되지 않으므로 커서 제거 */}
            </div>
          </div>
        )}

        {/* 일반 AI 응답 메시지 스타일 */}
        {message.role === 'assistant' && !message.isStatusMessage && (
          <div 
            ref={contentRef}
            className={`overflow-hidden ${isStreaming ? 'typing' : ''} w-full`}
          >
            <ReactMarkdown 
              remarkPlugins={[remarkGfm, remarkBreaks]}
              skipHtml={true}
              unwrapDisallowed={true}
              className={`prose max-w-none markdown text-sm md:text-base
                  [&>h3]:font-semibold [&>h3]:mt-3 [&>h3]:mb-1.5
                  [&>p]:leading-relaxed [&>p]:mt-0 [&>p]:mb-1
                  [&>ul]:mt-0 [&>ul]:mb-2 [&>ul]:pl-4
                  [&>li]:leading-relaxed
                  [&>p:only-child]:m-0
                  [&>h3]:text-gray-800 [&>p]:text-gray-700 [&>li]:text-gray-700 dark:[&>h3]:text-gray-200 dark:[&>p]:text-gray-300 dark:[&>li]:text-gray-300
                  mb-[5px] // 아래 여백 5px 추가
                  selection:bg-[#ABABAB] selection:text-white // 텍스트 선택 스타일 추가
              `}
              components={{ text: ({node, ...props}) => <>{props.children}</> }}
            >
              {message.content}
            </ReactMarkdown>
            {isStreaming && <span className="cursor blink-cursor" />}
          </div>
        )}
      </div>
    </div>
  )
}); // }; -> }); 로 수정
