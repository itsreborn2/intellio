'use client'

import { useState, useEffect, useMemo, useRef } from 'react'
import ChartComponent from './ChartComponent'
import { fetchCSVData } from '../utils/fetchCSVData'
import Papa from 'papaparse'
import { copyTableAsImage } from '../utils/tableCopyUtils'

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
  etfChangePercent: string; // 20malist.csv에서 가져온 ETF 등락률
  대표종목?: string;  // 대표 종목 정보 추가
  지속일?: string;      // 지속일 정보 추가
  변동일?: string;      // 변동일 정보 추가 - 추가된 필드
  selectedStocks?: {   // 선택된 대표 종목 정보 추가 (복수형으로 변경)
    code: string;
    name: string;
    rsValue: number;
    chartData: CandleData[];
  }[];
  selectedStock?: {   // 선택된 대표 종목 정보 (단수형 유지 - 호환성)
    code: string;
    name: string;
    rsValue: number;
  };
}

// 20malist.csv 파일의 행 타입 정의
interface ETFListRow {
  종목코드: string;
  종목명: string;
  섹터: string;
  대표종목: string;
  등락률: string;
  변동일: string;
  지속일: string;
}

// ETF 데이터 타입 정의
interface ETFData {
  종목코드: string;
  종목명: string;
  섹터: string;
  대표종목: string;
  등락률: string;
  변동일: string;
  지속일: string;
}

// 대표 주식 정보 타입 정의
interface RepresentativeStock {
  code: string;
  name: string;
  rsValue: number;
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
  
  useEffect(() => {
    // 초기 ETF 정보 설정
    setEtfInfoList([]);
    
    // 모든 ETF 데이터 로드
    loadAllETFData();
  }, []);
  
  // 모든 ETF 데이터 로드 함수
  const loadAllETFData = async () => {
    try {
      // 선택된 종목 코드 초기화
      setSelectedStockCodes([]);
      
      // 20malist.csv 파일 로드
      const response = await fetch('/requestfile/20ma_list/20malist.csv');
      const csvText = await response.text();
      
      // CSV 파싱
      const results = Papa.parse(csvText, {
        header: true,
        skipEmptyLines: true
      });
      
      // 데이터 변환 및 필터링
      const rows = results.data as ETFListRow[];
      console.log(`20malist.csv 파일에서 로드된 전체 ETF 수: ${rows.length}`);
      
      // 유지일 10일 이상인 ETF 필터링 및 로깅
      const filteredRows = rows.filter(row => {
        // 지속일 파싱 - 정규식 개선
        const durationText = row.지속일 || '';
        let durationDays = 0;
        
        // "유지 +" 패턴 확인
        if (durationText.includes('유지 +')) {
          const match = durationText.match(/유지\s+\+(\d+)일/);
          durationDays = match ? parseInt(match[1]) : 0;
        }
        
        const isAbove10Days = !isNaN(durationDays) && durationDays >= 10;
        console.log(`ETF ${row.종목명} (${row.종목코드}), 섹터: ${row.섹터}, 지속일: ${row.지속일}, 10일 이상: ${isAbove10Days}, 대표종목: ${row.대표종목}`);
        
        // 유지 +10일 이상인 경우만 포함
        return isAbove10Days;
      });
      
      console.log(`유지일 10일 이상 필터링 후 ETF 수: ${filteredRows.length}`);
      console.log('필터링된 ETF 섹터 목록:', Array.from(new Set(filteredRows.map(row => row.섹터))));
      
      // 각 ETF에 대해 대표 주식 로드
      const stocksData = await loadAllStocksData();
      console.log(`로드된 전체 주식 데이터 수: ${stocksData.length}`);
      
      // 로딩 상태 초기화
      const initialETFInfoList = filteredRows.map(etf => {
        return {
          name: etf.종목명,
          code: etf.종목코드,
          종목명: etf.종목명,
          섹터: etf.섹터,
          chartData: [],
          isLoading: true,
          error: '',
          isAboveMA20: false,
          durationDays: 0,
          // 등락률 파싱 - 음수 값도 올바르게 처리
          changePercent: (() => {
            const rawValue = etf.등락률 || '0%';
            const numericValue = parseFloat(rawValue.replace('%', '')) || 0;
            return numericValue;
          })(),
          etfChangePercent: etf.등락률 || '0%', // 20malist.csv에서 가져온 원본 등락률 문자열 저장
          대표종목: etf.대표종목,
          지속일: etf.지속일,
          변동일: etf.변동일 // 변동일 정보 추가
        } as ETFInfo;
      });
      
      // 각 ETF에 대해 대표 주식 로드
      for (const etf of filteredRows) {
        await loadRepresentativeStocks(etf, stocksData);
      }
      
      setEtfInfoList(initialETFInfoList);
      
      // 각 ETF에 대해 차트 데이터 로드 (순차 처리로 변경)
      // 이미 선택된 종목을 추적하기 위한 변수
      const selectedCodes: string[] = [];
      
      for (let i = 0; i < initialETFInfoList.length; i++) {
        const etf = initialETFInfoList[i];
        try {
          await loadETFChartData(etf.code, i, etf, selectedCodes);
        } catch (error) {
          console.error(`ETF 차트 데이터 로드 오류 (${etf.code}):`, error);
        }
      }
      
      console.log('모든 ETF 데이터 로드 완료');
      
      return filteredRows;
    } catch (error) {
      console.error('20malist.csv 파일 로드 오류:', error);
      return [];
    }
  };
  
