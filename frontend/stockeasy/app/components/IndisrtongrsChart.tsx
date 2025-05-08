'use client'

import { useState, useEffect, useMemo, useRef } from 'react'
import ChartComponent from './ChartComponent'
import { fetchCSVData } from '../utils/fetchCSVData'
import Papa from 'papaparse'
import { copyTableAsImage } from '../utils/tableCopyUtils'
import { GuideTooltip } from 'intellio-common/components/ui/GuideTooltip';
import { formatDateMMDD } from '../utils/dateUtils';

// 차트 데이터 타입 정의
interface CandleData {
  time: string;
  open: number;
  high: number;
  low: number;
  close: number;
  volume: number;
}

// ETF 정보 타입 정의
interface ETFInfo {
  name: string;
  code: string;
  종목명: string;  // 추가: ETF 종목명
  섹터: string;    // 추가: ETF 섹터
  chartData: CandleData[];
  isLoading: boolean;
  error: string;
  isAboveMA20: boolean;  // null 타입 제거
  durationDays: number;  // null 타입 제거
  changePercent: number; // ETF 자체의 등락률
  대표종목?: string;  // 대표 종목 정보 추가
  포지션?: string;      // 포지션 정보 추가 (유지 +N일 등, CSV 기준)
  변동일?: string;      // 변동일 정보 추가 - 추가된 필드
  selectedStocks?: (RepresentativeStock & { chartData: CandleData[] })[];  // 선택된 대표 종목 정보 - RepresentativeStock 인터페이스 사용
  selectedStock?: RepresentativeStock;  // 선택된 대표 종목 정보 (단수형 유지 - 호환성)
}

// ETF 데이터 타입 정의
interface ETFData {
  종목코드: string;
  종목명: string;
  섹터: string;
  대표종목: string;
  등락률: string;
  변동일: string;
  포지션: string; // 유지 +N일 등 실제 유지 기간 정보 (CSV 컬럼명과 일치)
}

// 대표 주식 정보 타입 정의
interface RepresentativeStock {
  code: string;                // 종목코드
  name: string;                // 종목명
  lastChangePercent: string;   // 마지막등락률
  rs1m: number;               // RS_1M 값
  etfName: string;            // ETF명
  industry: string;           // 산업
  sector: string;             // 섹터
  originalEtfChange: string;  // 원본ETF등락률
  position: string;           // 포지션(일)
  rsValue: number;            // RS 값
}

