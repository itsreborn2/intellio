/**
 * QuestionButton.tsx
 * 추천 질문 버튼 컴포넌트
 */
'use client';

import React from 'react';
import { StockOption } from '../types';
import { useIsMobile } from '../hooks';

interface QuestionButtonProps {
  stock: StockOption;
  question: string;
  onClick: () => void;
}

export function QuestionButton({ stock, question, onClick }: QuestionButtonProps) {
  const isMobile = useIsMobile();
  
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
        overflow: 'hidden',
      }}
      onMouseEnter={(e) => {
        e.currentTarget.style.color = '#ffffff';
        e.currentTarget.style.backgroundColor = '#40414F';
      }}
      onMouseLeave={(e) => {
        e.currentTarget.style.color = '#333';
        e.currentTarget.style.backgroundColor = '#f5f5f5';
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
        alignItems: 'center',
        flexShrink: 0,
        maxWidth: '30%',
        overflow: 'hidden',
        textOverflow: 'ellipsis',
      }}>
        {stock.stockName}
      </span>
      <span style={{
        overflow: 'hidden',
        textOverflow: 'ellipsis',
        whiteSpace: 'nowrap',
        flexShrink: 1,
        minWidth: 0,
      }}>
        {question}
      </span>
    </button>
  );
}

export default QuestionButton; 