  // 모든 주식 데이터 로드 함수
  const loadAllStocksData = async (): Promise<RepresentativeStock[]> => {
    try {
      const stocksData: RepresentativeStock[] = [];
      
      try {
        // 폴더 내의 CSV 파일들을 직접 읽는 방식으로 변경
        // 파일 이름 패턴: 000250_삼천당제약.csv (종목코드_종목명.csv)
        const folderPath = '/requestfile/etf_indiestocklist';
        
        // 폴더 내 모든 CSV 파일 목록 가져오기 시도
        const files = await listDirectoryFiles(folderPath);
        console.log(`etf_indiestocklist 폴더에서 찾은 파일 수: ${files.length}`);
        
        // 각 파일에서 종목코드, 종목명, RS 값 추출
        for (const fileName of files) {
          // 파일명에서 종목코드와 종목명 추출 (RS 값은 파일 내용에서 가져올 예정)
          const match = fileName.match(/(\d+)_(.+)\.csv/);
          if (match) {
            const [_, code, name] = match;
            
            try {
              // 파일 내용 읽기
              const response = await fetch(`${folderPath}/${fileName}`);
              const csvText = await response.text();
              
              // 첫 두 줄만 추출 (헤더와 첫 번째 데이터 행)
              const lines = csvText.split('\n').slice(0, 2);
              if (lines.length < 2) {
                console.warn(`${fileName} 파일에 충분한 데이터가 없습니다.`);
                continue;
              }
              
              // 헤더 행과 데이터 행 분리
              const headerLine = lines[0];
              const dataLine = lines[1];
              
              // 헤더에서 RS 컬럼의 인덱스 찾기
              const headers = headerLine.split(',');
              const rsIndex = headers.findIndex(h => h.trim() === 'RS');
              
              if (rsIndex === -1) {
                console.warn(`${fileName} 파일에 RS 컬럼이 없습니다.`);
                continue;
              }
              
              // 데이터 행에서 RS 값 추출
              const values = dataLine.split(',');
              const rsValue = values[rsIndex] ? parseInt(values[rsIndex].trim()) : 0;
              
              stocksData.push({
                code,
                name, // 원래 이름 그대로 사용
                rsValue: rsValue
              });
              
              console.log(`종목 ${name}(${code})의 RS 값을 파일 내용에서 추출: ${rsValue}`);
            } catch (error) {
              console.error(`${fileName} 파일 읽기 오류:`, error);
            }
          }
        }
      } catch (error) {
        console.error('폴더 내 파일 목록을 가져오는데 실패했습니다:', error);
        
        // 폴백: 기존 방식으로 파일 목록 가져오기
        console.log('폴백 방식으로 파일 목록 가져오기 시도...');
        
        // 직접 파일 접근 시도
        const fileNames = [];
        let index = 0;
        
        while (true) {
          try {
            // 파일이 존재하는지 확인하기 위해 HEAD 요청 시도
            const testResponse = await fetch(`/requestfile/etf_indiestocklist/file_${index}.csv`, { method: 'HEAD' });
            if (testResponse.ok) {
              // 파일이 존재하면 목록에 추가
              const response = await fetch(`/requestfile/etf_indiestocklist/file_${index}.csv`);
              const text = await response.text();
              const firstLine = text.split('\n')[0];
              if (firstLine) {
                fileNames.push(firstLine.trim());
              }
              index++;
            } else {
              // 파일이 더 이상 없으면 종료
              break;
            }
          } catch (e) {
            // 오류 발생 시 종료
            break;
          }
          
          // 안전장치: 너무 많은 파일을 시도하지 않도록 함
          if (index > 1000) break;
        }
        
        // 파일명에서 종목코드, 종목명, RS 값 추출
        for (const fileName of fileNames) {
          const match = fileName.match(/(\d+)_(.+)_(\d+)\.csv/);
          if (match) {
            const [_, code, name, rsValue] = match;
            stocksData.push({
              code,
              name,
              rsValue: parseInt(rsValue)
            });
          }
        }
      }
      
      return stocksData;
    } catch (error) {
      console.error('주식 데이터 로드 오류:', error);
      return [];
    }
  };
  