// 산업 차트 컴포넌트
export default function IndustryCharts() {
  // ETF 정보 상태
  const [etfInfoList, setEtfInfoList] = useState<ETFInfo[]>([]);
  const [stockPriceData, setStockPriceData] = useState<{[key: string]: number[]}>({});
  const [chartDataMap, setChartDataMap] = useState<Record<string, CandleData[]>>({});
  const [selectedStocksChartMap, setSelectedStocksChartMap] = useState<Record<string, CandleData[]>>({});
  const [processedStocks, setProcessedStocks] = useState<string[]>([]);
  const [selectedStockCodes, setSelectedStockCodes] = useState<string[]>([]);
  const [isInitialLoading, setIsInitialLoading] = useState(true); // 초기 로딩 상태 추가
  const [updateDate, setUpdateDate] = useState<string | null>(null); // 새로운 업데이트 날짜 상태
  
  useEffect(() => {
    // 초기 ETF 정보 설정
    setEtfInfoList([]);
    
    // 모든 ETF 데이터 로드
    loadAllETFData();
    // 업데이트 날짜 로드
    loadUpdateDate();

    // 업데이트 시간 설정은 chartDataMap과 isInitialLoading을 기반으로 하는 별도의 useEffect에서 처리합니다.
  }, []);

  // 업데이트 날짜를 로드하는 함수 추가
  const loadUpdateDate = async () => {
    try {
      const cacheFilePath = '/requestfile/stock-data/stock_1idvb5kio0d6dchvoywe7ovwr-ez1cbpb.csv';
      const response = await fetch(cacheFilePath, { cache: 'no-store' });
      if (!response.ok) {
        throw new Error(`날짜 데이터 파일 로드 실패: ${response.status}`);
      }
      const csvText = await response.text();
      const parsedResult = Papa.parse(csvText, {
        header: true,
        skipEmptyLines: true,
      });

      if (parsedResult.data && parsedResult.data.length > 0) {
        const firstRow = parsedResult.data[0] as Record<string, string>; 
        const dateString = firstRow['날짜']; 
        if (dateString) {
          const formatted = formatDateMMDD(dateString);
          if (formatted) {
            setUpdateDate(formatted);
          } else {
            console.error('IndisrtongrsChart: 날짜 포맷 실패.');
          }
        } else {
          console.error('IndisrtongrsChart: CSV 파일에 "날짜" 컬럼이 없거나 비어있습니다.');
        }
      } else {
        console.error('IndisrtongrsChart: 날짜 CSV 파싱에 실패했거나 데이터가 없습니다.');
      }
    } catch (err) {
      console.error('IndisrtongrsChart: 업데이트 날짜 로드 중 오류 발생:', err);
    }
  };

  // chartDataMap에서 가장 최근 날짜를 추출하는 헬퍼 함수
  const getLatestDataDateFromMap = (dataMap: Record<string, CandleData[]>): string | null => {
    let latestDateObj: Date | null = null;

    Object.values(dataMap).forEach(chartDataArray => {
      if (chartDataArray.length > 0) {
        const lastDataPoint = chartDataArray[chartDataArray.length - 1];
        if (lastDataPoint && lastDataPoint.time) {
          try {
            const currentDateObj: Date = new Date(lastDataPoint.time);
            if (!isNaN(currentDateObj.getTime())) {
              if (!latestDateObj || currentDateObj > latestDateObj) {
                latestDateObj = currentDateObj;
              }
            }
          } catch (e) {
            console.error(`Error parsing date: ${lastDataPoint.time}`, e);
          }
        }
      }
    });

    if (latestDateObj) {
      // Workaround for potential type inference issue: explicitly cast to Date.
      // TypeScript should infer latestDateObj as Date here, but the linter reports 'never'.
      return formatDateMMDD((latestDateObj as Date).toISOString());
    }
    return null;
  };

  // 모든 ETF 데이터 로드 함수 - file_list.json을 사용하도록 완전히 재작성
  const loadAllETFData = async () => {
    setIsInitialLoading(true); // 로딩 시작 시 상태 설정
    try {
      // 선택된 종목 코드 초기화
      setSelectedStockCodes([]);
      
      // file_list.json에서 직접 파일 목록 가져오기
      const loadFileListFromJson = async () => {
        try {
          const response = await fetch(`/requestfile/etf_indiestocklist/file_list.json?t=${Date.now()}`);
          
          if (response.ok) {
            const fileList = await response.json();
            return fileList.files || [];
          }
          return [];
        } catch (error) {
          console.error('파일 목록 가져오기 오류:', error);
          return [];
        }
      };
      
      // 파일 목록 가져오기
      const fileList = await loadFileListFromJson();
      
      // 파일명에서 정보 추출하여 주식 데이터 객체로 변환
      const stocksData: RepresentativeStock[] = fileList
        .filter((fileName: string) => fileName !== 'file_list.json')
        .map((fileName: string) => {
          const parts = fileName.split('_');
          
          if (parts.length >= 10) {
            const code = parts[0];
            const name = parts[1];
            const lastChangePercent = parts[2];
            const rs1m = parseInt(parts[3] || '0');
            const etfName = parts[4] || '알 수 없음';
            const industry = parts[5] || '알 수 없음';
            const sector = parts[6] || '알 수 없음';
            const originalEtfChange = parts[7] || '0.00';
            const position = parts[8] || '0';
            // .csv 확장자 제거
            const rsValueStr = parts[9]?.replace(/\.csv$/, '') || '0';
            const rsValue = parseInt(rsValueStr);
            
            return {
              code,
              name,
              lastChangePercent,
              rs1m,
              etfName,
              industry,
              sector,
              originalEtfChange,
              position,
              rsValue
            };
          } else {
            // 파일명 형식이 다른 경우 기본값 설정
            return {
              code: '000000',
              name: '알 수 없음',
              lastChangePercent: '0.00',
              rs1m: 0,
              etfName: '알 수 없음',
              industry: '알 수 없음',
              sector: '알 수 없음',
              originalEtfChange: '0.00',
              position: '0',
              rsValue: 0
            };
          }
        })
        // RS_1M 기준 내림차순 정렬
        .sort((a: RepresentativeStock, b: RepresentativeStock) => b.rs1m - a.rs1m);
      
      // 고유한 ETF 목록 추출 (중복 제거)
      const uniqueEtfs = Array.from(
        new Set(stocksData.map(stock => stock.etfName))
      ).map(etfName => {
        // 해당 ETF에 속한 주식들
        const etfStocks = stocksData.filter(stock => stock.etfName === etfName);
        // 최대 RS_1M 값을 가진 주식 찾기
        const maxRs1mStock = etfStocks.reduce((max, stock) => 
          stock.rs1m > max.rs1m ? stock : max, etfStocks[0]);
        
        return {
          name: etfName,
          code: maxRs1mStock.code,  // 표시용 코드
          종목명: etfName,
          섹터: maxRs1mStock.sector,
          chartData: [],
          isLoading: false,
          error: '',
          isAboveMA20: false,
          durationDays: 0,
          changePercent: parseFloat(maxRs1mStock.lastChangePercent),
          포지션: `유지 +${maxRs1mStock.position}일`,
          selectedStocks: [] as (RepresentativeStock & { chartData: CandleData[] })[]
        } as ETFInfo;
      });
      
      // ETF 리스트 업데이트
      setEtfInfoList(uniqueEtfs);
      
      // 각 ETF에 대해 대표 종목 찾기
      for (let i = 0; i < uniqueEtfs.length; i++) {
        const etf = uniqueEtfs[i];
        // 해당 ETF에 속한 주식들 가져오기 (RS_1M 기준 정렬)
        const etfStocks = stocksData
          .filter(stock => stock.etfName === etf.name)
          .sort((a, b) => b.rs1m - a.rs1m)
          .slice(0, 2);  // 상위 2개만 선택
        
        try {
          // 각 주식의 차트 데이터 로드
          const stocksWithChart: (RepresentativeStock & { chartData: CandleData[] })[] = [];
          
          for (const stock of etfStocks) {
            try {
              // 파일 이름 생성
              const csvFilePath = `/requestfile/etf_indiestocklist/${stock.code}_${stock.name}_${stock.lastChangePercent}_${stock.rs1m}_${stock.etfName}_${stock.industry}_${stock.sector}_${stock.originalEtfChange}_${stock.position}_${stock.rsValue}.csv?t=${Date.now()}`;
              
              const response = await fetch(csvFilePath);
              
              if (response.ok) {
                const csvText = await response.text();
                const chartData = parseChartData(csvText);
                
                // 차트 데이터 저장
                const stockKey = `${etf.code}_${stock.code}`;
                setSelectedStocksChartMap(prev => ({
                  ...prev,
                  [stockKey]: chartData
                }));
                
                stocksWithChart.push({
                  ...stock,
                  chartData
                });
              }
            } catch (error) {
              console.error(`주식 차트 데이터 로드 오류 (${stock.code}):`, error);
            }
          }
          
          // ETF 정보 업데이트
          setEtfInfoList(prev => {
            const newList = [...prev];
            newList[i] = {
              ...newList[i],
              selectedStocks: stocksWithChart,
              selectedStock: stocksWithChart.length > 0 ? stocksWithChart[0] : undefined
            };
            return newList;
          });
          
        } catch (error) {
          console.error(`ETF 차트 데이터 로드 오류 (${etf.name}):`, error);
        }
      }
      
      return stocksData; // 주식 데이터 반환
    } catch (error) {
      console.error('ETF 데이터 로드 오류:', error);
      setEtfInfoList([]); // 오류 발생 시 목록 비우기
      // return []; // 이전 코드 주석 처리 또는 삭제
    } finally {
      setIsInitialLoading(false); // 로딩 완료 (성공/실패 무관)
    }
  };
  
  // 모든 주식 데이터 로드 함수 - 새로운 방식으로 재작성
  const loadAllStocksData = async (): Promise<RepresentativeStock[]> => {
    try {
      // file_list.json에서 파일 목록 가져오기
      const loadFileListFromJson = async () => {
        try {
          const response = await fetch(`/requestfile/etf_indiestocklist/file_list.json?t=${Date.now()}`);
          
          if (response.ok) {
            const fileList = await response.json();
            return fileList.files || [];
          }
          return [];
        } catch (error) {
          console.error('파일 목록 가져오기 오류:', error);
          return [];
        }
      };
      
      // 파일 목록 가져오기
      const files = await loadFileListFromJson();
      
      // 파일명에서 정보 추출하여 RepresentativeStock 객체로 변환
      const stocksData: RepresentativeStock[] = files
        .filter((fileName: string) => fileName !== 'file_list.json')
        .map((fileName: string) => {
          const parts = fileName.split('_');
          
          if (parts.length >= 10) {
            const code = parts[0];
            const name = parts[1];
            const lastChangePercent = parts[2];
            const rs1m = parseInt(parts[3] || '0');
            const etfName = parts[4] || '알 수 없음';
            const industry = parts[5] || '알 수 없음';
            const sector = parts[6] || '알 수 없음';
            const originalEtfChange = parts[7] || '0.00';
            const position = parts[8] || '0';
            // .csv 확장자 제거
            const rsValueStr = parts[9]?.replace(/\.csv$/, '') || '0';
            const rsValue = parseInt(rsValueStr);
            
            return {
              code,
              name,
              lastChangePercent,
              rs1m,
              etfName,
              industry,
              sector,
              originalEtfChange,
              position,
              rsValue
            };
          } else {
            // 파일명 형식이 다른 경우 기본값 설정
            return {
              code: '000000',
              name: '알 수 없음',
              lastChangePercent: '0.00',
              rs1m: 0,
              etfName: '알 수 없음',
              industry: '알 수 없음',
              sector: '알 수 없음',
              originalEtfChange: '0.00',
              position: '0',
              rsValue: 0
            };
          }
        })
        // RS_1M 기준 내림차순 정렬
        .sort((a: RepresentativeStock, b: RepresentativeStock) => b.rs1m - a.rs1m);
      
      return stocksData;
    } catch (error) {
      console.error('주식 데이터 로드 오류:', error);
      return [];
    }
  };
  
  // 참고: 대표 주식 로드 함수는 새로운 방식으로 구현되어 더 이상 필요하지 않음
  
  // ETF 차트 데이터 로드 함수
  const loadETFChartData = async (code: string, index: number, etfInfo: ETFInfo, selectedCodes: string[] = [], sectorToSelectedStocks: Record<string, string[]> = {}) => {
    try {
      // 로딩 상태 설정
      setEtfInfoList(prev => {
        const newList = [...prev];
        newList[index] = {
          ...newList[index],
          isLoading: true,
          error: ''
        };
        return newList;
      });
      
      // 대표종목 목록 가져오기
      const representativeStockNames = etfInfo.대표종목?.split(',').map(name => {
        // 괄호와 숫자 제거 (예: "파마리서치 (85)" -> "파마리서치")
        return name.trim().replace(/\s*\(\d+\)/g, '');
      }) || [];
      
      // 모든 주식 데이터 로드
      const stocksData = await loadAllStocksData();
      
      // 대표종목에 해당하는 모든 주식 찾기
      const allMatchingStocks: RepresentativeStock[] = [];
      
      // 각 대표종목에 대해 개별적으로 검색
      for (const stockName of representativeStockNames) {
        // 현재 종목명과 일치하는 주식 찾기 (대소문자 무시 및 공백 처리)
        const normalizedStockName = stockName.replace(/\s+/g, '').toLowerCase();
        
        const matchingStocks = stocksData.filter(stock => {
          const normalizedName = stock.name.replace(/\s+/g, '').toLowerCase();
          return normalizedName.includes(normalizedStockName) || normalizedStockName.includes(normalizedName);
        });
        
        if (matchingStocks.length > 0) {
          allMatchingStocks.push(...matchingStocks);
        }
      }
      
      // 중복 제거 (동일한 종목코드는 한 번만 포함)
      const uniqueStocks = Array.from(
        new Map(allMatchingStocks.map(stock => [stock.code, stock])).values()
      );
      
      // 현재 섹터
      const currentSector = etfInfo.섹터;

      // file_list.json에서 직접 파일 목록 가져오기
      const loadFileListFromJson = async () => {
        try {
          const response = await fetch(`/requestfile/etf_indiestocklist/file_list.json?t=${Date.now()}`);
          
          if (response.ok) {
            const fileList = await response.json();
            return fileList.files || [];
          }
          return [];
        } catch (error) {
          console.error('파일 목록 가져오기 오류:', error);
          return [];
        }
      };
      
      // 파일 목록 가져오기
      const fileList = await loadFileListFromJson();
      
      // 파일명에서 정보 추출하여 RepresentativeStock 객체로 변환
      const topStocks: RepresentativeStock[] = fileList
        .filter((fileName: string) => fileName !== 'file_list.json')
        .map((fileName: string) => {
          const parts = fileName.split('_');
          
          if (parts.length >= 10) {
            const code = parts[0];
            const name = parts[1];
            const lastChangePercent = parts[2];
            const rs1m = parseInt(parts[3] || '0');
            const etfName = parts[4] || etfInfo.종목명 || '알 수 없음';
            const industry = parts[5] || etfInfo.섹터 || '알 수 없음';
            const sector = parts[6] || '알 수 없음';
            const originalEtfChange = parts[7] || '0.00';
            const position = parts[8] || '0';
            // .csv 확장자 제거
            const rsValueStr = parts[9]?.replace(/\.csv$/, '') || '0';
            const rsValue = parseInt(rsValueStr);
            
            return {
              code,
              name,
              lastChangePercent,
              rs1m,
              etfName,
              industry,
              sector,
              originalEtfChange,
              position,
              rsValue
            };
          } else {
            // 파일명 형식이 다른 경우 기본값 설정
            return {
              code: '000000',
              name: '알 수 없음',
              lastChangePercent: '0.00',
              rs1m: 0,
              etfName: etfInfo.종목명 || '알 수 없음',
              industry: etfInfo.섹터 || '알 수 없음',
              sector: '알 수 없음',
              originalEtfChange: '0.00',
              position: '0',
              rsValue: 0
            };
          }
        })
        // RS_1M 기준 내림차순 정렬
        .sort((a: RepresentativeStock, b: RepresentativeStock) => b.rs1m - a.rs1m)
        // 최대 10개만 선택
        .slice(0, 10);


      // 섹터별로 이미 선택된 종목명을 추적
      // const sector = etfInfo.섹터; // 중복 선언 제거
      if (!sectorToSelectedStocks[currentSector]) {
        sectorToSelectedStocks[currentSector] = [];
      }

      // 대표종목이 없는 경우 처리 (topStocks가 비었으면 여기서 걸러짐)
      if (topStocks.length === 0) {
        setEtfInfoList(prev => {
          const newList = [...prev];
          // RS 90 이상 종목이 없다는 메시지로 변경
          newList[index] = {
            ...newList[index],
            isLoading: false,
            error: `RS 90 이상 대표종목 없음`,
            selectedStocks: [] // selectedStocks를 빈 배열로 명확히 설정
          };
          return newList;
        });
        return []; // 빈 배열 반환
      }
      
      // 선택된 종목들의 이름을 섹터 맵에 추가
      const selectedStockNames = topStocks.map(stock => stock.name);
      sectorToSelectedStocks[currentSector].push(...selectedStockNames);
      
      // 선택된 종목 코드 추가
      for (const stock of topStocks) {
        if (!selectedCodes.includes(stock.code)) {
          selectedCodes.push(stock.code);
        }
      }
      
      // 모든 선택된 종목의 차트 데이터 로드
      const loadedStocksData: (RepresentativeStock & { chartData: CandleData[] })[] = [];
      
      // 각 종목별로 차트 데이터 로드
      for (const stock of topStocks) {
        // 파일 경로 - 새로운 파일명 형식에 맞게 수정
        // 파일 경로: {code}_{name}_{lastChangePercent}_{rs1m}_{etfName}_{industry}_{sector}_{originalEtfChange}_{position}_{rsValue}.csv
        const csvFilePath = `/requestfile/etf_indiestocklist/${stock.code}_${stock.name}_${stock.lastChangePercent}_${stock.rs1m}_${stock.etfName}_${stock.industry}_${stock.sector}_${stock.originalEtfChange}_${stock.position}_${stock.rsValue}.csv?t=${Date.now()}`;
        
        try {
          const response = await fetch(csvFilePath);
          
          if (!response.ok) {
            // 종명이 변경되었거나 파일명 형식이 다른 경우 기존 방식 시도
            const oldFormatPath = `/requestfile/etf_indiestocklist/${stock.code}_${stock.name}_${stock.rsValue}.csv?t=${Date.now()}`;
            const oldResponse = await fetch(oldFormatPath);
            
            if (!oldResponse.ok) {
              continue; // 다음 종목으로 넘어감
            }
            
            const csvText = await oldResponse.text();
            const chartData = parseChartData(csvText);
            
            // 차트 데이터 저장
            const stockKey = `${code}_${stock.code}`;
            setSelectedStocksChartMap(prev => ({
              ...prev,
              [stockKey]: chartData
            }));
            
            // 로드된 데이터 배열에 추가 - 모든 필수 속성 포함
            loadedStocksData.push({ 
              code: stock.code, 
              name: stock.name, 
              lastChangePercent: stock.lastChangePercent || '0.00',
              rs1m: stock.rs1m || 0,
              etfName: stock.etfName || etfInfo.종목명 || '알 수 없음',
              industry: stock.industry || etfInfo.섹터 || '알 수 없음',
              sector: stock.sector || '알 수 없음',
              originalEtfChange: stock.originalEtfChange || '0.00',
              position: stock.position || '0',
              rsValue: stock.rsValue, 
              chartData 
            });
          } else {
            // 새 형식 파일 성공적으로 로드
            const csvText = await response.text();
            const chartData = parseChartData(csvText);
            
            // 차트 데이터 저장
            const stockKey = `${code}_${stock.code}`;
            setSelectedStocksChartMap(prev => ({
              ...prev,
              [stockKey]: chartData
            }));
            
            // 로드된 데이터 배열에 추가 - 모든 필수 속성 포함
            loadedStocksData.push({ 
              code: stock.code, 
              name: stock.name, 
              lastChangePercent: stock.lastChangePercent,
              rs1m: stock.rs1m,
              etfName: stock.etfName,
              industry: stock.industry,
              sector: stock.sector,
              originalEtfChange: stock.originalEtfChange,
              position: stock.position,
              rsValue: stock.rsValue, 
              chartData 
            });
          }
        } catch (error) {
          // 오류가 발생해도 다음 종목으로 계속 진행
        }
      }
      
      // 로드된 종목이 없는 경우
      if (loadedStocksData.length === 0) {
        setEtfInfoList(prev => {
          const newList = [...prev];
          newList[index] = {
            ...newList[index],
            isLoading: false,
            error: `대표종목 파일을 찾을 수 없습니다 (RS 값이 낮을 수 있음): ${topStocks.map(s => s.name).join(', ')}`
          };
          return newList;
        });
        return [];
      }
      
      // ETF 차트 데이터 로드
      const etfCsvFilePath = `/requestfile/rs_etf/${code}.csv?t=${Date.now()}`; // 타임스탬프 추가
      let etfChartData: CandleData[] = [];
      
      try {
        const response = await fetch(etfCsvFilePath);
        
        if (response.ok) {
          const csvText = await response.text();
          etfChartData = parseChartData(csvText);
          
          // 차트 데이터가 비어있는 경우 첫 번째 종목의 차트 데이터 사용
          if (!etfChartData || etfChartData.length < 2) {
            etfChartData = loadedStocksData[0].chartData;
          }
        } else {
          // ETF 차트 데이터가 없는 경우 첫 번째 종목의 차트 데이터 사용
          etfChartData = loadedStocksData[0].chartData;
        }
        
        // 차트 데이터 맵에 저장
        setChartDataMap(prev => ({ ...prev, [code]: etfChartData }));
      } catch (error) {
        // 오류 발생 시 첫 번째 종목의 차트 데이터 사용
        etfChartData = loadedStocksData[0].chartData;
        setChartDataMap(prev => ({ ...prev, [code]: etfChartData }));
      }
      
      // 등락율 계산 (차트 데이터가 있는 경우에만)
      const changePercent = etfChartData && etfChartData.length >= 2 ? calculateChangePercent(code) : 0;
      
      // 상태 업데이트
      setEtfInfoList(prev => {
        const newList = [...prev];
        const prevEtfInfo = newList[index]; // 이전 상태 가져오기
        newList[index] = {
          ...prevEtfInfo, // 이전 상태 값 유지
          chartData: etfChartData,
          isLoading: false,
          error: '',
          changePercent, // 계산된 숫자 값은 필요 시 유지
          selectedStocks: loadedStocksData, // 로드된 주식 데이터 설정
          selectedStock: loadedStocksData.length > 0 ? loadedStocksData[0] : undefined // 첫 번째 종목 정보 저장 (호환성 유지) - 모든 필드 포함
        };
        return newList;
      });
      
      return etfChartData;
    } catch (error) {
      console.error(`ETF 차트 데이터 로드 오류 (${code}):`, error);
      
      // 오류 상태 업데이트
      setEtfInfoList(prev => {
        const newList = [...prev];
        newList[index] = {
          ...newList[index],
          isLoading: false,
          error: error instanceof Error ? error.message : '알 수 없는 오류'
        };
        return newList;
      });
      
      return [];
    }
  };
  
  // 모든 ETF의 종가 데이터 로드 (20일선 계산용)
  const loadAllPriceData = async (tickers: string[]) => {
    const priceData: {[key: string]: number[]} = {};
    
    await Promise.all(
      tickers.map(async (ticker) => {
        try {
          const response = await fetch(`/requestfile/rs_etf/${ticker}.csv?t=${Date.now()}`); // 타임스탬프 추가
          if (response.ok) {
            const csvText = await response.text();
            const result = Papa.parse(csvText, { header: true });
            
            // 종가 데이터 추출
            const closePrices = result.data
              .filter((row: any) => row['종가'] && !isNaN(parseFloat(row['종가'])))
              .map((row: any) => parseFloat(row['종가']));
            
            if (closePrices.length > 0) {
              priceData[ticker] = closePrices;
            }
          }
        } catch (error) {
          console.error(`${ticker} 종가 데이터 로드 오류:`, error);
        }
      })
    );
    
    setStockPriceData(priceData);
    return priceData;
  };
  
  // 20일선 계산 및 정렬
  const calculateMA20AndSort = () => {
    setEtfInfoList(prev => {
      const newList = [...prev].map(etf => {
        // 20일선 위/아래 여부 및 유지 기간 계산
        const { isAboveMA20, durationDays } = calculate20DayMAStatus(etf.code);
        
        return {
          ...etf,
          isAboveMA20,
          durationDays
        };
      });
      
      // 정렬: 20일선 위에 있는 종목을 유지 기간 내림차순으로, 아래에 있는 종목을 20일선과의 근접도 순으로
      return newList.sort((a, b) => {
        // 둘 다 20일선 위에 있는 경우 -> 유지 기간 내림차순
        if (a.isAboveMA20 === true && b.isAboveMA20 === true) {
          return (b.durationDays || 0) - (a.durationDays || 0);
        }
        
        // 둘 다 20일선 아래에 있는 경우 -> 20일선과의 근접도 오름차순
        if (a.isAboveMA20 === false && b.isAboveMA20 === false) {
          return calculateMA20Proximity(a.code) - calculateMA20Proximity(b.code);
        }
        
        // 하나는 위, 하나는 아래에 있는 경우 -> 위에 있는 것이 우선
        return a.isAboveMA20 === true ? -1 : 1;
      });
    });
  };
  
  // 20일선 상태 계산
  const calculate20DayMAStatus = (ticker: string): { isAboveMA20: boolean; durationDays: number } => {
    try {
      const chartData = chartDataMap[ticker];
      if (!chartData || chartData.length < 20) {
        return { isAboveMA20: false, durationDays: 0 };
      }

      // 최근 20일 종가 데이터
      const recentData = chartData.slice(-20);
      const currentPrice = recentData[recentData.length - 1].close;
      const ma20 = recentData.reduce((sum, data) => sum + data.close, 0) / 20;
      const isAboveMA = currentPrice > ma20;

      // 연속일수 계산
      let durationDays = 1;
      for (let i = chartData.length - 2; i >= 0; i--) {
        const price = chartData[i].close;
        const prevMA20 = chartData.slice(Math.max(0, i - 19), i + 1).reduce((sum, data) => sum + data.close, 0) / Math.min(20, i + 1);
        
        if ((price > prevMA20) !== isAboveMA) {
          break;
        }
        durationDays++;
      }

      return { isAboveMA20: isAboveMA, durationDays };
    } catch (error) {
      console.error(`20일선 상태 계산 오류 (${ticker}):`, error);
      return { isAboveMA20: false, durationDays: 0 };
    }
  };
  
  // 20일선과의 근접도 계산 (낮을수록 더 가까움)
  const calculateMA20Proximity = (ticker: string): number => {
    if (!ticker || !stockPriceData[ticker] || stockPriceData[ticker].length < 20) {
      return Number.MAX_SAFE_INTEGER; // 데이터가 없으면 가장 낮은 우선순위
    }
    
    try {
      // 최근 데이터 추출
      const recentData = stockPriceData[ticker];
      
      // 현재가 (가장 최근 데이터)
      const currentPrice = recentData[recentData.length - 1];
      
      // 20일 이동평균 계산
      const ma20 = recentData.slice(-20).reduce((acc, val) => acc + val, 0) / 20;
      
      // 현재가와 20일 이동평균선의 차이 (절대값)
      return Math.abs((currentPrice - ma20) / ma20 * 100);
    } catch (error) {
      console.error(`20일선 근접도 계산 오류 (${ticker}):`, error);
      return Number.MAX_SAFE_INTEGER;
    }
  };
  
  // 등락율 계산
  const calculateChangePercent = (ticker: string): number => {
    try {
      const chartData = chartDataMap[ticker];
      
      if (!chartData || chartData.length < 2) {
        return 0;
      }
      
      // 최신 2개 데이터 추출
      const sortedData = [...chartData].sort((a, b) => 
        new Date(b.time).getTime() - new Date(a.time).getTime()
      );
      
      const recentData = sortedData.slice(0, 10); // 최근 10개 데이터
      
      if (recentData.length < 2) {
        return 0;
      }
      
      // 최신 종가와 이전 종가
      const latestData = recentData[0];
      const previousData = recentData[1];
      
      const previousClose = previousData.close;
      const currentClose = latestData.close;
      
      return ((currentClose - previousClose) / previousClose) * 100;
    } catch (error) {
      return 0;
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
  
  // 지속일에서 숫자 추출하는 함수
  const extractDurationDays = (durationText: string | undefined): number => {
    if (!durationText) return 0;
    const match = durationText.match(/유지\s+\+(\d+)일/);
    return match ? parseInt(match[1]) : 0;
  };
  
  // 헤더 배경색 결정 함수
  const getHeaderBackgroundColor = (etf: ETFInfo): string => {
    // 항상 초록색 계열 배경 사용
    return 'bg-[#D8EFE9] border-[#BBDCD3]';
  };
  
  // 상태 텍스트 가져오기
  const getStatusText = (etf: ETFInfo): string => {
    if (etf.isLoading) return '상태 확인 중';

    let statusText = '';
    const positionText = etf.포지션 || '';

    // '유지 +X일' 또는 '이탈 Y일' 형식 추출
    const match = positionText.match(/(유지\s*\+\d+일|이탈\s*-?\d+일)/);
    if (match) {
      statusText = match[0].replace('유지 ', ''); // '유지 ' 접두사를 제거
    } else {
      statusText = positionText; // 매칭되지 않으면 원본 텍스트 사용
    }

    return statusText;
  };
  
  // ETF를 행과 열로 분배
  const etfGrid = useMemo(() => {
    // 유지 +10일 이상인 ETF만 필터링하고 포지션 기준으로 정렬
    const sortedETFs = [...etfInfoList].filter(etf => {
      // 포지션에서 유지 기간 추출 및 10일 이상인지 확인
      const durationDays = extractDurationDays(etf.포지션);
      const isAbove10Days = !isNaN(durationDays) && durationDays >= 10;
      
      // 유지 상태인지 확인
      const isMaintenanceStatus = etf.포지션?.includes('유지') || false;
      
      // 필터링 조건: 유지 상태이고 10일 이상인 경우만 확인
      return isAbove10Days && isMaintenanceStatus;
    }).sort((a, b) => {
      const daysA = extractDurationDays(a.포지션);
      const daysB = extractDurationDays(b.포지션);
      return daysB - daysA; // 유지 기간 내림차순 정렬
    });
    
    // 데스크톱에서는 4개씩, 모바일에서는 1개씩 ETF를 행으로 나누기 위해 모든 ETF를 반환
    return sortedETFs;
  }, [etfInfoList]);
  
  // 종목명 우측에 등락률 표시
  const calculateStockChangePercent = (stock: { code: string; name: string; rsValue: number; chartData: CandleData[] }) => {
    try {
      if (!stock.chartData || stock.chartData.length < 2) {
        return 0;
      }
      
      // 가장 최근 데이터와 전일 데이터 가져오기
      const latestData = stock.chartData[stock.chartData.length - 1];
      const previousData = stock.chartData[stock.chartData.length - 2];
      
      // 전일 종가와 당일 종가로 등락율 계산
      const previousClose = previousData.close;
      const currentClose = latestData.close;
      
      return ((currentClose - previousClose) / previousClose) * 100;
    } catch (error) {
      console.error(`등락율 계산 오류 (${stock.name}):`, error);
      return 0;
    }
  };
  
  // 클립보드에 텍스트 복사 함수
  const copyToClipboard = (text: string) => {
    try {
      // 모던 브라우저에서 지원하는 Clipboard API 사용
      if (navigator.clipboard && navigator.clipboard.writeText) {
        navigator.clipboard.writeText(text)
          .then(() => {
            // 성공 시 추가 작업이 필요하면 여기에 구현
          })
          .catch((error) => {
            console.error('클립보드 복사 오류:', error);
            // 실패 시 대체 방법 사용
            fallbackCopyToClipboard(text);
          });
      } else {
        // 구형 브라우저 지원을 위한 대체 방법
        fallbackCopyToClipboard(text);
      }
    } catch (error) {
      console.error('클립보드 복사 중 오류 발생:', error);
    }
  };

  // 대체 클립보드 복사 방법
  const fallbackCopyToClipboard = (text: string) => {
    try {
      // 임시 텍스트 영역 생성
      const textArea = document.createElement('textarea');
      textArea.value = text;
      
      // 화면 밖으로 위치시키기
      textArea.style.position = 'fixed';
      textArea.style.left = '-999999px';
      textArea.style.top = '-999999px';
      
      document.body.appendChild(textArea);
      textArea.focus();
      textArea.select();
      
      // 복사 명령 실행
      const successful = document.execCommand('copy');
      
      // 임시 요소 제거
      document.body.removeChild(textArea);
      
      if (!successful) {
        console.error('클립보드 복사 실패 (대체 방법)');
      }
    } catch (error) {
      console.error('대체 클립보드 복사 중 오류 발생:', error);
    }
  };
  
  // 차트 클릭 시 종목 코드 복사 - 이벤트 핸들러 대신 직접 호출 방식으로 변경
  const copyStockCode = (etf: ETFInfo) => {
    try {
      // 클립보드에 종목 코드 복사
      if (etf.selectedStock) {
        const textToCopy = `${etf.selectedStock.code}`;
        // 안전한 클립보드 복사 함수 사용
        copyToClipboard(textToCopy);
      }
    } catch (error) {
      console.error('종목 코드 복사 오류:', error);
    }
  };
  
  return (
    <div>
      <div className="mb-4 flex items-center justify-between"> 
        <GuideTooltip
          title="섹터별 주도종목 차트"
          description={`이 차트는 각 섹터를 이끄는 주도 종목들을 한눈에 비교하고 파악할 수 있도록 설계되었습니다.\n\n*차트 구성*\n녹색 헤더: 해당 섹터가 속한 산업 분류, 관련 대표 ETF 명칭, 그리고 해당 ETF가 *20일 이동평균선 위에 머무른 기간(일수)*이 표시됩니다. 이를 통해 섹터 자체의 추세 강도를 참고할 수 있습니다.\n개별 종목 차트: 헤더 아래에는 해당 섹터 내에서 상대적으로 강한 흐름을 보이는 주요 종목들의 차트가 나열됩니다.\n\n각 종목 차트는 *일일 가격 변동(일봉)*을 기준으로 최근 약 2개월간의 가격 추세를 보여줍니다.`}
          side="bottom"
          width="min(90vw, 450px)"
          collisionPadding={{ top: 10, left: 260, right: 10, bottom: 10 }} 
        >
          <h2 className="font-semibold whitespace-nowrap text-sm md:text-base cursor-help">섹터별 주도종목 차트</h2>
        </GuideTooltip>
        <div className="flex items-center space-x-2">
          {updateDate && (
            <div className="text-xs text-gray-500">
              updated 17:00 {updateDate}
            </div>
          )}
        </div>
      </div>
      
      {/* 로딩 상태 표시 */}
      {isInitialLoading && (
        <div className="flex justify-center items-center h-64">
          <div className="loader ease-linear rounded-full border-4 border-t-4 border-gray-200 h-12 w-12 mb-4"></div>
          <span className="ml-4 text-gray-500">데이터 로딩 중...</span>
        </div>
      )}

      {/* 로딩 완료 후 데이터 없음 메시지 표시 */}
      {!isInitialLoading && etfInfoList.length === 0 && (
        <div className="text-center text-gray-500 text-sm sm:text-base px-4 py-6">
          <p>현재 조건에 맞는 종목 차트가 없습니다.</p>
          <p className="mt-1">시장 환경이 좋지 않은 상태를 의미합니다.</p>
        </div>
      )}

      {/* 로딩 완료 후 데이터 있음: 차트 렌더링 */}
      {!isInitialLoading && etfInfoList.length > 0 && (
        <div className="grid grid-cols-1 sm:grid-cols-2 md:grid-cols-3 lg:grid-cols-3 gap-6">
          {etfGrid.map((etf, index) => {
            // 모든 ETF 섹션 렌더링
            if (!etf.selectedStocks) {
              etf.selectedStocks = [];
            }

            // 대표 종목 데이터가 있는 경우에만 렌더링 진행
            return (
              <div key={index} className="flex flex-col gap-4">
                <div>
                  <div className="bg-[#EEF8F5] px-3 py-1 border-b flex justify-between items-center flex-wrap" style={{ borderRadius: '0.375rem 0.375rem 0 0' }}>
                    {/* flex-1을 적용하여 왼쪽 영역이 가능한 한 크게 확장되도록 하고, overflow-hidden으로 컨텐츠 자름 */}
                    <div className="flex items-center flex-1 min-w-0 overflow-hidden mr-2">
                      <span 
                        className="px-1.5 py-0.5 rounded bg-blue-100 text-blue-800 mr-1 shrink"
                        title={etf.섹터}
                        style={{
                          fontSize: 'clamp(0.65rem, 0.75vw, 0.75rem)', 
                          minWidth: '40px', 
                          maxWidth: '120px',
                          overflow: 'hidden', 
                          textOverflow: 'ellipsis', 
                          whiteSpace: 'nowrap',
                          display: 'inline-block',
                          verticalAlign: 'middle', 
                          textAlign: 'center', 
                          width: 'auto' 
                        }}
                      >
                        {etf.섹터}
                      </span>
                      <span 
                        className="font-medium shrink mr-1" 
                        title={etf.종목명} 
                        style={{
                          fontSize: 'clamp(0.65rem, 0.75vw, 0.75rem)', 
                          minWidth: '60px', 
                          overflow: 'hidden', 
                          textOverflow: 'ellipsis', 
                          whiteSpace: 'nowrap',
                          display: 'inline-block',
                          verticalAlign: 'middle'
                        }}
                      >
                        {etf.종목명}
                      </span>
                      <span 
                        className={`px-0 py-0.5 rounded shrink-0 ${etf.changePercent >= 0 ? 'text-red-600' : 'text-blue-600'}`}
                        style={{ fontSize: 'clamp(0.65rem, 0.75vw, 0.75rem)' }} 
                      >
                        {etf.changePercent}%
                      </span>
                    </div>
                    {/* shrink-0으로 오른쪽 버튼이 항상 필요한 너비만 유지하도록 함 */}
                    <span 
                      className={`px-1.5 py-0.5 rounded bg-[#D8EFE9] text-teal-800 shrink-0`}
                      style={{ fontSize: 'clamp(0.65rem, 0.75vw, 0.75rem)' }} 
                    >
                      {getStatusText(etf)}
                    </span>
                  </div>
                  
                  {etf.selectedStocks && etf.selectedStocks.slice(0, 2).map((stock, stockIndex) => (
                    <div key={stockIndex}>
                      {/* 종목 헤더 - 반응형 레이아웃으로 개선 */}
                      <div className="bg-gray-100 px-3 py-1 border border-t-0 border-gray-200 flex justify-between items-center flex-wrap">
                        {/* 왼쪽 영역 - flex-1로 확장하고 overflow-hidden으로 컨텐츠 자름 */}
                        <div className="flex items-center flex-wrap flex-1 min-w-0 overflow-hidden mr-2">
                          {/* 산업 - shrink 클래스 추가하여 화면 소툰 시 법위 안에서 자동 축소되도록 설정 */}
                          <span 
                            className="px-1.5 py-0.5 rounded bg-blue-100 text-blue-800 mr-1 shrink" 
                            title={stock.industry}
                            style={{ 
                              fontSize: 'clamp(0.65rem, 0.75vw, 0.75rem)', 
                              minWidth: '40px', 
                              maxWidth: '120px', 
                              overflow: 'hidden', 
                              textOverflow: 'ellipsis', 
                              whiteSpace: 'nowrap',
                              display: 'inline-block',
                              verticalAlign: 'middle', 
                              textAlign: 'center', 
                              width: 'auto' 
                            }}
                          >
                            {stock.industry}
                          </span>
                          
                          {/* 종목명 - shrink 클래스 추가 */}
                          <span className="font-medium mr-1 shrink" 
                            title={stock.name}
                            style={{ 
                              fontSize: 'clamp(0.65rem, 0.75vw, 0.75rem)', 
                              minWidth: '40px', 
                              overflow: 'hidden', 
                              textOverflow: 'ellipsis', 
                              whiteSpace: 'nowrap',
                              display: 'inline-block',
                              verticalAlign: 'middle'
                            }}
                          >
                            {stock.name}
                          </span>
                          
                          {/* 마지막등락률 - shrink-0으로 항상 필요한 너비 유지 */}
                          <span 
                            className={`px-0 py-0.5 rounded shrink-0 ${parseFloat(stock.lastChangePercent) >= 0 ? 'text-red-600' : 'text-blue-600'}`}
                            style={{ fontSize: 'clamp(0.65rem, 0.75vw, 0.75rem)' }} 
                          >
                            {parseFloat(stock.lastChangePercent) >= 0 ? '+' : ''}{stock.lastChangePercent}%
                          </span>
                          
                          {/* ETF명 - 상단 헤더에서 이미 표시하고 있어 제거함 */}
                        </div>
                        
                        {/* 오른쪽 RS 값 영역 - shrink-0으로 항상 필요한 너비만 유지 */}
                        <div className="flex items-center shrink-0">
                          {/* 포지션(일) - 이미 상단에 표시되고 있어 제거함 */}
                          
                          {/* RS 값 */}
                          <div className="flex items-center">
                            <span className="text-xs text-gray-500 mr-1" style={{ fontSize: 'clamp(0.65rem, 0.75vw, 0.75rem)' }}>RS</span>
                            <span className="font-medium text-xs text-blue-600" style={{ fontSize: 'clamp(0.65rem, 0.75vw, 0.75rem)' }}>
                              {stock.rsValue}
                            </span>
                          </div>
                        </div>
                      </div>
                      <div className="border border-t-0 border-gray-200" style={{ borderRadius: stockIndex === Math.min((etf.selectedStocks?.length || 0) - 1, 1) ? '0 0 0.375rem 0.375rem' : '0', overflow: 'hidden' }}>
                        <ChartComponent
                          data={stock.chartData || []}
                          height={300}
                          width="100%"
                          showVolume={true}
                          showMA20={true}
                          title={`${stock.name}`}
                          parentComponent="IndisrtongrsChart"
                        />
                      </div>
                    </div>
                  ))}
                </div>
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
}
