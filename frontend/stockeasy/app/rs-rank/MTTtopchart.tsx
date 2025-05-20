'use client'

import { useState, useEffect, useMemo } from 'react'
import { formatDateMMDD } from '../utils/dateUtils'
import ChartComponent from '../components/ChartComponent'
import { fetchCSVData } from '../utils/fetchCSVData'
import Papa from 'papaparse'

// 차트 데이터 타입 정의
interface CandleData {
  time: string
  open: number
  high: number
  low: number
  close: number
  volume: number
}

// CSV 데이터를 파싱한 결과를 위한 인터페이스
interface CSVData {
  headers: string[]
  rows: any[]
  errors: any[]
}

// MTTtopchart 컴포넌트
export default function MTTtopchart() {
  // 상태 관리
  const [chartData, setChartData] = useState<{ [key: string]: CandleData[] }>({})
  const [stockInfo, setStockInfo] = useState<{ [key: string]: { name: string, marketType: string, rs1m: string } }>({})
  const [loading, setLoading] = useState<boolean>(true)
  const [error, setError] = useState<string | null>(null)
  const [updateDate, setUpdateDate] = useState<string>('')
  const [fileNames, setFileNames] = useState<string[]>([])
  const [kospiIndexData, setKospiIndexData] = useState<CandleData[]>([])
  const [kosdaqIndexData, setKosdaqIndexData] = useState<CandleData[]>([])

  // 페이지 로드 시 데이터 로드
  useEffect(() => {
    loadFileList()
    loadMarketIndexData()
  }, [])

  // 파일 목록을 직접 설정
  const loadFileList = async () => {
    try {
      // 파일 목록을 직접 하드코딩 (find_by_name 도구로 확인한 CSV 파일 목록)
      const fileList = [
        '000500_가온전선_KOSDAQ_97_y.csv',
        '006800_미래에셋증권_KOSDAQ_97_y.csv',
        '018000_유니슨_KOSDAQ_98_y.csv',
        '034020_두산에너빌리티_KOSDAQ_97_y.csv',
        '071320_지역난방공사_KOSDAQ_97_y.csv',
        '079550_LIG넥스원_KOSDAQ_97_y.csv',
        '083650_비에이치아이_KOSDAQ_98_y.csv',
        '086820_바이오솔루션_KOSDAQ_96_y.csv',
        '108490_로보티즈_KOSDAQ_98_y.csv',
        '119850_지엔씨에너지_KOSDAQ_97_y.csv',
        '124500_아이티센글로벌_KOSDAQ_96_y.csv', 
        '180640_한진칼_KOSDAQ_97_y.csv',
        '256940_킵스파마_KOSDAQ_97_y.csv',
        '278470_에이피알_KOSDAQ_97_y.csv',
        '347700_스피어_KOSDAQ_96_y.csv',
        '347850_디앤디파마텍_KOSDAQ_98_y.csv',
        '376300_디어유_KOSDAQ_96_y.csv',
        '389140_포바이포_KOSDAQ_99_y.csv',
        '389470_인벤티지랩_KOSDAQ_98_y.csv',
        '419530_SAMG엔터_KOSDAQ_98_y.csv',
        '437730_삼현_KOSDAQ_96_y.csv'
      ];
      
      // 파일명에서 RS 값을 추출하여 정렬 (y.csv 앞의 숫자로 정렬)
      const sortedFiles = [...fileList].sort((a, b) => {
        const rsA = parseInt(a.split('_')[3], 10) || 0;
        const rsB = parseInt(b.split('_')[3], 10) || 0;
        return rsB - rsA; // 내림차순 정렬
      });
      
      setFileNames(sortedFiles);
      
      // 파일 목록이 준비되면 차트 데이터 로드
      if (sortedFiles.length > 0) {
        await loadAllChartData(sortedFiles);
      }
      
      // 현재 날짜/시간으로 업데이트 일자 설정
      const now = new Date();
      const dateString = now.toISOString().split('T')[0]; // YYYY-MM-DD 형식으로 변환
      const formattedDate = formatDateMMDD(dateString);
      if (formattedDate) {
        setUpdateDate(formattedDate);
      }
      
      setLoading(false);
    } catch (err) {
      console.error('파일 목록 로드 에러:', err);
      setError('파일 목록을 불러오는 중 오류가 발생했습니다.');
      setLoading(false);
    }
  }

  // 파일명에서 RS 값 추출 (숫자만 반환)
  const extractRS1mValue = (fileName: string): number => {
    const parts = fileName.split('_')
    if (parts.length >= 4) {
      return parseInt(parts[3], 10) || 0
    }
    return 0
  }

  // 시장 지수 데이터 로드 함수
  const loadMarketIndexData = async () => {
    try {
      // KOSPI 주간 데이터 로드
      const kospiResponse = await fetch('/requestfile/market-index/kospiwk.csv', { cache: 'no-store' });
      if (!kospiResponse.ok) {
        throw new Error(`KOSPI 데이터 로드 실패: ${kospiResponse.status}`);
      }
      const kospiCsvText = await kospiResponse.text();
      
      // Papa.parse 직접 사용
      const kospiParsedData = Papa.parse(kospiCsvText, {
        header: true,
        skipEmptyLines: true,
        dynamicTyping: true,
      });
      
      // 데이터 형식 변환 (CandleData)
      const kospiFormattedData = kospiParsedData.data
        .filter((row: any) => {
          const isValid = row && row['날짜'] && row['시가'] && row['고가'] && row['저가'] && row['종가'];
          return isValid;
        })
        .map((row: any) => {
          // 날짜 형식 변환 (YYYYMMDD -> YYYY-MM-DD)
          let timeStr = String(row['날짜'] || '');
          let formattedTime = '';
          
          if (timeStr.length === 8) {
            const year = timeStr.substring(0, 4);
            const month = timeStr.substring(4, 6);
            const day = timeStr.substring(6, 8);
            formattedTime = `${year}-${month}-${day}`;
          } else {
            // 다른 형식이면 그대로 사용
            formattedTime = timeStr;
          }
          
          return {
            time: formattedTime,
            open: Number(row['시가']),
            high: Number(row['고가']),
            low: Number(row['저가']),
            close: Number(row['종가']),
            volume: Number(row['거래량'] || 0)
          };
        })
        .sort((a: any, b: any) => new Date(a.time).getTime() - new Date(b.time).getTime());
        
      setKospiIndexData(kospiFormattedData);

      // KOSDAQ 주간 데이터 로드 (동일한 방식 적용)
      const kosdaqResponse = await fetch('/requestfile/market-index/kosdaqwk.csv', { cache: 'no-store' });
      if (!kosdaqResponse.ok) {
        throw new Error(`KOSDAQ 데이터 로드 실패: ${kosdaqResponse.status}`);
      }
      const kosdaqCsvText = await kosdaqResponse.text();
      
      // Papa.parse 직접 사용
      const kosdaqParsedData = Papa.parse(kosdaqCsvText, {
        header: true,
        skipEmptyLines: true,
        dynamicTyping: true,
      });
      
      // 데이터 형식 변환 (CandleData)
      const kosdaqFormattedData = kosdaqParsedData.data
        .filter((row: any) => {
          const isValid = row && row['날짜'] && row['시가'] && row['고가'] && row['저가'] && row['종가'];
          return isValid;
        })
        .map((row: any) => {
          // 날짜 형식 변환 (YYYYMMDD -> YYYY-MM-DD)
          let timeStr = String(row['날짜'] || '');
          let formattedTime = '';
          
          if (timeStr.length === 8) {
            const year = timeStr.substring(0, 4);
            const month = timeStr.substring(4, 6);
            const day = timeStr.substring(6, 8);
            formattedTime = `${year}-${month}-${day}`;
          } else {
            // 다른 형식이면 그대로 사용
            formattedTime = timeStr;
          }
          
          return {
            time: formattedTime,
            open: Number(row['시가']),
            high: Number(row['고가']),
            low: Number(row['저가']),
            close: Number(row['종가']),
            volume: Number(row['거래량'] || 0)
          };
        })
        .sort((a: any, b: any) => new Date(a.time).getTime() - new Date(b.time).getTime());
        
      setKosdaqIndexData(kosdaqFormattedData);
      
      console.log('시장 지수 데이터 로드 완료', {
        kospi: kospiFormattedData.length,
        kosdaq: kosdaqFormattedData.length
      });
    } catch (err) {
      console.error('시장 지수 데이터 로드 오류:', err);
    }
  };
  
  // 모든 차트 데이터 로드
  const loadAllChartData = async (files: string[]) => {
    try {
      const chartDataObj: { [key: string]: CandleData[] } = {}
      const stockInfoObj: { [key: string]: { name: string, marketType: string, rs1m: string } } = {}

      // 최대 21개만 처리 (메모리 최적화)
      const filesToProcess = files.slice(0, 21)

      for (let i = 0; i < filesToProcess.length; i++) {
        const fileName = filesToProcess[i]
        const filePath = `/requestfile/mtt_top21/${fileName}`
        
        try {
          const csvText = await fetchCSVData(filePath)
          
          // 파일명에서 종목 정보 추출 
          // 형식: 종목코드_종목명_시장구분_(RS_1m)_mtt.csv
          const fileNameParts = fileName.split('_')
          const stockCode = fileNameParts[0]
          const stockName = fileNameParts[1]
          const marketType = fileNameParts[2]
          
          // RS_1m 값 추출 - 네 번째 부분이 RS 값
          const rs1m = fileNameParts[3] || ''
          
          // 차트 데이터 파싱
          const { chartData } = parseCSVOptimized(csvText)
          
          chartDataObj[stockCode] = chartData
          stockInfoObj[stockCode] = { name: stockName, marketType, rs1m }
        } catch (err) {
          console.error(`${fileName} 로드 중 에러:`, err)
        }
      }

      setChartData(chartDataObj)
      setStockInfo(stockInfoObj)
      setLoading(false)
    } catch (err) {
      console.error('차트 데이터 로드 에러:', err)
      setError('차트 데이터를 불러오는 중 오류가 발생했습니다.')
      setLoading(false)
    }
  }

  // 업데이트 날짜 로드
  const loadUpdateDate = async () => {
    try {
      // 첫 번째 파일을 가져와서 수정 날짜를 확인
      const response = await fetch('/requestfile/mtt_top21/file_list.json')
      
      if (response.ok) {
        const lastModified = response.headers.get('last-modified')
        if (lastModified) {
          const date = new Date(lastModified)
          const dateString = date.toISOString().split('T')[0] // YYYY-MM-DD 형식으로 변환
          const formattedDate = formatDateMMDD(dateString)
          if (formattedDate) { // null 체크
            setUpdateDate(formattedDate)
          }
        }
      }
    } catch (err) {
      console.error('업데이트 날짜 로드 에러:', err)
    }
  }

  // CSV 파싱 최적화 함수
  const parseCSVOptimized = (csvText: string): { chartData: CandleData[] } => {
    if (!csvText || typeof csvText !== 'string') {
      console.error('유효하지 않은 CSV 텍스트')
      return { chartData: [] }
    }

    // Papa Parse 옵션
    const results = Papa.parse(csvText, {
      header: true,
      skipEmptyLines: true,
      dynamicTyping: false,
    })

    // 차트 데이터 생성
    const chartData: CandleData[] = []
    
    if (results.data && Array.isArray(results.data)) {
      for (const row of results.data as Record<string, string>[]) {
        if (row['날짜'] && row['시가'] && row['고가'] && row['저가'] && row['종가']) {
          chartData.push({
            time: row['날짜'],
            open: parseFloat(row['시가']),
            high: parseFloat(row['고가']),
            low: parseFloat(row['저가']),
            close: parseFloat(row['종가']),
            volume: parseFloat(row['거래량'] || '0')
          })
        }
      }
    }

    return { chartData }
  }

  // 차트 컴포넌트 렌더링
  const renderChartComponent = (stockCode: string) => {
    const data = chartData[stockCode]
    const info = stockInfo[stockCode]

    if (!data || !info) {
      return (
        <div className="h-[280px] flex items-center justify-center bg-gray-50 border border-gray-200 rounded-md">
          <span className="text-gray-400">데이터 없음</span>
        </div>
      )
    }

    return (
      <div>
        <div 
          className="bg-gray-100 px-3 py-1 border border-gray-200 flex justify-between items-center"
          style={{ borderRadius: '0.375rem 0.375rem 0 0' }}
        >
          <div className="flex items-center">
            <span 
              className="font-medium text-xs text-xs" 
              style={{ fontSize: 'clamp(0.65rem, 0.75vw, 0.75rem)' }}
            >
              {info.name}
            </span>
            <span 
              className="ml-2 px-1.5 py-0.5 rounded bg-gray-200 text-gray-700" 
              style={{ fontSize: 'clamp(0.6rem, 0.7vw, 0.7rem)' }}
            >
              {info.marketType}
            </span>
          </div>
          <div className="flex items-center">
            <span 
              className="text-xs text-gray-500 mr-1" 
              style={{ fontSize: 'clamp(0.65rem, 0.75vw, 0.75rem)' }}
            >
              RS_1m
            </span>
            <span 
              className="font-medium text-xs text-blue-600" 
              style={{ fontSize: 'clamp(0.65rem, 0.75vw, 0.75rem)' }}
            >
              {info.rs1m}
            </span>
          </div>
        </div>
        <div style={{ position: 'relative', width: '100%', height: '280px' }}>
          <div 
            className="border border-gray-200 border-t-0" 
            style={{ 
              width: '100%', 
              height: '100%', 
              borderRadius: '0 0 0.375rem 0.375rem',
              overflow: 'hidden'
            }}
          >
            <ChartComponent 
              data={data} 
              height={280}
              showVolume={true}
              marketType={info.marketType}
              stockName={info.name}
            />
          </div>
        </div>
      </div>
    )
  }

  // 로딩 상태일 때
  if (loading) {
    return (
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
        {Array.from({ length: 9 }).map((_, index) => (
          <div key={index} className="rounded-md">
            <div className="h-[280px] flex items-center justify-center bg-gray-50 border border-gray-200 rounded-md">
              <span className="text-gray-400">로딩 중...</span>
            </div>
          </div>
        ))}
      </div>
    )
  }

  // 에러 상태일 때
  if (error) {
    return (
      <div className="flex items-center justify-center h-60 bg-gray-50 border border-dashed border-gray-300 rounded-lg">
        <span className="text-red-500">{error}</span>
      </div>
    )
  }

  return (
    <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
      {Object.keys(stockInfo).map((stockCode) => (
        <div key={stockCode} className="rounded-md">
          {renderChartComponent(stockCode)}
        </div>
      ))}
    </div>
  )
}