  // 폴더 내 파일 목록 가져오기 함수
  const listDirectoryFiles = async (folderPath: string): Promise<string[]> => {
    try {
      // file_list.json 파일에서 파일 목록 가져오기
      const response = await fetch(`${folderPath}/file_list.json`);
      const fileList = await response.json();
      
      console.log('file_list.json에서 가져온 파일 목록:', fileList.files);
      
      return fileList.files || [];
    } catch (error) {
      console.error('파일 목록을 가져오는데 실패했습니다:', error);
      return [];
    }
  };
  
  // 대표 주식 로드 함수
  const loadRepresentativeStocks = async (etf: ETFListRow, stocksData: RepresentativeStock[]) => {
    try {
      // 대표 주식 배열 초기화
      const representativeStocks: RepresentativeStock[] = [];
      
      // 대표 주식 목록 가져오기
      const stockNames = etf.대표종목.split(',').map(name => {
        // 괄호와 숫자 제거 (예: "파마리서치 (85)" -> "파마리서치")
        return name.trim().replace(/\s*\(\d+\)/g, '');
      }) || [];
      
      if (stockNames.length === 0) {
        console.log(`대표종목이 없습니다: ${etf.종목명}`);
      }
      
      // 각 대표 주식에 대해 RS 값 찾기
      for (const stockName of stockNames) {
        // 현재 종목명과 일치하는 주식 찾기 (대소문자 무시 및 공백 처리)
        const normalizedStockName = stockName.replace(/\s+/g, '').toLowerCase();
        
        const matchingStocks = stocksData.filter(stock => {
          const normalizedName = stock.name.replace(/\s+/g, '').toLowerCase();
          return normalizedName.includes(normalizedStockName) || normalizedStockName.includes(normalizedName);
        });
        
        if (matchingStocks.length > 0) {
          console.log(`ETF ${etf.종목명}의 대표종목 ${stockName}에 대해 ${matchingStocks.length}개 매칭 종목 찾음`);
          representativeStocks.push(...matchingStocks);
        } else {
          console.log(`ETF ${etf.종목명}의 대표종목 ${stockName}에 대한 매칭 종목을 찾을 수 없음`);
        }
      }
      
      // 중복 제거 (동일한 종목코드는 한 번만 포함)
      const uniqueStocks = Array.from(
        new Map(representativeStocks.map(stock => [stock.code, stock])).values()
      );
      
      // RS 값 기준으로 내림차순 정렬
      uniqueStocks.sort((a, b) => b.rsValue - a.rsValue);
      
      // 상위 2개 주식 선택
      const topStocks = uniqueStocks.slice(0, 2);
      
      console.log(`ETF ${etf.종목명}의 최종 선택된 대표종목: ${topStocks.map(s => `${s.name} (RS: ${s.rsValue})`).join(', ')}`);
      console.log(`ETF ${etf.종목명}의 대표종목 수: ${topStocks.length}`);
      
      // 선택된 대표 주식 정보 저장
      etf.대표종목 = topStocks.map(stock => `${stock.name} (${stock.rsValue})`).join(', ');
    } catch (error) {
      console.error(`대표 주식 로드 오류 (${etf.종목명}):`, error);
    }
  };
  
