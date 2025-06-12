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
  updatesDaily: PopularStock[];
  updatesWeekly: PopularStock[];
  onSelectUpdate: (stock: StockOption, question: string) => void;
}

export function LatestUpdates({ updatesDaily, updatesWeekly, onSelectUpdate }: LatestUpdatesProps) {
  const isMobile = useIsMobile();

  const renderStockList = (stocks: PopularStock[]) => {
    return stocks.map((item) => (
      <button
        key={`rank-${item.rank}-${item.stock.stockCode}`}
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
          overflow: 'hidden',
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
          textOverflow: 'ellipsis',
        }}>
          {item.stock.stockName}
        </span>
      </button>
    ));
  };

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
      <div style={{ display: 'flex', gap: '12px', alignItems: 'baseline', marginBottom: '8px' }}>
        {/* Column 1 */}
        <div style={{ flex: 1, display: 'flex', justifyContent: 'space-between', alignItems: 'baseline', paddingRight: '10px' }}>
          <span style={{ fontSize: '13px', color: '#333', fontWeight: '500' }}>
            검색 순위
          </span>
          <span style={{ fontSize: '12px', color: '#888', fontWeight: '500' }}>
            당일
          </span>
        </div>
        {/* Column 2 */}
        <div style={{ flex: 1, display: 'flex', justifyContent: 'flex-end', alignItems: 'baseline', paddingRight: '10px' }}>
          <span style={{ fontSize: '12px', color: '#888', fontWeight: '500' }}>
            일주일
          </span>
        </div>
      </div>
      <div style={{ display: 'flex', gap: '12px' }}>
        {/* 첫 번째 열: 당일 */}
        <div style={{ flex: 1, display: 'flex', flexDirection: 'column', gap: '8px' }}>
          {renderStockList(updatesDaily)}
        </div>
        
        {/* 두 번째 열: 일주일 */}
        <div style={{ flex: 1, display: 'flex', flexDirection: 'column', gap: '8px' }}>
          {renderStockList(updatesWeekly)}
        </div>
      </div>
    </div>
  );
}

export default LatestUpdates;