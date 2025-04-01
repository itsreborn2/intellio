'use client'

import { useState, useEffect } from 'react'
import { toast } from 'sonner'
import ReactMarkdown from 'react-markdown'
import remarkGfm from 'remark-gfm';
import remarkBreaks from 'remark-breaks';

const API_BASE_URL = process.env.NEXT_PUBLIC_API_URL;
export const API_ENDPOINT_COMMON = `${API_BASE_URL}/v1`;
export const API_ENDPOINT_STOCKEASY = `${API_BASE_URL}/v1/stockeasy`;

// 타입 정의
interface AgentPromptConfig {
  agent_name: string
  prompt_template: string | null
  enabled: boolean
}

interface VectorDBConfig {
  namespace: string | null
  metadata_filter: Record<string, any> | null
  top_k: number | null
}

interface AgentProcessResult {
  agent_name: string
  input: Record<string, any>
  output: Record<string, any>
  error: string | null
  execution_time: number
}

interface TestResponse {
  question: string
  answer: string
  agent_results: AgentProcessResult[]
  total_execution_time: number
  error: string | null
}

interface Agent {
  name: string
  description: string
}

// 로컬 스토리지 키 상수
const STORAGE_KEY = 'stockeasy_internal_test'

// 임시 에이전트 목록 (백엔드에서 받아와야 함)
const AVAILABLE_AGENTS: Agent[] = [
  { name: 'stock_analyst', description: '주식 분석 에이전트' },
  { name: 'retriever_agent', description: '문서 검색 에이전트' },
  { name: 'financial_analyst', description: '재무 분석 에이전트' },
  { name: 'summarization_agent', description: '요약 에이전트' },
  { name: 'qa_agent', description: '질의응답 에이전트' }
]

// 테스트 모드 타입
type TestMode = 'full' | 'selective' | 'single'

// 프롬프트 템플릿 타입
interface AgentPrompt {
  agent_name: string
  prompt_template: string | null
  is_modified: boolean
}

