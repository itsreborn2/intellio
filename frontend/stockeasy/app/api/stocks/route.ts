import { NextRequest, NextResponse } from 'next/server';
import fs from 'fs';
import path from 'path';
import Papa from 'papaparse';
import axios from 'axios';

// 캐시 디렉토리 설정
const CACHE_DIR = path.join(process.cwd(), 'cache');
const STOCK_CACHE_DIR = path.join(CACHE_DIR, 'stock-data');
const CHART_CACHE_DIR = path.join(CACHE_DIR, 'chart-data');
const MARKET_INDEX_CACHE_DIR = path.join(CACHE_DIR, 'market-index');

// 캐시 디렉토리 생성 함수
function ensureCacheDirectories() {
  if (!fs.existsSync(CACHE_DIR)) {
    fs.mkdirSync(CACHE_DIR, { recursive: true });
    console.log('캐시 디렉토리 생성됨:', CACHE_DIR);
  }
  
  if (!fs.existsSync(STOCK_CACHE_DIR)) {
    fs.mkdirSync(STOCK_CACHE_DIR, { recursive: true });
    console.log('주식 캐시 디렉토리 생성됨:', STOCK_CACHE_DIR);
  }

  if (!fs.existsSync(CHART_CACHE_DIR)) {
    fs.mkdirSync(CHART_CACHE_DIR, { recursive: true });
    console.log('차트 캐시 디렉토리 생성됨:', CHART_CACHE_DIR);
  }

  if (!fs.existsSync(MARKET_INDEX_CACHE_DIR)) {
    fs.mkdirSync(MARKET_INDEX_CACHE_DIR, { recursive: true });
    console.log('시장 지수 캐시 디렉토리 생성됨:', MARKET_INDEX_CACHE_DIR);
  }
}

// 캐시 키 정규화 함수
function normalizeCacheKey(fileId: string): string {
  return fileId.trim().toLowerCase();
}

// 캐시 파일 경로 생성 함수 (데이터 타입에 따라 다른 경로 반환)
function getCacheFilePath(fileId: string, dataType: string = 'stock'): string {
  const normalizedKey = normalizeCacheKey(fileId);
  
  switch (dataType) {
    case 'chart':
      return path.join(CHART_CACHE_DIR, `chart_${normalizedKey}.csv`);
    case 'market-index':
      // 시장 지수 데이터의 경우 파일 ID 그대로 사용 (접두사 없음)
      return path.join(MARKET_INDEX_CACHE_DIR, `${normalizedKey}.csv`);
    case 'stock':
    default:
      return path.join(STOCK_CACHE_DIR, `stock_${normalizedKey}.csv`);
  }
}

// 캐시에서 데이터 가져오기
function getFromCache(fileId: string, dataType: string = 'stock'): string | null {
  try {
    const filePath = getCacheFilePath(fileId, dataType);
    if (fs.existsSync(filePath)) {
      // 파일의 마지막 수정 시간 확인
      const stats = fs.statSync(filePath);
      const lastModified = stats.mtime;
      const now = new Date();
      
      // 오늘 날짜의 17:50 시간 생성
      const todayCutoff = new Date(
        now.getFullYear(),
        now.getMonth(),
        now.getDate(),
        17, 50, 0
      );
      
      // 현재 시간이 오늘의 17:50 이전이고, 파일이 어제 17:50 이후에 수정되었으면 유효함
      const yesterdayCutoff = new Date(todayCutoff);
      yesterdayCutoff.setDate(yesterdayCutoff.getDate() - 1);
      
      // 캐시가 유효한지 확인
      const isCacheValid = 
        (now < todayCutoff && lastModified > yesterdayCutoff) || // 오늘 17:50 이전이고 어제 17:50 이후에 수정됨
        (now >= todayCutoff && lastModified > todayCutoff);      // 오늘 17:50 이후이고 오늘 17:50 이후에 수정됨
      
      if (isCacheValid) {
        console.log(`유효한 캐시 데이터 사용: ${filePath}`);
        const data = fs.readFileSync(filePath, 'utf-8');
        return data;
      } else {
        console.log(`캐시 만료됨 (마지막 수정: ${lastModified.toISOString()}): ${filePath}`);
        return null;
      }
    }
  } catch (error) {
    console.error('캐시 파일 읽기 오류:', error);
  }
  return null;
}

// 캐시에 데이터 저장
function saveToCache(fileId: string, data: string, dataType: string = 'stock'): void {
  try {
    ensureCacheDirectories();
    const filePath = getCacheFilePath(fileId, dataType);
    
    // 기존 파일이 있는지 확인하고 덮어쓰기
    if (fs.existsSync(filePath)) {
      console.log('기존 캐시 파일 덮어쓰기:', filePath);
    } else {
      console.log('새 캐시 파일 생성:', filePath);
    }
    
    fs.writeFileSync(filePath, data, 'utf-8');
    console.log('데이터 캐시에 저장됨:', filePath);
  } catch (error) {
    console.error('캐시 파일 쓰기 오류:', error);
  }
}

