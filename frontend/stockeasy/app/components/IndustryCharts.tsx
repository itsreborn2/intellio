'use client'

import { useState, useEffect } from 'react'
import ChartComponent from './ChartComponent'
import { fetchCSVData } from '../utils/fetchCSVData'

// 차트 데이터 타입 정의
interface CandleData {
  time: string;
  open: number;
  high: number;
  low: number;
  close: number;
  volume: number;
}

// 산업 차트 컴포넌트
export default function IndustryCharts() {
  // 차트 데이터 관련 상태 - 13개의 차트를 위한 상태 배열
  const [chartDataArray, setChartDataArray] = useState<CandleData[][]>(Array.from({length: 13}, () => []));
  const [chartLoadingArray, setChartLoadingArray] = useState<boolean[]>(Array.from({length: 13}, () => true));
  const [chartErrorArray, setChartErrorArray] = useState<string[]>(Array.from({length: 13}, () => ''));
  // 산업명을 저장할 상태 추가
  const [industryNames, setIndustryNames] = useState<string[]>(Array.from({length: 13}, () => ''));
  
  // 산업 차트 데이터 파일 ID 목록 (실제 파일 ID로 교체 필요)
  const industryChartFileIds = [
    'industry_semiconductor', // 반도체
    'industry_it', // IT
    'industry_auto', // 자동차
    'industry_steel', // 철강
    'industry_shipbuilding', // 조선
    'industry_chemical', // 화학
    'industry_construction', // 건설
    'industry_finance', // 금융
    'industry_retail', // 유통
    'industry_food', // 식품
    'industry_pharma', // 제약
    'industry_energy', // 에너지
    'industry_telecom' // 통신
  ];
  
  // 산업명 목록
  const industryNameList = [
    '반도체',
    'IT',
    '자동차',
    '철강',
    '조선',
    '화학',
    '건설',
    '금융',
    '유통',
    '식품',
    '제약',
    '에너지',
    '통신'
  ];
  
  useEffect(() => {
    // 모든 산업 차트 데이터 로드
    const loadAllIndustryChartData = async () => {
      // 산업명 설정
      setIndustryNames(industryNameList);
      
      // 각 산업별 차트 데이터 로드
      await Promise.all(
        industryChartFileIds.map((fileId, index) => loadIndustryChartData(fileId, index))
      );
    };
    
    loadAllIndustryChartData();
  }, []);
  
  // 산업 차트 데이터 로드 함수
  const loadIndustryChartData = async (fileId: string, index: number) => {
    // 차트 로딩 상태 설정
    setChartLoadingArray(prev => {
      const newArray = [...prev];
      newArray[index] = true;
      return newArray;
    });
    
    // 차트 오류 초기화
    setChartErrorArray(prev => {
      const newArray = [...prev];
      newArray[index] = '';
      return newArray;
    });
    
    try {
      // 로컬 캐시 파일 경로 (실제 경로로 교체 필요)
      const cacheFilePath = `/cache/stock-data/${fileId}.csv`;
      
      // 로컬 캐시 파일 로드
      const response = await fetch(cacheFilePath);
      
      if (!response.ok) {
        throw new Error(`캐시 파일 로드 실패: ${response.status}`);
      }
      
      const csvText = await response.text();
      
      // CSV 파싱 및 차트 데이터 변환
      const chartData = parseChartData(csvText);
      
      // 차트 데이터 설정
      setChartDataArray(prev => {
        const newArray = [...prev];
        newArray[index] = chartData;
        return newArray;
      });
    } catch (err) {
      console.error(`산업 차트 데이터 로드 오류 (${fileId}):`, err);
      
      // 오류 메시지 설정
      setChartErrorArray(prev => {
        const newArray = [...prev];
        newArray[index] = `데이터를 로드하는데 실패했습니다: ${err instanceof Error ? err.message : '알 수 없는 오류'}`;
        return newArray;
      });
      
      // 샘플 데이터 생성
      const sampleData = generateSampleChartData();
      setChartDataArray(prev => {
        const newArray = [...prev];
        newArray[index] = sampleData;
        return newArray;
      });
    } finally {
      // 로딩 상태 해제
      setChartLoadingArray(prev => {
        const newArray = [...prev];
        newArray[index] = false;
        return newArray;
      });
    }
  };
  
  // CSV 데이터를 차트 데이터로 파싱하는 함수
  const parseChartData = (csvText: string): CandleData[] => {
    try {
      // CSV 파싱 (간단한 구현, 실제로는 더 복잡할 수 있음)
      const lines = csvText.trim().split('\n');
      const headers = lines[0].split(',');
      
      // 헤더 인덱스 찾기
      const dateIndex = headers.findIndex(h => h.includes('날짜') || h.includes('Date'));
      const openIndex = headers.findIndex(h => h.includes('시가') || h.includes('Open'));
      const highIndex = headers.findIndex(h => h.includes('고가') || h.includes('High'));
      const lowIndex = headers.findIndex(h => h.includes('저가') || h.includes('Low'));
      const closeIndex = headers.findIndex(h => h.includes('종가') || h.includes('Close'));
      const volumeIndex = headers.findIndex(h => h.includes('거래량') || h.includes('Volume'));
      
      // 데이터 변환
      const chartData: CandleData[] = [];
      
      for (let i = 1; i < lines.length; i++) {
        const values = lines[i].split(',');
        
        if (values.length >= Math.max(dateIndex, openIndex, highIndex, lowIndex, closeIndex, volumeIndex) + 1) {
          chartData.push({
            time: values[dateIndex],
            open: parseFloat(values[openIndex]),
            high: parseFloat(values[highIndex]),
            low: parseFloat(values[lowIndex]),
            close: parseFloat(values[closeIndex]),
            volume: parseFloat(values[volumeIndex])
          });
        }
      }
      
      return chartData;
    } catch (error) {
      console.error('차트 데이터 파싱 오류:', error);
      return generateSampleChartData();
    }
  };
  
  // 샘플 차트 데이터 생성 함수
  const generateSampleChartData = (): CandleData[] => {
    const data: CandleData[] = [];
    const today = new Date();
    
    // 최근 60일 데이터 생성
    for (let i = 60; i >= 0; i--) {
      const date = new Date(today);
      date.setDate(today.getDate() - i);
      
      // 주말 제외
      if (date.getDay() === 0 || date.getDay() === 6) continue;
      
      const formattedDate = date.toISOString().split('T')[0]; // YYYY-MM-DD 형식
      
      // 이전 종가 또는 초기값
      const prevClose = data.length > 0 ? data[data.length - 1].close : 10000;
      
      // 가격 변동 (-3% ~ +3%)
      const changePercent = (Math.random() * 6) - 3;
      const close = Math.round(prevClose * (1 + changePercent / 100));
      
      // 일중 변동폭
      const dayRange = close * 0.02; // 2% 범위
      const high = Math.round(close + (Math.random() * dayRange));
      const low = Math.round(close - (Math.random() * dayRange));
      const open = Math.round(low + (Math.random() * (high - low)));
      
      // 거래량 (100,000 ~ 1,000,000)
      const volume = Math.round(100000 + Math.random() * 900000);
      
      data.push({
        time: formattedDate,
        open,
        high,
        low,
        close,
        volume
      });
    }
    
    return data;
  };
  
  return (
    <div className="bg-white rounded-md shadow p-4">
      <div className="mb-4 font-medium">산업 차트</div>
      
      <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
        {Array.from({ length: 13 }).map((_, index) => (
          <div key={index} className="bg-white rounded-md shadow">
            <div className="p-3 border-b border-gray-200 flex justify-between items-center">
              <span className="font-medium">{industryNames[index]}</span>
            </div>
            
            {chartLoadingArray[index] ? (
              <div className="h-80 flex items-center justify-center">
                <div className="text-gray-500">차트 로딩 중...</div>
              </div>
            ) : chartErrorArray[index] ? (
              <div className="h-80 flex items-center justify-center">
                <div className="text-red-500">{chartErrorArray[index]}</div>
              </div>
            ) : chartDataArray[index].length === 0 ? (
              <div className="h-80 flex items-center justify-center">
                <div className="text-gray-500">데이터가 없습니다.</div>
              </div>
            ) : (
              <ChartComponent
                data={chartDataArray[index]}
                height={300}
              />
            )}
          </div>
        ))}
      </div>
    </div>
  );
}
