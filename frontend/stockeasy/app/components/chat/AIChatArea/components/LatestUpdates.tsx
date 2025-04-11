/**
 * LatestUpdates.tsx
 * 최신 업데이트 종목 컴포넌트
 */
'use client';

import React from 'react';
import { StockOption } from '../types';
import { useIsMobile } from '../hooks';
import QuestionButton from './QuestionButton';

interface StockUpdate {
  stock: StockOption;
  updateInfo: string;
}

interface LatestUpdatesProps {
  updates: StockUpdate[];
  onSelectUpdate: (stock: StockOption, updateInfo: string) => void;
}

export function LatestUpdates({ updates, onSelectUpdate }: LatestUpdatesProps) {
  const isMobile = useIsMobile();
  
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
        최신 업데이트
      </div>
      
      {updates.map((item, index) => (
        <QuestionButton
          key={`update-${index}`}
          stock={item.stock}
          question={item.updateInfo}
          onClick={() => onSelectUpdate(item.stock, item.updateInfo)}
        />
      ))}
    </div>
  );
}

export default LatestUpdates; 