// Google Drive에서 파일 다운로드
async function downloadFileFromGoogleDrive(fileId: string): Promise<string> {
  try {
    const url = `https://drive.google.com/uc?export=download&id=${fileId}`;
    console.log(`Google Drive에서 파일 다운로드 시도: ${url}`);
    
    const response = await axios.get(url, { responseType: 'text' });
    
    if (response.status !== 200) {
      throw new Error(`Google Drive 다운로드 실패: 상태 코드 ${response.status}`);
    }
    
    return response.data;
  } catch (error) {
    console.error('Google Drive 다운로드 오류:', error);
    throw error;
  }
}

// CSV 파싱 함수
function parseCSV(csvText: string) {
  try {
    const results = Papa.parse(csvText, {
      header: true,
      skipEmptyLines: true
    });
    
    return {
      headers: results.meta.fields || [],
      rows: results.data,
      errors: results.errors
    };
  } catch (error) {
    console.error('CSV 파싱 오류:', error);
    return {
      headers: [],
      rows: [],
      errors: [{ message: '파싱 오류', type: 'Parse', code: '', row: 0 }]
    };
  }
}

// CSV 데이터를 차트 데이터로 파싱하는 함수
function parseCSVToChartData(csvText: string) {
  try {
    const results = Papa.parse(csvText, {
      header: true,
      skipEmptyLines: true,
      dynamicTyping: true // 숫자를 자동으로 변환
    });
    
    if (results.errors && results.errors.length > 0) {
      console.warn('CSV 파싱 경고:', results.errors);
    }
    
    // 데이터 형식 변환
    const chartData = results.data.map((row: any) => {
      // CSV 열 이름에 따라 적절히 조정해야 합니다
      return {
        time: row.Date || row.date || row.time || '',
        open: row.Open || row.open || 0,
        high: row.High || row.high || 0,
        low: row.Low || row.low || 0,
        close: row.Close || row.close || 0,
        volume: row.Volume || row.volume || 0
      };
    }).filter((item: any) => item.time && item.open && item.high && item.low && item.close);
    
    // 날짜 기준으로 정렬 (오래된 순)
    chartData.sort((a: any, b: any) => {
      return new Date(a.time).getTime() - new Date(b.time).getTime();
    });
    
    return chartData;
  } catch (error) {
    console.error('차트 데이터 파싱 오류:', error);
    throw error;
  }
}

// 시장 지수 데이터 추출 함수
function extractMarketIndexData(csvData: string): Array<{ date: string; close: number }> {
  try {
    // CSV 파싱
    const parsedData = Papa.parse(csvData, { 
      header: true,
      skipEmptyLines: true
    });
    
    console.log(`[Market Index API] CSV 파싱 완료, 총 ${parsedData.data.length}개 행 처리`);
    
    if (parsedData.data.length === 0) {
      console.error('[Market Index API] 파싱된 CSV 데이터가 비어 있습니다.');
      return [];
    }
    
    // 종가 데이터 추출
    const closeData = parsedData.data
      .map((row: any) => {
        // 데이터 검증
        if (!row || typeof row !== 'object') {
          console.warn(`[Market Index API] 유효하지 않은 행 데이터:`, row);
          return null;
        }
        
        // 모든 키 로깅
        const keys = Object.keys(row);
        if (keys.length === 0) {
          console.warn(`[Market Index API] 행에 키가 없습니다.`);
          return null;
        }
        
        // 날짜 필드 찾기
        let dateField = '';
        if ('날짜' in row) dateField = '날짜';
        else if ('Date' in row) dateField = 'Date';
        else if ('date' in row) dateField = 'date';
        else if ('일자' in row) dateField = '일자';
        else {
          // 날짜 관련 키 찾기
          dateField = keys.find(k => /날짜|date|일자/i.test(k)) || '';
        }
        
        if (!dateField || !row[dateField]) {
          console.warn(`[Market Index API] 날짜 필드를 찾을 수 없습니다. 사용 가능한 키:`, keys);
          return null;
        }
        
        const date = String(row[dateField]);
        
        // 종가 필드 찾기
        let closeField = '';
        if ('종가' in row) closeField = '종가';
        else if ('Close' in row) closeField = 'Close';
        else if ('close' in row) closeField = 'close';
        else if ('CLOSE' in row) closeField = 'CLOSE';
        else {
          // 종가 관련 키 찾기
          closeField = keys.find(k => /종가|close/i.test(k)) || '';
        }
        
        if (!closeField || row[closeField] === undefined || row[closeField] === null) {
          console.warn(`[Market Index API] 종가 필드를 찾을 수 없습니다. 사용 가능한 키:`, keys);
          return null;
        }
        
        // 종가 값 파싱
        let close = row[closeField];
        if (typeof close === 'string') {
          close = parseFloat(close.replace(/,/g, ''));
        } else if (typeof close !== 'number') {
          console.warn(`[Market Index API] 종가 값이 숫자가 아닙니다:`, close);
          return null;
        }
        
        if (isNaN(close)) {
          console.warn(`[Market Index API] 종가 값이 NaN입니다:`, row[closeField]);
          return null;
        }
        
        // 날짜 형식 변환 (YYYYMMDD -> YYYY-MM-DD)
        let formattedDate = date;
        if (date.length === 8 && !date.includes('-') && !date.includes('/')) {
          formattedDate = `${date.substring(0, 4)}-${date.substring(4, 6)}-${date.substring(6, 8)}`;
        }
        
        return { date: formattedDate, close };
      })
      .filter((item): item is { date: string; close: number } => item !== null);
    
    console.log(`[Market Index API] 종가 데이터 추출 완료, 총 ${closeData.length}개 데이터 포인트 추출`);
    
    return closeData;
  } catch (error) {
    console.error(`[Market Index API] 종가 데이터 추출 실패:`, error);
    return []; // 오류 발생 시 빈 배열 반환
  }
}

