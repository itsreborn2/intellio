"use client";

import React from "react";
import {
  Card, 
  CardContent, 
  CardHeader, 
  CardTitle 
} from 'intellio-common/components/ui/card';
import Plot from "react-plotly.js";
import { cn } from 'intellio-common/lib/utils'; 

interface ChartCardProps {
  title?: string;
  plotData: Plotly.Data[];
  plotLayout: Partial<Plotly.Layout>;
  plotConfig?: Partial<Plotly.Config>;
  plotStyle?: React.CSSProperties;
  containerClassName?: string;
  titleClassName?: string;
}

/**
 * 차트 카드 컴포넌트
 * Plotly 차트를 표시하는 재사용 가능한 카드 컴포넌트입니다.
 * 공간 활용을 최대화하고 여백을 최소화하여 데이터 가시성을 향상시킵니다.
 */
const ChartCard: React.FC<ChartCardProps> = ({
  title,
  plotData,
  plotLayout,
  plotConfig,
  // 기본 높이를 300px로 통일하여 일관된 레이아웃 유지
  plotStyle = { width: "100%", height: "300px" },
  // 여백을 최소화하여 더 많은 공간 활용
  containerClassName,
  // 제목 여백 최소화 (mb-2 → mb-1)
  titleClassName = "font-semibold mb-1 text-center text-sm",
}) => {
  return (
    <div className="px-0 mb-0 w-full"> {/* 좌우 여백 제거 */}
      {title && <h3 className={cn(titleClassName)}>{title}</h3>}
      <div style={plotStyle} className={cn("h-full", containerClassName)}>
        <Plot
          data={plotData}
          layout={{
            ...plotLayout,
            margin: { l: 50, r: 30, t: 10, b: 40 }, // 차트 내부 여백 최적화
          }}
          config={plotConfig}
          style={{ width: "100%", height: "100%" }}
        />
      </div>
    </div>
  );
};

export default ChartCard;
