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

const ChartCard: React.FC<ChartCardProps> = ({
  title,
  plotData,
  plotLayout,
  plotConfig,
  plotStyle = { width: "100%", height: "240px" }, // 높이를 300px에서 240px로 변경
  containerClassName,
  titleClassName = "font-semibold mb-2 text-center text-sm",
}) => {
  return (
    <div>
      {title && <h3 className={cn(titleClassName)}>{title}</h3>}
      <div style={plotStyle} className={cn(containerClassName)}>
        <Plot
          data={plotData}
          layout={plotLayout}
          config={plotConfig}
          style={{ width: "100%", height: "100%" }}
        />
      </div>
    </div>
  );
};

export default ChartCard;
