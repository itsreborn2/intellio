/**
 * LatestUpdates.tsx
 * 인기 검색 종목 순위 컴포넌트
 */
'use client';

import React from 'react';
import { StockOption } from '../types';
import { useIsMobile } from '../hooks';

// 인기 검색 종목 인터페이스 정의
interface PopularStock {
  stock: StockOption;
  rank: number;
}

interface LatestUpdatesProps {
  updates: PopularStock[];
  onSelectUpdate: (stock: StockOption, question: string) => void;
}

export function LatestUpdates({ updates, onSelectUpdate }: LatestUpdatesProps) {
  const isMobile = useIsMobile();
  
  const top20Stocks = updates.slice(0, 20);
  const firstColumn = top20Stocks.slice(0, 10); 
  const secondColumn = top20Stocks.slice(10, 20);
  
  return (
    <div className="latest-updates-group" style={{
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
        인기 검색 종목 순위
      </div>
      
      <div style={{ display: 'flex', gap: '8px' }}>
        {/* 첫 번째 열: 1-5위 */}
        <div style={{ flex: 1, display: 'flex', flexDirection: 'column', gap: '8px' }}>
          {firstColumn.map((item) => (
            <button 
              key={`rank-${item.rank}`}
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
                overflow: 'hidden'
              }}
              onClick={() => onSelectUpdate(item.stock, '')}
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
                fontSize: '13px',
                color: '#333',
                whiteSpace: 'nowrap',
                overflow: 'hidden',
                textOverflow: 'ellipsis',
                marginRight: '6px'
              }}>
                {item.rank}.
              </span>
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
                maxWidth: '70%', 
                overflow: 'hidden',
                textOverflow: 'ellipsis'
              }}>
                {item.stock.stockName}
              </span>
            </button>
          ))}
        </div>
        
        {/* 두 번째 열: 6-10위 */}
        <div style={{ flex: 1, display: 'flex', flexDirection: 'column', gap: '8px' }}>
          {secondColumn.map((item) => (
            <button 
              key={`rank-${item.rank}`}
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
                overflow: 'hidden'
              }}
              onClick={() => onSelectUpdate(item.stock, '')}
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
                fontSize: '13px',
                color: '#333',
                whiteSpace: 'nowrap',
                overflow: 'hidden',
                textOverflow: 'ellipsis',
                marginRight: '6px'
              }}>
                {item.rank}.
              </span>
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
                maxWidth: '70%', 
                overflow: 'hidden',
                textOverflow: 'ellipsis'
              }}>
                {item.stock.stockName}
              </span>
            </button>
          ))}
        </div>
      </div>
    </div>
  );
}

export default LatestUpdates;