// 미니 캔들 차트(1봉) 컴포넌트
// 시가, 고가, 저가, 종가를 받아 SVG로 미니 캔들차트(봉차트)를 그림
import * as React from 'react';

interface CandleMiniProps {
  open: number;
  high: number;
  low: number;
  close: number;
  width?: number; // 기본값 28
  height?: number; // 기본값 44
}

/**
 * 미니 캔들 차트: SVG로 1봉만 그림 (시가, 고가, 저가, 종가)
 * - 상승(양봉): 빨간색, 하락(음봉): 파란색
 * - open, close가 같으면 회색
 */
export function CandleMini({ open, high, low, close, width = 28, height = 44 }: CandleMiniProps) {
  // 가격이 모두 유효한지 확인
  if ([open, high, low, close].some(v => typeof v !== 'number' || isNaN(v))) {
    return <svg width={width} height={height}></svg>;
  }

  // min/max로 정규화
  const maxPrice = Math.max(open, high, low, close);
  const minPrice = Math.min(open, high, low, close);
  const priceRange = maxPrice - minPrice || 1;

  // y좌표 변환 함수 (가격이 높을수록 y가 작아짐)
  const priceToY = (price: number) => {
    return ((maxPrice - price) / priceRange) * (height - 8) + 4;
  };

  // 캔들 색상
  // ChartComponent.tsx와 동일한 캔들 색상 사용
  let color = '#888';
  if (close > open) color = '#F87171'; // 상승(양봉): Tailwind Red 400
  else if (close < open) color = '#60A5FA'; // 하락(음봉): Tailwind Blue 400

  // 캔들 바 위치
  const barY = Math.min(priceToY(open), priceToY(close));
  const barHeight = Math.abs(priceToY(open) - priceToY(close)) || 2;

  return (
    <svg width={width} height={height} viewBox={`0 0 ${width} ${height}`}>
      {/* 윗꼬리(고가) */}
      <line x1={width/2} x2={width/2} y1={priceToY(high)} y2={barY} stroke={color} strokeWidth={2} />
      {/* 캔들 바(시가~종가) */}
      <rect x={width/2-5} y={barY} width={10} height={barHeight} fill={color} rx={2} />
      {/* 아랫꼬리(저가) */}
      <line x1={width/2} x2={width/2} y1={barY+barHeight} y2={priceToY(low)} stroke={color} strokeWidth={2} />
    </svg>
  );
}