// 차트 데이터 처리 함수
async function handleChartData(fileId: string): Promise<string> {
  console.log(`차트 데이터 요청 처리 중: ${fileId}`);
  
  // 파일 ID에서 확장자가 있으면 제거 (클라이언트에서 이미 제거했을 수 있음)
  const cleanFileId = fileId.endsWith('.csv') ? fileId : `${fileId}.csv`;
  
  // 캐시 파일 경로
  const cacheFilePath = path.join(process.cwd(), 'cache', 'chart-data', cleanFileId);
  
  try {
    // 캐시 파일 확인
    if (fs.existsSync(cacheFilePath)) {
      console.log(`캐시된 차트 데이터 사용: ${cacheFilePath}`);
      return fs.readFileSync(cacheFilePath, 'utf-8');
    }
    
    // 캐시 디렉토리 내 모든 파일 확인 (디버깅용)
    const cacheDir = path.join(process.cwd(), 'cache', 'chart-data');
    if (fs.existsSync(cacheDir)) {
      console.log('캐시 디렉토리 내 파일 목록:');
      const files = fs.readdirSync(cacheDir);
      files.forEach(file => console.log(` - ${file}`));
      
      // 파일명 부분 일치 검색 시도
      const matchingFile = files.find(file => file.includes(fileId));
      if (matchingFile) {
        console.log(`부분 일치하는 파일 발견: ${matchingFile}`);
        const matchingFilePath = path.join(cacheDir, matchingFile);
        return fs.readFileSync(matchingFilePath, 'utf-8');
      }
    }
    
    // 캐시 파일이 없는 경우 오류 반환
    throw new Error(`차트 데이터 캐시 파일을 찾을 수 없습니다: ${fileId}`);
  } catch (error) {
    console.error(`차트 데이터 처리 오류:`, error);
    throw error;
  }
}

// 파일 ID 상수 정의
const FILE_IDS = {
  STOCK_LIST: '1idVB5kIo0d6dChvOyWE7OvWr-eZ1cbpB',  // 종목 리스트
  RS_RANK: '1UYJVdMZFXarsxs0jy16fEGfRqY9Fs8YD',     // RS 순위
  WEEK_HIGH: '1mbee4O9_NoNpfIAExI4viN8qcN8BtTXz',   // 52주 신고가
  KOSDAQ: '1ks9QkdZMsxV-qEnV6udZZIDfWgYKC1qg',      // 코스닥 지수
  KOSPI: '1Dzf65fZ6elQ6b5zNvhUAFtN10HqJBE_c'        // 코스피 지수
};

