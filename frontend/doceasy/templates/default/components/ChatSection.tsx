"use client"

import { useState, useEffect, useRef, useCallback, useMemo } from 'react'
import { Send, Square } from 'lucide-react'
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
    <div className="flex flex-col items-end mb-2 w-full">
      <div className={`flex items-start gap-3 ${
        message.role === 'assistant' 
          ? `bg-gray-100 dark:bg-gray-800 ${isLongContent ? 'w-full' : 'w-fit'}`
          : `bg-sky-100 dark:bg-sky-900 ${isLongContent ? 'w-full' : 'w-fit'}`
      } ${isLongContent ? 'px-4 py-3' : 'px-3 py-2'} rounded-lg ${
        message.role === 'user' ? 'ml-auto' : 'mr-auto'
      }`}>
        <div 
          ref={contentRef}
          className={`overflow-hidden ${isStreaming ? 'typing' : ''}`}
        >
          <ReactMarkdown 
            remarkPlugins={[remarkGfm, remarkBreaks]}
            skipHtml={true}
            unwrapDisallowed={true}
            className="prose max-w-none markdown
                [&>h3]:text-base [&>h3]:font-semibold [&>h3]:text-gray-700 [&>h3]:mt-4 [&>h3]:mb-2
                [&>p]:text-gray-600 [&>p]:leading-relaxed [&>p]:mt-0 [&>p]:mb-2 [&>p]:text-xs
                [&>ul]:mt-0 [&>ul]:mb-2 [&>ul]:pl-4
                [&>li]:text-gray-600 [&>li]:leading-relaxed [&>li]:text-xs
                [&>p:only-child]:m-0
                [&>code]:text-xs [&>pre]:text-xs
                [&>table]:text-xs [&>table>thead>tr>th]:text-xs [&>table>tbody>tr>td]:text-xs"
            components={{
              text: ({node, ...props}) => <>{props.children}</>
            }}
          >
            {message.content}
          </ReactMarkdown>
          {isStreaming && <span className="cursor" />}
        </div>
      </div>
    </div>
  )
});

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
    <div className="fixed bottom-24 right-8 bg-white dark:bg-gray-800 shadow-lg rounded-lg p-4 z-50 max-w-xs">
      <div className="flex flex-col space-y-2">
        <h4 className="font-semibold text-sm">{streamingState.headerName ? `'${streamingState.headerName}' 분석 중` : '문서 분석 중'}</h4>
        
        <div className="space-y-1">
          <div className="flex justify-between text-xs">
            <span>진행 중:</span>
            <span className="font-medium">{streamingState.processingDocIds.length}</span>
          </div>
          <div className="flex justify-between text-xs">
            <span>완료:</span> 
            <span className="font-medium">{streamingState.completedDocIds.length}</span>
          </div>
          
          {/* 프로그레스 바 */}
          <div className="w-full bg-gray-200 rounded-full h-1.5 mt-1">
            <div 
              className="bg-blue-600 h-1.5 rounded-full transition-all duration-300"
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

export const ChatSection = () => {
  const { state, dispatch } = useApp()
  const [input, setInput] = useState('')
  const [streamingMessageId, setStreamingMessageId] = useState<string | null>(null)
  const [isGenerating, setIsGenerating] = useState(false)
  const messagesEndRef = useRef<HTMLDivElement>(null)
  const inputRef = useRef<HTMLInputElement>(null)
  const messageCountRef = useRef(0)
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
        console.warn('프로젝트 ID 또는 선택된 문서가 없습니다')
        dispatch({ type: actionTypes.SET_IS_ANALYZING, payload: false })
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
    <div className="relative h-full pb-[68px] flex flex-col">
      {/* 모드 선택 버튼 - absolute 제거하고 상단에 배치 */}
      <div className="p-2 bg-white dark:bg-gray-900">
        <div className="flex space-x-2">
          <Button
            variant={state.analysis.mode === 'chat' ? 'default' : 'outline'}
            size="sm"
            onClick={() => dispatch({ type: actionTypes.SET_MODE, payload: 'chat' })}
            className="text-xs"
            disabled={isGenerating || state.isAnalyzing}
          >
            통합분석
          </Button>
          <Button
            variant={state.analysis.mode === 'table' ? 'default' : 'outline'}
            size="sm"
            onClick={() => dispatch({ type: actionTypes.SET_MODE, payload: 'table' })}
            className="text-xs"
            disabled={isGenerating || state.isAnalyzing}
          >
            개별분석
          </Button>
        </div>
      </div>
      
      {/* 메시지 컨테이너 - 나머지 영역 채우도록 변경 */}
      <div className="flex-grow overflow-y-auto p-4" id="chat-container">
        <div className="flex flex-col space-y-2">
          {renderMessages}
          <div ref={messagesEndRef} />
        </div>
      </div>

      <div className="absolute bottom-0 left-0 right-0 bg-white dark:bg-gray-900 border-t border-gray-200 dark:border-gray-800 p-3">
        <form onSubmit={handleSubmit} className="flex space-x-2">
          <Input
            className="flex-1 pr-20"
            placeholder={isGenerating ? "응답 중..." : (state.analysis.mode === 'table' ? "테이블 분석을 위한 질문을 입력하세요..." : "메시지를 입력하세요...")}
            value={input}
            onChange={handleInputChange}
            onKeyDown={handleKeyDown}
            disabled={isGenerating || state.isAnalyzing}
            ref={inputRef}
          />
          {isGenerating ? (
            <Button 
              type="button" 
              variant="destructive" 
              size="icon"
              onClick={handleStopGeneration}
              disabled={state.analysis.mode === 'table' && tableStreamingState.isStreaming} // 테이블 분석 중에는 중지 버튼 비활성화
            >
              <Square className="h-4 w-4" />
            </Button>
          ) : (
            <Button type="submit" size="icon" disabled={!input.trim() || isGenerating || state.isAnalyzing}>
              <Send className="h-4 w-4" />
            </Button>
          )}
        </form>
      </div>

      {/* 테이블 모드 분석 진행 상태 표시 */}
      <TableAnalysisProgress streamingState={tableStreamingState} />
      
      {/* 마크다운 스타일 적용 */}
      <style jsx global>{`
  .typing .cursor {
    display: inline-block;
    width: 13px;
    height: 13px;
    border-radius: 50%;
    background-color: currentColor;
    margin-left: 4px;
    margin-bottom: 2px;
    animation: pulse 1s infinite;
    vertical-align: middle;
  }

  @keyframes pulse {
    0%, 100% { opacity: 0.4; transform: scale(1); }
    50% { opacity: 1; transform: scale(1.2); }
  }
`}</style>
    </div>
  )
}
