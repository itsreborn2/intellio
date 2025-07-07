/**
 * LatestUpdates.tsx
 * 인기 검색 종목 순위 컴포넌트
 */
'use client';

import React from 'react';
import { StockOption } from '../types';
import { useIsMobile } from '../hooks';
import { 
  ArrowBigUp,
  ArrowBigDown,
  Minus,
  // Sparkle, // Removed as NEW type will no longer display an icon
} from 'lucide-react'; // 아이콘 임포트

// 인기 검색 종목 인터페이스 정의
interface PopularStock {
  stock: StockOption;
  rank: number;
  rankChange?: {
    change_type: 'UP' | 'DOWN' | 'SAME' | 'NEW' | 'OUT';
    change_value: number;
    previous_rank?: number;
  };
}

interface LatestUpdatesProps {
  updatesDaily: PopularStock[];
  updatesWeekly: PopularStock[];
  onSelectUpdate: (stock: StockOption, question: string) => void;
}

export function LatestUpdates({ updatesDaily, updatesWeekly, onSelectUpdate }: LatestUpdatesProps) {
  const isMobile = useIsMobile();



  // 순위 변동 텍스트 및 아이콘 생성 함수
  const getRankChangeInfo = (rankChange?: PopularStock['rankChange']) => {
    if (!rankChange) return null;

    const { change_type, change_value } = rankChange;

    switch (change_type) {
      case 'NEW':
        return { text: 'NEW', Icon: null, color: '#10b981', size: 14, change_type, iconFill: 'none' }; // 초록색, 아이콘 없음, 내부 채우지 않음
      case 'UP':
        return { text: `${Math.abs(change_value)}`, Icon: ArrowBigUp, color: '#ef4444', size: 14, change_type, iconFill: '#ef4444' }; // 빨간색 (상승), 내부 채움
      case 'DOWN':
        return { text: `${Math.abs(change_value)}`, Icon: ArrowBigDown, color: '#3b82f6', size: 14, change_type, iconFill: '#3b82f6' }; // 파란색 (하락), 내부 채움
      case 'SAME':
        return { text: '-', Icon: Minus, color: '#999999', size: 11, change_type, iconFill: 'none', strokeWidth: 2.4 }; // 아이콘 두께 추가
      default:
        return null; // 변동 없거나 'OUT'이면 표시하지 않음
    }
  };

  const renderStockList = (stocks: PopularStock[]) => {
    return stocks.map((item) => {
      const rankChangeDisplayInfo = getRankChangeInfo(item.rankChange);

      return (
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
            transition: 'background-color 0.2s, color 0.2s',
            fontSize: '13px',
            color: '#333',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'space-between', // 양 끝으로 정렬
            overflow: 'hidden',
          }}
          onClick={() => onSelectUpdate(item.stock, '')}
          onMouseEnter={(e) => {
            e.currentTarget.style.color = '#ffffff';
            e.currentTarget.style.backgroundColor = '#40414F';
            const iconElement = e.currentTarget.querySelector('svg.rank-change-icon'); // Corrected selector
            if (iconElement && rankChangeDisplayInfo) {
              (iconElement as HTMLElement).style.stroke = '#ffffff';
              if (rankChangeDisplayInfo.iconFill !== 'none') {
                (iconElement as HTMLElement).style.fill = '#ffffff';
              }
            }
            const rankTextElement = e.currentTarget.querySelector('.rank-change-text');
            if (rankTextElement) {
              (rankTextElement as HTMLElement).style.color = '#ffffff';
            }
            // rank-dot과 stock-name-text는 color: inherit으로 인해 자동으로 변경됨
          }}
          onMouseLeave={(e) => {
            e.currentTarget.style.color = '#333';
            e.currentTarget.style.backgroundColor = '#f5f5f5';
            const iconElement = e.currentTarget.querySelector('svg.rank-change-icon'); // Corrected selector
            if (iconElement && rankChangeDisplayInfo) {
              (iconElement as HTMLElement).style.stroke = rankChangeDisplayInfo.color;
              if (rankChangeDisplayInfo.iconFill !== 'none') {
                (iconElement as HTMLElement).style.fill = rankChangeDisplayInfo.iconFill;
              }
            }
            const rankTextElement = e.currentTarget.querySelector('.rank-change-text');
            if (rankTextElement && rankChangeDisplayInfo) { // rankChangeDisplayInfo null 체크 추가
              (rankTextElement as HTMLElement).style.color = rankChangeDisplayInfo.color;
            }
            // rank-dot과 stock-name-text는 color: inherit으로 인해 자동으로 변경됨
          }}
        >
          {/* 순위 숫자와 종목명을 묶는 그룹 */}
          <div style={{ display: 'flex', alignItems: 'center', overflow: 'hidden', flexShrink: 1, marginRight: '6px' }}>
            <span className="rank-dot" style={{ 
              fontSize: '13px',
              color: 'inherit', 
              whiteSpace: 'nowrap',
              marginRight: '6px' 
            }}>
              {item.rank}.
            </span>
            <span className="stock-name-text" style={{ 
              padding: '3px 8px',
              height: '24px',
              borderRadius: '6px',
              border: '1px solid #ddd',
              backgroundColor: 'inherit', 
              color: 'inherit', 
              fontSize: '13px',
              fontWeight: 'normal',
              whiteSpace: 'nowrap',
              display: 'flex',
              alignItems: 'center',
              overflow: 'hidden',
              textOverflow: 'ellipsis',
            }}>
              {item.stock.stockName}
            </span>
          </div>

          {/* 순위 변동 아이콘/텍스트 그룹 */}
          {rankChangeDisplayInfo && (
            <div style={{ display: 'flex', alignItems: 'center', color: rankChangeDisplayInfo.color, flexShrink: 0 }}>
              {rankChangeDisplayInfo.Icon && (
                <rankChangeDisplayInfo.Icon 
                  className="rank-change-icon" 
                  size={rankChangeDisplayInfo.size} 
                  style={{ 
                    marginRight: (rankChangeDisplayInfo.change_type === 'UP' || rankChangeDisplayInfo.change_type === 'DOWN') ? '2px' : '0px' 
                  }} 
                  fill={rankChangeDisplayInfo.iconFill}
                  strokeWidth={rankChangeDisplayInfo.strokeWidth}
                />
              )}
              {(rankChangeDisplayInfo.change_type === 'UP' || rankChangeDisplayInfo.change_type === 'DOWN' || rankChangeDisplayInfo.change_type === 'NEW') && (
                <span 
                  className="rank-change-text" 
                  style={{ 
                    fontSize: rankChangeDisplayInfo.change_type === 'NEW' ? '8px' : '11px', 
                    fontWeight: '500' 
                  }}
                >
                  {rankChangeDisplayInfo.text}
                </span>
              )}
            </div>
          )}
        </button>
      );
    });
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
      // 모바일에서 입력창에 가려지는 것 방지를 위한 추가 속성
      marginBottom: isMobile ? '60px' : '0',
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