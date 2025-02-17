"use client"

import { useState, useEffect, useRef, useCallback, useMemo } from 'react'
import { Send, Square } from 'lucide-react'
import { Avatar, AvatarImage, AvatarFallback } from 'intellio-common/components/ui/avatar'
import { Button } from 'intellio-common/components/ui/button'
import { Input } from 'intellio-common/components/ui/input'
import { useApp } from '@/contexts/AppContext'
import { searchTable, sendChatMessage, sendChatMessage_streaming, stopChatMessageGeneration } from '@/services/api'
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
                [&>h3]:text-xl [&>h3]:font-semibold [&>h3]:text-gray-700 [&>h3]:mt-6 [&>h3]:mb-2
                [&>p]:text-gray-600 [&>p]:leading-relaxed [&>p]:mt-0 [&>p]:mb-3
                [&>ul]:mt-0 [&>ul]:mb-3 [&>ul]:pl-4
                [&>li]:text-gray-600 [&>li]:leading-relaxed
                [&>p:only-child]:m-0"
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

class StreamingMarkdownHandler {

  processChunk(chunk: string, dispatch: any, tempMessageId: string): void {
    // data: [DONE] 체크
    
    if (chunk.endsWith('[DONE]\n\n')) {

      // 앞뒤 공백을 포함한 data: [DONE] 제거
      const cleanedChunk = chunk.replace('data: [DONE]\n\n', '');
      if (cleanedChunk)
        // 일반 텍스트 처리
        dispatch({
          type: actionTypes.UPDATE_CHAT_MESSAGE,
          payload: {
            id: tempMessageId,
            content: (prevContent: string) => prevContent + cleanedChunk
          }
        });
      return;
    }

    // 앞뒤 공백을 포함한 data: 프리픽스 제거
    const cleanedChunk = chunk.replace(/^\s*data:\s*/, '');
    if (!cleanedChunk) return;

    // [DONE] 문자열이 포함된 경우 제거 (끝의 공백만 제거)
    const finalChunk = cleanedChunk.replace(/\[DONE\]$/, '');
    if (!finalChunk) return;

    console.log(finalChunk)
    // 일반 텍스트 처리
    dispatch({
      type: actionTypes.UPDATE_CHAT_MESSAGE,
      payload: {
        id: tempMessageId,
        content: (prevContent: string) => prevContent + finalChunk
      }
    });
  }

  reset(): void {

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

      console.log('테이블 검색 시작:', {
        mode: state.analysis.mode,
        projectId: state.currentProjectId,
        documentIds: state.analysis.selectedDocumentIds,
        query: currentInput
      })

      // AI 요청
      try {
        const result:TableResponse = await searchTable(
          state.currentProjectId,
          state.analysis.selectedDocumentIds,
          currentInput
        )
        

        console.log('테이블 검색 결과:', result)

        if (result.columns?.length > 0) {
          if(result.columns[0].cells[0].doc_id === 'empty') {
            dispatch({
              type: actionTypes.ADD_CHAT_MESSAGE,
              payload: {
                role: 'assistant',
                content: result.columns[0].cells[0].content
              }
            })
            return;
          }
          dispatch({
            type: actionTypes.UPDATE_TABLE_DATA,
            payload: result //{

          })

          // 성공 메시지 추가
          dispatch({
            type: actionTypes.ADD_CHAT_MESSAGE,
            payload: {
              role: 'assistant',
              content: '새로운 컬럼이 추가되었습니다.'
            }
          })
        }
      } catch (error) {
        console.error('테이블 분석 중 오류:', error)
        
        // 오류 메시지 추가
        dispatch({
          type: actionTypes.ADD_CHAT_MESSAGE,
          payload: {
            role: 'assistant',
            content: '죄송합니다. 분석 중 오류가 발생했습니다.'
          }
        })
        
      } finally {
        dispatch({ type: actionTypes.SET_IS_ANALYZING, payload: false })
        setIsGenerating(false)
      }
    } else {
      const streamingHandler = new StreamingMarkdownHandler();
      const tempMessageId = generateMessageId();

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
        const docIds = Object.values(state.documents).map(doc => doc.id)
        console.log('doc ids : ', docIds)
        const response = await sendChatMessage_streaming(
          state.currentProjectId!,
          //state.analysis.selectedDocumentIds,
          docIds,
          currentInput
        );
    
        const reader = response.body?.getReader();
        const decoder = new TextDecoder();
    
        if (!reader) throw new Error('No reader available');
        setStreamingMessageId(tempMessageId);
    
        while (true) {
          const { value, done } = await reader.read();
          if (done) {
            setStreamingMessageId(null);
            setIsGenerating(false)
            break;
          }
          
          const chunk = decoder.decode(value);
          console.log('chunk : ', chunk)
          if (chunk === 'data: [DONE]' || chunk === '[DONE]') {
            setStreamingMessageId(null);
            setIsGenerating(false)
            break;
          }
    
          streamingHandler.processChunk(chunk, dispatch, tempMessageId);
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
      } finally {
        streamingHandler.reset();
        dispatch({ type: actionTypes.SET_IS_ANALYZING, payload: false });
        setStreamingMessageId(null);
        setIsGenerating(false)
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
    <div className="h-full w-full overflow-y-auto bg-muted/90">
      <div className="max-w-4xl mx-auto p-1 h-full">
        <div className="bg-background rounded-lg shadow-sm border p-2 h-full flex flex-col">
          <div className="flex items-center gap-1 mb-2">
            <Button
              variant={state.analysis.mode === 'chat' ? 'default' : 'outline'}
              size="sm"
              onClick={() => dispatch({ type: actionTypes.SET_MODE, payload: 'chat' })}
              className="text-xs"
            >
              Chat
            </Button>
            <Button
              variant={state.analysis.mode === 'table' ? 'default' : 'outline'}
              size="sm"
              onClick={() => dispatch({ type: actionTypes.SET_MODE, payload: 'table' })}
              className="text-xs"
            >
              Table
            </Button>
          </div>
          <div className="flex-1 overflow-y-auto p-2">
            {renderMessages}
            <div ref={messagesEndRef} />
          </div>
          <div className="flex items-center gap-2 relative mt-2 pt-2 border-t">
            <Input
              ref={inputRef}
              value={input}
              onChange={handleInputChange}
              onKeyDown={handleKeyDown}
              placeholder={isGenerating ? "응답 중..." : "메시지를 입력하세요..."}
              className="pr-20"
            />
            <Button
              size="icon"
              className="absolute right-0"
              onClick={isGenerating ? handleStopGeneration : handleSubmit}
              disabled={state.isAnalyzing && !isGenerating}
            >
              {isGenerating ? (
                <Square className="w-4 h-4" />
              ) : (
                <Send className="w-4 h-4" />
              )}
            </Button>
          </div>
        </div>
      </div>
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
