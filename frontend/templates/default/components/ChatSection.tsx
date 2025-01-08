"use client"

import { useState, useEffect, useRef } from 'react'
import { Send } from 'lucide-react'
import { Avatar, AvatarImage, AvatarFallback } from '@/components/ui/avatar'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { useApp } from '@/contexts/AppContext'
import { searchTable, sendChatMessage } from '@/services/api'
import { IMessage, IChatResponse } from '@/types/index'

export const ChatSection = () => {
  const { state, dispatch } = useApp()
  const [input, setInput] = useState('')
  const messagesEndRef = useRef<HTMLDivElement>(null)

  // useEffect(() => {
  //   console.log('메시지 상태 변경:', {
  //     messages: state.messages,
  //     lastMessage: state.messages[state.messages.length - 1]
  //   })
  // }, [state.messages])

  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' })
  }

  useEffect(() => {
    scrollToBottom()
  }, [state.messages])

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    if (!input.trim()) return

    const currentInput = input
    setInput('')

    // 분석 시작 상태 설정
    dispatch({ type: 'SET_IS_ANALYZING', payload: true })

    // 사용자 메시지 추가
    dispatch({
      type: 'ADD_CHAT_MESSAGE',
      payload: {
        role: 'user',
        content: currentInput
      }
    })

    if (state.analysis.mode === 'table') {
      if (!state.currentProjectId || !state.analysis.selectedDocumentIds.length) {
        console.warn('프로젝트 ID 또는 선택된 문서가 없습니다')
        dispatch({ type: 'SET_IS_ANALYZING', payload: false })
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
        const result = await searchTable(
          state.currentProjectId,
          state.analysis.selectedDocumentIds,
          currentInput
        )

        console.log('테이블 검색 결과:', result)

        if (result.columns?.length > 0) {
          dispatch({
            type: 'UPDATE_TABLE_DATA',
            payload: {
              columns: [...state.analysis.tableData.columns, ...result.columns]
            }
          })

          // 성공 메시지 추가
          dispatch({
            type: 'ADD_CHAT_MESSAGE',
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
          type: 'ADD_CHAT_MESSAGE',
          payload: {
            role: 'assistant',
            content: '죄송합니다. 분석 중 오류가 발생했습니다.'
          }
        })
      } finally {
        dispatch({ type: 'SET_IS_ANALYZING', payload: false })
      }
    } else {

      try {
        const response: IChatResponse = await sendChatMessage(
          state.currentProjectId!,
          state.analysis.selectedDocumentIds,
          currentInput
        )

        // 응답 메시지 추가
        if (response) {
          console.log('채팅 응답 상세:', {
            response,
          })
          dispatch({
            type: 'ADD_CHAT_MESSAGE',
            payload: {
              role: response.role,
              content: response.content,
              timestamp: response.timestamp
            }
          })
        }
      } catch (error) {
        console.error('채팅 중 오류:', error)
        dispatch({
          type: 'ADD_CHAT_MESSAGE',
          payload: {
            role: 'assistant',
            content: '죄송합니다. 응답을 생성하는 중에 오류가 발생했습니다.'
          }
        })
      } finally {
        dispatch({ type: 'SET_IS_ANALYZING', payload: false })
      }
    }
  }

  return (
    <div className="h-full w-full overflow-y-auto bg-muted/90">
      <div className="max-w-4xl mx-auto p-1 h-full">
        <div className="bg-background rounded-lg shadow-sm border p-2 h-full flex flex-col">
          <div className="flex items-center gap-1 mb-2">
            <Button
              variant={state.analysis.mode === 'chat' ? 'default' : 'outline'}
              size="sm"
              onClick={() => dispatch({ type: 'SET_MODE', payload: 'chat' })}
              className="text-xs"
            >
              Chat
            </Button>
            <Button
              variant={state.analysis.mode === 'table' ? 'default' : 'outline'}
              size="sm"
              onClick={() => dispatch({ type: 'SET_MODE', payload: 'table' })}
              className="text-xs"
            >
              Table
            </Button>
          </div>
          <div className="flex-1 overflow-y-auto p-2">
            {state.messages.map((message, index) => (
              <div
                key={index}
                className={`mb-2 ${
                  message.role === 'user' ? 'text-right' : 'text-left'
                }`}
              >
                {message.role === 'user' ? (
                  <div className="inline-block p-2 rounded-lg bg-blue-500 text-white text-sm whitespace-pre-wrap max-w-[95%] leading-relaxed mr-2">
                    {message.content}
                  </div>
                ) : (
                  <div className="inline-block p-2 rounded-lg bg-gray-200 text-gray-800 text-sm whitespace-pre-wrap max-w-[95%] leading-relaxed ml-2">
                    {message.content.split(/(<[mnp][pn]?>.*?<\/[mnp][pn]?>)/).map((part, index) => {
                      const moneyPlusMatch = part.match(/<mp>(.*?)<\/mp>/);
                      const moneyMinusMatch = part.match(/<mn>(.*?)<\/mn>/);
                      const moneyMatch = part.match(/<m>(.*?)<\/m>/);
                      const numberPlusMatch = part.match(/<np>(.*?)<\/np>/);
                      const numberMinusMatch = part.match(/<nn>(.*?)<\/nn>/);
                      const numberMatch = part.match(/<n>(.*?)<\/n>/);
                      
                      if (moneyPlusMatch) {
                        return <span key={index} className="text-blue-600 font-bold">+{moneyPlusMatch[1]}</span>;
                      } else if (moneyMinusMatch) {
                        return <span key={index} className="text-red-600 font-bold">-{moneyMinusMatch[1]}</span>;
                      } else if (moneyMatch) {
                        return <span key={index} className="font-bold">{moneyMatch[1]}</span>;
                      } else if (numberPlusMatch) {
                        return <span key={index} className="text-blue-600 font-bold">+{numberPlusMatch[1]}</span>;
                      } else if (numberMinusMatch) {
                        return <span key={index} className="text-red-600 font-bold">-{numberMinusMatch[1]}</span>;
                      } else if (numberMatch) {
                        return <span key={index} className="font-bold">{numberMatch[1]}</span>;
                      }
                      return part;
                    })}
                  </div>
                )}
              </div>
            ))}
            {state.isAnalyzing && (
              <div className="text-left">
                <div className="flex items-center gap-2 p-2">
                  <div className="w-6 h-6 rounded-full bg-gray-200 pulse" />
                  <div className="inline-block p-2 rounded-lg bg-gray-200 text-gray-800">
                    <div className="typing-indicator">
                      <span></span>
                      <span></span>
                      <span></span>
                    </div>
                  </div>
                </div>
                <div className="text-xs text-gray-500 ml-8 mt-1">분석중...</div>
              </div>
            )}
            <div ref={messagesEndRef} />
          </div>
          <div className="flex items-center gap-2 relative mt-2 pt-2 border-t">
            <Input
              value={input}
              onChange={(e) => setInput(e.target.value)}
              placeholder="메시지를 입력하세요..."
              className="pr-20"
              onKeyDown={(e) => {
                if (e.key === 'Enter' && !e.shiftKey) {
                  e.preventDefault();
                  handleSubmit(e);
                }
              }}
            />
            <Button
              size="icon"
              className="absolute right-0"
              onClick={(e) => handleSubmit(e)}
              disabled={state.isAnalyzing}
            >
              <Send className="w-4 h-4" />
            </Button>
          </div>
        </div>
      </div>
    </div>
  )
}
