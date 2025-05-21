'use client';

import { useEffect, useState, useRef } from 'react';
import Papa from 'papaparse';
import dynamic from 'next/dynamic';
import { PlotData, Layout, Config } from 'plotly.js';
// 공통 로딩 스피너 컴포넌트 import
import LoadingSpinner from '../../../components/LoadingSpinner';

// Plotly를 클라이언트 사이드에서만 로드하기 위해 dynamic import 사용
const Plot = dynamic(() => import('react-plotly.js'), { ssr: false });

// 부모 컴포넌트에서 전달받을 데이터 타입
interface MarketMonitorData {
  [key: string]: any;
}

interface Chart3Props {
  data: MarketMonitorData[];
}

interface ChartData {
  date: string[];
  kospi: number[];
  highRatio: number[];  // 52W_High_ratio (신고가)
  lowRatio: number[];   // 52W_Low_ratio (신저가)
}

export default function Chart3({ data: marketDataFromProps }: Chart3Props) {
  const [chartData, setChartData] = useState<ChartData>({ 
    date: [], 
    kospi: [], 
    highRatio: [],
    lowRatio: []
  });
  const [loading, setLoading] = useState<boolean>(true);
  const [chartReady, setChartReady] = useState<boolean>(false);
  const [error, setError] = useState<string | null>(null);
  const containerRef = useRef<HTMLDivElement>(null);
  const [containerWidth, setContainerWidth] = useState<number>(0);

  // 컨테이너 크기 측정을 위한 리사이즈 핸들러
  useEffect(() => {
    const handleResize = () => {
      if (containerRef.current) {
        setContainerWidth(containerRef.current.offsetWidth);
      }
    };

    // 초기 크기 설정
    handleResize();

    // 리사이즈 이벤트 리스너 등록
    window.addEventListener('resize', handleResize);
    return () => {
      window.removeEventListener('resize', handleResize);
    };
  }, []);

  // 차트 데이터가 변경되면 차트 렌더링을 위한 충분한 시간(2초) 후에 로딩 상태 해제
  useEffect(() => {
    if (chartData.date.length > 0) {
      console.log('데이터 로딩 완료, 차트 렌더링 대기 시작...');
      const timer = setTimeout(() => {
        console.log('차트 렌더링 완료 처리');
        setChartReady(true);
        setLoading(false); // 로딩이 완전히 끝났음을 표시
      }, 2000); // 2초 지연 - 차트 렌더링에 충분한 시간
      
      return () => clearTimeout(timer);
    }
  }, [chartData]);
  
  // Props로 받은 데이터 처리
  useEffect(() => {
    if (marketDataFromProps && marketDataFromProps.length > 0) {
      setLoading(true); // 데이터 처리 시작
      setError(null);
      try {
        const dates: string[] = [];
        const kospiValues: number[] = [];
        const highRatioValues: number[] = [];
        const lowRatioValues: number[] = [];

        // 모든 데이터 사용 - 시간순 정렬 (props로 받은 데이터는 이미 정렬되어있을 수 있으나, 안전하게 재정렬)
        const sortedData = [...marketDataFromProps].sort((a, b) => {
          const dateA = new Date(a['일자']).getTime();
          const dateB = new Date(b['일자']).getTime();
          return dateA - dateB;
        });

        sortedData.forEach(row => {
          const date = row['일자'];
          const kospi = parseFloat(row['KOSPI']);
          const highRatio = parseFloat(row['52W_High_ratio']);
          const lowRatio = parseFloat(row['52W_Low_ratio']);

          if (date && !isNaN(kospi) && !isNaN(highRatio) && !isNaN(lowRatio)) {
            dates.push(date);
            kospiValues.push(kospi);
            highRatioValues.push(highRatio);
            lowRatioValues.push(lowRatio);
          } else {
            // console.warn('데이터 유효성 검사 실패 또는 누락된 값:', row);
          }
        });

        setChartData({
          date: dates,
          kospi: kospiValues,
          highRatio: highRatioValues,
          lowRatio: lowRatioValues
        });
        // setLoading(false)는 chartData 변경 후 chartReady를 설정하는 useEffect에서 관리
      } catch (e: any) {
        console.error('Props 데이터 처리 중 오류:', e);
        setError('차트 데이터를 처리하는 중 오류가 발생했습니다.');
        setLoading(false); // 오류 발생 시 로딩 중단
      }
    } else {
      // Props 데이터가 없거나 비어있는 경우 초기화 또는 로딩 상태 유지
      setChartData({ date: [], kospi: [], highRatio: [], lowRatio: [] });
      // 부모에서 로딩을 관리하므로 여기서는 setLoading(true)를 하지 않을 수 있음.
      // 현재는 부모의 로딩/에러 상태를 따르도록 이 부분은 비워둠.
    }
  }, [marketDataFromProps]);

  if (error) {
    return (
      <div className="h-full flex items-center justify-center">
        <p className="text-red-500">{error}</p>
      </div>
    );
  }

  // 부모 컴포넌트에서 loading, error를 이미 처리하고 있으므로, Chart3에서는 chartData 유무와 chartReady만으로 판단.
  if (!marketDataFromProps || marketDataFromProps.length === 0) {
    return null; // 부모의 로딩/에러 메시지에 의존
  }

  if (error) {
    return (
      <div className="h-full flex items-center justify-center">
        <p className="text-red-500">{error}</p>
      </div>
    );
  }

  // 데이터가 있고, 아직 차트가 준비되지 않은 경우
  if (!chartReady) {
    // 로딩 상태에 따라 다른 메시지 표시
    const message = chartData.date.length > 0 ? "차트를 준비하는 중..." : "데이터를 불러오는 중..."; 
    return <LoadingSpinner size="md" message={message} />;
  }

  // 차트 데이터와 레이아웃 설정
  const data: Partial<PlotData>[] = [
    // KOSPI를 처음에 배치하여 레전드에 먼저 표시
    {
      type: 'scatter',
      mode: 'lines',
      name: 'KOSPI',
      x: chartData.date,
      y: chartData.kospi,
      line: { color: '#2962FF', width: 2 },
      yaxis: 'y' as any
    },
    // 52W_High_ratio (신고가)
    {
      type: 'scatter',
      mode: 'lines',
      name: '52주 신고가 비율',
      x: chartData.date,
      y: chartData.highRatio,
      line: { color: '#FF1744', width: 2 },
      yaxis: 'y2' as any
    },
    // 52W_Low_ratio (신저가)
    {
      type: 'scatter',
      mode: 'lines',
      name: '52주 신저가 비율',
      x: chartData.date,
      y: chartData.lowRatio,
      line: { color: 'rgba(255, 183, 77, 1)', width: 2 },
      yaxis: 'y2' as any
    }
  ];

  // 최소/최대값 계산을 통한 Y축 범위 조정
  const kospiMin = Math.min(...chartData.kospi) * 0.98;
  const kospiMax = Math.max(...chartData.kospi) * 1.02;
  
  // 신고가/신저가 비율의 최대값을 함께 고려
  const ratioMax = Math.max(
    Math.max(...chartData.highRatio),
    Math.max(...chartData.lowRatio)
  ) * 1.1; // 여유 공간 10% 추가
  
  const ratioMin = 0; // 비율은 0부터 시작

  const layout: Partial<Layout> = {
    title: 'KOSPI vs 52주 신고가/신저가 비율',
    autosize: true,
    height: 300,
    margin: { l: 50, r: 50, b: 50, t: 50, pad: 4 },
    legend: { orientation: 'h', y: 1.1 },
    xaxis: {
      title: '일자',
      tickangle: -45,
      tickfont: { size: 10 },
      // 시간순 정렬된 데이터 모두 표시
      type: 'category' as any,
      categoryorder: 'trace' as any,
      // 날짜가 많을 경우 일분만 표시, 하지만 데이터는 모두 포함
      tickmode: 'auto',
      nticks: Math.min(12, chartData.date.length)
    },
    yaxis: {
      title: 'KOSPI',
      titlefont: { color: '#2962FF' },
      tickfont: { color: '#2962FF' },
      side: 'left' as 'left',
      range: [kospiMin, kospiMax]
    },
    yaxis2: {
      title: '52주 신고가/신저가 비율',
      titlefont: { color: '#7F7F7F' },
      tickfont: { color: '#7F7F7F' },
      overlaying: 'y',
      side: 'right' as 'right',
      range: [0, 1.0], // 고정 범위: 0.00부터 1.00까지
      tickformat: '.2f' // 소수점 두 자리까지 표시
    },
    showlegend: true,
    plot_bgcolor: '#ffffff',
    paper_bgcolor: '#ffffff',
    font: {
      family: 'Noto Sans KR, sans-serif'
    }
  };

  const config: Partial<Config> = {
    responsive: true,
    displayModeBar: false
  };

  return (
    <div ref={containerRef} className="w-full h-full">
      <Plot
        data={data}
        layout={{ ...layout, width: containerWidth }}
        config={config}
        style={{ width: '100%', height: '100%' }}
        onInitialized={() => setChartReady(true)} // 차트가 초기화 완료되면 표시
      />
    </div>
  );
}
