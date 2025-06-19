/**
 * MessageComponentRenderer.tsx
 * 구조화된 메시지 컴포넌트를 렌더링하는 컴포넌트
 */
'use client';

import React, { useState, CSSProperties } from 'react';
import { 
  MessageComponent, 
  IBarChartComponent, 
  ILineChartComponent,
  IMixedChartComponent,
  IPriceChartComponent,
  ITechnicalIndicatorChartComponent
} from '../types/chat';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import remarkBreaks from 'remark-breaks';
import { 
  LineChart, Line, BarChart, Bar, XAxis, YAxis, CartesianGrid, 
  Tooltip, Legend, ResponsiveContainer, ComposedChart, Area,
  Cell, Sector, PieChart, Pie, RadialBarChart, RadialBar, ReferenceArea
} from 'recharts';
import { createChart, ColorType, LineStyle, CandlestickSeries, HistogramSeries, LineSeries, AreaSeries, Time } from 'lightweight-charts';
import { useMediaQuery } from '../hooks';

// PreliminaryChartData 인터페이스 정의
interface PreliminaryChartData {
  components: MessageComponent[];
  message: string;
  timestamp: number;
  stockCode: string;
  stockName: string;
}

// 차트 색상 테마 정의
const CHART_COLORS = [
  '#4285F4', '#34A853', '#FBBC05', '#EA4335', 
  '#8C9EFF', '#1DE9B6', '#FFAB40', '#FF5252',
  '#7C4DFF', '#00E5FF', '#EEFF41', '#FF4081'
];

// 차트 그라데이션 정의
const CHART_GRADIENTS = {
  blue: ['#4285F4', '#8C9EFF'],
  green: ['#34A853', '#1DE9B6'],
  yellow: ['#FBBC05', '#FFAB40'],
  red: ['#EA4335', '#FF5252'],
  purple: ['#7C4DFF', '#B388FF'],
  cyan: ['#00E5FF', '#84FFFF'],
  lime: ['#EEFF41', '#B2FF59'],
  pink: ['#FF4081', '#FF80AB'],
};

// Tooltip 타입 정의
interface CustomTooltipProps {
  active?: boolean;
  payload?: Array<{
    name: string;
    value: number | string;
    color: string;
  }>;
  label?: string;
  valuePrefix?: string;
  valueSuffix?: string;
}

// 커스텀 툴팁 컴포넌트
const CustomTooltip: React.FC<CustomTooltipProps> = ({ 
  active, 
  payload, 
  label, 
  valuePrefix = '', 
  valueSuffix = '' 
}) => {
  if (active && payload && payload.length) {
    return (
      <div style={{ 
        backgroundColor: 'rgba(255, 255, 255, 0.95)', 
        border: '1px solid #ddd', 
        padding: '10px', 
        borderRadius: '8px',
        boxShadow: '0 2px 10px rgba(0, 0, 0, 0.15)'
      }}>
        <p style={{ margin: '0 0 5px 0', fontWeight: 'bold' }}>{label}</p>
        {payload.map((entry, index) => (
          <p key={`tooltip-${index}`} style={{ 
            margin: '0', 
            color: entry.color,
            display: 'flex',
            justifyContent: 'space-between' 
          }}>
            <span style={{ marginRight: '10px', fontWeight: 500 }}>{entry.name}: </span>
            <span style={{ fontWeight: 'bold' }}>
              {valuePrefix}{typeof entry.value === 'number' ? entry.value.toLocaleString() : entry.value}{valueSuffix}
            </span>
          </p>
        ))}
      </div>
    );
  }
  return null;
};

// 커스텀 X축 틱 렌더링 함수 추가
const CustomXAxisTick = (props: any) => {
  const { x, y, payload, fontSize, isMobile, isChartPair } = props;
  
  return (
    <g transform={`translate(${x},${y})`}>
      <text
        x={0}
        y={16}
        textAnchor="middle"
        fill="#333"
        fontSize={fontSize || (isMobile ? '0.75em' : (isChartPair ? '0.75em' : '0.75em'))}
        fontWeight={500}
      >
        {payload.value}
      </text>
    </g>
  );
};

interface MessageComponentRendererProps {
  component: MessageComponent;
  nextComponent?: MessageComponent; // 다음 컴포넌트 정보 추가
  isFirstInPair?: boolean; // 2열 배치에서 첫 번째 컴포넌트인지 여부
  isChartPair?: boolean; // 차트 쌍의 일부인지 여부
}