export default function InternalTestPage() {
  // 상태 관리
  const [question, setQuestion] = useState('')
  const [stockCode, setStockCode] = useState('')
  const [stockName, setStockName] = useState('')
  const [sessionId, setSessionId] = useState('test_session')
  const [testMode, setTestMode] = useState<TestMode>('full')
  const [selectedAgents, setSelectedAgents] = useState<Record<string, boolean>>({})
  const [agentConfigs, setAgentConfigs] = useState<AgentPromptConfig[]>([])
  const [vectorDBConfig, setVectorDBConfig] = useState<VectorDBConfig>({
    namespace: null,
    metadata_filter: null,
    top_k: null
  })
  
  const [isLoading, setIsLoading] = useState(false)
  const [result, setResult] = useState<TestResponse | null>(null)
  const [elapsedTime, setElapsedTime] = useState(0)
  const [timerId, setTimerId] = useState<NodeJS.Timeout | null>(null)
  const [availableAgents, setAvailableAgents] = useState<Agent[]>(AVAILABLE_AGENTS)
  const [agentPrompts, setAgentPrompts] = useState<Record<string, AgentPrompt>>({})
  const [expandedAgent, setExpandedAgent] = useState<string | null>(null)
  const [isLoadingPrompts, setIsLoadingPrompts] = useState<Record<string, boolean>>({})
  
  // 타이머 관리
  useEffect(() => {
    // 로딩 중일 때만 타이머 실행
    if (isLoading) {
      // 타이머 시작
      const startTime = Date.now()
      const timer = setInterval(() => {
        const seconds = Math.floor((Date.now() - startTime) / 1000)
        setElapsedTime(seconds)
      }, 1000)
      setTimerId(timer)
      
      // 컴포넌트 언마운트 또는 로딩 상태 변경 시 타이머 정리
      return () => {
        clearInterval(timer)
        setTimerId(null)
        setElapsedTime(0)
      }
    }
  }, [isLoading])
  
  // 에이전트 목록 초기화
  useEffect(() => {
    // 백엔드에서 에이전트 목록 가져오기
    const initAgents = async () => {
      try {
        // 로딩 표시
        toast.loading('에이전트 목록을 불러오는 중...')
        
        // 백엔드 API 호출 (경로 수정)
        const response = await fetch(`${API_ENDPOINT_STOCKEASY}/_internal_test/agents`);
        
        if (!response.ok) {
          throw new Error(`에이전트 목록 조회 실패: ${response.status}`)
        }
        
        const data = await response.json();
        
        if (data && Array.isArray(data.agents)) {
          // 제외할 에이전트 목록
          const excludedAgents = ['session_manager', 'orchestrator', 'fallback_manager'];
          
          // 필터링된 에이전트 목록 설정
          const filteredAgents = data.agents.filter((agent: Agent) => 
            !excludedAgents.includes(agent.name)
          );
          
          // 백엔드에서 받아온 에이전트 목록 설정
          setAvailableAgents(filteredAgents);
          toast.success('에이전트 목록을 불러왔습니다.');
          
          // 초기 선택 상태 설정
          const initialSelection: Record<string, boolean> = {}
          filteredAgents.forEach((agent: Agent) => {
            initialSelection[agent.name] = false
          })
          setSelectedAgents(initialSelection)
        } else {
          throw new Error('잘못된 응답 형식')
        }
      } catch (error) {
        console.error('에이전트 목록을 가져오는 중 오류 발생:', error)
        toast.error('에이전트 목록을 가져오는 데 실패했습니다. 기본 목록을 사용합니다.')
        
        // 제외할 에이전트 목록
        const excludedAgents = ['session_manager', 'orchestrator', 'fallback_manager'];
        
        // 오류 발생 시 기본 에이전트 목록에서 필터링하여 사용
        const filteredAgents = AVAILABLE_AGENTS.filter(agent => 
          !excludedAgents.includes(agent.name)
        );
        
        setAvailableAgents(filteredAgents)
        
        // 초기 선택 상태 설정
        const initialSelection: Record<string, boolean> = {}
        filteredAgents.forEach(agent => {
          initialSelection[agent.name] = false
        })
        setSelectedAgents(initialSelection)
      }
    }
    
    initAgents()
  }, [])
  
  // 로컬 스토리지에서 이전 입력값 불러오기
  useEffect(() => {
    try {
      if (typeof window !== 'undefined') {
        const savedData = localStorage.getItem(STORAGE_KEY)
        if (savedData) {
          const parsedData = JSON.parse(savedData)
          setQuestion(parsedData.question || '')
          setStockCode(parsedData.stockCode || '')
          setStockName(parsedData.stockName || '')
          setSessionId(parsedData.sessionId || 'test_session')
          
          // 테스트 모드 및 선택된 에이전트 복원
          if (parsedData.testMode) {
            setTestMode(parsedData.testMode)
          }
          if (parsedData.selectedAgents) {
            setSelectedAgents(parsedData.selectedAgents)
          }
        }
      }
    } catch (error) {
      console.error('로컬 스토리지에서 데이터를 불러오는 중 오류 발생:', error)
    }
  }, [])
  
  // 입력값 변경 시 로컬 스토리지에 저장
  useEffect(() => {
    try {
      if (typeof window !== 'undefined') {
        const dataToSave = {
          question,
          stockCode,
          stockName,
          sessionId,
          testMode,
          selectedAgents
        }
        localStorage.setItem(STORAGE_KEY, JSON.stringify(dataToSave))
      }
    } catch (error) {
      console.error('로컬 스토리지에 데이터를 저장하는 중 오류 발생:', error)
    }
  }, [question, stockCode, stockName, sessionId, testMode, selectedAgents])
  
  // 모드 변경 핸들러
  const handleModeChange = (mode: TestMode) => {
    setTestMode(mode)
    
    // 단일 에이전트 모드로 전환 시, 이전 선택 초기화
    if (mode === 'single') {
      const resetSelection: Record<string, boolean> = {}
      availableAgents.forEach(agent => {
        resetSelection[agent.name] = false
      })
      setSelectedAgents(resetSelection)
    }
  }
  
  // 에이전트 선택 핸들러
  const handleAgentSelection = (agentName: string, selected: boolean) => {
    // 단일 에이전트 모드인 경우, 하나만 선택 가능
    if (testMode === 'single') {
      const newSelection: Record<string, boolean> = {}
      availableAgents.forEach(agent => {
        newSelection[agent.name] = agent.name === agentName ? selected : false
      })
      setSelectedAgents(newSelection)
    } else {
      // 선택적 모드에서는 다중 선택 가능
      setSelectedAgents(prev => ({
        ...prev,
        [agentName]: selected
      }))
    }
  }
  
  // 모든 에이전트 선택/해제 핸들러
  const handleSelectAllAgents = (selectAll: boolean) => {
    const newSelection: Record<string, boolean> = {}
    availableAgents.forEach(agent => {
      newSelection[agent.name] = selectAll
    })
    setSelectedAgents(newSelection)
  }
  
  // 에이전트 프롬프트 가져오기
  const fetchAgentPrompt = async (agentName: string) => {
    if (!agentName) return
    
    try {
      setIsLoadingPrompts(prev => ({...prev, [agentName]: true}))
      
      const response = await fetch(`${API_ENDPOINT_STOCKEASY}/_internal_test/agent_prompts/${agentName}`)
      
      if (!response.ok) {
        throw new Error(`프롬프트 가져오기 실패: ${response.status}`)
      }
      
      const data = await response.json()
      
      if (data.prompt_template || data.message) {
        setAgentPrompts(prev => ({
          ...prev, 
          [agentName]: {
            agent_name: agentName,
            prompt_template: data.prompt_template || null,
            is_modified: false
          }
        }))
      }
    } catch (error) {
      console.error(`에이전트 ${agentName} 프롬프트 가져오기 오류:`, error)
      toast.error(`프롬프트를 가져올 수 없습니다: ${agentName}`)
    } finally {
      setIsLoadingPrompts(prev => ({...prev, [agentName]: false}))
    }
  }
  
  // 프롬프트 템플릿 업데이트
  const updatePromptTemplate = (agentName: string, template: string) => {
    setAgentPrompts(prev => ({
      ...prev,
      [agentName]: {
        ...prev[agentName],
        prompt_template: template,
        is_modified: true
      }
    }))
  }
  
  // 프롬프트 템플릿 초기화
  const resetPromptTemplate = async (agentName: string) => {
    await fetchAgentPrompt(agentName)
    toast.success(`${agentName} 프롬프트가 초기화되었습니다.`)
  }
  
  // 선택된 에이전트 기반으로 에이전트 설정 생성
  const generateAgentConfigs = () => {
    if (testMode === 'full') {
      // 전체 테스트 모드에서는 수정된 프롬프트만 설정
      const configs: AgentPromptConfig[] = []
      
      Object.values(agentPrompts).forEach(prompt => {
        if (prompt.is_modified) {
          configs.push({
            agent_name: prompt.agent_name,
            prompt_template: prompt.prompt_template,
            enabled: true
          })
        }
      })
      
      return configs
    }
    
    // 선택적/단일 테스트 모드에서는 선택된 에이전트만 활성화
    const configs: AgentPromptConfig[] = []
    
    // 모든 에이전트에 대해 설정 생성
    availableAgents.forEach(agent => {
      // 프롬프트 정보 가져오기
      const promptInfo = agentPrompts[agent.name]
      
      configs.push({
        agent_name: agent.name,
        prompt_template: promptInfo?.is_modified ? promptInfo.prompt_template : null,
        enabled: selectedAgents[agent.name] // 선택된 에이전트만 활성화
      })
    })
    
    return configs
  }
  
  // 테스트 실행
  const runTest = async () => {
    if (!question.trim()) {
      toast.error('질문을 입력해주세요.')
      return
    }
    
    // 선택적/단일 테스트 모드에서 에이전트가 선택되지 않은 경우 검증
    if ((testMode === 'selective' || testMode === 'single') && 
        !Object.values(selectedAgents).some(selected => selected)) {
      toast.error('최소한 하나의 에이전트를 선택해주세요.')
      return
    }
    
    // 단일 에이전트 모드에서 여러 에이전트가 선택된 경우 검증
    if (testMode === 'single') {
      const selectedCount = Object.values(selectedAgents).filter(Boolean).length
      if (selectedCount > 1) {
        toast.error('단일 에이전트 모드에서는 하나의 에이전트만 선택해주세요.')
        return
      } else if (selectedCount === 0) {
        toast.error('테스트할 에이전트를 선택해주세요.')
        return
      }
    }
    
    try {
      // 테스트 시작 시 이전 결과 초기화
      setResult(null)
      setElapsedTime(0)
      setIsLoading(true)
      
      // 에이전트 설정 생성
      const configs = generateAgentConfigs()
      
      // 수정된 프롬프트를 콘솔에 출력
      const modifiedPrompts = Object.values(agentPrompts).filter(prompt => prompt.is_modified)
      
      if (modifiedPrompts.length > 0) {
        console.log('===== 수정된 프롬프트 =====')
        modifiedPrompts.forEach(prompt => {
          console.log(`[에이전트: ${prompt.agent_name}]`)
          console.log(prompt.prompt_template)
          console.log('------------------------')
        })
        console.log('==========================')
      }
      
      // 단일 에이전트 모드에서 선택된 에이전트 이름 가져오기
      let singleAgentName = null
      if (testMode === 'single') {
        const selectedAgentNames = Object.entries(selectedAgents)
          .filter(([_, selected]) => selected)
          .map(([name, _]) => name)
          
        if (selectedAgentNames.length === 1) {
          singleAgentName = selectedAgentNames[0]
        }
      }
      
      // 요청 데이터 구성
      const requestData = {
        question,
        stock_code: stockCode || undefined,
        stock_name: stockName || undefined,
        session_id: sessionId || 'test_session',
        agent_configs: configs.length > 0 ? configs : undefined,
        vector_db_config: vectorDBConfig.namespace || vectorDBConfig.metadata_filter || vectorDBConfig.top_k
          ? vectorDBConfig
          : undefined,
        // 테스트 모드 추가
        test_mode: {
          mode: testMode,
          selected_agents: testMode !== 'full' ? selectedAgents : undefined,
          single_agent_name: singleAgentName
        }
      }
      
      const response = await fetch(`${API_ENDPOINT_STOCKEASY}/_internal_test`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify(requestData),
      })
      
      if (!response.ok) {
        throw new Error(`서버 오류: ${response.status}`)
      }
      
      const data = await response.json()
      setResult(data)
      toast.success('테스트가 완료되었습니다.')
      
    } catch (error) {
      console.error('테스트 실행 오류:', error)
      toast.error('테스트 실행 중 오류가 발생했습니다.')
    } finally {
      setIsLoading(false)
      // 타이머 정리
      if (timerId) {
        clearInterval(timerId)
        setTimerId(null)
      }
    }
  }

  // JSON 포맷팅 유틸리티
  const formatJson = (data: any) => {
    try {
      return JSON.stringify(data, null, 2)
    } catch (error) {
      return 'Error parsing JSON'
    }
  }
  
  return (
    <div className="space-y-8">
      <section className="bg-white rounded-lg shadow p-6">
        <h2 className="text-2xl font-bold mb-6">스톡이지 에이전트 테스트</h2>
        
        <div className="grid gap-6">
          <div>
            <label htmlFor="question" className="block font-medium mb-2">질문</label>
            <textarea
              id="question"
              className="w-full border rounded-md p-3 h-24"
              placeholder="테스트할 질문을 입력하세요."
              value={question}
              onChange={(e) => setQuestion(e.target.value)}
            />
          </div>
          
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            <div>
              <label htmlFor="stockCode" className="block font-medium mb-2">종목 코드</label>
              <input
                id="stockCode"
                className="w-full border rounded-md p-3"
                placeholder="예: 005930"
                value={stockCode}
                onChange={(e) => setStockCode(e.target.value)}
              />
            </div>
            <div>
              <label htmlFor="stockName" className="block font-medium mb-2">종목명</label>
              <input
                id="stockName"
                className="w-full border rounded-md p-3"
                placeholder="예: 삼성전자"
                value={stockName}
                onChange={(e) => setStockName(e.target.value)}
              />
            </div>
          </div>
          
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            <div>
              <label htmlFor="sessionId" className="block font-medium mb-2">세션 ID</label>
              <input
                id="sessionId"
                className="w-full border rounded-md p-3"
                placeholder="테스트용 세션 ID"
                value={sessionId}
                onChange={(e) => setSessionId(e.target.value)}
              />
            </div>
            
            <div>
              <label className="block font-medium mb-2">테스트 모드</label>
              <div className="border rounded-md p-3">
                <label className="flex items-center">
                  <input
                    type="radio"
                    className="mr-2"
                    checked={testMode === 'full'}
                    onChange={() => handleModeChange('full')}
                  />
                  <span>전체 에이전트 테스트</span>
                </label>
              </div>
            </div>
          </div>
          
          {/* 테스트 모드 선택 - selective/single 모드만 분리해서 표시 */}
          {(testMode === 'selective' || testMode === 'single') && (
          <div className="border rounded-md p-4">
            <div className="space-y-4">
              <div className="flex justify-between items-center">
                <h4 className="font-medium">
                  {testMode === 'single' ? '테스트할 에이전트 선택 (하나만)' : '사용할 에이전트 선택'}
                </h4>
                
                {testMode === 'selective' && (
                  <div className="flex space-x-2">
                    <button
                      className="text-sm text-blue-600 hover:underline"
                      onClick={() => handleSelectAllAgents(true)}
                    >
                      모두 선택
                    </button>
                    <button
                      className="text-sm text-blue-600 hover:underline"
                      onClick={() => handleSelectAllAgents(false)}
                    >
                      모두 해제
                    </button>
                  </div>
                )}
              </div>
              
              <div className="grid grid-cols-1 md:grid-cols-2 gap-2">
                {availableAgents.map((agent) => (
                  <label key={agent.name} className="flex items-center p-2 border rounded-md hover:bg-gray-50">
                    <input
                      type={testMode === 'single' ? 'radio' : 'checkbox'}
                      className="mr-2"
                      checked={selectedAgents[agent.name] || false}
                      onChange={(e) => handleAgentSelection(agent.name, e.target.checked)}
                    />
                    <span>{agent.name}</span>
                  </label>
                ))}
              </div>
            </div>
          </div>
          )}
          
          {/* 에이전트 프롬프트 편집 섹션 */}
          <div className="border rounded-md p-4">
            <h3 className="font-medium mb-4">에이전트 프롬프트 편집</h3>
            
            <div className="space-y-4">
              {availableAgents.map((agent) => (
                <div key={agent.name} className="border rounded-md p-3">
                  <div 
                    className="flex justify-between items-center cursor-pointer"
                    onClick={() => {
                      if (expandedAgent === agent.name) {
                        setExpandedAgent(null)
                      } else {
                        setExpandedAgent(agent.name)
                        if (!agentPrompts[agent.name]) {
                          fetchAgentPrompt(agent.name)
                        }
                      }
                    }}
                  >
                    <h4 className="font-medium flex items-center">
                      <span>{agent.name}</span>
                      {agentPrompts[agent.name]?.is_modified && (
                        <span className="ml-2 text-xs bg-yellow-100 text-yellow-800 px-2 py-0.5 rounded">수정됨</span>
                      )}
                    </h4>
                    <button className="text-gray-500">
                      {expandedAgent === agent.name ? '접기' : '펼치기'}
                    </button>
                  </div>
                  
                  {expandedAgent === agent.name && (
                    <div className="mt-3 space-y-3">
                      {isLoadingPrompts[agent.name] ? (
                        <div className="py-4 text-center text-gray-500">프롬프트 로딩 중...</div>
                      ) : !agentPrompts[agent.name] ? (
                        <div className="py-4 text-center text-gray-500">프롬프트 정보 없음</div>
                      ) : (
                        <>
                          <textarea
                            className="w-full h-64 border rounded-md p-3 font-mono text-sm"
                            value={agentPrompts[agent.name]?.prompt_template || ''}
                            onChange={(e) => updatePromptTemplate(agent.name, e.target.value)}
                            placeholder="프롬프트 템플릿이 없습니다."
                          />
                          
                          <div className="flex justify-end space-x-2">
                            <button
                              className="px-3 py-1 text-sm border rounded-md hover:bg-gray-50"
                              onClick={() => resetPromptTemplate(agent.name)}
                            >
                              기본값으로 초기화
                            </button>
                          </div>
                        </>
                      )}
                    </div>
                  )}
                </div>
              ))}
            </div>
          </div>
          
          <button
            style={{backgroundColor: '#2563eb', color: 'white', padding: '12px 24px', borderRadius: '6px', fontWeight: 'bold'}}
            onClick={runTest}
            disabled={isLoading}
          >
            {isLoading ? `테스트 실행 중...(${elapsedTime}초 경과)` : '테스트 실행'}
          </button>
        </div>
      </section>
      
      {result && (
        <section className="bg-white rounded-lg shadow p-6">
          <h2 className="text-2xl font-bold mb-6">테스트 결과</h2>
          
          <div className="space-y-6">
            <div className="border rounded-lg p-4">
              <h3 className="font-bold text-lg mb-2">최종 응답</h3>
              <div className="bg-gray-50 rounded-md p-4 prose max-w-none">
                <ReactMarkdown 
                        remarkPlugins={[
                          remarkGfm,
                          [remarkBreaks, { breaks: false }]
                        ]}
                        components={{
                          text: ({node, ...props}) => <>{props.children}</>,
                          h1: ({node, ...props}) => <h1 style={{marginTop: '1.5em', marginBottom: '1em'}} {...props} />,
                          h2: ({node, ...props}) => <h2 style={{marginTop: '1.5em', marginBottom: '1em'}} {...props} />,
                          h3: ({node, ...props}) => <h3 style={{marginTop: '1.2em', marginBottom: '0.8em'}} {...props} />,
                          ul: ({node, ...props}) => <ul style={{marginTop: '0.5em', marginBottom: '1em', paddingLeft: '1.5em'}} {...props} />,
                          ol: ({node, ...props}) => <ol style={{marginTop: '0.5em', marginBottom: '1em', paddingLeft: '1.5em'}} {...props} />,
                          li: ({node, ...props}) => <li style={{marginBottom: '0'}} {...props} />,
                          p: ({node, ...props}) => <p style={{marginTop: '0.5em', marginBottom: '1em'}} {...props} />
                        }}
                      >
                  {result.answer}
                </ReactMarkdown>
              </div>
              <div className="mt-2 text-sm text-gray-500">
                총 실행 시간: {result.total_execution_time.toFixed(2)}초
              </div>
            </div>
            
            <div>
              <h3 className="font-bold text-lg mb-4">에이전트별 실행 결과 ({result.agent_results.length}개)</h3>
              
              <div className="space-y-4">
                {result.agent_results
                  .filter(agentResult => !['session_manager', 'parallel_search'].includes(agentResult.agent_name))
                  .map((agentResult) => (
                  <div key={agentResult.agent_name} className={`border rounded-lg p-4 ${agentResult.error ? 'border-red-500' : ''}`}>
                    <div className="flex justify-between mb-4">
                      <h4 className="font-bold">{agentResult.agent_name}</h4>
                      <span className="text-sm text-gray-500">
                        {agentResult.execution_time.toFixed(2)}초
                      </span>
                    </div>
                    
                    {agentResult.error && (
                      <div className="bg-red-50 text-red-700 p-3 mb-4 rounded-md">
                        {agentResult.error}
                      </div>
                    )}
                    
                    <div className="grid grid-cols-1 md:grid-cols-1 gap-4">
                      <div>
                        <h5 className="font-medium mb-2">Agent Results</h5>
                        <pre className="bg-gray-50 p-3 rounded-md h-40 text-xs whitespace-pre-wrap break-words overflow-y-auto overflow-x-hidden">
                          {(() => {
                            // 에이전트별로 표시할 필드 선택
                            switch(agentResult.agent_name) {
                              case 'question_analyzer':
                                return formatJson(agentResult.output?.question_analysis || {});
                              case 'financial_analyzer':
                                return formatJson(agentResult.output?.agent_results?.financial_analyzer || {});
                              case 'telegram_retriever':
                                return formatJson(agentResult.output?.agent_results?.telegram_retriever || {});
                              case 'report_analyzer':
                                return formatJson(agentResult.output?.agent_results?.report_analyzer || {});
                              case 'confidential_analyzer':
                                return formatJson(agentResult.output?.agent_results?.confidential_analyzer || {});
                              case 'industry_analyzer':
                                return formatJson(agentResult.output?.agent_results?.industry_analyzer || {});
                              case 'knowledge_integrator':
                                return formatJson(agentResult.output?.agent_results?.knowledge_integrator || {});
                              case 'summarizer':
                                return formatJson(agentResult.output?.summary || {});
                              case 'response_formatter':
                                return formatJson(agentResult.output?.formatted_response || {});
                              case 'orchestrator':
                                return formatJson(agentResult.output?.execution_plan?.agents || {});
                              default:
                                return formatJson(agentResult.output || {});
                            }
                          })()}
                        </pre>
                      </div>
                    </div>
                  </div>
                ))}
              </div>
            </div>
          </div>
        </section>
      )}
    </div>
  )
} 