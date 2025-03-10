/**
 * 시장 지수 데이터를 가져오는 API 엔드포인트
 * 
 * KOSDAQ 또는 KOSPI 시장 지수 데이터를 가져와서 반환합니다.
 * - KOSDAQ: https://docs.google.com/spreadsheets/d/12be5QzfkFDJn76-mVsDCqU6bhHFanTMG
 * - KOSPI: https://docs.google.com/spreadsheets/d/1pwd2ps_WE7Qs_f8-TODMxxvpDfLUJDUR
 */
import { NextRequest, NextResponse } from 'next/server';
import Papa from 'papaparse';
import axios from 'axios';

/**
 * 시장 지수 파일 ID 맵핑
 */
const MARKET_INDEX_FILE_IDS = {
  'KOSDAQ': '1ks9QkdZMsxV-qEnV6udZZIDfWgYKC1qg', // 새로운 KOSDAQ 파일 ID로 업데이트
  'KOSPI': '1Dzf65fZ6elQ6b5zNvhUAFtN10HqJBE_c' // 새로운 KOSPI 파일 ID로 업데이트
};

/**
 * 캐시 아이템 인터페이스
 */
interface CacheItem {
  data: Array<{ date: string; close: number }>;
  timestamp: number;
  marketType: string;
}

// 캐시 맵 (시장 타입을 키로 사용)
const marketIndexCache = new Map<string, CacheItem>();

// 캐시 유효 시간 (24시간 = 86400000 밀리초)
const CACHE_TTL = 86400000;

// 캐시 통계
let cacheHits = 0;
let cacheMisses = 0;

/**
 * 캐시 상태 로깅 함수
 */
function logCacheStats() {
  const totalRequests = cacheHits + cacheMisses;
  const hitRate = totalRequests > 0 ? (cacheHits / totalRequests) * 100 : 0;
  console.log(`[Market Index API] 캐시 통계: 총 요청=${totalRequests}, 히트=${cacheHits}, 미스=${cacheMisses}, 히트율=${hitRate.toFixed(2)}%`);
  console.log(`[Market Index API] 현재 캐시 항목 수: ${marketIndexCache.size}`);
}

/**
 * 구글 드라이브에서 시장 지수 데이터 CSV 파일을 다운로드하는 함수
 * @param marketType - 시장 구분 (KOSDAQ 또는 KOSPI)
 * @returns CSV 파일 내용
 */
async function downloadMarketIndexFile(marketType: string): Promise<string> {
  try {
    // 시장 구분에 해당하는 파일 ID 가져오기
    const fileId = MARKET_INDEX_FILE_IDS[marketType as keyof typeof MARKET_INDEX_FILE_IDS];
    if (!fileId) {
      throw new Error(`시장 구분 ${marketType}에 해당하는 파일 ID가 없습니다.`);
    }
    
    console.log(`[Market Index API] ${marketType} 시장 지수 파일(ID: ${fileId}) 다운로드 시작`);
    
    // Google Drive 파일 다운로드 URL 생성
    const downloadUrl = `https://drive.google.com/uc?export=download&id=${fileId}`;
    
    // Axios를 사용하여 파일 다운로드
    const response = await axios.get(downloadUrl, {
      responseType: 'text',
      headers: {
        'Accept': 'text/csv,text/plain',
      }
    });
    
    if (!response.data || response.data.length === 0) {
      throw new Error(`다운로드된 CSV 데이터가 비어 있습니다.`);
    }
    
    console.log(`[Market Index API] ${marketType} 시장 지수 파일 다운로드 완료: ${response.data.substring(0, 100)}...`);
    
    return response.data;
  } catch (error) {
    console.error(`[Market Index API] ${marketType} 시장 지수 파일 다운로드 실패:`, error);
    throw error;
  }
}

/**
 * CSV 데이터에서 종가 데이터만 추출하는 함수
 * @param csvData - CSV 데이터
 * @returns {Array} 종가 데이터 배열 (날짜와 종가)
 */
