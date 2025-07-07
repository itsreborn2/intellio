/**
 * RecommendedQuestions.tsx
 * 추천 질문 컴포넌트
 */
'use client';

import React, { useState, useEffect } from 'react';
import { StockOption } from '../types';
import { useIsMobile } from '../hooks';
import QuestionButton from './QuestionButton';

interface RecommendedQuestion {
  stock: StockOption;
  question: string;
}

interface RecommendedQuestionsProps {
  onSelectQuestion: (stock: StockOption, question: string) => void;
}

interface CSVData {
  stockCode: string;
  stockName: string;
  question: string;
}

export function RecommendedQuestions({ onSelectQuestion }: RecommendedQuestionsProps) {
  const isMobile = useIsMobile();
  const [recommendedQuestions, setRecommendedQuestions] = useState<RecommendedQuestion[]>([]);
  const [isLoading, setIsLoading] = useState<boolean>(true);
  const [error, setError] = useState<string | null>(null);
  
  useEffect(() => {
    /**
     * CSV 파일에서 추천 질문 데이터를 가져오는 함수
     */
    const fetchRecommendedQuestions = async () => {
      try {
        // CSV 파일 경로
        const csvFilePath = '/requestfile/chatarea/recomended-questions.csv';
        
        // 파일 가져오기
        const response = await fetch(csvFilePath);
        if (!response.ok) {
          throw new Error('CSV 파일을 가져오는 데 실패했습니다.');
        }
        
        // CSV 텍스트 얻기
        const csvText = await response.text();
        
        // CSV 파싱 (첫 번째 줄은 헤더로 간주)
        const lines = csvText.split('\n').filter(line => line.trim().length > 0);
        const dataLines = lines.slice(1); // 헤더 제외
        
        // 각 라인 파싱하여 RecommendedQuestion 객체로 변환
        const parsedData: RecommendedQuestion[] = dataLines.map(line => {
          // 쉼표로 구분하되, 따옴표 안의 쉼표는 무시 (정규식 사용)
          const match = line.match(/('?[^,]*),([^,]*),(.*)/); 
          
          if (match) {
            const stockCode = match[1].replace(/^'/, ''); // 앞에 붙은 작은따옴표 제거
            const stockName = match[2];
            const question = match[3].replace(/^"|"$/g, ''); // 앞뒤 큰따옴표 제거
            
            return {
              stock: {
                stockCode,
                stockName,
                value: stockCode,
                label: stockName
              },
              question
            };
          }
          return null;
        }).filter(item => item !== null) as RecommendedQuestion[];
        
        setRecommendedQuestions(parsedData);
        setIsLoading(false);
      } catch (err) {
        console.error('추천 질문 데이터를 가져오는 중 오류 발생:', err);
        setError('데이터를 불러오지 못했습니다.');
        setIsLoading(false);
      }
    };
    
    fetchRecommendedQuestions();
  }, []);
  
  return (
    <div className="recommendation-buttons-group" style={{
      display: 'flex',
      flexDirection: 'column',
      gap: isMobile ? '6px' : '8px',
      border: '1px solid #ddd',
      borderRadius: '10px',
      padding: isMobile ? '10px 15px' : '12px',
      backgroundColor: '#ffffff',
      flex: '1',
      width: '100%',
      minWidth: 'unset',
      maxWidth: '420px',
      overflow: 'hidden',
    }}>
      <div style={{ 
        fontSize: '13px',
        marginBottom: '8px',
        color: '#333', 
        fontWeight: '500' 
      }}>
        추천 질문
      </div>
      
      {isLoading ? (
        // 스켈레톤 UI - 로딩 중에도 레이아웃이 안정적으로 유지되도록 비슷한 크기의 플레이스홀더 사용
        <>
          {[...Array(8)].map((_, index) => (
            <div 
              key={`skeleton-${index}`} 
              style={{
                height: '36px',
                borderRadius: '18px',
                backgroundColor: '#f0f0f0',
                marginBottom: '8px',
                animation: 'pulse 1.5s infinite ease-in-out',
              }}
            />
          ))}
          <style jsx>{`
            @keyframes pulse {
              0% { opacity: 0.6; }
              50% { opacity: 0.8; }
              100% { opacity: 0.6; }
            }
          `}</style>
        </>
      ) : error ? (
        <div style={{ color: 'red', padding: '10px', minHeight: '300px', display: 'flex', alignItems: 'center', justifyContent: 'center' }}>{error}</div>
      ) : recommendedQuestions.map((item, index) => (
        <QuestionButton
          key={`recommended-${index}`}
          stock={item.stock}
          question={item.question}
          onClick={() => onSelectQuestion(item.stock, item.question)}
        />
      ))}
    </div>
  );
}

export default RecommendedQuestions;