// POST: 통합 API 엔드포인트
export async function POST(request: NextRequest) {
  try {
    const { symbol, fileId, dataType, marketType } = await request.json();
    
    // 1. 시장 지수 데이터 요청 처리
    if (marketType) {
      // 시장 구분에 해당하는 파일 ID 가져오기
      let targetFileId = '';
      if (marketType === 'KOSDAQ') {
        targetFileId = FILE_IDS.KOSDAQ;
      } else if (marketType === 'KOSPI') {
        targetFileId = FILE_IDS.KOSPI;
      } else {
        return NextResponse.json(
          { error: `유효하지 않은 시장 구분: ${marketType}. 'KOSDAQ' 또는 'KOSPI'만 지원합니다.` },
          { status: 400 }
        );
      }
      
      console.log(`[Market Index API] ${marketType} 시장 지수 데이터 요청 받음`);
      
      // 캐시 확인
      const cachedData = getFromCache(targetFileId, 'market-index');
      
      // 캐시가 있는 경우
      if (cachedData) {
        console.log(`캐시된 시장 지수 데이터 반환: ${marketType}`);
        
        // 시장 지수 데이터 파싱 및 반환
        const closeData = extractMarketIndexData(cachedData);
        return NextResponse.json({
          marketType,
          data: closeData,
          cached: true
        });
      }
      
      // 캐시가 없는 경우 오류 반환
      console.log(`캐시된 시장 지수 데이터 없음: ${marketType}`);
      return NextResponse.json(
        { 
          error: `시장 지수 데이터를 찾을 수 없습니다: ${marketType}`,
          warning: `로컬 캐시 파일이 없습니다. 시장 지수 데이터는 로컬 캐시 파일에서만 제공됩니다.`
        },
        { status: 404 }
      );
    }
    
    // 2. 차트 데이터 요청 처리
    if (dataType === 'chart') {
      if (!fileId) {
        return NextResponse.json({ error: '차트 데이터를 위한 파일 ID가 필요합니다.' }, { status: 400 });
      }
      
      console.log(`차트 데이터 요청: 파일 ID ${fileId}`);
      
      // 캐시 확인
      const cachedData = getFromCache(fileId, 'chart');
      
      // 캐시가 있는 경우
      if (cachedData) {
        console.log(`캐시된 차트 데이터 반환: ${fileId}`);
        return new NextResponse(cachedData, {
          status: 200,
          headers: {
            'Content-Type': 'text/csv; charset=utf-8',
          },
        });
      }
      
      // 캐시가 없는 경우 Google Drive에서 다운로드
      console.log(`캐시된 차트 데이터 없음. Google Drive에서 다운로드 시도: ${fileId}`);
      try {
        const fileData = await downloadFileFromGoogleDrive(fileId);
        
        // 다운로드한 데이터 캐시에 저장
        saveToCache(fileId, fileData, 'chart');
        
        // 데이터 반환
        return new NextResponse(fileData, {
          status: 200,
          headers: {
            'Content-Type': 'text/csv; charset=utf-8',
          },
        });
      } catch (downloadError) {
        console.error('Google Drive 다운로드 실패:', downloadError);
        return NextResponse.json(
          { error: '차트 데이터를 다운로드하는 중 오류가 발생했습니다.' },
          { status: 500 }
        );
      }
    }
    
    // 3. 주식 데이터 요청 처리 (기존 코드)
    // 데이터 타입이 제공된 경우 해당 파일 ID 사용
    let targetFileId = fileId;
    
    if (dataType && !fileId) {
      switch (dataType) {
        case 'rs-rank':
          targetFileId = FILE_IDS.RS_RANK;
          break;
        case 'week-high':
          targetFileId = FILE_IDS.WEEK_HIGH;
          break;
        case 'stock-list':
          targetFileId = FILE_IDS.STOCK_LIST;
          break;
        default:
          return NextResponse.json({ error: '유효하지 않은 데이터 타입입니다.' }, { status: 400 });
      }
    }
    
    // 파일 ID가 없는 경우 오류 반환
    if (!targetFileId) {
      return NextResponse.json({ error: '파일 ID 또는 데이터 타입이 필요합니다.' }, { status: 400 });
    }
    
    console.log(`데이터 요청: 파일 ID ${targetFileId}`);
    
    // 캐시 확인
    const cachedData = getFromCache(targetFileId);
    
    // 캐시가 있는 경우
    if (cachedData) {
      console.log(`캐시된 데이터 반환: ${targetFileId}`);
      return new NextResponse(cachedData, {
        status: 200,
        headers: {
          'Content-Type': 'text/csv; charset=utf-8',
        },
      });
    }
    
    // 캐시가 없는 경우 Google Drive에서 다운로드
    console.log(`캐시된 데이터 없음. Google Drive에서 다운로드 시도: ${targetFileId}`);
    try {
      const fileData = await downloadFileFromGoogleDrive(targetFileId);
      
      // 다운로드한 데이터 캐시에 저장
      saveToCache(targetFileId, fileData);
      
      // 데이터 반환
      return new NextResponse(fileData, {
        status: 200,
        headers: {
          'Content-Type': 'text/csv; charset=utf-8',
        },
      });
    } catch (downloadError) {
      console.error('Google Drive 다운로드 실패:', downloadError);
      return NextResponse.json(
        { error: '데이터를 다운로드하는 중 오류가 발생했습니다.' },
        { status: 500 }
      );
    }
  } catch (error) {
    console.error('API 오류:', error);
    return NextResponse.json(
      { error: `데이터를 처리하는 중 오류가 발생했습니다: ${error instanceof Error ? error.message : '알 수 없는 오류'}` },
      { status: 500 }
    );
  }
}
