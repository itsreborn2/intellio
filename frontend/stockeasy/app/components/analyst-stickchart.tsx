/**
 * analyst-stickchart.tsx
 * 애널리스트 페이지용 막대 그래프 차트 컴포넌트
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
interface AnalystStickChartProps {
  stockName?: string;
  stockCode?: string;
}

const AnalystStickChart: React.FC<AnalystStickChartProps> = ({ stockName, stockCode }) => {
  // 상태 관리
  const [stockData, setStockData] = useState<StockData>({
    name: '',
    code: '',
    values: [0, 0, 0, 0],
    labels: ['', '', '', '']
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
              // 헤더 행 가져오기 (J, K, L, M 컬럼에 해당하는 레이블)
              const headers = results.data[0] as string[];
              console.log('헤더:', headers);
              
              // 레이블을 고정값으로 설정하여 한글 깨짐 문제 해결
              const labels = [
                '직전4분기', 
                '2025(E)', 
                '2026(E)', 
                '2027(E)'
              ];
              
              console.log('라벨:', labels);
              
              // 기본 데이터 (3번째 행)
              let selectedStock = results.data[2] as string[]; 
              console.log('기본 선택 종목:', selectedStock);
              
              // 종목 코드/이름이 있을 경우 해당 종목 찾기
              if (stockCode) {
                console.log('검색할 종목코드:', stockCode);
                
                // 종목코드로 찾기 (C 컬럼이 종목코드)
                const stockIndex = results.data.findIndex((row: any, index: number) => {
                  if (index >= 2 && row && Array.isArray(row) && row.length > 2) {
                    console.log(`${index}번 행 종목코드:`, row[2]);
                    return row[2] === stockCode;
                  }
                  return false;
                });
                
                console.log('찾은 종목 인덱스:', stockIndex);
                
                if (stockIndex !== -1) {
                  selectedStock = results.data[stockIndex] as string[];
                  console.log('선택된 종목 데이터:', selectedStock);
                }
              }
              
              if (selectedStock && selectedStock.length > 12) {
                // J, K, L, M 컬럼 값 추출 (인덱스 9~12)
                console.log('J컬럼 원본값:', selectedStock[9]);
                console.log('K컬럼 원본값:', selectedStock[10]);
                console.log('L컬럼 원본값:', selectedStock[11]);
                console.log('M컬럼 원본값:', selectedStock[12]);
                
                // 숫자 변환 전 문자열 처리
                const cleanNumber = (str: string | undefined): number => {
                  if (!str) return 0;
                  // 콤마 제거 및 공백 제거
                  const cleaned = str.replace(/,/g, '').trim();
                  const num = parseFloat(cleaned);
                  return isNaN(num) ? 0 : num;
                };
                
                const values = [
                  cleanNumber(selectedStock[9]),  // J 컬럼
                  cleanNumber(selectedStock[10]), // K 컬럼
                  cleanNumber(selectedStock[11]), // L 컬럼
                  cleanNumber(selectedStock[12])  // M 컬럼
                ];
                
                console.log('변환된 값들:', values);
                
                // props에서 직접 종목명과 종목코드를 사용
                setStockData({
                  name: stockName || '종목명 없음',
                  code: stockCode || '종목코드 없음',
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
        color: '#6366F1', // 보라색 계열로 변경
        line: {
          color: '#4F46E5',
          width: 1
        }
      },
      text: stockData.values.map(val => val.toFixed(2)), // PER 값을 텍스트로 표시
      textposition: 'outside', // 막대 위에 텍스트 표시
      hovertemplate: '<b>PER: %{y:.2f}</b><extra></extra>' // 호버 시 소수점 두 자리까지 표시
    },
    // 선 그래프와 포인트 (막대 꼭지점 연결)
    {
      x: stockData.labels,
      y: stockData.values, // 막대 꼭지점을 연결하도록 수정
      type: 'scatter' as const,
      mode: 'lines+markers',
      line: {
        color: '#F87171', // 빨간색 계열
        width: 2
      },
      marker: {
        color: '#FFFFFF', // 흰색 내부
        size: 8,
        line: {
          color: '#F87171', // 빨간색 테두리
          width: 2
        }
      },
      hoverinfo: 'none',
      showlegend: false
    }
  ];

  const plotLayout: Partial<PlotlyTypes.Layout> = {
    title: {
      text: `${stockData.name} (${stockData.code}) PER 추이`,
      font: {
        family: 'Arial, "맑은 고딕", "Malgun Gothic", sans-serif',
        size: 18
      }
    },
    font: {
      family: 'Arial, "맑은 고딕", "Malgun Gothic", sans-serif'
    },
    showlegend: false, // 범례 숨기기
    xaxis: {
      title: {
        text: '', // '지표' 텍스트 제거
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
        text: '', // '값' 텍스트 제거
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
      gridcolor: '#E5E7EB', // 그리드 색상
      zeroline: true, // 0 라인 표시
      zerolinecolor: '#9CA3AF', // 0 라인 색상
      zerolinewidth: 1 // 0 라인 두께
    },
    margin: {
      l: 60,  // 왼쪽 여백 감소
      r: 60,  // 오른쪽 여백 증가
      t: 80,
      b: 80,
      pad: 10 // 패딩 추가
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
    <div className="my-4 w-full flex justify-center items-center">
      <div className="w-full max-w-4xl">
        <Plot
          data={plotData}
          layout={{
            ...plotLayout,
            width: undefined, // 자동 너비 설정
            autosize: true,   // 자동 크기 조정 활성화
          }}
          config={{
            ...config,
            responsive: true  // 반응형 설정 추가
          }}
          className="w-full h-full"
          style={{ margin: '0 auto' }} // 중앙 정렬을 위한 스타일 추가
        />
      </div>
    </div>
  );
};

export default AnalystStickChart;