export function MessageComponentRenderer({ 
  component, 
  nextComponent,
  isFirstInPair = false,
  isChartPair = false 
}: MessageComponentRendererProps) {
  // 모바일 환경 감지
  const isMobile = useMediaQuery('mobile');
  
  // 차트 인터랙션 상태
  const [activeIndex, setActiveIndex] = useState<number>(-1);
  
  // 컴포넌트 타입에 따라 다른 렌더링 로직 적용
  switch (component.type as string) {
    case 'heading': {
      const { level, content } = component as any;
      //console.log(`lv ${level} - ${content}`);
      // 헤딩 레벨에 따라 적절한 스타일 적용
      const styles: React.CSSProperties = {
        fontWeight: 'bold',
        lineHeight: 1.3,
        margin: level === 1 ? '0.4em 0 0.2em 0' :
                level === 2 ? '0.8em 0 0.2em 0' :  // level 2는 위쪽 여백을 더 크게
                level === 3 ? '0.5em 0 0.2em 0' :
                level === 4 ? '0.4em 0 0.2em 0' :
                level === 5 ? '0.4em 0 0.2em 0' : '0.4em 0 0.2em 0',
        fontSize: level === 1 ? '2em' :
                 level === 2 ? '1.75em' :
                 level === 3 ? '1.4em' :
                 level === 4 ? '1.25em' :
                 level === 5 ? '1.1em' : '1em'
      };
      
      return <div style={styles}>{content}</div>;
    }
    
    case 'paragraph': {
      const { content } = component as any;
      return (
        <div style={{  
                    fontSize: '1.1em',
                    paddingLeft: '0.5em',
                   }}>
          <ReactMarkdown
            remarkPlugins={[remarkGfm, remarkBreaks]}
          >
            {content}
          </ReactMarkdown>
        </div>
      );
    }
    
    case 'list': {
      const { ordered, items } = component as any;
      
      if (ordered) {
        return (
          <ol style={{ paddingLeft: '1.5em', margin: '0.5em 0',fontSize: '1.1em' }}>
            {items.map((item: any, index: number) => (
              <li key={index} style={{ margin: '0.25em 0' }}>
                <ReactMarkdown remarkPlugins={[remarkGfm, remarkBreaks]}>
                  {item.content}
                </ReactMarkdown>
              </li>
            ))}
          </ol>
        );
      }
      
      return (
        <ul style={{ listStyleType: 'none', paddingLeft: '1.5em', margin: '0.25em 0',fontSize: '1.1em' }}>
          {items.map((item: any, index: number) => (
            <li key={index} style={{ 
              margin: '0.15em 0',
              position: 'relative',
              paddingLeft: '1.2em'
            }}>
              <span style={{
                position: 'absolute',
                left: '0',
                top: '0',
                fontWeight: 'bold',
              }}>•</span>
              <ReactMarkdown remarkPlugins={[remarkGfm, remarkBreaks]}>
                {item.content}
              </ReactMarkdown>
            </li>
          ))}
        </ul>
      );
    }
    
    case 'code_block': {
      const { language, content } = component as any;
      return (
        <div style={{ margin: '1em 0' }}>
          <pre style={{ 
            padding: '1em', 
            backgroundColor: '#f5f5f5', 
            borderRadius: '5px',
            overflow: 'auto',
            fontSize: '0.9em',
            fontFamily: 'monospace' 
          }}>
            <code className={language ? `language-${language}` : ''}>
              {content}
            </code>
          </pre>
        </div>
      );
    }
    
    case 'bar_chart': {
      const { title, data } = component as any;
      
      // 컨테이너 스타일 - hover 효과를 별도 클래스로 적용
      const containerBaseStyle: CSSProperties = {
        backgroundColor: 'rgba(255, 255, 255, 0.8)',
        borderRadius: '12px',
        padding: '1em',
        boxShadow: '0 4px 12px rgba(0, 0, 0, 0.05)',
        transition: 'box-shadow 0.3s ease'
      };
      
      // 모바일 또는 2열 레이아웃에 따른 컨테이너 스타일 설정
      const containerStyle: CSSProperties = (!isMobile && isChartPair)
        ? {
            ...containerBaseStyle,
            margin: isFirstInPair ? '1em 0.5% 1em 0' : '1em 0 1em 0.5%',
            width: '49%',  // 각 차트가 49%를 차지하여 더 넓게 표시
            display: 'inline-block',
            verticalAlign: 'top'
          }
        : { 
            ...containerBaseStyle,
            margin: '1em 0', 
            width: '100%'
          };
      
      // 차트 높이 계산 (모바일이거나 2열인 경우 높이 조정)
      const chartHeight = isMobile ? 270 : (isChartPair ? 300 : 330);
      
      // 데이터 가공
      const formattedData = data.labels.map((label: string, index: number) => {
        const dataPoint: Record<string, any> = { name: label };
        
        // 각 데이터셋의 해당 인덱스 값을 추가 - 고유한 키 생성
        data.datasets.forEach((dataset: any, datasetIndex: number) => {
          // 동일한 라벨을 가진 데이터셋들을 구분하기 위해 인덱스 추가
          const uniqueKey = `${dataset.label}_${datasetIndex}`;
          dataPoint[uniqueKey] = dataset.data[index];
        });
        
        return dataPoint;
      });
      
      return (
        <div className="chart-container" style={containerStyle}>
          {title && <div style={{ 
            fontWeight: 'bold', 
            marginBottom: '0.5em',
            fontSize: '1.2em',
            textAlign: 'center',
            color: '#333'
          }}>{title}</div>}
          <ResponsiveContainer width="100%" height={chartHeight}>
            <BarChart 
              data={formattedData}
              margin={isChartPair 
                ? { top: 20, right: 30, left: 0, bottom: 15 } // 2열 배치 시 마진
                : { top: 25, right: 30, left: 0, bottom: 30 } // 1열 배치 시 마진
              }
              barCategoryGap="20%" // 카테고리 그룹 간격 추가
              barGap={3} // 막대 간 간격
              onMouseMove={(e) => {
                if (e && 'activeTooltipIndex' in e && e.activeTooltipIndex !== undefined) {
                  setActiveIndex(e.activeTooltipIndex);
                }
              }}
              onMouseLeave={() => setActiveIndex(-1)}
            >
              <CartesianGrid 
                strokeDasharray="3 3" 
                stroke="rgba(0,0,0,0.1)" 
                vertical={true} // 세로 격자선 추가
              />
              <XAxis 
                dataKey="name"
                height={20} // X축 높이 감소
                tick={<CustomXAxisTick isMobile={isMobile} isChartPair={isChartPair} />} // 커스텀 틱 적용
                tickLine={{ stroke: '#666', strokeWidth: 1.5 }}
                axisLine={{ stroke: '#666', strokeWidth: 1.5 }}
                interval={0} // 모든 X축 레이블 표시
                padding={{ left: 10, right: 10 }} // X축 패딩 추가
              />
              <YAxis 
                width={isChartPair ? 30 : 40} // Y축 너비를 제한하여 공간 확보, 2열일 때 더 좁게 설정
                tick={{ fill: '#666', fontSize: isChartPair ? '0.7em' : '0.8em' }} // 2열일 때 글꼴 크기 축소
                tickLine={{ stroke: '#666' }}
                axisLine={{ stroke: '#666' }}
                tickFormatter={(value) => {
                  // 모든 숫자를 간결하게 표시 (K, M, B 단위 사용)
                  if (value >= 1000000000) return (value / 1000000000).toFixed(1) + 'B';
                  if (value >= 1000000) return (value / 1000000).toFixed(1) + 'M';
                  if (value >= 1000) return (value / 1000).toFixed(1) + 'K';
                  return value.toString();
                }}
                label={data.y_axis_title ? { 
                  value: `${data.y_axis_title}`, 
                  angle: 0,
                  position: 'top',
                  offset: 0,
                  dx: 0,
                  dy: -15,
                  style: { 
                    textAnchor: 'middle',
                    fill: '#0066cc',
                    fontWeight: 'bold',
                    fontSize: '0.85em',
                    backgroundColor: 'rgba(255, 255, 255, 0.9)',
                    padding: '3px 6px',
                    borderRadius: '3px',
                    border: '1px solid #ddd'
                  }
                } : undefined}
              />
              <Tooltip content={<CustomTooltip />} />
              <Legend 
                wrapperStyle={{ 
                  paddingTop: '8px',
                  paddingBottom: '2px',
                  fontSize: '0.75em',
                  fontWeight: 500
                }}
                iconType="circle"
                iconSize={8}
                verticalAlign="bottom"
                height={20}
                layout="horizontal"
                margin={{ top: 0, bottom: 0 }}
              />
              
              {/* X축 마우스 오버 효과를 위한 배경 하이라이트 */}
              {formattedData.map((entry: any, index: number) => (
                <ReferenceArea
                  key={`ref-area-${index}`}
                  x1={entry.name}
                  x2={entry.name}
                  y1={0}
                  y2={10000000} // 충분히 큰 값으로 설정하여 전체 영역 커버
                  fillOpacity={activeIndex === index ? 0.2 : 0} // 마우스 오버 시에만 배경색 표시 (투명도 감소)
                  fill="#666" // 회색 배경
                />
              ))}
              
              {data.datasets.map((dataset: any, index: number) => {
                const datasetColor = dataset.backgroundColor || CHART_COLORS[index % CHART_COLORS.length];
                // 고유한 키 생성 (데이터 가공 시와 동일한 방식)
                const uniqueKey = `${dataset.label}_${index}`;
                
                return (
                  <Bar 
                    key={index} 
                    dataKey={uniqueKey}
                    name={dataset.label} // 범례에 표시될 이름은 원래 라벨 사용
                    fill={datasetColor}
                    animationDuration={1500}
                    animationEasing="ease-in-out"
                    barSize={isMobile ? 15 : 25} // 막대 크기 조정
                    radius={[4, 4, 0, 0]}
                  >
                    {formattedData.map((entry: any, idx: number) => (
                      <Cell 
                        key={`cell-${idx}`} 
                        fill={datasetColor} 
                        fillOpacity={activeIndex === idx ? 1 : 0.8}
                      />
                    ))}
                  </Bar>
                );
              })}
            </BarChart>
          </ResponsiveContainer>
        </div>
      );
    }
    
    case 'line_chart': {
      const { title, data } = component as any;
      
      // 컨테이너 스타일 - hover 효과를 별도 클래스로 적용
      const containerBaseStyle: CSSProperties = {
        backgroundColor: 'rgba(255, 255, 255, 0.8)',
        borderRadius: '12px',
        padding: '1em',
        boxShadow: '0 4px 12px rgba(0, 0, 0, 0.05)',
        transition: 'box-shadow 0.3s ease'
      };
      
      // 모바일 또는 2열 레이아웃에 따른 컨테이너 스타일 설정
      const containerStyle: CSSProperties = (!isMobile && isChartPair)
        ? {
            ...containerBaseStyle,
            margin: isFirstInPair ? '1em 0.5% 1em 0' : '1em 0 1em 0.5%',
            width: '49%',  // 각 차트가 49%를 차지하여 더 넓게 표시
            display: 'inline-block',
            verticalAlign: 'top'
          }
        : { 
            ...containerBaseStyle,
            margin: '1em 0', 
            width: '100%'
          };
      
      // 차트 높이 계산 (모바일이거나 2열인 경우 높이 조정)
      const chartHeight = isMobile ? 250 : (isChartPair ? 280 : 350);
      
      // 데이터 가공
      const formattedData = data.labels.map((label: string, index: number) => {
        const dataPoint: Record<string, any> = { name: label };
        
        // 각 데이터셋의 해당 인덱스 값을 추가 - 고유한 키 생성
        data.datasets.forEach((dataset: any, datasetIndex: number) => {
          // 동일한 라벨을 가진 데이터셋들을 구분하기 위해 인덱스 추가
          const uniqueKey = `${dataset.label}_${datasetIndex}`;
          dataPoint[uniqueKey] = dataset.data[index];
        });
        
        return dataPoint;
      });
      
      return (
        <div className="chart-container" style={containerStyle}>
          {title && <div style={{ 
            fontWeight: 'bold', 
            marginBottom: '0.5em',
            fontSize: '1.2em',
            textAlign: 'center',
            color: '#333'
          }}>{title}</div>}
          <ResponsiveContainer width="100%" height={chartHeight}>
            <LineChart 
              data={formattedData}
              margin={isChartPair 
                ? { top: 20, right: 30, left: 0, bottom: 15 } // 2열 배치 시 마진
                : { top: 25, right: 30, left: 0, bottom: 30 } // 1열 배치 시 마진
              }
              onMouseMove={(e) => {
                if (e && 'activeTooltipIndex' in e && e.activeTooltipIndex !== undefined) {
                  setActiveIndex(e.activeTooltipIndex);
                }
              }}
              onMouseLeave={() => setActiveIndex(-1)}
            >
              <CartesianGrid 
                strokeDasharray="3 3" 
                stroke="rgba(0,0,0,0.1)" 
                vertical={true} // 세로 격자선 추가
              />
              <XAxis 
                dataKey="name" 
                height={30} // X축 높이 감소
                tick={<CustomXAxisTick isMobile={isMobile} isChartPair={isChartPair} />} // 커스텀 틱 적용
                tickLine={{ stroke: '#666', strokeWidth: 1.5 }}
                axisLine={{ stroke: '#666', strokeWidth: 1.5 }}
                interval={0} // 모든 X축 레이블 표시
                padding={{ left: 10, right: 10 }} // X축 패딩 추가
              />
              <YAxis 
                width={isChartPair ? 30 : 40} // Y축 너비를 제한하여 공간 확보, 2열일 때 더 좁게 설정
                tick={{ fill: '#666', fontSize: isChartPair ? '0.7em' : '0.8em' }} // 2열일 때 글꼴 크기 축소
                tickLine={{ stroke: '#666' }}
                axisLine={{ stroke: '#666' }}
                tickFormatter={(value) => {
                  // 모든 숫자를 간결하게 표시 (K, M, B 단위 사용)
                  if (value >= 1000000000) return (value / 1000000000).toFixed(1) + 'B';
                  if (value >= 1000000) return (value / 1000000).toFixed(1) + 'M';
                  if (value >= 1000) return (value / 1000).toFixed(1) + 'K';
                  return value.toString();
                }}
                label={data.y_axis_title ? { 
                  value: `${data.y_axis_title}`, 
                  angle: 0,
                  position: 'top',
                  offset: 0,
                  dx: 0,
                  dy: -15,
                  style: { 
                    textAnchor: 'middle',
                    fill: '#0066cc',
                    fontWeight: 'bold',
                    fontSize: '0.85em',
                    backgroundColor: 'rgba(255, 255, 255, 0.9)',
                    padding: '3px 6px',
                    borderRadius: '3px',
                    border: '1px solid #ddd'
                  }
                } : undefined}
              />
              <Tooltip content={<CustomTooltip />} />
              <Legend 
                wrapperStyle={{ 
                  paddingTop: '4px',
                  paddingBottom: '0px',
                  fontSize: '0.75em',
                  fontWeight: 500
                }}
                iconType="plainline"
                iconSize={8}
                verticalAlign="bottom"
                height={15}
                layout="horizontal"
                margin={{ top: 0, bottom: 0 }}
              />
              
              {/* X축 마우스 오버 효과를 위한 배경 하이라이트 */}
              {formattedData.map((entry: any, index: number) => (
                <ReferenceArea
                  key={`ref-area-${index}`}
                  x1={entry.name}
                  x2={entry.name}
                  y1={0}
                  y2={10000000} // 충분히 큰 값으로 설정하여 전체 영역 커버
                  fillOpacity={activeIndex === index ? 0.2 : 0} // 마우스 오버 시에만 배경색 표시 (투명도 조정)
                  fill="#666" // 회색 배경
                />
              ))}
              
              {data.datasets.map((dataset: any, index: number) => {
                const datasetColor = dataset.borderColor || CHART_COLORS[index % CHART_COLORS.length];
                // 고유한 키 생성 (데이터 가공 시와 동일한 방식)
                const uniqueKey = `${dataset.label}_${index}`;
                
                return (
                  <Line 
                    key={index} 
                    type="monotone" 
                    dataKey={uniqueKey}
                    name={dataset.label} // 범례에 표시될 이름은 원래 라벨 사용
                    stroke={datasetColor}
                    strokeWidth={3}
                    activeDot={{ 
                      r: 8, 
                      fill: datasetColor,
                      stroke: '#fff',
                      strokeWidth: 2
                    }} 
                    dot={{ 
                      r: 4, 
                      fill: datasetColor,
                      stroke: '#fff',
                      strokeWidth: 2
                    }}
                    isAnimationActive={true}
                    animationDuration={2000}
                    animationEasing="ease-in-out"
                  />
                );
              })}
            </LineChart>
          </ResponsiveContainer>
        </div>
      );
    }
    
    case 'mixed_chart': {
      const { title, data } = component as any;
      
      // 컨테이너 스타일 - hover 효과를 별도 클래스로 적용
      const containerBaseStyle: CSSProperties = {
        backgroundColor: 'rgba(255, 255, 255, 0.8)',
        borderRadius: '12px',
        padding: '1em',
        boxShadow: '0 4px 12px rgba(0, 0, 0, 0.05)',
        transition: 'box-shadow 0.3s ease'
      };
      
      // 모바일 또는 2열 레이아웃에 따른 컨테이너 스타일 설정
      const containerStyle: CSSProperties = (!isMobile && isChartPair)
        ? {
            ...containerBaseStyle,
            margin: isFirstInPair ? '1em 0.5% 1em 0' : '1em 0 1em 0.5%',
            width: '49%',
            display: 'inline-block',
            verticalAlign: 'top'
          }
        : { 
            ...containerBaseStyle,
            margin: '1em 0', 
            width: '100%'
          };
      
      // 차트 높이 계산
      const chartHeight = isMobile ? 270 : (isChartPair ? 320 : 380);
      
      // 데이터 가공
      const formattedData = data.labels.map((label: string, index: number) => {
        const dataPoint: Record<string, any> = { name: label };
        
        // 막대 차트 데이터셋 (왼쪽 Y축)
        data.bar_datasets.forEach((dataset: any) => {
          dataPoint[dataset.label] = dataset.data[index];
        });
        
        // 선 차트 데이터셋 (오른쪽 Y축) - 고유한 키 생성
        data.line_datasets.forEach((dataset: any, datasetIndex: number) => {
          // 동일한 라벨을 가진 데이터셋들을 구분하기 위해 인덱스 추가
          const uniqueKey = `${dataset.label}_${datasetIndex}`;
          dataPoint[uniqueKey] = dataset.data[index];
        });
        
        return dataPoint;
      });
      
      // 마우스 오버 이벤트 핸들러
      const handleMouseOver = (index: number) => {
        setActiveIndex(index);
      };
      
      // 마우스 아웃 이벤트 핸들러
      const handleMouseOut = () => {
        setActiveIndex(-1);
      };
      
      return (
        <div className="chart-container" style={containerStyle}>
          {title && <div style={{ 
            fontWeight: 'bold', 
            marginBottom: '0.5em',
            fontSize: '1.2em',
            textAlign: 'center',
            color: '#333'
          }}>{title}</div>}
          <ResponsiveContainer width="100%" height={chartHeight}>
            <ComposedChart 
              data={formattedData}
              margin={isChartPair 
                ? { top: 25, right: 10, left: 20, bottom: 10 } // 2열 배치 시 마진
                : { top: 25, right: 15, left: 15, bottom: 0 } // 1열 배치 시 마진 (왼쪽 여백 제거)
              }
              barCategoryGap="20%" // 카테고리 그룹 간격 추가
              barGap={3} // 막대 간 간격
              onMouseMove={(e) => {
                if (e && 'activeTooltipIndex' in e && e.activeTooltipIndex !== undefined) {
                  setActiveIndex(e.activeTooltipIndex);
                }
              }}
              onMouseLeave={() => setActiveIndex(-1)}
            >
              {/* 마우스 오버 효과를 위한 배경 하이라이트 - 레이어 순서를 위해 맨 먼저 렌더링 */}
              {formattedData.map((entry: any, index: number) => (
                <ReferenceArea
                  key={`ref-area-${index}`}
                  x1={entry.name}
                  x2={entry.name}
                  y1={0}
                  y2="auto" // 자동 높이 계산
                  yAxisId="left" // 왼쪽 Y축 기준
                  ifOverflow="visible" // 넘치는 부분도 표시
                  fillOpacity={activeIndex === index ? 0.2 : 0} // 마우스 오버 시에만 배경색 표시
                  fill="#666" // 회색 배경
                  stroke="none" // 테두리 없음
                  strokeOpacity={0}
                />
              ))}
              
              <CartesianGrid 
                strokeDasharray="3 3" 
                stroke="rgba(0,0,0,0.1)" 
                vertical={true} // 세로 격자선 추가
              />
              <XAxis 
                dataKey="name" 
                height={30} // X축 높이 감소
                tick={<CustomXAxisTick isMobile={isMobile} isChartPair={isChartPair} />} // 커스텀 틱 적용
                tickLine={{ stroke: '#666', strokeWidth: 1.5 }}
                axisLine={{ stroke: '#666', strokeWidth: 1.5 }}
                interval={0} // 모든 X축 레이블 표시
                padding={{ left: 10, right: 10 }} // X축 패딩 추가
              />
              
              {/* 왼쪽 Y축 (막대 차트용) */}
              <YAxis 
                yAxisId="left" 
                orientation="left"
                width={isChartPair ? 30 : 40} // Y축 너비를 제한하여 공간 확보, 2열일 때 더 좁게 설정
                tick={{ fill: '#666', fontSize: isChartPair ? '0.7em' : '0.8em' }} // 2열일 때 글꼴 크기 축소
                tickLine={{ stroke: '#666' }}
                axisLine={{ stroke: '#666' }}
                tickFormatter={(value) => {
                  // 모든 숫자를 간결하게 표시 (K, M, B 단위 사용)
                  if (value >= 1000000000) return (value / 1000000000).toFixed(1) + 'B';
                  if (value >= 1000000) return (value / 1000000).toFixed(1) + 'M';
                  if (value >= 1000) return (value / 1000).toFixed(1) + 'K';
                  return value.toString();
                }}
                label={data.y_axis_left_title ? { 
                  value: `${data.y_axis_left_title}`, 
                  angle: 0,
                  position: 'top',
                  offset: 0,
                  dx: 0,
                  dy: -15,
                  style: { 
                    textAnchor: 'middle',
                    fill: '#0066cc',
                    fontWeight: 'bold',
                    fontSize: '0.85em',
                    backgroundColor: 'rgba(255, 255, 255, 0.9)',
                    padding: '3px 6px',
                    borderRadius: '3px',
                    border: '1px solid #ddd'
                  }
                } : undefined}
              />
              
              {/* 오른쪽 Y축 (선 차트용) */}
              <YAxis 
                yAxisId="right" 
                orientation="right"
                width={isChartPair ? 30 : 40} // Y축 너비를 제한하여 공간 확보, 2열일 때 더 좁게 설정
                tick={{ fill: '#666', fontSize: isChartPair ? '0.7em' : '0.8em' }} // 2열일 때 글꼴 크기 축소
                tickLine={{ stroke: '#666' }}
                axisLine={{ stroke: '#666' }}
                tickFormatter={(value) => {
                  // 오른쪽 Y축은 주로 퍼센트 값이므로 정수형 퍼센트로 표시
                  return `${Math.round(value)}%`;
                }}
                label={data.y_axis_right_title ? { 
                  value: `${data.y_axis_right_title}`, 
                  angle: 0,
                  position: 'top',
                  offset: 0,
                  dx: 0,
                  dy: -15,
                  style: { 
                    textAnchor: 'middle',
                    fill: '#cc3300',
                    fontWeight: 'bold',
                    fontSize: '0.85em',
                    backgroundColor: 'rgba(255, 255, 255, 0.9)',
                    padding: '3px 6px',
                    borderRadius: '3px',
                    border: '1px solid #ddd'
                  }
                } : undefined}
              />
              
              <Tooltip content={<CustomTooltip />} />
              <Legend 
                wrapperStyle={{ 
                  paddingTop: '4px',
                  paddingBottom: '0px',
                  fontSize: '0.75em',
                  fontWeight: 500
                }}
                iconType="circle"
                iconSize={8}
                verticalAlign="bottom"
                height={15}
                layout="horizontal"
                margin={{ top: 0, bottom: 0 }}
              />
              
              {/* 막대 차트 요소들 (왼쪽 Y축에 매핑) */}
              {data.bar_datasets.map((dataset: any, index: number) => {
                // 데이터셋의 backgroundColor를 우선적으로 사용
                const datasetColor = dataset.backgroundColor || 
                  (dataset.label.includes('순이익') ? '#34A853' : 
                   dataset.label.includes('영업이익') ? '#FBBC05' : 
                   dataset.label.includes('매출액') ? '#4285F4' : 
                   CHART_COLORS[index % CHART_COLORS.length]);
                
                return (
                  <Bar 
                    key={`bar-${index}`} 
                    yAxisId="left"
                    dataKey={dataset.label} 
                    fill={datasetColor}
                    animationDuration={1500}
                    animationEasing="ease-in-out"
                    barSize={isMobile ? 15 : 25}
                    radius={[4, 4, 0, 0]}
                    fillOpacity={0.8}
                  >
                    {formattedData.map((entry: any, idx: number) => (
                      <Cell 
                        key={`cell-${idx}`} 
                        fill={datasetColor} 
                        fillOpacity={activeIndex === idx ? 1 : 0.8}
                      />
                    ))}
                  </Bar>
                );
              })}
              
              {/* 선 차트 요소들 (오른쪽 Y축에 매핑) */}
              {data.line_datasets.map((dataset: any, index: number) => {
                // 데이터셋의 borderColor를 우선적으로 사용
                const datasetColor = dataset.borderColor || 
                  (dataset.label.includes('YoY') ? '#FF4335' : 
                   dataset.label.includes('QoQ') ? '#7C4DFF' : 
                   CHART_COLORS[(index + 4) % CHART_COLORS.length]);
                
                // 고유한 키 생성 (데이터 가공 시와 동일한 방식)
                const uniqueKey = `${dataset.label}_${index}`;
                
                return (
                  <Line 
                    key={`line-${index}`} 
                    yAxisId="right"
                    type="monotone" 
                    dataKey={uniqueKey}
                    name={dataset.label} // 범례에 표시될 이름은 원래 라벨 사용
                    stroke={datasetColor}
                    strokeWidth={3}
                    activeDot={{ 
                      r: 8, 
                      fill: datasetColor,
                      stroke: '#fff',
                      strokeWidth: 2
                    }}
                    dot={{ 
                      r: 4, 
                      fill: datasetColor,
                      stroke: '#fff',
                      strokeWidth: 2
                    }}
                    isAnimationActive={true}
                    animationDuration={2000}
                    animationEasing="ease-in-out"
                  />
                );
              })}
            </ComposedChart>
          </ResponsiveContainer>
        </div>
      );
    }
    
    case 'price_chart': {
      const { title, data } = component as IPriceChartComponent;
      
      // 주가차트 컨테이너 스타일
      const containerStyle: CSSProperties = {
        backgroundColor: 'rgba(255, 255, 255, 0.8)',
        borderRadius: '12px',
        padding: '1em',
        boxShadow: '0 4px 12px rgba(0, 0, 0, 0.05)',
        margin: '1em 0',
        width: '100%'
      };
      
      // 차트 높이 설정
      const chartHeight = isMobile ? 400 : 500;
      
      return (
        <div style={containerStyle}>
          {title && <div style={{ 
            fontWeight: 'bold', 
            marginBottom: '0.5em',
            fontSize: '1.2em',
            textAlign: 'center',
            color: '#333'
          }}>{title}</div>}
          
          <PriceChart 
            data={data}
            height={chartHeight}
            isMobile={isMobile}
          />
        </div>
      );
    }
    
    case 'technical_indicator_chart': {
      const { title, data } = component as ITechnicalIndicatorChartComponent;
      
      
      // 백엔드 데이터 구조 변환 처리
      let processedData = data;
      
      // chart_data가 객체 형태인 경우 (백엔드에서 보내는 구조)
      const dataWithChartData = data as any;
      if (dataWithChartData?.chart_data && typeof dataWithChartData.chart_data === 'object' && !Array.isArray(dataWithChartData.chart_data)) {
        console.log('[MessageComponentRenderer] chart_data 객체 구조 변환 시작');
        console.log('[MessageComponentRenderer] chart_data 키:', Object.keys(dataWithChartData.chart_data));
        
        try {
          const chartData = dataWithChartData.chart_data;
          
          // dates 배열 추출
          const dates = chartData.dates || [];
          console.log('[MessageComponentRenderer] dates 길이:', dates?.length || 0);
          console.log('[MessageComponentRenderer] 첫 번째 날짜:', dates?.[0]);
          
          // 날짜 형식 최종 검증 및 정규화
          const normalizedDates = dates.map((date: any) => {
            if (typeof date === 'string') {
              // ISO 형식인 경우 YYYY-MM-DD로 변환
              if (date.includes('T')) {
                const normalized = date.split('T')[0];
                console.log(`[MessageComponentRenderer] 날짜 변환: ${date} → ${normalized}`);
                return normalized;
              }
              // 이미 YYYY-MM-DD 형식인지 검증
              if (/^\d{4}-\d{2}-\d{2}$/.test(date)) {
                return date;
              }
            }
            // Date 객체인 경우 문자열로 변환
            if (date instanceof Date) {
              return date.toISOString().split('T')[0];
            }
            return String(date);
          });
          
          console.log('[MessageComponentRenderer] 정규화된 날짜 수:', normalizedDates.length);
          if (normalizedDates.length > 0) {
            console.log('[MessageComponentRenderer] 첫 번째 정규화된 날짜:', normalizedDates[0]);
            console.log('[MessageComponentRenderer] 마지막 정규화된 날짜:', normalizedDates[normalizedDates.length - 1]);
          }
          
          // OHLCV 데이터로 candle_data 구성
          const candle_data: any[] = [];
          if (normalizedDates && normalizedDates.length > 0) {
            for (let i = 0; i < normalizedDates.length; i++) {
              const candleItem = {
                time: normalizedDates[i],
                open: parseFloat(chartData.open?.[i] || chartData.close?.[i] || 0),
                high: parseFloat(chartData.high?.[i] || 0),
                low: parseFloat(chartData.low?.[i] || 0),
                close: parseFloat(chartData.close?.[i] || 0),
                volume: parseInt(chartData.volume?.[i] || 0)
              };
              
              // NaN 값 체크
              if (!isNaN(candleItem.close) && candleItem.close > 0) {
                candle_data.push(candleItem);
              }
            }
          }
          
          console.log('[MessageComponentRenderer] candle_data 길이:', candle_data.length);
          console.log('[MessageComponentRenderer] 첫 번째 캔들:', candle_data[0]);
          
          // 지표 데이터 추출 (dates, close, high, low, volume 제외)
          const indicators: any[] = [];
          const indicatorKeys = Object.keys(chartData).filter(key => 
            !['dates', 'close', 'high', 'low', 'volume', 'open'].includes(key)
          );
          
          console.log('[MessageComponentRenderer] 지표 키:', indicatorKeys);
          
          indicatorKeys.forEach(key => {
            const indicatorData = chartData[key];
            if (Array.isArray(indicatorData) && indicatorData.length > 0) {
              // 지표 데이터를 {time, value} 형태로 변환 (정규화된 날짜 사용)
              const indicatorSeries = normalizedDates.map((date: string, index: number) => ({
                time: date,
                value: parseFloat(indicatorData[index]) || null
              })).filter((item: any) => item.value !== null && !isNaN(item.value));
              
              if (indicatorSeries.length > 0) {
                indicators.push({
                  name: key,
                  data: indicatorSeries,
                  color: getIndicatorColor(key), // 지표별 색상 함수
                  type: getIndicatorType(key) // 지표 타입 (line, histogram 등)
                });
              }
            }
          });
          
          console.log('[MessageComponentRenderer] 변환된 지표 수:', indicators.length);
          
          // 기존 indicators와 병합 (있는 경우)
          const existingIndicators = data.indicators || [];
          const allIndicators = [...existingIndicators, ...indicators];
          
          processedData = {
            ...data,
            dates: normalizedDates, // 정규화된 날짜 사용
            candle_data,
            indicators: allIndicators
          };
          
          console.log('[MessageComponentRenderer] 최종 변환 결과:', {
            datesCount: dates.length,
            candleDataCount: candle_data.length,
            indicatorsCount: allIndicators.length,
            indicatorNames: allIndicators.map(ind => ind.name)
          });
          
        } catch (error) {
          console.error('[MessageComponentRenderer] 데이터 변환 오류:', error);
          // 변환 실패 시 원본 데이터 유지
          processedData = data;
        }
      }
      // } else if (dataWithChartData?.chart_data && Array.isArray(dataWithChartData.chart_data)) {
      //   // 기존 배열 형태 처리 로직 (하위 호환성)
      //   console.log('[MessageComponentRenderer] chart_data 배열 구조 변환 (레거시)');
        
      //   try {
      //     const dates = dataWithChartData.chart_data.map((item: any) => item.date || item.Date);
      //     const candle_data = dataWithChartData.chart_data.map((item: any, index: number) => ({
      //       time: item.date || item.Date || dates[index],
      //       open: parseFloat(item.open || item.Open || 0),
      //       high: parseFloat(item.high || item.High || 0),
      //       low: parseFloat(item.low || item.Low || 0),
      //       close: parseFloat(item.close || item.Close || 0),
      //       volume: parseInt(item.volume || item.Volume || 0)
      //     }));
          
      //     const indicators = data.indicators || [];
          
      //     processedData = {
      //       ...data,
      //       dates,
      //       candle_data,
      //       indicators
      //     };
          
      //     console.log('[MessageComponentRenderer] 레거시 변환 완료:', {
      //       datesCount: dates.length,
      //       candleDataCount: candle_data.length,
      //       indicatorsCount: indicators.length
      //     });
      //   } catch (error) {
      //     console.error('[MessageComponentRenderer] 레거시 데이터 변환 오류:', error);
      //   }
      // }
      // } else {
      //   console.log('[MessageComponentRenderer] chart_data가 없거나 예상과 다른 형태입니다.');
      //   console.log('[MessageComponentRenderer] 데이터 구조:', {
      //     hasChartData: !!dataWithChartData?.chart_data,
      //     chartDataType: typeof dataWithChartData?.chart_data,
      //     isArray: Array.isArray(dataWithChartData?.chart_data)
      //   });
      // }
      
      // 기술적 지표 차트 컨테이너 스타일
      const containerStyle: CSSProperties = {
        backgroundColor: 'rgba(255, 255, 255, 0.8)',
        borderRadius: '12px',
        padding: '1em',
        boxShadow: '0 4px 12px rgba(0, 0, 0, 0.05)',
        margin: '1em 0',
        width: '100%'
      };
      
      // 차트 높이 설정
      const chartHeight = isMobile ? 350 : 420;
      
      return (
        <div style={containerStyle}>
          {title && <div style={{ 
            fontWeight: 'bold', 
            marginBottom: '0.5em',
            fontSize: '1.2em',
            textAlign: 'center',
            color: '#333'
          }}>{title}</div>}
          
          <TechnicalIndicatorChart 
            data={processedData}
            height={chartHeight}
            isMobile={isMobile}
          />
        </div>
      );
    }
    
    case 'table': {
      const { title, data } = component as any;
      
      return (
        <div style={{ margin: '1em 0', width: '100%', overflowX: 'auto' }}>
          {title && <div style={{ fontWeight: 'bold', marginBottom: '0.5em', paddingLeft: '0.3em' }}>{title}</div>}
          <table style={{ 
            width: '100%', 
            borderCollapse: 'collapse',
            fontSize: '0.9em'
          }}>
            <thead>
              <tr>
                {data.headers.map((header: any, index: number) => (
                  <th 
                    key={index} 
                    style={{ 
                      padding: '0.5em', 
                      borderBottom: '2px solid #ddd',
                      textAlign: 'left',
                      fontWeight: 'bold'
                    }}
                  >
                    {header.label}
                  </th>
                ))}
              </tr>
            </thead>
            <tbody>
              {data.rows.map((row: any, rowIndex: number) => (
                <tr key={rowIndex}>
                  {data.headers.map((header: any, colIndex: number) => (
                    <td 
                      key={colIndex} 
                      style={{ 
                        padding: '0.5em', 
                        borderBottom: '1px solid #ddd'
                      }}
                    >
                      <ReactMarkdown remarkPlugins={[remarkGfm, remarkBreaks]}>
                        {row[header.key]}
                      </ReactMarkdown>
                    </td>
                  ))}
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      );
    }
    
    case 'image': {
      const { url, alt, caption } = component as any;
      
      return (
        <div style={{ margin: '1em 0', width: '100%', textAlign: 'center' }}>
          <img 
            src={url} 
            alt={alt || '이미지'} 
            style={{ 
              maxWidth: '100%', 
              height: 'auto', 
              borderRadius: '4px'
            }} 
          />
          {caption && (
            <div style={{ 
              marginTop: '0.5em', 
              fontSize: '0.9em', 
              color: '#666'
            }}>
              {caption}
            </div>
          )}
        </div>
      );
    }
    
    default:
      // 알 수 없는 컴포넌트 타입일 경우 기본 텍스트로 표시
      return <div>지원되지 않는 컴포넌트 타입: {(component as any).type}</div>;
  }
}

// 차트 컴포넌트 쌍을 렌더링하는 함수형 컴포넌트
export function ChartPairRenderer({ components }: { components: MessageComponent[] }) {
  if (components.length === 0) return null;
  
  // 모바일 환경 감지
  const isMobile = useMediaQuery('mobile');
  
  // 컴포넌트 렌더링 결과 배열
  const renderedComponents: JSX.Element[] = [];

  // 컴포넌트 순회하면서 2열로 배치 가능한지 확인
  for (let i = 0; i < components.length; i++) {
    const currentComponent = components[i];
    const nextComponent = i + 1 < components.length ? components[i + 1] : undefined;
    
    // 모바일에서는 항상 한 열로 표시
    if (isMobile) {
      // 일반 방식으로 렌더링
      renderedComponents.push(
        <MessageComponentRenderer 
          key={`component-${i}`} 
          component={currentComponent} 
        />
      );
    } else {
      // 현재와 다음 컴포넌트가 모두 차트인 경우 (bar_chart, line_chart, mixed_chart)
      const chartTypes = ['bar_chart', 'line_chart', 'mixed_chart'];
      const bothAreCharts = 
        chartTypes.includes(currentComponent.type as string) && 
        nextComponent && 
        chartTypes.includes(nextComponent.type as string);
      
      if (bothAreCharts) {
        // 차트 데이터 구조 분석 - x축 개수 및 데이터셋 개수 확인
        let hasComplexData = false;
        
        // 현재 차트 검사
        const currentChartData = (currentComponent as any).data;
        // mixed_chart 여부 확인 (타입 안전하게 문자열 비교)
        const isCurrentMixedChart = (currentComponent.type as string) === 'mixed_chart';
        
        // 현재 차트의 데이터셋 수집
        let currentDatasets: any[] = [];
        if (isCurrentMixedChart) {
          // mixed_chart인 경우 bar_datasets와 line_datasets을 모두 사용
          currentDatasets = [
            ...(currentChartData.bar_datasets || []), 
            ...(currentChartData.line_datasets || [])
          ];
        } else {
          // bar_chart 또는 line_chart인 경우 datasets 사용
          currentDatasets = currentChartData.datasets || [];
        }

        // 디버깅: 차트 데이터 로깅
        console.log('[ChartPairRenderer] 차트 데이터 분석:', {
          chart_type: currentComponent.type,
          labels_count: currentChartData.labels?.length || 0,
          datasets_count: currentDatasets.length,
          is_mixed_chart: isCurrentMixedChart,
          title: currentComponent.type === 'bar_chart' ? 
            (currentComponent as IBarChartComponent).title : 
            (currentComponent.type === 'line_chart' ? 
              (currentComponent as ILineChartComponent).title : 
              (currentComponent.type === 'mixed_chart' ? 
                (currentComponent as IMixedChartComponent).title : undefined))
        });
        const chartTitle = currentComponent.type === 'bar_chart' ? 
            (currentComponent as IBarChartComponent).title : 
            (currentComponent.type === 'line_chart' ? 
              (currentComponent as ILineChartComponent).title : 
              (currentComponent.type === 'mixed_chart' ? 
                (currentComponent as IMixedChartComponent).title : undefined));

        // 복잡한 데이터 조건 1: X축 라벨 개수가 6개 이상인 경우
        if (currentChartData.labels && currentChartData.labels.length >= 6 && currentDatasets.length >= 4) {
          hasComplexData = true;
          console.log('[ChartPairRenderer] 복잡한 데이터 감지 - 조건1: X축 개수가 많고 데이터셋도 많음, 차트제목: ', chartTitle);
        }
        
        // 복잡한 데이터 조건 2: 하나의 X축에 할당된 Y값이 5개 이상인 경우
        if (currentDatasets.length >= 5) {
          hasComplexData = true;
          
          console.log('[ChartPairRenderer] 복잡한 데이터 감지 - 조건2: 데이터셋이 5개 이상, 차트제목: ', chartTitle);
        }
        
        // 다음 차트 검사 (현재 차트가 복잡하지 않은 경우에만)
        if (!hasComplexData && nextComponent) {
          const nextChartData = (nextComponent as any).data;
          // mixed_chart 여부 확인 (타입 안전하게 문자열 비교)
          const isNextMixedChart = (nextComponent.type as string) === 'mixed_chart';
          
          // 다음 차트의 데이터셋 수집
          let nextDatasets: any[] = [];
          if (isNextMixedChart) {
            // mixed_chart인 경우 bar_datasets와 line_datasets을 모두 사용
            nextDatasets = [
              ...(nextChartData.bar_datasets || []), 
              ...(nextChartData.line_datasets || [])
            ];
          } else {
            // bar_chart 또는 line_chart인 경우 datasets 사용
            nextDatasets = nextChartData.datasets || [];
          }

          // 디버깅: 다음 차트 데이터 로깅
          console.log('[ChartPairRenderer] 다음 차트 데이터 분석:', {
            chart_type: nextComponent.type,
            labels_count: nextChartData.labels?.length || 0,
            datasets_count: nextDatasets.length,
            is_mixed_chart: isNextMixedChart,
            title: nextComponent.type === 'bar_chart' ? 
              (nextComponent as IBarChartComponent).title : 
              (nextComponent.type === 'line_chart' ? 
                (nextComponent as ILineChartComponent).title : 
                (nextComponent.type === 'mixed_chart' ? 
                  (nextComponent as IMixedChartComponent).title : undefined))
          });
          
          // 복잡한 데이터 조건 검사: 다음 차트
          if (nextChartData.labels && nextChartData.labels.length >= 6 && nextDatasets.length >= 4) {
            hasComplexData = true;
            console.log('[ChartPairRenderer] 복잡한 데이터 감지 - 다음 차트 조건1: X축 개수가 많고 데이터셋도 많음, 차트제목: ', chartTitle);
          }
          
          if (nextDatasets.length >= 5) {
            hasComplexData = true;
            console.log('[ChartPairRenderer] 복잡한 데이터 감지 - 다음 차트 조건2: 데이터셋이 5개 이상, 차트제목: ', chartTitle);
          }
        }
        
        // 최종 레이아웃 결정 로깅
        console.log('[ChartPairRenderer] 최종 레이아웃 결정:', hasComplexData ? '1열' : '2열');
        
        // 복잡한 데이터가 아닌 경우에만 2열로 배치
        if (!hasComplexData) {
          // 차트 쌍을 감싸는 컨테이너 - 애니메이션 효과 추가
          renderedComponents.push(
            <div 
              key={`chart-pair-container-${i}`} 
              style={{ 
                width: '100%', 
                display: 'flex', 
                flexWrap: 'wrap',
                margin: '1em 0',
                gap: '1%',
                animation: 'fadeIn 0.8s ease-in-out'
              }}
            >
              <MessageComponentRenderer 
                component={currentComponent} 
                nextComponent={nextComponent}
                isFirstInPair={true}
                isChartPair={true}
              />
              <MessageComponentRenderer 
                component={nextComponent!} 
                isFirstInPair={false}
                isChartPair={true}
              />
            </div>
          );
          
          // 다음 컴포넌트는 이미 처리했으므로 건너뜀
          i++;
        } else {
          // 복잡한 데이터인 경우 1열로 표시
          renderedComponents.push(
            <MessageComponentRenderer 
              key={`component-${i}`} 
              component={currentComponent} 
            />
          );
        }
      } else {
        // 일반 방식으로 렌더링
        renderedComponents.push(
          <MessageComponentRenderer 
            key={`component-${i}`} 
            component={currentComponent} 
          />
        );
      }
    }
  }
  
  return <>{renderedComponents}</>;
}

// 추가 CSS 스타일 컴포넌트
// fade-in 애니메이션을 위한 글로벌 스타일 컴포넌트
const globalStyle = `
  @keyframes fadeIn {
    from {
      opacity: 0;
      transform: translateY(20px);
    }
    to {
      opacity: 1;
      transform: translateY(0);
    }
  }
  
  .chart-container {
    transition: box-shadow 0.3s ease;
  }
  
  .chart-container:hover {
    box-shadow: 0 6px 16px rgba(0, 0, 0, 0.1);
  }
  
  /* X축 레이블 스타일 */
  .recharts-cartesian-axis-tick-value {
    transition: fill 0.2s ease;
  }
  
  .recharts-cartesian-axis-tick:hover .recharts-cartesian-axis-tick-value {
    fill: #1976d2;
    font-weight: bold;
  }
  
  /* 세로 격자선 스타일 */
  .recharts-cartesian-grid-vertical line {
    stroke-opacity: 0.6;
  }
`;

// PriceChart 컴포넌트 - Lightweight Charts를 사용한 주가차트
const PriceChart: React.FC<{
  data: any;
  height: number;
  isMobile: boolean;
}> = ({ data, height, isMobile }) => {
  const chartContainerRef = React.useRef<HTMLDivElement>(null);
  const chartRef = React.useRef<any>(null);
  const [crosshairData, setCrosshairData] = React.useState<{
    time: string;
    candle?: { open: number; high: number; low: number; close: number };
    indicators: { name: string; value: number | string; color: string }[];
    mouseX: number;
    mouseY: number;
  } | null>(null);
  
  React.useEffect(() => {
    if (!chartContainerRef.current || !data.candle_data || data.candle_data.length === 0) {
      return;
    }
    
    // 차트 생성
    const chart = createChart(chartContainerRef.current, {
      width: chartContainerRef.current.clientWidth,
      height: height,
      layout: {
        background: { color: '#ffffff' },
        textColor: '#333333',
      },
      grid: {
        vertLines: {
          color: '#e1e1e1',
        },
        horzLines: {
          color: '#e1e1e1',
        },
      },
      rightPriceScale: {
        borderColor: '#cccccc',
      },
      timeScale: {
        borderColor: '#cccccc',
        timeVisible: true,
        secondsVisible: false,
      },
      crosshair: {
        mode: 1, // Normal crosshair mode
        vertLine: {
          width: 1,
          color: '#999999',
          style: 2, // LightweightCharts.LineStyle.Dashed
        },
        horzLine: {
          width: 1,
          color: '#999999',
          style: 2, // LightweightCharts.LineStyle.Dashed
        },
      },
      localization: {
        timeFormatter: (time: any) => {
          // yyyy-mm-dd 형식으로 변환
          if (typeof time === 'string') {
            return time; // 이미 문자열 형태면 그대로 반환
          }
          const date = new Date(time * 1000);
          const year = date.getFullYear();
          const month = String(date.getMonth() + 1).padStart(2, '0');
          const day = String(date.getDate()).padStart(2, '0');
          return `${year}-${month}-${day}`;
        },
      },
    });
    
    chartRef.current = chart;
    
    // 시리즈 참조들을 저장할 배열
    const seriesRefs: Array<{ series: any; name: string; color: string; type: 'candle' | 'indicator' | 'volume' | 'ma' }> = [];
    
    // 캔들스틱 시리즈 추가 - 한국 스타일 (상승: 빨간색, 하락: 파란색)
    const candlestickSeries = chart.addSeries(CandlestickSeries, {
      upColor: '#ef5350',
      downColor: '#2196f3',
      borderUpColor: '#ef5350',
      borderDownColor: '#2196f3',
      wickUpColor: '#ef5350',
      wickDownColor: '#2196f3',
      //title: '주가',
    });
    
    // 주가 스케일 설정 - 거래량이 있으면 상단 70% 영역 사용
    if (data.volume_data && data.volume_data.length > 0) {
      chart.priceScale('right').applyOptions({
        scaleMargins: {
          top: 0.1,
          bottom: 0.3, // 하단 30%는 거래량을 위해 여백 확보
        },
      });
    }
    
    // 캔들 데이터 설정
    const candleData = data.candle_data.map((item: any) => ({
      time: item.time as Time,
      open: item.open,
      high: item.high,
      low: item.low,
      close: item.close,
    }));
    
    candlestickSeries.setData(candleData);
    
    // 캔들스틱 시리즈 참조 저장
    seriesRefs.push({
      series: candlestickSeries,
      name: '캔들스틱',
      color: '#ef5350',
      type: 'candle'
    });
    
    // 거래량 데이터 처리 - volume_data가 있으면 사용하고, 없으면 candle_data에서 추출
    let volumeDataToUse = data.volume_data;
    
    // volume_data가 없지만 candle_data에 volume 정보가 있는 경우 추출
    if ((!volumeDataToUse || volumeDataToUse.length === 0) && data.candle_data && data.candle_data.length > 0) {
      // candle_data에서 volume 정보만 추출하여 volume_data 형태로 변환
      volumeDataToUse = data.candle_data
        .filter((candle: any) => candle.volume !== undefined && candle.volume > 0)
        .map((candle: any) => ({
          time: candle.time,
          value: candle.volume,
        }));
    }
    
    // 거래량 데이터가 있으면 추가
    if (volumeDataToUse && volumeDataToUse.length > 0) {
      const volumeSeries = chart.addSeries(HistogramSeries, {
        color: '#26a69a',
        priceFormat: {
          type: 'volume',
        },
        priceScaleId: 'volume',
        //title: '거래량',
      });
      
      // 거래량 스케일 설정 - 하단 30% 영역 사용
      chart.priceScale('volume').applyOptions({
        scaleMargins: {
          top: 0.7, // 상단 70% 지점부터 시작
          bottom: 0,
        },
        borderColor: '#cccccc',
        textColor: '#666',
        entireTextOnly: false,
        ticksVisible: true,
        borderVisible: true,
      });
      
      // 거래량 데이터 처리 - 전일 대비 증감으로 색상 결정
      const volumeData = volumeDataToUse.map((item: any, index: number) => {
        let volumeColor = '#ef535080'; // 기본 상승 색상 (반투명)
        
        // 전일 거래량과 비교하여 색상 결정
        if (index > 0 && volumeDataToUse[index - 1]) {
          const prevVolume = volumeDataToUse[index - 1].value;
          const currentVolume = item.value;
          
          // 전일 대비 거래량 증가: 빨간색, 감소: 파란색 (반투명)
          volumeColor = currentVolume >= prevVolume ? '#ef535080' : '#2196f380';
        } else if (item.color) {
          // 별도로 색상이 지정된 경우 사용 (반투명 처리)
          volumeColor = item.color + '80';
        }
        
        return {
          time: item.time as Time,
          value: item.value,
          color: volumeColor,
        };
      });
      
      volumeSeries.setData(volumeData);
      
      // 거래량 시리즈 참조 저장 (대표 색상으로 표시)
      seriesRefs.push({
        series: volumeSeries,
        name: '거래량',
        color: '#26a69a',
        type: 'volume'
      });
    }
    
    // 이동평균선 추가
    if (data.moving_averages && data.moving_averages.length > 0) {
      const maSeries = chart.addSeries(LineSeries, {
        color: '#ff6b35',
        lineWidth: 2,
      });
      
      const maData = data.moving_averages.map((item: any) => ({
        time: item.time as Time,
        value: item.value
      }));
      
      maSeries.setData(maData);
      
      // 이동평균선 시리즈 참조 저장
      seriesRefs.push({
        series: maSeries,
        name: '이동평균선',
        color: '#ff6b35',
        type: 'ma'
      });
    }
    
    // 지지선 추가
    if (data.support_lines && data.support_lines.length > 0) {
      data.support_lines.forEach((line: any) => {
        // 캔들스틱 시리즈에 직접 프라이스 라인 추가 (중복 방지)
        if (candlestickSeries && line.show_label) {
          candlestickSeries.createPriceLine({
            price: line.price,
            color: line.color || '#2196f3',
            lineWidth: line.line_width || 2,
            lineStyle: line.line_style === 'solid' ? LineStyle.Solid :
                      line.line_style === 'dotted' ? LineStyle.Dotted :
                      LineStyle.Dashed,
            axisLabelVisible: false, // 오른쪽 Y축 라벨 제거
            title: line.label,
          });
        }
      });
    }
    
    // 저항선 추가
    if (data.resistance_lines && data.resistance_lines.length > 0) {
      data.resistance_lines.forEach((line: any) => {
        // 캔들스틱 시리즈에 직접 프라이스 라인 추가 (중복 방지)
        if (candlestickSeries && line.show_label) {
          candlestickSeries.createPriceLine({
            price: line.price,
            color: line.color || '#ef5350',
            lineWidth: line.line_width || 2,
            lineStyle: line.line_style === 'solid' ? LineStyle.Solid :
                      line.line_style === 'dotted' ? LineStyle.Dotted :
                      LineStyle.Dashed,
            axisLabelVisible: false, // 오른쪽 Y축 라벨 제거
            title: line.label,
          });
        }
      });
    }
    
    // 마우스 이벤트를 위한 차트 컨테이너에 이벤트 리스너 추가
    let currentMouseX = 0;
    let currentMouseY = 0;
    
    const handleMouseMove = (event: MouseEvent) => {
      const rect = chartContainerRef.current?.getBoundingClientRect();
      if (rect) {
        currentMouseX = event.clientX - rect.left;
        currentMouseY = event.clientY - rect.top;
      }
    };
    
    chartContainerRef.current.addEventListener('mousemove', handleMouseMove);
    
    // 크로스헤어 이벤트 리스너 추가
    chart.subscribeCrosshairMove((param: any) => {
      if (!param.time) {
        setCrosshairData(null);
        return;
      }
      
      const indicators: { name: string; value: number | string; color: string }[] = [];
      let candleData: { open: number; high: number; low: number; close: number } | undefined;
      
      // 모든 시리즈에서 해당 시점의 데이터 수집
      seriesRefs.forEach(({ series, name, color, type }) => {
        const dataPoint = param.seriesData?.get(series);
        if (dataPoint) {
          if (type === 'candle') {
            candleData = {
              open: dataPoint.open,
              high: dataPoint.high,
              low: dataPoint.low,
              close: dataPoint.close,
            };
          } else {
            // 지표, 거래량, 이동평균선 데이터
            const value = dataPoint.value !== undefined ? dataPoint.value : dataPoint;
            let displayValue: string;
            
            if (type === 'volume') {
              // 거래량은 천 단위로 표시
              displayValue = typeof value === 'number' ? 
                (value >= 1000000 ? (value / 1000000).toFixed(1) + 'M' :
                 value >= 1000 ? (value / 1000).toFixed(0) + 'K' :
                 value.toString()) : value.toString();
            } else {
              // 일반 지표는 소수점 2자리로 표시
              displayValue = typeof value === 'number' ? value.toFixed(2) : value.toString();
            }
            
            indicators.push({
              name,
              value: displayValue,
              color
            });
          }
        }
      });
      
      // 시간 포맷팅
      const timeStr = typeof param.time === 'string' ? param.time : 
                     new Date(param.time * 1000).toISOString().split('T')[0];
      
      setCrosshairData({
        time: timeStr,
        candle: candleData,
        indicators,
        mouseX: currentMouseX,
        mouseY: currentMouseY
      });
    });
    
    // 리사이즈 핸들러
    const handleResize = () => {
      if (chartContainerRef.current && chartRef.current) {
        chartRef.current.applyOptions({
          width: chartContainerRef.current.clientWidth,
        });
      }
    };
    
    window.addEventListener('resize', handleResize);
    
    // 정리
    return () => {
      window.removeEventListener('resize', handleResize);
      if (chartContainerRef.current) {
        chartContainerRef.current.removeEventListener('mousemove', handleMouseMove);
      }
      if (chartRef.current) {
        chartRef.current.remove();
      }
    };
  }, [data, height]);
  
  // 범례 정보 표시용 컴포넌트
  const renderLegend = () => {
    const legendItems = [];
    
    // 캔들스틱 범례
    if (data.candle_data && data.candle_data.length > 0) {
      legendItems.push({
        name: '주가',
        color: '#26a69a',
        type: 'candle'
      });
    }
    
    // 거래량 범례 - volume_data가 있거나 candle_data에 volume이 있는 경우
    const hasVolumeData = (data.volume_data && data.volume_data.length > 0) || 
                         (data.candle_data && data.candle_data.length > 0 && 
                          data.candle_data.some((candle: any) => candle.volume !== undefined && candle.volume > 0));
    
    if (hasVolumeData) {
      legendItems.push({
        name: '거래량',
        color: '#666',
        type: 'bar'
      });
    }
    
    // 이동평균선 범례
    if (data.moving_averages && data.moving_averages.length > 0) {
      legendItems.push({
        name: '이동평균선',
        color: '#ff6b35',
        type: 'line'
      });
    }
    
                // 지지선 범례 - 실제 라인 색상과 일치
    if (data.support_lines && data.support_lines.length > 0) {
      const supportLineColor = data.support_lines[0]?.color || '#2196f3';
      legendItems.push({
        name: '지지선',
        color: supportLineColor,
        type: 'line'
      });
    }
    
    // 저항선 범례 - 실제 라인 색상과 일치
    if (data.resistance_lines && data.resistance_lines.length > 0) {
      const resistanceLineColor = data.resistance_lines[0]?.color || '#ef5350';
      legendItems.push({
        name: '저항선',
        color: resistanceLineColor,
        type: 'line'
      });
    }
    
    if (legendItems.length === 0) return null;
    
    return (
      <div style={{
        display: 'flex',
        flexWrap: 'wrap',
        justifyContent: 'center',
        alignItems: 'center',
        gap: '15px',
        marginTop: '10px',
        padding: '8px',
        fontSize: '0.75em',
        fontWeight: 500,
      }}>
        {legendItems.map((item, index) => (
          <div key={`legend-${index}`} style={{
            display: 'flex',
            alignItems: 'center',
            gap: '5px',
          }}>
            <div style={{
              width: item.type === 'candle' ? '8px' : '12px',
              height: item.type === 'candle' ? '12px' : item.type === 'bar' ? '8px' : '2px',
              backgroundColor: item.color,
              borderRadius: item.type === 'candle' ? '1px' : '1px',
              border: item.type === 'candle' ? `1px solid ${item.color}` : 'none',
            }} />
            <span style={{ color: '#333' }}>{item.name}</span>
          </div>
        ))}
      </div>
    );
  };
  
  return (
    <div style={{ width: '100%' }}>
      {/* 차트 영역 */}
      <div 
        ref={chartContainerRef} 
        style={{ 
          width: '100%', 
          height: `${height}px`,
          position: 'relative'
        }}
      >
        {/* 크로스헤어 데이터 표시 - 마우스 팝업 */}
        {crosshairData && (() => {
          // 팝업 위치 계산 (화면 경계를 벗어나지 않도록 조정)
          const popupWidth = 300; // 예상 팝업 너비
          const popupHeight = 80; // 예상 팝업 높이
          
          let left = crosshairData.mouseX + 15; // 마우스 오른쪽에 표시
          let top = crosshairData.mouseY - 40; // 마우스 위쪽에 표시
          
          // 오른쪽 경계 체크
          if (left + popupWidth > chartContainerRef.current?.clientWidth!) {
            left = crosshairData.mouseX - popupWidth - 15; // 마우스 왼쪽에 표시
          }
          
          // 위쪽 경계 체크
          if (top < 0) {
            top = crosshairData.mouseY + 15; // 마우스 아래쪽에 표시
          }
          
          // 아래쪽 경계 체크
          if (top + popupHeight > chartContainerRef.current?.clientHeight!) {
            top = chartContainerRef.current?.clientHeight! - popupHeight - 10;
          }
          
          return (
            <div style={{
              position: 'absolute',
              left: `${left}px`,
              top: `${top}px`,
              zIndex: 1000,
              background: 'linear-gradient(135deg, rgba(255, 255, 255, 0.98), rgba(248, 250, 252, 0.98))',
              backdropFilter: 'blur(12px)',
              border: '1px solid rgba(226, 232, 240, 0.6)',
              borderRadius: '10px',
              padding: '10px 14px',
              fontSize: '0.85em',
              fontFamily: 'system-ui, -apple-system, sans-serif',
              boxShadow: '0 8px 32px rgba(0, 0, 0, 0.12)',
              display: 'flex',
              flexDirection: 'column',
              gap: '6px',
              minWidth: '200px',
              maxWidth: '300px',
              lineHeight: '1.3',
              transition: 'all 0.15s ease',
              pointerEvents: 'none', // 마우스 이벤트 무시
            }}>
              {/* 시간 표시 */}
              <div style={{ 
                fontSize: '0.9em',
                fontWeight: '600',
                color: '#1e293b',
                marginBottom: '4px',
                textAlign: 'center'
              }}>
                📅 {crosshairData.time}
              </div>
              
              {/* 캔들 데이터 표시 */}
              {crosshairData.candle && (
                <div style={{ 
                  display: 'grid',
                  gridTemplateColumns: 'repeat(4, 1fr)',
                  gap: '8px',
                  padding: '6px',
                  backgroundColor: 'rgba(248, 113, 113, 0.08)',
                  borderRadius: '6px',
                  border: '1px solid rgba(248, 113, 113, 0.2)'
                }}>
                  {[
                    { label: '시가', value: crosshairData.candle.open, color: '#64748b' },
                    { label: '고가', value: crosshairData.candle.high, color: '#dc2626' },
                    { label: '저가', value: crosshairData.candle.low, color: '#2563eb' },
                    { label: '종가', value: crosshairData.candle.close, color: '#1e293b' }
                  ].map(({ label, value, color }, idx) => (
                    <div key={idx} style={{ textAlign: 'center' }}>
                      <div style={{ 
                        fontSize: '0.75em', 
                        color: '#64748b',
                        fontWeight: '500',
                        marginBottom: '2px'
                      }}>{label}</div>
                      <div style={{ 
                        color: color,
                        fontWeight: '600',
                        fontSize: '0.85em'
                      }}>{value.toLocaleString()}</div>
                    </div>
                  ))}
                </div>
              )}
              
              {/* 지표 데이터 표시 */}
              {crosshairData.indicators.length > 0 && (
                <div style={{ display: 'flex', flexDirection: 'column', gap: '4px' }}>
                  {crosshairData.indicators.map((indicator, index) => (
                    <div key={index} style={{ 
                      display: 'flex', 
                      justifyContent: 'space-between',
                      alignItems: 'center',
                      padding: '3px 6px',
                      backgroundColor: 'rgba(99, 102, 241, 0.06)',
                      borderRadius: '4px'
                    }}>
                      <div style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
                        <div style={{
                          width: '6px',
                          height: '6px',
                          borderRadius: '50%',
                          backgroundColor: indicator.color,
                        }} />
                        <span style={{ 
                          color: '#475569',
                          fontSize: '0.8em',
                          fontWeight: '500'
                        }}>{indicator.name}</span>
                      </div>
                      <span style={{ 
                        color: '#1e293b',
                        fontWeight: '600',
                        fontSize: '0.85em'
                      }}>{indicator.value}</span>
                    </div>
                  ))}
                </div>
              )}
            </div>
          );
        })()}
      </div>
      
      {/* 범례 */}
      {renderLegend()}
    </div>
  );
};

// TechnicalIndicatorChart 컴포넌트 - Lightweight Charts를 사용한 기술적 지표 차트
const TechnicalIndicatorChart: React.FC<{
  data: any;
  height: number;
  isMobile: boolean;
}> = ({ data, height, isMobile }) => {
  const chartContainerRef = React.useRef<HTMLDivElement>(null);
  const chartRef = React.useRef<any>(null);
  const [crosshairData, setCrosshairData] = React.useState<{
    time: string;
    candle?: { open: number; high: number; low: number; close: number };
    indicators: { name: string; value: number | string; color: string }[];
    mouseX: number;
    mouseY: number;
  } | null>(null);
  
  React.useEffect(() => {
    console.log('[TechnicalIndicatorChart] useEffect 시작, 데이터 검증:', {
      hasContainer: !!chartContainerRef.current,
      hasDates: !!data.dates,
      datesLength: data.dates?.length || 0,
      hasIndicators: !!data.indicators,
      indicatorsLength: data.indicators?.length || 0,
      hasCandleData: !!data.candle_data,
      candleDataLength: data.candle_data?.length || 0,
      fullData: data
    });

    if (!chartContainerRef.current) {
      console.warn('[TechnicalIndicatorChart] 차트 컨테이너 ref가 없습니다.');
      return;
    }

    if (!data.dates || data.dates.length === 0) {
      console.warn('[TechnicalIndicatorChart] dates 데이터가 없거나 비어있습니다.');
      return;
    }

    // 캔들 데이터가 없으면 차트를 그릴 수 없음
    if (!data.candle_data || data.candle_data.length === 0) {
      console.warn('[TechnicalIndicatorChart] candle_data가 없거나 비어있습니다.');
      return;
    }
    
    // indicators는 선택사항으로 처리 (없어도 캔들차트는 표시)
    const indicatorsList = data.indicators || [];
    console.log('[TechnicalIndicatorChart] 렌더링 시작 - 캔들데이터:', data.candle_data.length, '지표:', indicatorsList.length);
    
    // 차트 생성
    const chart = createChart(chartContainerRef.current, {
      width: chartContainerRef.current.clientWidth,
      height: height,
      layout: {
        background: { color: '#ffffff' },
        textColor: '#333333',
      },
      grid: {
        vertLines: {
          color: '#e1e1e1',
        },
        horzLines: {
          color: '#e1e1e1',
        },
      },
      rightPriceScale: {
        borderColor: '#cccccc',
        visible: true,
      },
      leftPriceScale: {
        borderColor: '#cccccc',
        visible: true,
      },
      timeScale: {
        borderColor: '#cccccc',
        timeVisible: false,
        secondsVisible: false,
      },
      crosshair: {
        mode: 1, // Normal crosshair mode
        vertLine: {
          width: 1,
          color: '#999999',
          style: 2, // LightweightCharts.LineStyle.Dashed
        },
        horzLine: {
          width: 1,
          color: '#999999',
          style: 2, // LightweightCharts.LineStyle.Dashed
        },
      },
      localization: {
        timeFormatter: (time: any) => {
          // yyyy-mm-dd 형식으로 변환
          if (typeof time === 'string') {
            return time; // 이미 문자열 형태면 그대로 반환
          }
          const date = new Date(time * 1000);
          const year = date.getFullYear();
          const month = String(date.getMonth() + 1).padStart(2, '0');
          const day = String(date.getDate()).padStart(2, '0');
          return `${year}-${month}-${day}`;
        },
      },
    });
    
    chartRef.current = chart;
    
    // 시리즈 참조들을 저장할 배열
    const seriesRefs: Array<{ series: any; name: string; color: string; type: 'candle' | 'indicator' }> = [];
    
    // 선 스타일 변환 함수
    const getLineStyle = (lineStyle: string): LineStyle => {
      switch (lineStyle) {
        case 'dashed':
          return LineStyle.Dashed;
        case 'dotted':
          return LineStyle.Dotted;
        default:
          return LineStyle.Solid;
      }
    };
    
    // Y축 설정
    const primaryAxisConfig = data.y_axis_configs?.primary || {
      title: "Primary",
      position: "left",
      color: "#3b82f6"
    };

    const secondaryAxisConfig = data.y_axis_configs?.secondary || {
      title: "Secondary", 
      position: "right",
      color: "#8b5cf6"
    };

    const hiddenAxisConfig = data.y_axis_configs?.hidden || null;
    
    // 캔들 데이터가 있는 경우 캔들스틱 시리즈 추가 - 한국 스타일
    if (data.candle_data && data.candle_data.length > 0) {
      console.log('[TechnicalIndicatorChart] 캔들 데이터 생성 시작:', data.candle_data.length, '개');
      
      try {
        const candlestickSeries = chart.addSeries(CandlestickSeries, {
          upColor: '#ef5350',
          downColor: '#26a69a', 
          borderUpColor: '#ef5350',
          borderDownColor: '#26a69a',
          wickUpColor: '#ef5350',
          wickDownColor: '#26a69a',
          priceScaleId: 'right', // 오른쪽 스케일 사용
        });
        
        // 캔들 데이터 변환 및 검증
        const candleData = data.candle_data.map((item: any, index: number) => {
          // 시간 데이터 정규화 (YYYY-MM-DD 형식)
          let timeValue: string;
          if (typeof item.time === 'string' && /^\d{4}-\d{2}-\d{2}$/.test(item.time)) {
            timeValue = item.time;
          } else {
            // 날짜 변환 시도
            const date = new Date(item.time);
            if (!isNaN(date.getTime())) {
              const year = date.getFullYear();
              const month = String(date.getMonth() + 1).padStart(2, '0');
              const day = String(date.getDate()).padStart(2, '0');
              timeValue = `${year}-${month}-${day}`;
            } else {
              console.warn(`[TechnicalIndicatorChart] 유효하지 않은 시간 데이터 (인덱스 ${index}):`, item.time);
              timeValue = '2024-01-01'; // 기본값
            }
          }
          
          // OHLC 데이터 검증
          const open = Number(item.open) || 0;
          const high = Number(item.high) || 0;
          const low = Number(item.low) || 0;
          const close = Number(item.close) || 0;
          
          if (high < low || high < Math.max(open, close) || low > Math.min(open, close)) {
            console.warn(`[TechnicalIndicatorChart] 비정상적인 OHLC 데이터 (인덱스 ${index}):`, {
              time: timeValue, open, high, low, close
            });
          }
          
          return {
            time: timeValue as Time,
            open: open,
            high: high,
            low: low,
            close: close,
          };
        });
        
        console.log('[TechnicalIndicatorChart] 변환된 캔들 데이터 샘플:', candleData.slice(0, 3));
        
        candlestickSeries.setData(candleData);
        
        // 캔들스틱 시리즈 참조 저장
        seriesRefs.push({
          series: candlestickSeries,
          name: '캔들스틱',
          color: '#ef5350',
          type: 'candle'
        });
        
        console.log('[TechnicalIndicatorChart] 캔들스틱 시리즈 생성 완료');
        
      } catch (error) {
        console.error('[TechnicalIndicatorChart] 캔들스틱 시리즈 생성 중 오류:', error);
      }
    } else {
      console.warn('[TechnicalIndicatorChart] 캔들 데이터가 없습니다:', {
        hasCandleData: !!data.candle_data,
        candleDataLength: data.candle_data?.length || 0
      });
    }

    // 지표별 시리즈 생성
    console.log('=== TechnicalIndicatorChart 분석 시작 ===');
    console.log('전체 데이터:', data);
    console.log('지표 목록:', indicatorsList);
    
    indicatorsList.forEach((indicator: any, index: number) => {
      const color = indicator.color || CHART_COLORS[index % CHART_COLORS.length];
      const lineStyle = getLineStyle(indicator.line_style);
      
      // 슈퍼트렌드 지표인지 확인
      const isSupertrend = indicator.name && (
        indicator.name.toLowerCase().includes('supertrend') || 
        indicator.name.includes('슈퍼트렌드')
      );
      
      console.log(`지표 ${index + 1} 분석:`, {
        name: indicator.name,
        isSupertrend,
        hasDirections: !!indicator.directions,
        directionsLength: indicator.directions?.length,
        directions: indicator.directions,
        dataLength: indicator.data?.length
      });
      
      // 스케일 ID 결정: 슈퍼트렌드는 캔들 데이터와 동일한 스케일 사용
      let priceScaleId;
      if (isSupertrend && data.candle_data && data.candle_data.length > 0) {
        priceScaleId = 'right'; // 캔들 데이터와 동일한 스케일 사용 (오른쪽)
      } else if (indicator.y_axis_id === 'hidden') {
        priceScaleId = 'hidden'; // 범용 hidden 축 사용
      } else {
        priceScaleId = indicator.y_axis_id === 'secondary' ? 'right' : 'left'; // secondary는 오른쪽, primary는 왼쪽
      }
      
      // 시계열 데이터 생성 - 슈퍼트렌드의 경우 항상 실제 값 사용
      let seriesData;
      if (isSupertrend) {
        // 슈퍼트렌드는 실제 가격 값을 사용 (data 필드에 이미 실제 값이 들어있음)
        seriesData = data.dates.map((date: string, idx: number) => ({
          time: date as Time,
          value: indicator.data[idx] || 0, // 백엔드에서 이미 실제 값으로 설정됨
        }));
      } else {
        seriesData = data.dates.map((date: string, idx: number) => ({
          time: date as Time,
          value: indicator.data[idx] || 0,
        }));
      }
      
      // 차트 타입에 따라 시리즈 생성
      if (indicator.chart_type === 'bar') {
        const histogramSeries = chart.addSeries(HistogramSeries, {
          color: color,
          priceFormat: {
            type: 'price',
            precision: 2,
            minMove: 0.01,
          },
          priceScaleId: priceScaleId,
        });
        
        // 막대 차트용 데이터 형식으로 변환
        const histogramData = seriesData.map((item: any) => ({
          time: item.time,
          value: item.value,
          color: color,
        }));
        
        histogramSeries.setData(histogramData);
        
      } else if (indicator.chart_type === 'area') {
        const areaSeries = chart.addSeries(AreaSeries, {
          topColor: color,
          bottomColor: `${color}20`, // 투명도 적용
          lineColor: color,
          lineWidth: 2,
          lineStyle: lineStyle,
          priceFormat: {
            type: 'price',
            precision: 2,
            minMove: 0.01,
          },
          priceScaleId: priceScaleId,
        });
        
        areaSeries.setData(seriesData);
        
      } else {
        // 기본값: line
        // 슈퍼트렌드의 경우 방향에 따라 구간별 색상 변경
        // console.log('🟡 슈퍼트렌드 체크:', { 
        //   name: indicator.name,
        //   isSupertrend, 
        //   hasDirections: !!indicator.directions, 
        //   directionsLength: indicator.directions?.length,
        //   directions: indicator.directions?.slice(0, 10), // 처음 10개만 로깅
        //   seriesDataLength: seriesData.length
        // });
        if (isSupertrend && indicator.directions && indicator.directions.length > 0) {
          // 방향 변화 지점을 찾아서 구간별로 시리즈 생성
          const segments: Array<{data: any[], direction: number}> = [];
          let currentSegment: any[] = [];
          let currentDirection = indicator.directions[0];
          
          seriesData.forEach((point: any, idx: number) => {
            const direction = indicator.directions[idx];
            
            // 방향이 바뀌는 지점
            if (direction !== currentDirection && currentSegment.length > 0) {
              // 이전 구간을 저장 (연결점 포함)
              segments.push({
                data: [...currentSegment, point], // 연결을 위해 현재 포인트도 포함
                direction: currentDirection
              });
              
              // 새 구간 시작 (연결점으로 현재 포인트부터 시작)
              currentSegment = [point];
              currentDirection = direction;
            } else {
              currentSegment.push(point);
            }
          });
          
          // 마지막 구간 저장
          if (currentSegment.length > 0) {
            segments.push({
              data: currentSegment,
              direction: currentDirection
            });
          }
          
          // 각 구간별로 시리즈 생성
          //console.log(`🔵 슈퍼트렌드 구간 개수: ${segments.length}`);
          segments.forEach((segment, segmentIdx) => {
            const segmentColor = segment.direction === 1 ? '#34A853' : '#ef5350'; // 상승: 초록색, 하락: 빨간색
            const segmentName = segment.direction === 1 ? '상승' : '하락';
            
            if (segment.data.length > 1) { // 최소 2개 포인트가 있어야 선을 그릴 수 있음
              const segmentSeries = chart.addSeries(LineSeries, {
                color: segmentColor,
                lineWidth: 3, // 슈퍼트렌드는 좀 더 굵게
                lineStyle: lineStyle,
                priceFormat: {
                  type: 'price',
                  precision: 2,
                  minMove: 0.01,
                },
                priceScaleId: priceScaleId,
                title: segmentIdx === 0 ? indicator.name : '', // 첫 번째 구간에만 이름 표시
                lastValueVisible: false, // 마지막 값 표시 숨김
                priceLineVisible: false, // 프라이스 라인 표시 숨김
              });
              
              segmentSeries.setData(segment.data);
              
              // 첫 번째 구간만 참조로 저장 (전체 지표를 대표)
              if (segmentIdx === 0) {
                seriesRefs.push({
                  series: segmentSeries,
                  name: indicator.name,
                  color: color,
                  type: 'indicator'
                });
              }

            } else {
              console.log(`❌ 구간 ${segmentIdx + 1} 스킵 (데이터 부족: ${segment.data.length}개)`);
            }
          });
          console.log('🟢 슈퍼트렌드 방향별 색상 적용 완료!');
        } else {
          // 일반 지표는 기존 방식으로 처리
          console.log(`🔴 일반 지표 처리: ${indicator.name}`);
          const lineSeriesOptions: any = {
            color: color,
            lineWidth: 2,
            lineStyle: lineStyle,
            priceFormat: {
              type: 'price',
              precision: 2,
              minMove: 0.01,
            },
            priceScaleId: priceScaleId,
          };
          
          // 슈퍼트렌드가 아닌 일반 지표는 부가 정보 표시 숨김
          if (!isSupertrend) {
            lineSeriesOptions.lastValueVisible = false; // 마지막 값 표시 숨김
            lineSeriesOptions.priceLineVisible = false; // 프라이스 라인 표시 숨김
          }
          
          const lineSeries = chart.addSeries(LineSeries, lineSeriesOptions);
          
          lineSeries.setData(seriesData);
          
          // 일반 지표 시리즈 참조 저장
          seriesRefs.push({
            series: lineSeries,
            name: indicator.name,
            color: color,
            type: 'indicator'
          });
          console.log(`✅ 일반 지표 시리즈 생성 완료: ${indicator.name}`);
        }
      }
    });
    
    // Y축 스케일 설정
    if (data.y_axis_configs) {
      if (primaryAxisConfig.title) {
        chart.priceScale('left').applyOptions({
          borderColor: primaryAxisConfig.color,
          scaleMargins: {
            top: data.candle_data && data.candle_data.length > 0 ? 0.6 : 0.1, // 캔들이 있으면 지표들을 위한 공간
            bottom: 0.1,
          },
          visible: primaryAxisConfig.display !== false, // display가 false면 축 숨김
        });
      }
      
      if (secondaryAxisConfig.title) {
        chart.priceScale('right').applyOptions({
          borderColor: secondaryAxisConfig.color,
          scaleMargins: {
            top: 0.1, // 캔들을 위한 적절한 여백
            bottom: data.candle_data && data.candle_data.length > 0 ? 0.4 : 0.1, // 다른 지표들을 위한 공간 확보
          },
          visible: secondaryAxisConfig.display !== false, // display가 false면 축 숨김
        });
      }

      // 범용 hidden 축 설정
      if (hiddenAxisConfig) {
        chart.priceScale('hidden').applyOptions({
          borderColor: hiddenAxisConfig.color || '#2196f3',
          visible: false, // 항상 숨김
          scaleMargins: {
            top: 0.25,    // 상단 패딩 증가 (10% → 20%)
            bottom: 0.25, // 하단 패딩 증가 (10% → 20%)
          },
        });
      }
    }
    
    // 마우스 이벤트를 위한 차트 컨테이너에 이벤트 리스너 추가
    let currentMouseX = 0;
    let currentMouseY = 0;
    
    const handleMouseMove = (event: MouseEvent) => {
      const rect = chartContainerRef.current?.getBoundingClientRect();
      if (rect) {
        currentMouseX = event.clientX - rect.left;
        currentMouseY = event.clientY - rect.top;
      }
    };
    
    chartContainerRef.current.addEventListener('mousemove', handleMouseMove);
    
    // 크로스헤어 이벤트 리스너 추가
    chart.subscribeCrosshairMove((param: any) => {
      if (!param.time) {
        setCrosshairData(null);
        return;
      }
      
      const indicators: { name: string; value: number | string; color: string }[] = [];
      let candleData: { open: number; high: number; low: number; close: number } | undefined;
      
      // 모든 시리즈에서 해당 시점의 데이터 수집
      seriesRefs.forEach(({ series, name, color, type }) => {
        const dataPoint = param.seriesData?.get(series);
        if (dataPoint) {
          if (type === 'candle') {
            candleData = {
              open: dataPoint.open,
              high: dataPoint.high,
              low: dataPoint.low,
              close: dataPoint.close,
            };
          } else {
            // 지표 데이터
            const value = dataPoint.value !== undefined ? dataPoint.value : dataPoint;
            indicators.push({
              name,
              value: typeof value === 'number' ? value.toFixed(2) : value,
              color
            });
          }
        }
      });
      
      // 시간 포맷팅
      const timeStr = typeof param.time === 'string' ? param.time : 
                     new Date(param.time * 1000).toISOString().split('T')[0];
      
      setCrosshairData({
        time: timeStr,
        candle: candleData,
        indicators,
        mouseX: currentMouseX,
        mouseY: currentMouseY
      });
    });
    
    // 리사이즈 핸들러
    const handleResize = () => {
      if (chartContainerRef.current && chartRef.current) {
        chartRef.current.applyOptions({
          width: chartContainerRef.current.clientWidth,
        });
      }
    };
    
    window.addEventListener('resize', handleResize);
    
    // 정리
    return () => {
      window.removeEventListener('resize', handleResize);
      if (chartContainerRef.current) {
        chartContainerRef.current.removeEventListener('mousemove', handleMouseMove);
      }
      if (chartRef.current) {
        chartRef.current.remove();
      }
    };
  }, [data, height]);
  
  // 범례 정보 표시용 컴포넌트
  const renderLegend = () => {
    return (
      <div style={{
        display: 'flex',
        flexWrap: 'wrap',
        justifyContent: 'center',
        alignItems: 'center',
        gap: '15px',
        marginTop: '10px',
        padding: '8px',
        fontSize: '0.75em',
        fontWeight: 500,
      }}>
        {/* 캔들 범례 - 한국 스타일 */}
        {data.candle_data && data.candle_data.length > 0 && (
          <div style={{
            display: 'flex',
            alignItems: 'center',
            gap: '5px',
          }}>
            <div style={{
              width: '8px',
              height: '12px',
              backgroundColor: '#ef5350',
              borderRadius: '1px',
              border: '1px solid #ef5350',
            }} />
            <span style={{ color: '#333' }}>캔들스틱</span>
          </div>
        )}
        
        {/* 지표 범례 */}
        {data.indicators && data.indicators.map((indicator: any, index: number) => {
          const color = indicator.color || CHART_COLORS[index % CHART_COLORS.length];
          
          // 슈퍼트렌드 지표인지 확인
          const isSupertrend = indicator.name && (
            indicator.name.toLowerCase().includes('supertrend') || 
            indicator.name.includes('슈퍼트렌드')
          );
          
          return (
            <div key={`legend-${index}`} style={{
              display: 'flex',
              alignItems: 'center',
              gap: '5px',
            }}>
              {isSupertrend ? (
                // 슈퍼트렌드의 경우 녹색+빨간색 반반 표시
                <div style={{
                  width: '12px',
                  height: '2px',
                  borderRadius: '1px',
                  display: 'flex',
                  overflow: 'hidden',
                }}>
                  <div style={{
                    width: '50%',
                    height: '100%',
                    backgroundColor: '#34A853', // 상승 녹색
                  }} />
                  <div style={{
                    width: '50%',
                    height: '100%',
                    backgroundColor: '#ef5350', // 하락 빨간색
                  }} />
                </div>
              ) : (
                // 일반 지표는 기존 방식
                <div style={{
                  width: '12px',
                  height: '2px',
                  backgroundColor: color,
                  borderRadius: '1px',
                }} />
              )}
              <span style={{ color: '#333' }}>{indicator.name}</span>
            </div>
          );
        })}
      </div>
    );
  };
  
  // 데이터가 유효하지 않은 경우 에러 메시지 표시 (indicators는 선택사항으로 변경)
  if (!data || !data.dates || data.dates.length === 0 || !data.candle_data || data.candle_data.length === 0) {
    return (
      <div style={{ 
        width: '100%', 
        height: `${height}px`,
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'center',
        backgroundColor: '#f8f9fa',
        border: '2px dashed #dee2e6',
        borderRadius: '8px',
        color: '#6c757d'
      }}>
        <div style={{ textAlign: 'center' }}>
          <div style={{ fontSize: '1.2em', marginBottom: '0.5em' }}>📊</div>
          <div>차트 데이터를 처리하는 중입니다...</div>
          <div style={{ fontSize: '0.8em', marginTop: '0.5em', color: '#999' }}>
            날짜: {data?.dates?.length || 0}개 | 캔들: {data?.candle_data?.length || 0}개 | 지표: {data?.indicators?.length || 0}개
          </div>
        </div>
      </div>
    );
  }

  return (
    <div style={{ width: '100%' }}>
      {/* Y축 라벨 */}
      {data.y_axis_configs && (
        <div style={{
          display: 'flex',
          justifyContent: 'space-between',
          marginBottom: '5px',
          fontSize: '0.75em',
          fontWeight: 'bold',
          color: '#666',
        }}>
          {data.y_axis_configs.primary?.title && data.y_axis_configs.primary?.display !== false && (
            <span style={{ color: data.y_axis_configs.primary.color }}>
              {data.y_axis_configs.primary.title}
            </span>
          )}
          {data.y_axis_configs.secondary?.title && data.y_axis_configs.secondary?.display !== false && (
            <span style={{ color: data.y_axis_configs.secondary.color }}>
              {data.y_axis_configs.secondary.title}
            </span>
          )}
          {/* hidden 축은 라벨을 표시하지 않음 (visible: false이므로) */}
        </div>
      )}
      
      {/* 차트 영역 */}
      <div 
        ref={chartContainerRef} 
        style={{ 
          width: '100%', 
          height: `${height}px`,
          position: 'relative'
        }}
      >
        {/* 크로스헤어 데이터 표시 - 마우스 팝업 */}
        {crosshairData && (() => {
          // 팝업 위치 계산 (화면 경계를 벗어나지 않도록 조정)
          const popupWidth = 300; // 예상 팝업 너비
          const popupHeight = 80; // 예상 팝업 높이
          
          let left = crosshairData.mouseX + 15; // 마우스 오른쪽에 표시
          let top = crosshairData.mouseY - 40; // 마우스 위쪽에 표시
          
          // 오른쪽 경계 체크
          if (left + popupWidth > chartContainerRef.current?.clientWidth!) {
            left = crosshairData.mouseX - popupWidth - 15; // 마우스 왼쪽에 표시
          }
          
          // 위쪽 경계 체크
          if (top < 0) {
            top = crosshairData.mouseY + 15; // 마우스 아래쪽에 표시
          }
          
          // 아래쪽 경계 체크
          if (top + popupHeight > chartContainerRef.current?.clientHeight!) {
            top = chartContainerRef.current?.clientHeight! - popupHeight - 10;
          }
          
          return (
            <div style={{
              position: 'absolute',
              left: `${left}px`,
              top: `${top}px`,
              zIndex: 1000,
              background: 'linear-gradient(135deg, rgba(255, 255, 255, 0.98), rgba(248, 250, 252, 0.98))',
              backdropFilter: 'blur(12px)',
              border: '1px solid rgba(226, 232, 240, 0.6)',
              borderRadius: '10px',
              padding: '10px 14px',
              fontSize: '0.85em',
              fontFamily: 'system-ui, -apple-system, sans-serif',
              boxShadow: '0 8px 32px rgba(0, 0, 0, 0.12)',
              display: 'flex',
              flexDirection: 'column',
              gap: '6px',
              minWidth: '200px',
              maxWidth: '300px',
              lineHeight: '1.3',
              transition: 'all 0.15s ease',
              pointerEvents: 'none', // 마우스 이벤트 무시
            }}>
              {/* 시간 표시 */}
              <div style={{ 
                fontSize: '0.9em',
                fontWeight: '600',
                color: '#1e293b',
                marginBottom: '4px',
                textAlign: 'center'
              }}>
                📅 {crosshairData.time}
              </div>
              
              {/* 캔들 데이터 표시 */}
              {crosshairData.candle && (
                <div style={{ 
                  display: 'grid',
                  gridTemplateColumns: 'repeat(4, 1fr)',
                  gap: '8px',
                  padding: '6px',
                  backgroundColor: 'rgba(248, 113, 113, 0.08)',
                  borderRadius: '6px',
                  border: '1px solid rgba(248, 113, 113, 0.2)'
                }}>
                  {[
                    { label: '시가', value: crosshairData.candle.open, color: '#64748b' },
                    { label: '고가', value: crosshairData.candle.high, color: '#dc2626' },
                    { label: '저가', value: crosshairData.candle.low, color: '#2563eb' },
                    { label: '종가', value: crosshairData.candle.close, color: '#1e293b' }
                  ].map(({ label, value, color }, idx) => (
                    <div key={idx} style={{ textAlign: 'center' }}>
                      <div style={{ 
                        fontSize: '0.75em', 
                        color: '#64748b',
                        fontWeight: '500',
                        marginBottom: '2px'
                      }}>{label}</div>
                      <div style={{ 
                        color: color,
                        fontWeight: '600',
                        fontSize: '0.85em'
                      }}>{value.toLocaleString()}</div>
                    </div>
                  ))}
                </div>
              )}
              
              {/* 지표 데이터 표시 */}
              {crosshairData.indicators.length > 0 && (
                <div style={{ display: 'flex', flexDirection: 'column', gap: '4px' }}>
                  {crosshairData.indicators.map((indicator, index) => (
                    <div key={index} style={{ 
                      display: 'flex', 
                      justifyContent: 'space-between',
                      alignItems: 'center',
                      padding: '3px 6px',
                      backgroundColor: 'rgba(99, 102, 241, 0.06)',
                      borderRadius: '4px'
                    }}>
                      <div style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
                        <div style={{
                          width: '6px',
                          height: '6px',
                          borderRadius: '50%',
                          backgroundColor: indicator.color,
                        }} />
                        <span style={{ 
                          color: '#475569',
                          fontSize: '0.8em',
                          fontWeight: '500'
                        }}>{indicator.name}</span>
                      </div>
                      <span style={{ 
                        color: '#1e293b',
                        fontWeight: '600',
                        fontSize: '0.85em'
                      }}>{indicator.value}</span>
                    </div>
                  ))}
                </div>
              )}
            </div>
          );
        })()}
      </div>
      
      {/* 범례 */}
      {renderLegend()}
    </div>
  );
};

// default export 수정
export default function EnhancedChartPairRenderer(props: { components: MessageComponent[] }) {
  // 글로벌 스타일 적용
  React.useEffect(() => {
    // 이미 스타일이 추가되어 있는지 확인
    const existingStyle = document.getElementById('chart-animations-style');
    if (!existingStyle) {
      const styleElement = document.createElement('style');
      styleElement.id = 'chart-animations-style';
      styleElement.innerHTML = globalStyle;
      document.head.appendChild(styleElement);
      
      // 컴포넌트 언마운트시 스타일 제거
      return () => {
        const styleToRemove = document.getElementById('chart-animations-style');
        if (styleToRemove) {
          document.head.removeChild(styleToRemove);
        }
      };
    }
  }, []);
  
  return <ChartPairRenderer components={props.components} />;
} 

// 지표별 색상을 반환하는 함수
function getIndicatorColor(indicatorName: string): string {
  const colorMap: { [key: string]: string } = {
    'rsi': '#ff6b6b',
    'macd': '#4ecdc4',
    'macd_signal': '#45b7d1',
    'macd_histogram': '#f9ca24',
    'sma_20': '#6c5ce7',
    'sma_60': '#a29bfe',
    'ema_12': '#fd79a8',
    'ema_26': '#fdcb6e',
    'bollinger_upper': '#00b894',
    'bollinger_middle': '#00cec9',
    'bollinger_lower': '#55a3ff',
    'adx': '#e17055',
    'adx_plus_di': '#00b894',
    'adx_minus_di': '#d63031',
    'supertrend': '#74b9ff',
    'adr': '#fd79a8',
    'stochastic_k': '#a29bfe',
    'stochastic_d': '#6c5ce7'
  };
  
  return colorMap[indicatorName] || '#74b9ff';
}

// 지표 타입을 반환하는 함수
function getIndicatorType(indicatorName: string): string {
  const typeMap: { [key: string]: string } = {
    'macd_histogram': 'histogram',
    'volume': 'histogram'
  };
  
  return typeMap[indicatorName] || 'line';
}