function extractCloseData(csvData: string): Array<{ date: string; close: number }> {
  try {
    // CSV 파싱
    const parsedData = Papa.parse(csvData, { 
      header: true,
      skipEmptyLines: true
    });
    
    console.log(`[Market Index API] CSV 파싱 완료, 총 ${parsedData.data.length}개 행 처리`);
    console.log(`[Market Index API] CSV 헤더:`, parsedData.meta.fields);
    
    if (parsedData.data.length === 0) {
      console.error('[Market Index API] 파싱된 CSV 데이터가 비어 있습니다.');
      return [];
    }
    
    // 첫 번째 행 샘플 로깅
    console.log(`[Market Index API] CSV 첫 번째 행 샘플:`, parsedData.data[0]);
    
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
    if (closeData.length > 0) {
      console.log(`[Market Index API] 첫 번째 데이터 포인트:`, closeData[0]);
    } else {
      console.error('[Market Index API] 추출된 종가 데이터가 없습니다.');
    }
    
    return closeData;
  } catch (error) {
    console.error(`[Market Index API] 종가 데이터 추출 실패:`, error);
    return []; // 오류 발생 시 빈 배열 반환
  }
}

/**
 * 시장 지수 데이터를 가져오는 API 핸들러
 */
export async function POST(request: NextRequest) {
  try {
    // 요청 본문에서 시장 구분 가져오기
    const body = await request.json();
    const { marketType } = body;
    
    if (!marketType || !MARKET_INDEX_FILE_IDS[marketType as keyof typeof MARKET_INDEX_FILE_IDS]) {
      return NextResponse.json(
        { error: `유효하지 않은 시장 구분: ${marketType}. 'KOSDAQ' 또는 'KOSPI'만 지원합니다.` },
        { status: 400 }
      );
    }
    
    console.log(`[Market Index API] ${marketType} 시장 지수 데이터 요청 받음`);
    
    // 캐시 확인
    const now = Date.now();
    const cachedItem = marketIndexCache.get(marketType);
    
    // 캐시가 유효한지 확인 (24시간 이내)
    if (cachedItem && (now - cachedItem.timestamp) < CACHE_TTL) {
      cacheHits++;
      console.log(`[Market Index API] 캐시 히트: ${marketType} 시장 지수, 캐시된 지 ${Math.floor((now - cachedItem.timestamp) / 60000)}분 경과`);
      logCacheStats();
      
      console.log(`[Market Index API] ${marketType} 시장 지수 데이터 반환: ${cachedItem.data.length}개 데이터 포인트`);
      
      return NextResponse.json({
        marketType,
        data: cachedItem.data,
        cached: true,
        cacheAge: now - cachedItem.timestamp
      });
    }
    
    cacheMisses++;
    console.log(`[Market Index API] 캐시 미스: ${marketType} 시장 지수, 원격 데이터 로드 시도`);
    logCacheStats();
    
    // 시장 지수 데이터 파일 다운로드
    const csvData = await downloadMarketIndexFile(marketType);
    
    // 종가 데이터 추출
    const closeData = extractCloseData(csvData);
    
    if (closeData.length === 0) {
      console.warn(`[Market Index API] ${marketType} 시장 지수 데이터가 비어 있습니다.`);
      // 빈 데이터라도 성공 응답 반환 (클라이언트에서 처리)
      return NextResponse.json({ 
        marketType,
        data: [],
        warning: `${marketType} 시장 지수 데이터를 찾을 수 없습니다.`
      });
    }
    
    // 캐시에 데이터 저장
    marketIndexCache.set(marketType, {
      data: closeData,
      timestamp: now,
      marketType
    });
    
    console.log(`[Market Index API] ${marketType} 시장 지수 데이터 반환: ${closeData.length}개 데이터 포인트`);
    
    return NextResponse.json({
      marketType,
      data: closeData
    });
  } catch (error) {
    console.error(`[Market Index API] 오류 발생:`, error);
    
    return NextResponse.json(
      { error: `시장 지수 데이터를 가져오는 중 오류가 발생했습니다: ${error instanceof Error ? error.message : String(error)}` },
      { status: 500 }
    );
  }
}
