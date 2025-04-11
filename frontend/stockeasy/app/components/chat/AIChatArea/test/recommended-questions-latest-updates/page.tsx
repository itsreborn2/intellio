/**
 * 추천질문과 최신 업데이트 종목 컴포넌트 테스트 페이지
 */
'use client';

import React, { useState, useEffect } from 'react';
import RecommendedQuestions from '../../components/RecommendedQuestions';
import LatestUpdates from '../../components/LatestUpdates';
import Link from 'next/link';
import { StockOption } from '../../types';
import { InputArea } from '../../components/InputArea';

export default function RecommendedQuestionsLatestUpdatesTestPage() {
  const [selectedQuestion, setSelectedQuestion] = useState<string | null>(null);
  const [selectedStock, setSelectedStock] = useState<StockOption | null>(null);
  const [inputMessage, setInputMessage] = useState('');
  const [isProcessing, setIsProcessing] = useState(false);
  const [showStockSuggestions, setShowStockSuggestions] = useState(false);
  const [filteredStocks, setFilteredStocks] = useState<StockOption[]>([]);
  const [recentStocks, setRecentStocks] = useState<StockOption[]>([]);
  const [searchMode, setSearchMode] = useState(false);
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [windowWidth, setWindowWidth] = useState(typeof window !== 'undefined' ? window.innerWidth : 1000);

  // 윈도우 너비 상태 업데이트
  useEffect(() => {
    function handleResize() {
      setWindowWidth(window.innerWidth);
    }
    
    window.addEventListener('resize', handleResize);
    return () => window.removeEventListener('resize', handleResize);
  }, []);

  // 샘플 추천 질문 데이터
  const sampleRecommendedQuestions = [
    {
      stock: { 
        value: '005930', 
        label: '삼성전자', 
        stockName: '삼성전자', 
        stockCode: '005930' 
      },
      question: '최근 HBM 개발 상황은?'
    },
    {
      stock: { 
        value: '000660', 
        label: 'SK하이닉스', 
        stockName: 'SK하이닉스', 
        stockCode: '000660' 
      },
      question: 'AI 반도체 시장 전망은?'
    },
    {
      stock: { 
        value: '005380', 
        label: '현대차', 
        stockName: '현대차', 
        stockCode: '005380' 
      },
      question: '전기차 시장에서의 경쟁력은?'
    },
    {
      stock: { 
        value: '051910', 
        label: 'LG에너지솔루션', 
        stockName: 'LG에너지솔루션', 
        stockCode: '051910' 
      },
      question: '배터리 기술 개발 현황은?'
    },
    {
      stock: { 
        value: '035420', 
        label: 'NAVER', 
        stockName: 'NAVER', 
        stockCode: '035420' 
      },
      question: '인공지능 사업 확장과 전망은?'
    }
  ];

  // 샘플 최신 업데이트 종목 데이터
  const sampleLatestUpdates = [
    {
      stock: { 
        value: '051910', 
        label: 'LG에너지솔루션', 
        stockName: 'LG에너지솔루션', 
        stockCode: '051910' 
      },
      updateInfo: '배터리 생산량 증대'
    },
    {
      stock: { 
        value: '035720', 
        label: '카카오', 
        stockName: '카카오', 
        stockCode: '035720' 
      },
      updateInfo: '글로벌 AI 기업과 협력 발표'
    },
    {
      stock: { 
        value: '373220', 
        label: '우진플라임', 
        stockName: '우진플라임', 
        stockCode: '373220' 
      },
      updateInfo: '발전소 수주 확대 소식'
    }
  ];

  // 질문 선택 핸들러
  const handleSelectQuestion = (stock: StockOption, question: string) => {
    setSelectedStock(stock);
    setSelectedQuestion(question);
    setInputMessage(question);
    setShowStockSuggestions(false);
  };

  // 업데이트 선택 핸들러
  const handleSelectUpdate = (stock: StockOption, updateInfo: string) => {
    setSelectedStock(stock);
    setSelectedQuestion(updateInfo);
    setInputMessage(updateInfo);
    setShowStockSuggestions(false);
  };

  // 메시지 전송 핸들러 (테스트용)
  const handleSendMessage = () => {
    if (selectedStock && inputMessage.trim()) {
      alert(`종목: ${selectedStock.stockName}(${selectedStock.stockCode})\n질문: ${inputMessage}`);
      setInputMessage('');
    }
  };

  return (
    <div style={{ 
      padding: '40px', 
      maxWidth: '800px', 
      margin: '0 auto',
      fontFamily: 'Arial, sans-serif'
    }}>
      <div style={{ marginBottom: '30px', display: 'flex', alignItems: 'center' }}>
        <Link href="/components/chat/AIChatArea/test" style={{ 
          marginRight: '15px', 
          color: '#1971c2', 
          textDecoration: 'none',
          fontSize: '14px'
        }}>
          ← 테스트 메인으로 돌아가기
        </Link>
        <h1 style={{ margin: '0', color: '#333' }}>추천질문 & 최신 업데이트 종목 테스트</h1>
      </div>
      
      <p style={{ marginBottom: '20px', color: '#555', fontSize: '16px', lineHeight: '1.5' }}>
        추천질문과 최신 업데이트 종목 컴포넌트의 기능과 렌더링을 테스트할 수 있습니다.
      </p>

      {/* 선택된 항목 표시 영역 */}
      {(selectedQuestion || selectedStock) && (
        <div style={{ 
          padding: '15px', 
          backgroundColor: '#f8f9fa', 
          border: '1px solid #e9ecef', 
          borderRadius: '8px', 
          marginBottom: '20px' 
        }}>
          <h3 style={{ margin: '0 0 10px 0', color: '#333', fontSize: '16px' }}>선택된 항목:</h3>
          {selectedStock && (
            <p style={{ margin: '0 0 5px 0', fontSize: '14px' }}>
              <strong>종목:</strong> {selectedStock.stockName} ({selectedStock.stockCode})
            </p>
          )}
          {selectedQuestion && (
            <p style={{ margin: '0', fontSize: '14px' }}>
              <strong>질문/정보:</strong> {selectedQuestion}
            </p>
          )}
        </div>
      )}
      
      {/* 추천질문과 최신 업데이트 종목 컨테이너 */}
      <div style={{ 
        display: 'flex', 
        flexDirection: 'row', 
        gap: '20px',
        flexWrap: 'wrap',
        marginBottom: '30px'
      }}>
        <div style={{ width: '48%', minWidth: '300px', flex: '1' }}>
          <RecommendedQuestions 
            questions={sampleRecommendedQuestions} 
            onSelectQuestion={handleSelectQuestion} 
          />
        </div>
        
        <div style={{ width: '48%', minWidth: '300px', flex: '1' }}>
          <LatestUpdates 
            updates={sampleLatestUpdates} 
            onSelectUpdate={handleSelectUpdate} 
          />
        </div>
      </div>

      {/* 채팅 입력창 */}
      <div style={{ 
        padding: '15px', 
        backgroundColor: '#f8f9fa', 
        border: '1px solid #e9ecef', 
        borderRadius: '8px', 
        marginTop: '30px',
        marginBottom: '20px'
      }}>
        <h3 style={{ margin: '0 0 15px 0', color: '#333', fontSize: '16px' }}>채팅 입력창:</h3>
        <InputArea
          inputMessage={inputMessage}
          setInputMessage={setInputMessage}
          selectedStock={selectedStock}
          isProcessing={isProcessing}
          isInputCentered={false}
          showStockSuggestions={showStockSuggestions}
          filteredStocks={filteredStocks}
          recentStocks={recentStocks}
          searchMode={searchMode}
          isLoading={isLoading}
          error={error}
          windowWidth={windowWidth}
          onSendMessage={handleSendMessage}
          onStockSelect={setSelectedStock}
          onShowStockSuggestions={setShowStockSuggestions}
          onSearchModeChange={setSearchMode}
          onClearRecentStocks={() => setRecentStocks([])}
        />
      </div>
    </div>
  );
} 