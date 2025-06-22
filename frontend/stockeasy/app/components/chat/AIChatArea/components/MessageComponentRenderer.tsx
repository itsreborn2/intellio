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
import { useMediaQuery } from '../hooks';
import PriceChart from './PriceChart';
import TechnicalIndicatorChart from './TechnicalIndicatorChart';

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
        <p style={{ margin: '0 0 5px 0', fontWeight: 'bold' }}>{String(label || '')}</p>
        {payload.map((entry, index) => (
          <p key={`tooltip-${index}`} style={{ 
            margin: '0', 
            color: entry.color,
            display: 'flex',
            justifyContent: 'space-between' 
          }}>
            <span style={{ marginRight: '10px', fontWeight: 500 }}>{String(entry.name || '')}: </span>
            <span style={{ fontWeight: 'bold' }}>
              {String(valuePrefix || '')}{typeof entry.value === 'number' ? entry.value.toLocaleString() : String(entry.value || '')}{String(valueSuffix || '')}
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
        {String(payload.value || '')}
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
          }}>{String(title)}</div>}
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
          }}>{String(title)}</div>}
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
          }}>{String(title)}</div>}
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
          }}>{String(title)}</div>}
          
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
          
          // dates 배열 추출 (이미 정규화된 값)
          const dates = chartData.dates || [];
          console.log('[MessageComponentRenderer] dates 길이:', dates?.length || 0);
          console.log('[MessageComponentRenderer] 첫 번째 날짜:', dates?.[0]);
          
          // OHLCV 데이터로 candle_data 구성
          const candle_data: any[] = [];
          if (dates && dates.length > 0) {
            for (let i = 0; i < dates.length; i++) {
              const candleItem = {
                time: dates[i],
                open: parseFloat(chartData.open?.[i] || chartData.close?.[i] || 0),
                high: parseFloat(chartData.high?.[i] || 0),
                low: parseFloat(chartData.low?.[i] || 0),
                close: parseFloat(chartData.close?.[i] || 0),
                volume: parseInt(chartData.volume?.[i] || 0),
                price_change_percent: parseFloat(chartData.price_change_percent?.[i] || 0)
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
              // 지표 데이터를 {time, value} 형태로 변환 (이미 정규화된 날짜 사용)
              const indicatorSeries = dates.map((date: string, index: number) => ({
                time: date,
                value: parseFloat(indicatorData[index]) || null
              })).filter((item: any) => item.value !== null && !isNaN(item.value));
              
              if (indicatorSeries.length > 0) {
                indicators.push({
                  name: key,
                  data: indicatorSeries
                  // 색상과 타입은 TechnicalIndicatorChart에서 결정
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
            dates: dates, // 이미 정규화된 날짜 사용
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
          }}>{String(title)}</div>}
          
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
          {title && <div style={{ fontWeight: 'bold', marginBottom: '0.5em', paddingLeft: '0.3em' }}>{String(title)}</div>}
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
                        {String(row[header.key] ?? '')}
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