  // ETF 차트 데이터 로드 함수
  const loadETFChartData = async (code: string, index: number, etfInfo: ETFInfo, selectedCodes: string[] = []) => {
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
      const stockNames = etfInfo.대표종목?.split(',').map(name => {
        // 괄호와 숫자 제거 (예: "파마리서치 (85)" -> "파마리서치")
        return name.trim().replace(/\s*\(\d+\)/g, '');
      }) || [];
      
      if (stockNames.length === 0) {
        console.log(`대표종목이 없습니다: ${etfInfo.종목명}`);
      }
      
      // 모든 주식 데이터 로드
      const stocksData = await loadAllStocksData();
      
      // 대표종목에 해당하는 모든 주식 찾기
      const allMatchingStocks: RepresentativeStock[] = [];
      
      // 각 대표종목에 대해 개별적으로 검색
      for (const stockName of stockNames) {
        // 현재 종목명과 일치하는 주식 찾기 (대소문자 무시 및 공백 처리)
        const normalizedStockName = stockName.replace(/\s+/g, '').toLowerCase();
        
        const matchingStocks = stocksData.filter(stock => {
          const normalizedName = stock.name.replace(/\s+/g, '').toLowerCase();
          return normalizedName.includes(normalizedStockName) || normalizedStockName.includes(normalizedName);
        });
        
        if (matchingStocks.length > 0) {
          console.log(`ETF ${etfInfo.종목명}의 대표종목 ${stockName}에 대해 ${matchingStocks.length}개 매칭 종목 찾음`);
          allMatchingStocks.push(...matchingStocks);
        } else {
          console.log(`ETF ${etfInfo.종목명}의 대표종목 ${stockName}에 대한 일치하는 주식을 찾을 수 없음`);
        }
      }
      
      // 중복 제거 (동일한 종목코드는 한 번만 포함)
      const uniqueStocks = Array.from(
        new Map(allMatchingStocks.map(stock => [stock.code, stock])).values()
      );
      
      console.log(`ETF ${etfInfo.종목명}의 중복 제거 후 대표종목 수: ${uniqueStocks.length}`);
      
      // 이미 선택된 종목 제외하고 RS 값 기준으로 내림차순 정렬
      const availableStocks = uniqueStocks
        .filter(stock => !selectedCodes.includes(stock.code))
        .sort((a, b) => b.rsValue - a.rsValue);
      
      // 사용 가능한 종목이 없는 경우, 모든 종목 중에서 선택
      let topStocks = availableStocks.length > 0 
        ? availableStocks.slice(0, 2) 
        : uniqueStocks.sort((a, b) => b.rsValue - a.rsValue).slice(0, 2);
      
      console.log(`ETF ${etfInfo.종목명}의 상위 종목:`, topStocks.map(s => `${s.name} (RS: ${s.rsValue})`));
      
      // 대표종목이 없는 경우 처리
      if (topStocks.length === 0) {
        console.log(`ETF ${etfInfo.종목명}에 대한 대표종목을 찾을 수 없습니다.`);
        
        // 오류 상태 업데이트
        setEtfInfoList(prev => {
          const newList = [...prev];
          newList[index] = {
            ...newList[index],
            isLoading: false,
            error: '대표종목을 찾을 수 없습니다.'
          };
          return newList;
        });
        
        return [];
      }
      
      // 선택된 종목 코드 추가
      for (const stock of topStocks) {
        if (!selectedCodes.includes(stock.code)) {
          selectedCodes.push(stock.code);
        }
      }
      
      // 모든 선택된 종목의 차트 데이터 로드
      const loadedStocksData: { code: string; name: string; rsValue: number; chartData: CandleData[] }[] = [];
      
      // 각 종목별로 차트 데이터 로드
      for (const stock of topStocks) {
        const csvFilePath = `/requestfile/etf_indiestocklist/${stock.code}_${stock.name}.csv`;
        console.log(`종목 ${stock.name}에 대한 파일 경로: ${csvFilePath}`);
        
        try {
          const response = await fetch(csvFilePath);
          
          if (!response.ok) {
            console.log(`종목 파일 없음 (RS 값이 낮을 수 있음): ${csvFilePath}`);
            continue; // 다음 종목으로 넘어감
          }
          
          const csvText = await response.text();
          const chartData = parseChartData(csvText);
          
          // 차트 데이터 저장
          const stockKey = `${code}_${stock.code}`;
          setSelectedStocksChartMap(prev => ({
            ...prev,
            [stockKey]: chartData
          }));
          
          // 로드된 데이터 배열에 추가
          loadedStocksData.push({ 
            code: stock.code, 
            name: stock.name, 
            rsValue: stock.rsValue, 
            chartData 
          });
          
          console.log(`종목 ${stock.name}의 차트 데이터 로드 성공: ${chartData.length}개 데이터 포인트`);
        } catch (error) {
          console.log(`종목 ${stock.name} 파일 로드 실패: ${error}`);
          // 오류가 발생해도 다음 종목으로 계속 진행
        }
      }
      
      // 로드된 종목이 없는 경우
      if (loadedStocksData.length === 0) {
        console.log(`ETF ${etfInfo.종목명}에 대한 대표종목 차트 데이터를 찾을 수 없습니다.`);
        
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
      const etfCsvFilePath = `/requestfile/rs_etf/${code}.csv`;
      let etfChartData: CandleData[] = [];
      
      try {
        const response = await fetch(etfCsvFilePath);
        
        if (response.ok) {
          const csvText = await response.text();
          etfChartData = parseChartData(csvText);
          
          // 차트 데이터가 비어있는 경우 첫 번째 종목의 차트 데이터 사용
          if (!etfChartData || etfChartData.length < 2) {
            console.log(`ETF ${code} 차트 데이터가 비어있어 첫 번째 종목의 차트 데이터를 사용합니다.`);
            etfChartData = loadedStocksData[0].chartData;
          }
        } else {
          console.log(`ETF 차트 파일 없음: ${etfCsvFilePath}, 첫 번째 종목의 차트 데이터를 사용합니다.`);
          // ETF 차트 데이터가 없는 경우 첫 번째 종목의 차트 데이터 사용
          etfChartData = loadedStocksData[0].chartData;
        }
        
        // 차트 데이터 맵에 저장
        setChartDataMap(prev => ({ ...prev, [code]: etfChartData }));
      } catch (error) {
        console.log(`ETF ${etfInfo.종목명} 차트 파일 로드 실패: ${error}, 첫 번째 종목의 차트 데이터를 사용합니다.`);
        // 오류 발생 시 첫 번째 종목의 차트 데이터 사용
        etfChartData = loadedStocksData[0].chartData;
        setChartDataMap(prev => ({ ...prev, [code]: etfChartData }));
      }
      
      // 등락율 계산 (차트 데이터가 있는 경우에만)
      const changePercent = etfChartData && etfChartData.length >= 2 ? calculateChangePercent(code) : 0;
      
      // 상태 업데이트
      setEtfInfoList(prev => {
        const newList = [...prev];
        newList[index] = {
          ...newList[index],
          chartData: etfChartData,
          isLoading: false,
          error: '',
          changePercent,
          selectedStocks: loadedStocksData, // 로드된 종목 정보 저장 (차트 데이터 포함)
          selectedStock: loadedStocksData.length > 0 ? { // 첫 번째 종목 정보 저장 (호환성 유지)
            code: loadedStocksData[0].code,
            name: loadedStocksData[0].name,
            rsValue: loadedStocksData[0].rsValue
          } : undefined
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
          const response = await fetch(`/requestfile/rs_etf/${ticker}.csv`);
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
      // 이미 로드된 차트 데이터 사용
      const chartData = chartDataMap[ticker];
      if (!chartData || chartData.length < 2) {
        console.log(`차트 데이터가 부족함: ${ticker}, 기본값 0% 반환`);
        return 0;
      }
      
      // 가장 최근 데이터와 전일 데이터 가져오기
      const latestData = chartData[chartData.length - 1];
      const previousData = chartData[chartData.length - 2];
      
      // 전일 종가와 당일 종가로 등락율 계산
      const previousClose = previousData.close;
      const currentClose = latestData.close;
      
      return ((currentClose - previousClose) / previousClose) * 100;
    } catch (error) {
      console.log(`등락율 계산 오류 (${ticker}): ${error}, 기본값 0% 반환`);
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
    // 항상 초록색 배경 사용 (유지 상태)
    return 'bg-green-100 border-green-200';
  };
  
  // 상태 텍스트 가져오기
  const getStatusText = (etf: ETFInfo) => {
    // 지속일 정보가 있는 경우
    if (etf.지속일) {
      // 변동일 정보 추가 (연도 제거하고 월-일만 표시)
      let 변동일Text = '';
      if (etf.변동일) {
        // YYYY-MM-DD 형식에서 MM-DD만 추출
        const dateParts = etf.변동일.split('-');
        if (dateParts.length === 3) {
          변동일Text = `(${dateParts[1]}-${dateParts[2]})`;
        } else {
          변동일Text = `(${etf.변동일})`;
        }
      }
      return `${etf.지속일} ${변동일Text}`;
    }
    
    // 기본값
    return '정보 없음';
  };
  
  // ETF를 행과 열로 분배
  const etfGrid = useMemo(() => {
    // 유지 +10일 이상인 ETF만 필터링하고 지속일 기준으로 정렬
    const sortedETFs = [...etfInfoList].filter(etf => {
      // 지속일 추출 및 10일 이상인지 확인
      const durationDays = extractDurationDays(etf.지속일);
      const isAbove10Days = !isNaN(durationDays) && durationDays >= 10;
      
      // 유지 상태인지 확인
      const isMaintenanceStatus = etf.지속일?.includes('유지') || false;
      
      // 디버깅 로그 추가
      console.log(`ETF ${etf.종목명}, 섹터: ${etf.섹터}, 지속일: ${etf.지속일}, 대표종목 수: ${etf.selectedStocks?.length || 0}`);
      
      // 필터링 조건 완화: 유지 상태이고 10일 이상인 경우만 확인
      return isAbove10Days && isMaintenanceStatus;
    }).sort((a, b) => {
      const daysA = extractDurationDays(a.지속일);
      const daysB = extractDurationDays(b.지속일);
      return daysB - daysA; // 지속일 내림차순 정렬
    });
    
    // 디버깅 로그 추가
    console.log(`필터링 후 ETF 개수: ${sortedETFs.length}`);
    sortedETFs.forEach(etf => {
      console.log(`선택된 ETF: ${etf.종목명}, 섹터: ${etf.섹터}, 지속일: ${etf.지속일}, 대표종목 수: ${etf.selectedStocks?.length || 0}`);
    });
    
    // 4개씩 ETF를 행으로 나누기
    const rows: ETFInfo[][] = [];
    for (let i = 0; i < sortedETFs.length; i += 4) {
      const row = sortedETFs.slice(i, i + 4);
      rows.push(row);
    }
    
    return rows;
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
  
  // 클립보드에 텍스트 복사 함수 (에러 처리 추가)
  const copyToClipboard = (text: string) => {
    try {
      if (navigator.clipboard && navigator.clipboard.writeText) {
        navigator.clipboard.writeText(text)
          .then(() => {
            console.log('텍스트가 클립보드에 복사되었습니다.');
            // 성공 메시지 표시 (toast 대신 콘솔 로그 사용)
            console.log(`종목 코드가 복사되었습니다: ${text}`);
          })
          .catch((error) => {
            console.error('클립보드 복사 실패:', error);
            // 대체 방법: 임시 텍스트 영역 생성
            fallbackCopyToClipboard(text);
          });
      } else {
        // 클립보드 API를 지원하지 않는 경우 대체 방법 사용
        fallbackCopyToClipboard(text);
      }
    } catch (error) {
      console.error('클립보드 복사 중 오류 발생:', error);
      // 대체 방법: 임시 텍스트 영역 생성
      fallbackCopyToClipboard(text);
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
      
      if (successful) {
        console.log('텍스트가 클립보드에 복사되었습니다. (대체 방법)');
      } else {
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
    <div className="p-4">
      <div className="mb-4">
        <h2 className="text-xl font-bold">섹터별 주도종목 차트</h2>
        <p className="text-sm text-gray-500">20일 이동평균선 위에 10일 이상 유지중인 섹터별 ETF중 단기 RS_1M(한달)의 값이 90 이상의 대표종목 차트. 유지일이 긴 섹터 우선 정렬.</p>
      </div>
      
      {etfInfoList.length === 0 ? (
        <div className="flex justify-center items-center h-64">
          <div className="animate-spin rounded-full h-12 w-12 border-t-2 border-b-2 border-blue-500"></div>
        </div>
      ) : (
        <div className="flex flex-col gap-8">
          {etfGrid.map((row, rowIndex) => (
            <div key={rowIndex} className="flex gap-4">
              {row.map((etf, etfIndex) => (
                <div key={etfIndex} className="flex-1">
                  <div className="flex flex-col gap-4">
                    <div>
                      <div className="bg-green-100 px-3 py-1 border border-green-200 flex justify-between items-center" style={{ borderRadius: '0.375rem 0.375rem 0 0' }}>
                        <div className="flex items-center gap-2">
                          <span className="text-xs px-1.5 py-0.5 rounded bg-blue-100 text-blue-800">{etf.섹터 || ''}</span>
                          <span className="font-medium text-sm">{etf.종목명}</span>
                          <span className={`text-xs px-1.5 py-0.5 rounded ${parseFloat(etf.etfChangePercent) >= 0 ? 'text-red-600' : 'text-blue-600'}`}>
                            {etf.etfChangePercent}
                          </span>
                        </div>
                        <span className={`text-xs px-1.5 py-0.5 rounded bg-green-100 text-green-800`}>
                          {getStatusText(etf)}
                        </span>
                      </div>
                      
                      {etf.selectedStocks && etf.selectedStocks.slice(0, 2).map((stock, stockIndex) => (
                        <div key={stockIndex}>
                          {/* 종목 헤더 */}
                          <div className="bg-gray-100 px-3 py-1 border border-t-0 border-gray-200 flex justify-between items-center">
                            <div className="flex items-center gap-2">
                              <span className="font-medium text-sm">{stock.name}</span>
                              <span className={`text-xs px-1.5 py-0.5 rounded ${calculateStockChangePercent(stock) >= 0 ? 'text-red-600' : 'text-blue-600'}`}>
                                {calculateStockChangePercent(stock) >= 0 ? '+' : ''}{calculateStockChangePercent(stock).toFixed(2)}%
                              </span>
                            </div>
                            <div className="flex items-center gap-2">
                              <span className="text-xs text-gray-500">RS</span>
                              <span className="font-medium text-sm text-blue-600">{stock.rsValue}</span>
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
                      
                      {/* 빈 공간 추가 (종목이 1개만 있는 경우) */}
                      {etf.selectedStocks && etf.selectedStocks.length === 1 && (
                        <div className="h-[350px]"></div> // 차트 높이 + 헤더 높이에 맞춰 빈 공간 추가
                      )}
                    </div>
                  </div>
                </div>
              ))}
              
              {/* 빈 열 추가 (행에 ETF가 4개 미만인 경우) */}
              {Array.from({ length: 4 - row.length }).map((_, i) => (
                <div key={`empty-${i}`} className="flex-1"></div>
              ))}
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
