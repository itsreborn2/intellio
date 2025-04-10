/**
 * RecommendedQuestions.tsx
 * 추천 질문 컴포넌트
 */
'use client';

import React from 'react';
import { StockOption } from '../types';
import { useIsMobile } from '../hooks';
import QuestionButton from './QuestionButton';

interface RecommendedQuestion {
  stock: StockOption;
  question: string;
}

interface RecommendedQuestionsProps {
  questions: RecommendedQuestion[];
  onSelectQuestion: (stock: StockOption, question: string) => void;
}

export function RecommendedQuestions({ questions, onSelectQuestion }: RecommendedQuestionsProps) {
  const isMobile = useIsMobile();
  
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
      
      {questions.map((item, index) => (
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