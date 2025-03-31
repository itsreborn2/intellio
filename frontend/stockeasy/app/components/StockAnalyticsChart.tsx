/**
 * StockAnalyticsChart.tsx
 * 종목 분석 차트 컴포넌트
 */
'use client';

import React, { useEffect, useState } from 'react';
import Plot from 'react-plotly.js';
import * as PlotlyTypes from 'plotly.js';
import Papa from 'papaparse';
import { fetchCSVData } from '../utils/fetchCSVData';

// CSV 행 타입 정의
interface CSVRow {
  [key: string]: string;
}

// 차트 데이터 타입 정의
interface StockData {
  name: string;
  code: string;
  values: number[];
  labels: string[];
}

// 컴포넌트 Props 타입 정의
interface StockAnalyticsChartProps {
  stockName?: string;
  stockCode?: string;
}

const StockAnalyticsChart: React.FC<StockAnalyticsChartProps> = ({ stockName, stockCode }) => {
  // 상태 관리
  const [stockData, setStockData] = useState<StockData>({
    name: '',
    code: '',
    values: [0, 0, 0, 0, 0],
    labels: ['', '', '', '', '']
  });
  const [loading, setLoading] = useState<boolean>(true);
  const [error, setError] = useState<string | null>(null);

  // CSV 데이터 로드 및 파싱
  useEffect(() => {
    const loadData = async () => {
      try {
        setLoading(true);
        setError(null);
        
        // CSV 파일 로드
        const csvData = await fetchCSVData('requestfile/value/PER.csv');
        
        console.log('CSV 데이터 로드 완료');
        
        // UTF-8 BOM이 있을 경우 제거 (한글 깨짐 방지를 위해)
        const cleanedCsvData = csvData.replace(/^\uFEFF/, '');
        
        // Papa Parse로 CSV 파싱 (complete 콜백을 사용한 올바른 방식)
        Papa.parse(cleanedCsvData, {
          header: false,
          encoding: 'utf8',
          complete: (results) => {
            console.log('파싱된 데이터 샘플:', results.data.slice(0, 3));
            
            if (results.data && Array.isArray(results.data) && results.data.length > 2) {
              // 헤더 행 가져오기 (G, H, I, J, K 컬럼에 해당하는 레이블)
              const headers = results.data[0] as string[];
              console.log('헤더:', headers);
              
              const labels = [
                headers[6] || 'G컬럼', 
                headers[7] || 'H컬럼', 
                headers[8] || 'I컬럼', 
                headers[9] || 'J컬럼', 
                headers[10] || 'K컬럼'
              ];
              
              console.log('라벨:', labels);
              
              // 기본 데이터 (3번째 행)
              let selectedStock = results.data[2] as string[]; 
              console.log('기본 선택 종목:', selectedStock);
              
              // 종목 코드/이름이 있을 경우 해당 종목 찾기
              if (stockName) {
                console.log('검색할 종목명:', stockName);
                
                // B 컬럼이 종목명
                const stockIndex = results.data.findIndex((row: any, index: number) => {
                  if (index >= 2 && row && Array.isArray(row) && row.length > 1) {
                    console.log(`${index}번 행 종목명:`, row[1]);
                    return row[1] === stockName;
                  }
                  return false;
                });
                
                console.log('찾은 종목 인덱스:', stockIndex);
                
                if (stockIndex !== -1) {
                  selectedStock = results.data[stockIndex] as string[];
                  console.log('선택된 종목 데이터:', selectedStock);
                }
              }
              
              if (selectedStock && selectedStock.length > 10) {
                // G, H, I, J, K 컬럼 값 추출 (인덱스 6~10)
                console.log('G컬럼 원본값:', selectedStock[6]);
                console.log('H컬럼 원본값:', selectedStock[7]);
                console.log('I컬럼 원본값:', selectedStock[8]);
                console.log('J컬럼 원본값:', selectedStock[9]);
                console.log('K컬럼 원본값:', selectedStock[10]);
                
                // 숫자 변환 전 문자열 처리
                const cleanNumber = (str: string | undefined): number => {
                  if (!str) return 0;
                  // 콤마 제거 및 공백 제거
                  const cleaned = str.replace(/,/g, '').trim();
                  const num = parseFloat(cleaned);
                  return isNaN(num) ? 0 : num;
                };
                
                const values = [
                  cleanNumber(selectedStock[6]), // G 컬럼
                  cleanNumber(selectedStock[7]), // H 컬럼
                  cleanNumber(selectedStock[8]), // I 컬럼
                  cleanNumber(selectedStock[9]), // J 컬럼
                  cleanNumber(selectedStock[10])  // K 컬럼
                ];
                
                console.log('변환된 값들:', values);
                
                setStockData({
                  name: selectedStock[1] || (stockName || ''),
                  code: selectedStock[0] || (stockCode || ''),
                  values,
                  labels
                });
                
                console.log('차트 데이터 설정 완료');
              } else {
                console.error('선택된 종목 데이터가 없거나 부족합니다');
                setError('종목 데이터를 찾을 수 없습니다.');
              }
            } else {
              console.error('CSV 데이터가 충분하지 않습니다');
              setError('데이터 형식이 올바르지 않습니다.');
            }
            
            setLoading(false);
          },
          error: (error: Error) => {
            console.error('파싱 중 오류 발생:', error);
            setError('CSV 파싱 중 오류가 발생했습니다.');
            setLoading(false);
          }
        });
      } catch (err) {
        console.error('데이터 로드 중 오류 발생:', err);
        setError('데이터를 불러오는 중 오류가 발생했습니다.');
        setLoading(false);
      }
    };
    
    loadData();
  }, [stockCode, stockName]);

  // 차트 데이터 및 레이아웃 설정
  const plotData: PlotlyTypes.Data[] = [
    {
      x: stockData.labels,
      y: stockData.values,
      type: 'bar' as const,
      marker: {
        color: Array(5).fill('#10A37F'), // 모든 막대를 동일한 색상(#10A37F)으로 설정
        line: {
          color: '#1F2937',
          width: 1
        }
      },
      hovertemplate: '%{y:.2f}<extra></extra>' // 호버 시 소수점 두 자리까지 표시
    }
  ];

  const plotLayout: Partial<PlotlyTypes.Layout> = {
    title: {
      text: `${stockData.name} (${stockData.code}) 재무 지표`,
      font: {
        family: 'Arial, "맑은 고딕", "Malgun Gothic", sans-serif',
        size: 18
      }
    },
    font: {
      family: 'Arial, "맑은 고딕", "Malgun Gothic", sans-serif'
    },
    xaxis: {
      title: {
        text: '지표',
        font: {
          family: 'Arial, "맑은 고딕", "Malgun Gothic", sans-serif',
          size: 14
        }
      },
      tickfont: {
        family: 'Arial, "맑은 고딕", "Malgun Gothic", sans-serif',
        size: 12
      }
    },
    yaxis: {
      title: {
        text: '값',
        font: {
          family: 'Arial, "맑은 고딕", "Malgun Gothic", sans-serif',
          size: 14
        }
      },
      showticklabels: true,
      tickformat: '.2f', // 소수점 두 자리까지 표시
      tickfont: {
        family: 'Arial, "맑은 고딕", "Malgun Gothic", sans-serif',
        size: 12
      },
      automargin: true, // Y축 레이블이 잘리지 않도록 자동 여백 설정
      tickmode: 'auto',
      nticks: 8, // 적절한 Y축 눈금 수 설정
      showgrid: true, // 그리드 라인 표시
      gridcolor: '#E5E7EB' // 그리드 색상
    },
    margin: {
      l: 100,  // 왼쪽 여백 더 증가
      r: 40,
      t: 80,
      b: 80
    },
    autosize: true,
    height: 400,
    hoverlabel: {
      font: {
        family: 'Arial, "맑은 고딕", "Malgun Gothic", sans-serif',
        size: 12
      },
      bgcolor: 'white',
      bordercolor: '#E5E7EB'
    }
  };

  // 차트 설정
  const config: Partial<PlotlyTypes.Config> = {
    displayModeBar: false,
    responsive: true,
    locale: 'ko'
  };

  // 로딩 중 표시
  if (loading) {
    return <div className="text-center p-4">데이터를 불러오는 중...</div>;
  }

  // 오류 표시
  if (error) {
    return <div className="text-center p-4 text-red-500">{error}</div>;
  }

  // 차트 렌더링
  return (
    <div className="my-4 w-full">
      <Plot
        data={plotData}
        layout={plotLayout}
        config={config}
        className="w-full h-full"
      />
    </div>
  );
};

export default StockAnalyticsChart;
