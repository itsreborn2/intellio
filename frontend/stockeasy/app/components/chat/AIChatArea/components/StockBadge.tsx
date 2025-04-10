/**
 * StockBadge.tsx
 * 입력 필드에 선택된 종목을 표시하는 배지 컴포넌트
 */
'use client';

import { StockOption } from '../types';
import { useIsMobile } from '../hooks';

interface StockBadgeProps {
  stock: StockOption;
  isProcessing: boolean;
  onClick: () => void;
}

export function StockBadge({ stock, isProcessing, onClick }: StockBadgeProps) {
  const isMobile = useIsMobile();
  
  return (
    <div 
      style={{
        display: 'flex',
        alignItems: 'center',
        padding: '4px 10px',
        margin: '0 0 0 8px',
        height: '26px',
        borderRadius: '6px',
        border: '1px solid #ddd',
        backgroundColor: '#3F424A',
        color: '#F4F4F4',
        fontSize: '0.7rem',
        fontWeight: 'normal',
        whiteSpace: 'nowrap',
        cursor: isProcessing ? 'not-allowed' : 'pointer'
      }}
      onClick={(e) => {
        if (isProcessing) {
          e.preventDefault();
          return;
        }
        onClick();
      }}
      title="클릭하여 종목 변경"
    >
      {stock.stockName}
    </div>
  );
}

export default StockBadge; 