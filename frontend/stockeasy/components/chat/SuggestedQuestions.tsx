'use client'

import { SuggestedQuestionsProps, StockOption } from './types'

// 추천 질문 데이터
const RECOMMENDED_QUESTIONS = [
  { 
    stock: { value: '005930', label: '삼성전자', stockName: '삼성전자', stockCode: '005930', display: '삼성전자 (005930)' },
    question: '최근 HBM 개발 상황 및 경쟁사와의 비교'
  },
  { 
    stock: { value: '000660', label: 'SK하이닉스', stockName: 'SK하이닉스', stockCode: '000660', display: 'SK하이닉스 (000660)' },
    question: 'AI 반도체 시장 진출 전략과 향후 전망'
  },
  { 
    stock: { value: '005380', label: '현대차', stockName: '현대차', stockCode: '005380', display: '현대차 (005380)' },
    question: '전기차 시장에서의 경쟁력과 최근 실적 분석'
  },
  { 
    stock: { value: '373220', label: 'LG에너지솔루션', stockName: 'LG에너지솔루션', stockCode: '373220', display: 'LG에너지솔루션 (373220)' },
    question: '배터리 기술 개발 현황 및 글로벌 시장 점유율'
  },
  { 
    stock: { value: '035420', label: 'NAVER', stockName: 'NAVER', stockCode: '035420', display: 'NAVER (035420)' },
    question: '인공지능 사업 확장과 해외 시장 진출 전략'
  }
]

// 최신 업데이트 질문 데이터
const LATEST_UPDATES = [
  { 
    stock: { value: '373220', label: 'LG에너지솔루션', stockName: 'LG에너지솔루션', stockCode: '373220', display: 'LG에너지솔루션 (373220)' },
    question: '배터리 생산량 1분기 32% 증가, 전기차 시장 확대로 실적 개선 전망'
  },
  { 
    stock: { value: '035720', label: '카카오', stockName: '카카오', stockCode: '035720', display: '카카오 (035720)' },
    question: '글로벌 AI 기업과 협력 발표, 생성형 AI 기술 통합으로 시장 점유율 확대 계획'
  }
]

export default function SuggestedQuestions({ 
  onStockSelect, 
  setInputMessage, 
  recentStocks, 
  setRecentStocks,
  isMobile 
}: SuggestedQuestionsProps) {
  
  // 종목과 질문 선택 처리
  const handleSelectQuestion = (stock: StockOption, question: string) => {
    // 종목 선택
    onStockSelect(stock)
    
    // 질문 설정
    setInputMessage(question)
    
    // 최근 조회 종목에 추가
    const updatedRecentStocks = [
      stock, 
      ...recentStocks.filter(s => s.value !== stock.value)
    ].slice(0, 5)
    
    setRecentStocks(updatedRecentStocks)
    
    // 로컬 스토리지에 저장
    try {
      localStorage.setItem('recentStocks', JSON.stringify(updatedRecentStocks))
    } catch (error) {
      console.error('Failed to save recent stocks to localStorage:', error)
    }
  }

  return (
    <div style={{
      width: isMobile ? '100%' : '57.6%', 
      margin: isMobile ? '50px auto 0' : '12px auto 0',
      padding: '0',
      display: 'flex',
      flexDirection: isMobile ? 'column' : 'row',
      gap: '8px'
    }}>
      <div style={{
        display: 'flex',
        flexDirection: isMobile ? 'column' : 'row',
        gap: isMobile ? '6px' : '8px',
        width: '100%'
      }}>
        {/* 추천 질문 그룹 */}
        <QuestionGroup 
          title="추천 질문" 
          questions={RECOMMENDED_QUESTIONS}
          onSelect={handleSelectQuestion}
          isMobile={isMobile}
        />
        
        {/* 최신 업데이트 종목 그룹 */}
        <QuestionGroup 
          title="최신 업데이트 종목" 
          questions={LATEST_UPDATES}
          onSelect={handleSelectQuestion}
          isMobile={isMobile}
        />
      </div>
    </div>
  )
}

// 질문 그룹 컴포넌트
interface QuestionGroupProps {
  title: string
  questions: Array<{stock: StockOption, question: string}>
  onSelect: (stock: StockOption, question: string) => void
  isMobile: boolean
}

function QuestionGroup({ title, questions, onSelect, isMobile }: QuestionGroupProps) {
  return (
    <div className="question-group" style={{
      display: 'flex',
      flexDirection: 'column',
      gap: isMobile ? '6px' : '8px',
      border: '1px solid #ddd',
      borderRadius: '10px',
      padding: isMobile ? '10px 15px' : '12px',
      backgroundColor: '#ffffff',
      flex: '1',
      width: isMobile ? '100%' : '50%',
      marginTop: isMobile && title === '최신 업데이트 종목' ? '12px' : '0'
    }}>
      <div style={{ 
        fontSize: '13px',
        marginBottom: '8px',
        color: '#333', 
        fontWeight: '500' 
      }}>
        {title}
      </div>
      
      {questions.map((item, index) => (
        <QuestionButton 
          key={`${item.stock.value}-${index}`}
          stock={item.stock}
          question={item.question}
          onClick={() => onSelect(item.stock, item.question)}
        />
      ))}
    </div>
  )
}

// 질문 버튼 컴포넌트
interface QuestionButtonProps {
  stock: StockOption
  question: string
  onClick: () => void
}

function QuestionButton({ stock, question, onClick }: QuestionButtonProps) {
  return (
    <button
      onClick={onClick}
      style={{
        width: '100%',
        padding: '6px 10px',
        borderRadius: '8px',
        border: '1px solid #ddd',
        backgroundColor: '#f5f5f5',
        textAlign: 'left',
        cursor: 'pointer',
        transition: 'background-color 0.2s',
        fontSize: '13px',
        color: '#333',
        display: 'flex',
        alignItems: 'center',
        gap: '6px',
      }}
      onMouseEnter={(e) => {
        e.currentTarget.style.color = '#ffffff'
        e.currentTarget.style.backgroundColor = '#40414F'
      }}
      onMouseLeave={(e) => {
        e.currentTarget.style.color = '#333'
        e.currentTarget.style.backgroundColor = '#f5f5f5'
      }}
    >
      <span style={{
        padding: '3px 8px',
        height: '24px',
        borderRadius: '6px',
        border: '1px solid #ddd',
        backgroundColor: '#f5f5f5',
        color: '#333',
        fontSize: '13px',
        fontWeight: 'normal',
        whiteSpace: 'nowrap',
        display: 'flex',
        alignItems: 'center'
      }}>
        {stock.stockName}
      </span>
      <span style={{
        overflow: 'hidden',
        textOverflow: 'ellipsis',
        whiteSpace: 'nowrap',
        maxWidth: '100%'
      }}>
        {question}
      </span>
    </button>
  )
} 