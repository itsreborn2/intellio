'use client';

import { useEffect, useState, useRef } from 'react';
import Papa from 'papaparse';
import dynamic from 'next/dynamic';
import { PlotData, Layout, Config } from 'plotly.js';
// 공통 로딩 스피너 컴포넌트 import
import LoadingSpinner from '../../../components/LoadingSpinner';

// Plotly를 클라이언트 사이드에서만 로드하기 위해 dynamic import 사용
const Plot = dynamic(() => import('react-plotly.js'), { ssr: false });

interface ChartData {
  date: string[];
  kospi: number[];
  downRatio200: number[];  // 200down_ratio
  downRatio20: number[];   // 20down_ratio
}

export default function Chart2() {
  const [chartData, setChartData] = useState<ChartData>({ 
    date: [], 
    kospi: [], 
    downRatio200: [],
    downRatio20: []
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
  
  // CSV 데이터 로드
  useEffect(() => {
    async function fetchData() {
      try {
        setLoading(true);
        const response = await fetch('/requestfile/trend-following/marketmonitor.csv', { cache: 'no-store' });
        const csvText = await response.text();

        Papa.parse(csvText, {
          header: true,
          skipEmptyLines: true,
          complete: (results) => {
            const data = results.data as Array<{[key: string]: string}>;
            
            // 데이터 추출 및 가공
            const dates: string[] = [];
            const kospiValues: number[] = [];
            const downRatio200Values: number[] = [];
            const downRatio20Values: number[] = [];

            // 모든 데이터 사용 - 시간순 정렬
            const sortedData = [...data].sort((a, b) => {
              const dateA = new Date(a['일자']).getTime();
              const dateB = new Date(b['일자']).getTime();
              return dateA - dateB;
            });
            
            sortedData.forEach(row => {
              // 데이터 유효성 검사: 값이 존재하고 숫자 변환이 NaN이 아니어야 함
              const date = row['일자'];
              const kospi = parseFloat(row['KOSPI']);
              const downRatio200 = parseFloat(row['200down_ratio']);
              const downRatio20 = parseFloat(row['20down_ratio']);
              
              if (date && !isNaN(kospi) && !isNaN(downRatio200) && !isNaN(downRatio20)) {
                dates.push(date);
                kospiValues.push(kospi);
                downRatio200Values.push(downRatio200);
                downRatio20Values.push(downRatio20);
              } else {
                // 누락 row가 있으면 콘솔에 경고 로그 출력
                console.warn('누락/잘못된 row:', row);
              }
            });

            setChartData({
              date: dates,
              kospi: kospiValues,
              downRatio200: downRatio200Values,
              downRatio20: downRatio20Values
            });
            // 데이터 로딩은 완료됐지만, 차트 렌더링이 완료될 때까지 로딩 상태 유지
            // 차트가 렌더링될 때 onRender 이벤트에서 loading=false 설정
          },
          error: (error: any) => {
            console.error('CSV 파싱 오류:', error);
            setError('데이터를 불러오는 중 오류가 발생했습니다.');
            setLoading(false);
          }
        });
      } catch (error: any) {
        console.error('데이터 불러오기 오류:', error);
        setError('데이터를 불러오는 중 오류가 발생했습니다.');
        setLoading(false);
      }
    }

    fetchData();
  }, []);

  if (error) {
    return (
      <div className="h-full flex items-center justify-center">
        <p className="text-red-500">{error}</p>
      </div>
    );
  }

  // 데이터 로딩 중이거나 차트가 준비되지 않은 경우 로딩 스피너 표시
  if (loading || !chartReady) {
    // 로딩 상태에 따라 다른 메시지 표시
    const message = chartData.date.length > 0 ? "차트를 준비하는 중..." : "데이터를 불러오는 중...";
    return <LoadingSpinner size="md" message={message} />;
  }

  // 차트 데이터와 레이아웃 설정
  const data: Partial<PlotData>[] = [
    // KOSPI 라인 차트 (파란색, 좌측 Y축)
    {
      type: 'scatter',
      mode: 'lines',
      name: 'KOSPI',
      x: chartData.date,
      y: chartData.kospi,
      line: { color: '#2962FF', width: 2 },
      yaxis: 'y' as any
    },
    // 200down_ratio 라인 차트 (주황색, 우측 Y축)
    {
      type: 'scatter',
      mode: 'lines',
      name: '200일선 하락비율',
      x: chartData.date,
      y: chartData.downRatio200,
      line: { color: '#FF6D00', width: 2 },
      yaxis: 'y2' as any
    },
    // 20down_ratio 라인 차트 (초록색, 우측 Y축)
    {
      type: 'scatter',
      mode: 'lines',
      name: '20일선 하락비율',
      x: chartData.date,
      y: chartData.downRatio20,
      line: { color: '#00C853', width: 2 },
      yaxis: 'y2' as any
    }
  ];

  // 최소/최대값 계산을 통한 Y축 범위 조정
  const kospiMin = Math.min(...chartData.kospi) * 0.98;
  const kospiMax = Math.max(...chartData.kospi) * 1.02;
  
  // 200down_ratio와 20down_ratio의 최대값을 함께 고려
  const downRatioMax = Math.max(
    Math.max(...chartData.downRatio200),
    Math.max(...chartData.downRatio20)
  ) * 1.1; // 여유 공간 10% 추가
  
  const downRatioMin = 0; // ratio는 0부터 시작

  const layout: Partial<Layout> = {
    title: 'KOSPI vs 하락비율',
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
      title: '하락비율',
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
        onInitialized={() => console.log('차트 초기화 완료')} 
      />
    </div>
  );
}
