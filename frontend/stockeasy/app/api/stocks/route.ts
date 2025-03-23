import { NextRequest, NextResponse } from 'next/server';
import fs from 'fs';
import path from 'path';
import Papa from 'papaparse';
import axios from 'axios';

// 캐시 디렉토리 설정
const CACHE_DIR = path.join(process.cwd(), 'public');
const STOCK_CACHE_DIR = path.join(CACHE_DIR, 'stock-data');
const CHART_CACHE_DIR = path.join(CACHE_DIR, 'chart-data');
const MARKET_INDEX_CACHE_DIR = path.join(CACHE_DIR, 'market-index');
const ETF_CURRENT_CACHE_DIR = path.join(CACHE_DIR, 'today_price_etf');
const ETF_HIGH_CACHE_DIR = path.join(CACHE_DIR, 'rs_etf');

// 마지막 업데이트 시간 파일 경로
const LAST_UPDATE_FILE_PATH = path.join(CACHE_DIR, 'last_update_time.json');

// RS 업데이트 시간 설정 (17:50)
const UPDATE_HOUR = 17;
const UPDATE_MINUTE = 50;

// 파일 정보 인터페이스 정의
interface FileInfo {
  fileId: string;
  dataType: string;
  fileName?: string;
  updateSchedule: 'regular' | 'market' | 'afternoon'; // regular: 17:50에 한 번, market: 9시-16시 10분마다, afternoon: 16:30에 한 번
}

// 캐시 정보 인터페이스 정의
interface CacheInfo {
  fileId: string;
  lastUpdated: string; // ISO 날짜 문자열
  cachePath: string;
  backupPath?: string;
}

// 캐시 레지스트리 인터페이스 정의
interface CacheRegistry {
  [fileId: string]: CacheInfo;
}

// ETF 관련 파일 정보
const ETF_FILES: FileInfo[] = [
  {
    fileId: '1u46PGtK4RY4vUOBIXzvrFsk_mUsxznbA',
    dataType: 'etf-current',
    fileName: 'etf_current_prices.csv',
    updateSchedule: 'market'
  },
  {
    fileId: '1cUcNxRD307dLGQVLiw1snAkX1LY0sEo0',
    dataType: 'etf-high',
    fileName: 'etf_high_prices.csv',
    updateSchedule: 'afternoon'  // 16:30에 업데이트
  }
];

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
  
  if (!fs.existsSync(ETF_CURRENT_CACHE_DIR)) {
    fs.mkdirSync(ETF_CURRENT_CACHE_DIR, { recursive: true });
    console.log('ETF 현재가 캐시 디렉토리 생성됨:', ETF_CURRENT_CACHE_DIR);
  }
  
  if (!fs.existsSync(ETF_HIGH_CACHE_DIR)) {
    fs.mkdirSync(ETF_HIGH_CACHE_DIR, { recursive: true });
    console.log('ETF 52주 신고가 캐시 디렉토리 생성됨:', ETF_HIGH_CACHE_DIR);
  }
}

// 캐시 키 정규화 함수
function normalizeCacheKey(fileId: string): string {
  return fileId.trim().toLowerCase();
}

// 캐시 파일 경로 생성 함수 (데이터 타입에 따라 다른 경로 반환)
function getCacheFilePath(fileId: string, dataType: string = 'stock', fileName?: string): string {
  const normalizedKey = normalizeCacheKey(fileId);
  
  switch (dataType) {
    case 'chart':
      // 차트 데이터는 접두사 없이 파일 ID만 사용
      return path.join(CHART_CACHE_DIR, `${normalizedKey}.csv`);
    case 'market-index':
      // 시장 지수 데이터의 경우 파일 ID 그대로 사용 (접두사 없음)
      return path.join(MARKET_INDEX_CACHE_DIR, `${normalizedKey}.csv`);
    case 'etf-current':
      // ETF 현재가 데이터
      return path.join(ETF_CURRENT_CACHE_DIR, fileName || `${normalizedKey}.csv`);
    case 'etf-high':
      // ETF 52주 신고가 데이터
      return path.join(ETF_HIGH_CACHE_DIR, fileName || `${normalizedKey}.csv`);
    case 'stock':
    default:
      // 주식 데이터는 'stock_' 접두사 사용
      return path.join(STOCK_CACHE_DIR, `stock_${normalizedKey}.csv`);
  }
}

/**
 * 캐시 레지스트리를 로드합니다.
 * 파일이 없으면 빈 객체를 반환합니다.
 */
function loadCacheRegistry(): CacheRegistry {
  try {
    if (fs.existsSync(LAST_UPDATE_FILE_PATH)) {
      const data = fs.readFileSync(LAST_UPDATE_FILE_PATH, 'utf8');
      return JSON.parse(data);
    }
  } catch (error) {
    console.error('캐시 레지스트리 로드 실패:', error);
  }
  return {};
}

/**
 * 캐시 레지스트리를 저장합니다.
 */
function saveCacheRegistry(registry: CacheRegistry): void {
  try {
    const dirPath = path.dirname(LAST_UPDATE_FILE_PATH);
    if (!fs.existsSync(dirPath)) {
      fs.mkdirSync(dirPath, { recursive: true });
    }
    fs.writeFileSync(LAST_UPDATE_FILE_PATH, JSON.stringify(registry, null, 2));
  } catch (error) {
    console.error('캐시 레지스트리 저장 실패:', error);
  }
}

/**
 * 현재 시간이 주식 시장 거래 시간인지 확인합니다.
 * 9:00 - 16:00 사이, 그리고 주말이 아닌 경우 true를 반환합니다.
 */
function isMarketHours(): boolean {
  const now = new Date();
  const hours = now.getHours();
  const day = now.getDay();
  
  // 주말(토: 6, 일: 0) 체크
  if (day === 0 || day === 6) {
    return false;
  }
  
  // 9시 ~ 16시 사이 체크
  return hours >= 9 && hours < 16;
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

/**
 * 파일 업데이트가 필요한지 확인합니다.
 */
function needsUpdate(cacheInfo: CacheInfo | undefined, updateSchedule: 'regular' | 'market' | 'afternoon'): boolean {
  if (!cacheInfo) {
    return true; // 캐시 정보가 없으면 업데이트 필요
  }
  
  const now = new Date();
  const lastUpdated = new Date(cacheInfo.lastUpdated);
  const today = new Date(now.getFullYear(), now.getMonth(), now.getDate());
  const lastUpdateDay = new Date(lastUpdated.getFullYear(), lastUpdated.getMonth(), lastUpdated.getDate());
  
  // 날짜가 다르면 업데이트 필요
  if (today.getTime() !== lastUpdateDay.getTime()) {
    return true;
  }
  
  // 정기 업데이트 (17:50)
  if (updateSchedule === 'regular') {
    const updateTime = new Date(today);
    updateTime.setHours(17, 50, 0, 0);
    
    // 현재 시간이 17:50 이후이고, 마지막 업데이트가 17:50 이전이면 업데이트 필요
    return now.getTime() >= updateTime.getTime() && lastUpdated.getTime() < updateTime.getTime();
  }
  
  // 시장 시간 업데이트 (9:00-16:00, 10분마다)
  if (updateSchedule === 'market' && isMarketHours()) {
    // 마지막 업데이트 후 10분 이상 지났으면 업데이트 필요
    return (now.getTime() - lastUpdated.getTime()) >= 10 * 60 * 1000;
  }
  
  // 오후에 업데이트하는 경우 (16:30)
  if (updateSchedule === 'afternoon') {
    const updateTime = new Date(today);
    updateTime.setHours(16, 30, 0, 0);
    
    // 현재 시간이 16:30 이후이고, 마지막 업데이트가 16:30 이전이면 업데이트 필요
    return now.getTime() >= updateTime.getTime() && lastUpdated.getTime() < updateTime.getTime();
  }
  
  return false;
}

// 캐시에 데이터 저장
function saveToCache(fileId: string, data: string, dataType: string = 'stock', fileName?: string): void {
  try {
    ensureCacheDirectories();
    const filePath = getCacheFilePath(fileId, dataType, fileName);
    
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

/**
 * 파일을 백업합니다.
 */
function backupFile(sourcePath: string, backupPath: string): boolean {
  try {
    if (fs.existsSync(sourcePath)) {
      const dir = path.dirname(backupPath);
      if (!fs.existsSync(dir)) {
        fs.mkdirSync(dir, { recursive: true });
      }
      fs.copyFileSync(sourcePath, backupPath);
      return true;
    }
    return false;
  } catch (error) {
    console.error(`파일 백업 실패 (${sourcePath} -> ${backupPath}):`, error);
    return false;
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

/**
 * 파일을 동기화합니다.
 * 필요한 경우에만 구글 드라이브에서 다운로드합니다.
 */
async function syncFile(fileInfo: FileInfo): Promise<string> {
  // 캐시 레지스트리 로드
  const registry = loadCacheRegistry();
  const cacheInfo = registry[fileInfo.fileId];
  
  // 캐시 파일 경로
  const cachePath = getCacheFilePath(fileInfo.fileId, fileInfo.dataType, fileInfo.fileName);
  const backupPath = `${cachePath}.backup`;
  
  // 업데이트가 필요한지 확인
  if (needsUpdate(cacheInfo, fileInfo.updateSchedule)) {
    console.log(`파일 업데이트 필요 (ID: ${fileInfo.fileId})`);
    
    // 기존 파일 백업
    if (fs.existsSync(cachePath)) {
      backupFile(cachePath, backupPath);
    }
    
    try {
      // 파일 다운로드
      const data = await downloadFileFromGoogleDrive(fileInfo.fileId);
      
      // 캐시에 저장
      fs.writeFileSync(cachePath, data, 'utf-8');
      
      // 캐시 정보 업데이트
      registry[fileInfo.fileId] = {
        fileId: fileInfo.fileId,
        lastUpdated: new Date().toISOString(),
        cachePath,
        backupPath
      };
      saveCacheRegistry(registry);
      return cachePath;
    } catch (error) {
      console.error(`파일 다운로드 실패 (ID: ${fileInfo.fileId}):`, error);
      
      // 다운로드 실패 시 백업 파일 사용
      if (fs.existsSync(backupPath)) {
        console.log(`다운로드 실패, 백업 파일 사용 (ID: ${fileInfo.fileId})`);
        return backupPath;
      }
    }
  } else if (cacheInfo && fs.existsSync(cacheInfo.cachePath)) {
    // 업데이트가 필요 없고 캐시 파일이 있으면 그것을 사용
    return cacheInfo.cachePath;
  }
  
  // 모든 시도 실패 시 빈 문자열 반환
  return '';
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
      skipEmptyLines: true
    });
    
    if (results.errors && results.errors.length > 0) {
      console.error('CSV 파싱 오류:', results.errors);
      return {
        labels: [],
        datasets: []
      };
    }
    
    // 날짜 컬럼 찾기 (보통 첫 번째 컬럼)
    const headers = results.meta.fields || [];
    const dateColumn = headers[0] || 'date';
    
    // 데이터 변환
    const labels = results.data.map((row: any) => row[dateColumn]);
    const datasets = [];
    
    // 날짜 외 다른 컬럼들을 데이터셋으로 변환
    for (let i = 1; i < headers.length; i++) {
      const header = headers[i];
      datasets.push({
        label: header,
        data: results.data.map((row: any) => parseFloat(row[header]) || 0)
      });
    }
    
    return {
      labels,
      datasets
    };
  } catch (error) {
    console.error('차트 데이터 파싱 오류:', error);
    return {
      labels: [],
      datasets: []
    };
  }
}

// 파일 ID 상수 정의
const FILE_IDS = {
  // 주식 데이터 (3개)
  STOCK_LIST: '1idVB5kIo0d6dChvOyWE7OvWr-eZ1cbpB',  // 종목 리스트
  RS_DATA: '1uYJvdMzfXaRsxS0jy16fEgfrQY9fS8yd',    // RS 데이터
  RS_RANK: '1MbEe4o9_nONpFiAeXI4vIn8QCn8bTtXZ',    // RS 랭크
  
  // 차트 데이터 (여러 개)
  CHART_DATA: {
    // 차트 데이터 파일 ID 목록
    KOSPI: '1dzf65fz6elq6b5znvhuaftn10hqjbe_c',     // 코스피 지수
    KOSDAQ: '1ks9qkdzmsxv-qenv6udzzidfwgykc1qg',    // 코스닥 지수
    // 여기에 더 많은 차트 데이터 파일 ID를 추가할 수 있습니다
  },
  
  // ETF 데이터 (2개)
  ETF_CURRENT: '1u46PGtK4RY4vUOBIXzvrFsk_mUsxznbA', // ETF 현재가
  ETF_HIGH: '1cUcNxRD307dLGQVLiw1snAkX1LY0sEo0'     // ETF 52주 신고가
};

// 파일 ID로 데이터 타입 결정하는 함수
function getDataTypeByFileId(fileId: string): string {
  // 주식 데이터
  if (fileId === FILE_IDS.STOCK_LIST || fileId === FILE_IDS.RS_DATA || fileId === FILE_IDS.RS_RANK) {
    return 'stock';
  }
  
  // 차트 데이터
  if (fileId === FILE_IDS.CHART_DATA.KOSPI || fileId === FILE_IDS.CHART_DATA.KOSDAQ) {
    return 'market-index';
  }
  
  // 다른 차트 데이터 (파일 ID가 chart_ 접두사로 시작하는 경우)
  if (fileId.startsWith('chart_')) {
    return 'chart';
  }
  
  // ETF 데이터
  if (fileId === FILE_IDS.ETF_CURRENT) {
    return 'etf-current';
  }
  
  if (fileId === FILE_IDS.ETF_HIGH) {
    return 'etf-high';
  }
  
  // 기본값은 'stock'
  return 'stock';
}

/**
 * 마지막 업데이트 시간을 저장합니다.
 */
function saveLastUpdateTime(): void {
  try {
    const updateInfo = {
      lastUpdate: new Date().toISOString()
    };
    
    const dirPath = path.dirname(LAST_UPDATE_FILE_PATH);
    if (!fs.existsSync(dirPath)) {
      fs.mkdirSync(dirPath, { recursive: true });
    }
    
    fs.writeFileSync(LAST_UPDATE_FILE_PATH, JSON.stringify(updateInfo, null, 2), 'utf-8');
    console.log('마지막 업데이트 시간이 저장되었습니다.');
  } catch (error) {
    console.error('마지막 업데이트 시간 저장 실패:', error);
  }
}

/**
 * 마지막 업데이트 시간을 가져옵니다.
 */
function getLastUpdateTime(): string {
  try {
    if (fs.existsSync(LAST_UPDATE_FILE_PATH)) {
      const data = fs.readFileSync(LAST_UPDATE_FILE_PATH, 'utf-8');
      const updateInfo = JSON.parse(data);
      return updateInfo.lastUpdate || '';
    }
  } catch (error) {
    console.error('마지막 업데이트 시간 로드 실패:', error);
  }
  return '';
}

/**
 * 전체 데이터 업데이트가 필요한지 확인합니다.
 * 하루에 한 번 (17:50) 업데이트가 필요합니다.
 */
function needUpdate(): boolean {
  try {
    const lastUpdateStr = getLastUpdateTime();
    if (!lastUpdateStr) {
      return true; // 마지막 업데이트 정보가 없으면 업데이트 필요
    }
    
    const now = new Date();
    const lastUpdate = new Date(lastUpdateStr);
    const today = new Date(now.getFullYear(), now.getMonth(), now.getDate());
    const lastUpdateDay = new Date(lastUpdate.getFullYear(), lastUpdate.getMonth(), lastUpdate.getDate());
    
    // 날짜가 다르면 업데이트 필요
    if (today.getTime() !== lastUpdateDay.getTime()) {
      return true;
    }
    
    // 정기 업데이트 시간 (17:50)
    const updateTime = new Date(today);
    updateTime.setHours(17, 50, 0, 0);
    
    // 현재 시간이 17:50 이후이고, 마지막 업데이트가 17:50 이전이면 업데이트 필요
    return now.getTime() >= updateTime.getTime() && lastUpdate.getTime() < updateTime.getTime();
  } catch (error) {
    console.error('업데이트 필요 여부 확인 실패:', error);
    return true; // 에러 발생 시 안전하게 업데이트 필요로 처리
  }
}

/**
 * ETF 현재가 데이터 파일 경로를 가져옵니다.
 */
async function getETFCurrentPricesPath(): Promise<string> {
  const fileInfo: FileInfo = {
    fileId: FILE_IDS.ETF_CURRENT,
    dataType: 'etf-current',
    fileName: 'etf_current_prices.csv',
    updateSchedule: 'market'
  };
  return await syncFile(fileInfo);
}

/**
 * ETF 52주 신고가 데이터 파일 경로를 가져옵니다.
 */
async function getETFHighPricesPath(): Promise<string> {
  const fileInfo: FileInfo = {
    fileId: FILE_IDS.ETF_HIGH,
    dataType: 'etf-high',
    fileName: 'etf_high_prices.csv',
    updateSchedule: 'afternoon'
  };
  return await syncFile(fileInfo);
}

/**
 * 모든 ETF 관련 파일을 동기화합니다.
 */
async function syncAllETFFiles(): Promise<void> {
  await getETFCurrentPricesPath();
  await getETFHighPricesPath();
}

// 모든 CSV 파일 업데이트 함수
async function updateAllCSVFiles() {
  try {
    console.log('모든 CSV 파일 업데이트 시작...');
    
    // 주식 데이터 파일 업데이트
    const stockFiles = [
      { fileId: FILE_IDS.STOCK_LIST, dataType: 'stock', updateSchedule: 'regular' },
      { fileId: FILE_IDS.RS_DATA, dataType: 'stock', updateSchedule: 'regular' },
      { fileId: FILE_IDS.RS_RANK, dataType: 'stock', updateSchedule: 'regular' }
    ];
    
    // 차트 데이터 파일 업데이트
    const chartFiles = [
      { fileId: FILE_IDS.CHART_DATA.KOSPI, dataType: 'market-index', updateSchedule: 'market' },
      { fileId: FILE_IDS.CHART_DATA.KOSDAQ, dataType: 'market-index', updateSchedule: 'market' }
    ];
    
    // 모든 파일 업데이트
    const allFiles = [...stockFiles, ...chartFiles];
    
    for (const file of allFiles) {
      try {
        await syncFile({
          fileId: file.fileId,
          dataType: file.dataType,
          updateSchedule: file.updateSchedule as 'regular' | 'market' | 'afternoon'
        });
      } catch (error) {
        console.error(`파일 업데이트 실패 (ID: ${file.fileId}):`, error);
      }
    }
    
    console.log('모든 CSV 파일 업데이트 완료');
  } catch (error) {
    console.error('CSV 파일 업데이트 중 오류 발생:', error);
    throw error;
  }
}

// POST: 통합 API 엔드포인트
export async function POST(request: NextRequest) {
  try {
    const body = await request.json();
    const { action, fileId, dataType } = body;
    
    // 특정 파일 업데이트 요청
    if (action === 'update-file' && fileId) {
      const fileType = getDataTypeByFileId(fileId);
      
      // 파일 정보 생성
      const fileInfo: FileInfo = {
        fileId,
        dataType: dataType || fileType,
        updateSchedule: 'regular' // 기본값은 정기 업데이트
      };
      
      // 파일 동기화
      const filePath = await syncFile(fileInfo);
      
      if (filePath && fs.existsSync(filePath)) {
        return NextResponse.json({
          success: true,
          message: `파일이 업데이트되었습니다. (ID: ${fileId})`,
          filePath
        });
      } else {
        return NextResponse.json({
          success: false,
          message: `파일 업데이트 실패 (ID: ${fileId})`
        }, { status: 500 });
      }
    }
    
    // 차트 데이터 요청
    if (action === 'get-chart-data' && fileId) {
      const fileType = getDataTypeByFileId(fileId);
      
      // 파일 정보 생성
      const fileInfo: FileInfo = {
        fileId,
        dataType: dataType || fileType,
        updateSchedule: 'market' // 차트 데이터는 시장 시간에 업데이트
      };
      
      // 파일 동기화
      const filePath = await syncFile(fileInfo);
      
      if (filePath && fs.existsSync(filePath)) {
        const data = fs.readFileSync(filePath, 'utf-8');
        const chartData = parseCSVToChartData(data);
        
        return NextResponse.json({
          success: true,
          data: chartData
        });
      } else {
        return NextResponse.json({
          success: false,
          message: `차트 데이터를 찾을 수 없습니다. (ID: ${fileId})`
        }, { status: 404 });
      }
    }
    
    return NextResponse.json({
      success: false,
      message: '지원되지 않는 작업'
    }, { status: 400 });
  } catch (error) {
    console.error('POST 요청 처리 중 오류 발생:', error);
    return NextResponse.json({
      success: false,
      message: '요청 처리 중 오류가 발생했습니다.',
      error: (error as Error).message
    }, { status: 500 });
  }
}

// GET: 데이터 업데이트 확인 및 수행
export async function GET(request: NextRequest) {
  try {
    // 요청 URL에서 쿼리 파라미터 추출
    const { searchParams } = new URL(request.url);
    const action = searchParams.get('action');
    
    // 모든 데이터 업데이트 요청
    if (action === 'update-all') {
      // 모든 파일 업데이트
      await updateAllCSVFiles();
      
      // ETF 파일도 업데이트
      await syncAllETFFiles();
      
      // 마지막 업데이트 시간 저장
      saveLastUpdateTime();
      
      return NextResponse.json({
        success: true,
        message: '모든 데이터 파일이 업데이트되었습니다.',
        lastUpdate: getLastUpdateTime()
      });
    }
    
    // ETF 데이터 요청
    if (action === 'get-etf-current') {
      const filePath = await getETFCurrentPricesPath();
      if (filePath && fs.existsSync(filePath)) {
        const data = fs.readFileSync(filePath, 'utf-8');
        const parsedData = parseCSV(data);
        return NextResponse.json({
          success: true,
          data: parsedData.rows
        });
      } else {
        return NextResponse.json({
          success: false,
          message: 'ETF 현재가 데이터를 찾을 수 없습니다.'
        }, { status: 404 });
      }
    }
    
    if (action === 'get-etf-high') {
      const filePath = await getETFHighPricesPath();
      if (filePath && fs.existsSync(filePath)) {
        const data = fs.readFileSync(filePath, 'utf-8');
        const parsedData = parseCSV(data);
        return NextResponse.json({
          success: true,
          data: parsedData.rows
        });
      } else {
        return NextResponse.json({
          success: false,
          message: 'ETF 52주 신고가 데이터를 찾을 수 없습니다.'
        }, { status: 404 });
      }
    }
    
    // 기본 응답: 상태 정보 반환
    const needsUpdateNow = needUpdate();
    
    return NextResponse.json({
      success: true,
      needsUpdate: needsUpdateNow,
      lastUpdate: getLastUpdateTime()
    });
  } catch (error) {
    console.error('GET 요청 처리 중 오류 발생:', error);
    return NextResponse.json({
      success: false,
      message: '데이터 업데이트 확인 중 오류가 발생했습니다.',
      error: (error as Error).message
    }, { status: 500 });
  }
}
