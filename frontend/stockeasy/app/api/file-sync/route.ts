import { NextRequest, NextResponse } from 'next/server';
import fs from 'fs';
import path from 'path';
import axios from 'axios';

// 파일 정보 인터페이스
interface FileInfo {
  fileId: string;
  folderPath: string;
  fileName: string;
  updateSchedule: 'regular' | 'market' | 'market_20ma' | 'afternoon' | 'stock_daily' | 'chart_daily' | 'etf_stocks' | 'today_price' | 'etf_indiestocklist';
}

// 캐시 정보 인터페이스
interface CacheInfo {
  cachePath: string;
  lastUpdated: string;
}

// 캐시 레지스트리 인터페이스
interface CacheRegistry {
  [fileId: string]: CacheInfo;
}

// 구글 드라이브 폴더 ID 상수
const CHART_DATA_FOLDER_ID = '1VFOD15oWpFvzG4rZz8FWWZZT_BGxb4M_';
const ETF_INDIESTOCKLIST_FOLDER_ID = '1PFBQNJ6qC0iRbZDK_4zI-jKQhTtTKS-V';

// 캐시 레지스트리 파일 경로
const CACHE_REGISTRY_PATH = path.join(process.cwd(), 'public', 'last_update.json');

// 동기화할 파일 목록
const FILES_TO_SYNC: FileInfo[] = [
  // ETF 현재가 데이터
  {
    fileId: '1u46PGtK4RY4vUOBIXzvrFsk_mUsxznbA',
    folderPath: 'today_price_etf',
    fileName: 'today_price_etf.csv',
    updateSchedule: 'etf_stocks'
  },
  // ETF 52주 신고가 데이터
  {
    fileId: '1cUcNxRD307dLGQVLiw1snAkX1LY0sEo0',
    folderPath: 'rs_etf',
    fileName: '1cUcNxRD307dLGQVLiw1snAkX1LY0sEo0.csv',
    updateSchedule: 'afternoon'
  },
  // 20MA 리스트
  {
    fileId: '1c4me7qyyOW3YrwCRwS7Szm2ia8ToMzzm',
    folderPath: '20ma_list',
    fileName: '20malist.csv',
    updateSchedule: 'market_20ma'
  },
  // ETF 종목 리스트
  {
    fileId: '1bJ4CnCgd6dSAAgbPgKvWbElSxWhertIy',
    folderPath: 'etf_stocklist',
    fileName: 'etf_stocklist.csv',
    updateSchedule: 'etf_stocks'
  },
  // Market-Index 파일들
  {
    fileId: '1ks9QkdZMsxV-qEnV6udZZIDfWgYKC1qg',
    folderPath: 'market-index',
    fileName: '1ks9QkdZMsxV-qEnV6udZZIDfWgYKC1qg.csv',
    updateSchedule: 'chart_daily'
  },
  {
    fileId: '1Dzf65fZ6elQ6b5zNvhUAFtN10HqJBE_c',
    folderPath: 'market-index',
    fileName: '1Dzf65fZ6elQ6b5zNvhUAFtN10HqJBE_c.csv',
    updateSchedule: 'chart_daily'
  },
  // 추가 파일
  {
    fileId: '1txqtWnVImMAq6vjD4byFiFFgmbM9KrrA',
    folderPath: 'today_price_etf',
    fileName: 'today_price_etf.csv',
    updateSchedule: 'etf_stocks'
  },
  // Stock-Data 파일들
  {
    fileId: '1idVB5kIo0d6dChvOyWE7OvWr-eZ1cbpB',
    folderPath: 'stock-data',
    fileName: 'stock_1idvb5kio0d6dchvoywe7ovwr-ez1cbpb.csv',
    updateSchedule: 'stock_daily'
  },
  {
    fileId: '1mbee4O9_NoNpfIAExI4viN8qcN8BtTXz',
    folderPath: 'stock-data',
    fileName: 'stock_1mbee4o9_nonpfiaexi4vin8qcn8bttxz.csv',
    updateSchedule: 'stock_daily'
  },
  {
    fileId: '1UYJVdMZFXarsxs0jy16fEGfRqY9Fs8YD',
    folderPath: 'stock-data',
    fileName: 'stock_1uyjvdmzfxarsxs0jy16fegfrqy9fs8yd.csv',
    updateSchedule: 'stock_daily'
  }
];

// 폴더 ID 목록
const FOLDER_IDS = [CHART_DATA_FOLDER_ID, ETF_INDIESTOCKLIST_FOLDER_ID];

// 마지막 실행 시간을 저장하는 변수
let lastRunTime = 0;

/**
 * 캐시 레지스트리를 로드합니다.
 * 파일이 없으면 빈 객체를 반환합니다.
 */
function loadCacheRegistry(): CacheRegistry {
  try {
    if (fs.existsSync(CACHE_REGISTRY_PATH)) {
      const data = fs.readFileSync(CACHE_REGISTRY_PATH, 'utf8');
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
    const dir = path.dirname(CACHE_REGISTRY_PATH);
    if (!fs.existsSync(dir)) {
      fs.mkdirSync(dir, { recursive: true });
    }
    
    fs.writeFileSync(CACHE_REGISTRY_PATH, JSON.stringify(registry, null, 2), 'utf8');
  } catch (error) {
    console.error('캐시 레지스트리 저장 실패:', error);
  }
}

/**
 * 오늘이 휴일인지 확인합니다.
 * 일요일과 토요일은 휴일로 간주합니다.
 */
function isHoliday(): boolean {
  const now = new Date();
  const day = now.getDay(); // 0: 일요일, 6: 토요일
  
  // 주말인 경우 휴일로 간주
  return day === 0 || day === 6;
}

/**
 * 시장 시간인지 확인합니다. (9:11 ~ 17:00, 10분 간격)
 */
function isMarketHours(): boolean {
  if (isHoliday()) return false;
  
  const now = new Date();
  const hours = now.getHours();
  const minutes = now.getMinutes();
  
  // 9시 11분부터 17시까지 체크
  return (hours === 9 && minutes >= 11) || (hours > 9 && hours < 17);
}

/**
 * 20MA 리스트 업데이트 시간인지 확인합니다. (9:20 ~ 16:00, 10분 간격)
 */
function isMarket20MAHours(): boolean {
  if (isHoliday()) return false;
  
  const now = new Date();
  const hours = now.getHours();
  const minutes = now.getMinutes();
  
  // 9시 20분부터 16시까지 체크
  return (hours === 9 && minutes >= 20) || (hours > 9 && hours < 16);
}

/**
 * ETF 종목 업데이트 시간인지 확인합니다. (9:10 ~ 16:00, 10분 간격)
 */
function isETFStocksUpdateHours(): boolean {
  if (isHoliday()) return false;
  
  const now = new Date();
  const hours = now.getHours();
  const minutes = now.getMinutes();
  
  // 9시 10분부터 16시까지 체크
  return (hours === 9 && minutes >= 10) || (hours > 9 && hours < 16);
}

/**
 * 오늘의 가격 업데이트 시간인지 확인합니다. (9:09 ~ 16:00, 10분 간격)
 */
function isTodayPriceUpdateHours(): boolean {
  if (isHoliday()) return false;
  
  const now = new Date();
  const hours = now.getHours();
  const minutes = now.getMinutes();
  
  // 9시 9분부터 16시까지 체크
  return (hours === 9 && minutes >= 9) || (hours > 9 && hours < 16);
}

/**
 * ETF 인디스톡 리스트 업데이트 시간인지 확인합니다. (9:10 ~ 16:00, 10분 간격)
 */
function isETFIndieStockListUpdateHours(): boolean {
  if (isHoliday()) return false;
  
  const now = new Date();
  const hours = now.getHours();
  const minutes = now.getMinutes();
  
  // 9시 10분부터 16시까지 체크
  return (hours === 9 && minutes >= 10) || (hours > 9 && hours < 16);
}

/**
 * 파일 업데이트가 필요한지 확인합니다.
 * @param filePath 파일 경로
 * @param cacheInfo 캐시 정보
 * @param updateSchedule 업데이트 스케줄
 * @param forceUpdate 강제 업데이트 여부
 * @returns 업데이트 필요 여부
 */
async function needsUpdate(
  filePath: string,
  cacheInfo: CacheInfo | undefined,
  updateSchedule: string,
  forceUpdate: boolean = false
): Promise<boolean> {
  // 강제 업데이트가 요청된 경우
  if (forceUpdate) {
    console.log(`강제 업데이트 요청됨: ${filePath}`);
    return true;
  }

  // 파일이 존재하지 않으면 업데이트 필요
  if (!fs.existsSync(filePath)) {
    console.log(`파일이 존재하지 않아 업데이트 필요: ${filePath}`);
    return true;
  }
  
  // 파일 경로의 디렉토리 확인
  const dir = path.dirname(filePath);
  if (!fs.existsSync(dir)) {
    console.log(`디렉토리가 존재하지 않아 업데이트 필요: ${dir}`);
    return true;
  }
  
  // 캐시 정보가 없으면 업데이트 필요
  if (!cacheInfo) {
    console.log(`캐시 정보가 없어 업데이트 필요: ${filePath}`);
    return true;
  }
  
  // 파일이 비어있거나 크기가 0이면 업데이트 필요
  try {
    const stats = fs.statSync(filePath);
    if (stats.size === 0) {
      console.log(`파일이 비어있어 업데이트 필요: ${filePath}`);
      return true;
    }
  } catch (error) {
    console.log(`파일 상태 확인 중 오류 발생, 업데이트 필요: ${filePath}`);
    return true;
  }
  
  const now = new Date();
  const lastUpdated = new Date(cacheInfo.lastUpdated);
  const today = new Date(now.getFullYear(), now.getMonth(), now.getDate());
  const lastUpdateDay = new Date(lastUpdated.getFullYear(), lastUpdated.getMonth(), lastUpdated.getDate());
  
  // 날짜가 다르면 업데이트 필요
  if (today.getTime() !== lastUpdateDay.getTime()) {
    console.log(`날짜가 달라 업데이트 필요: ${filePath}`);
    return true;
  }
  
  // 스케줄에 따른 업데이트 필요 여부 확인
  switch (updateSchedule) {
    case 'regular': {
      // 17:50에 한 번 업데이트
      const updateTime = new Date(today);
      updateTime.setHours(17, 50, 0, 0);
      return now.getTime() >= updateTime.getTime() && lastUpdated.getTime() < updateTime.getTime();
    }
    
    case 'market': {
      // 시장 시간 중 10분마다 업데이트
      if (!isMarketHours()) return false;
      return (now.getTime() - lastUpdated.getTime()) >= 10 * 60 * 1000;
    }
    
    case 'market_20ma': {
      // 20MA 리스트 업데이트 시간 중 10분마다 업데이트
      if (!isMarket20MAHours()) return false;
      return (now.getTime() - lastUpdated.getTime()) >= 10 * 60 * 1000;
    }
    
    case 'afternoon': {
      // 16:30에 한 번 업데이트
      const updateTime = new Date(today);
      updateTime.setHours(16, 30, 0, 0);
      return now.getTime() >= updateTime.getTime() && lastUpdated.getTime() < updateTime.getTime();
    }
    
    case 'stock_daily': {
      // 16:10에 한 번 업데이트 (휴일 제외)
      if (isHoliday()) return false;
      const updateTime = new Date(today);
      updateTime.setHours(16, 10, 0, 0);
      return now.getTime() >= updateTime.getTime() && lastUpdated.getTime() < updateTime.getTime();
    }
    
    case 'chart_daily': {
      // 17:10에 한 번 업데이트 (휴일 제외)
      if (isHoliday()) return false;
      const updateTime = new Date(today);
      updateTime.setHours(17, 10, 0, 0);
      return now.getTime() >= updateTime.getTime() && lastUpdated.getTime() < updateTime.getTime();
    }
    
    case 'etf_stocks': {
      // ETF 종목 업데이트 시간 중 10분마다 업데이트
      if (!isETFStocksUpdateHours()) return false;
      return (now.getTime() - lastUpdated.getTime()) >= 10 * 60 * 1000;
    }
    
    case 'today_price': {
      // 오늘의 가격 업데이트 시간 중 10분마다 업데이트
      if (!isTodayPriceUpdateHours()) return false;
      return (now.getTime() - lastUpdated.getTime()) >= 10 * 60 * 1000;
    }
    
    case 'etf_indiestocklist': {
      // ETF 인디스톡 리스트 업데이트 시간 중 10분마다 업데이트
      if (!isETFIndieStockListUpdateHours()) return false;
      return (now.getTime() - lastUpdated.getTime()) >= 10 * 60 * 1000;
    }
    
    default:
      return false;
  }
}

/**
 * 구글 드라이브에서 파일을 다운로드합니다.
 */
async function downloadFromGoogleDrive(fileId: string, outputPath: string): Promise<boolean> {
  try {
    console.log(`구글 드라이브에서 파일 다운로드 시작 (ID: ${fileId})`);
    
    // 구글 드라이브 다운로드 URL
    const url = `https://drive.google.com/uc?id=${fileId}&export=download&confirm=t`;
    
    // 최대 3번 재시도
    let retryCount = 0;
    const maxRetries = 3;
    
    while (retryCount < maxRetries) {
      try {
        // 파일 다운로드
        const response = await axios({
          method: 'get',
          url,
          responseType: 'arraybuffer',
          timeout: 120000, // 타임아웃 시간 증가 (120초)
          headers: {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,image/apng,*/*;q=0.8',
            'Accept-Encoding': 'gzip, deflate, br',
            'Cache-Control': 'no-cache',
            'Pragma': 'no-cache'
          }
        });
        
        // 응답 상태 코드 확인
        if (response.status !== 200) {
          console.error(`파일 다운로드 실패 (ID: ${fileId}): 상태 코드 ${response.status}`);
          retryCount++;
          continue;
        }
        
        // 응답 데이터 확인
        if (!response.data || response.data.length === 0) {
          console.error(`파일 다운로드 실패 (ID: ${fileId}): 빈 응답 데이터`);
          retryCount++;
          continue;
        }
        
        // HTML 응답 확인 (오류 응답일 수 있음)
        const dataString = Buffer.from(response.data).toString('utf8').slice(0, 100);
        if (dataString.includes('<!DOCTYPE html>') || dataString.includes('<html')) {
          console.error(`파일 다운로드 실패 (ID: ${fileId}): HTML 응답 받음`);
          retryCount++;
          continue;
        }
        
        // 디렉토리가 없으면 생성
        const dir = path.dirname(outputPath);
        if (!fs.existsSync(dir)) {
          fs.mkdirSync(dir, { recursive: true });
        }
        
        // 파일 저장
        fs.writeFileSync(outputPath, Buffer.from(response.data));
        
        // 파일이 제대로 저장되었는지 확인
        if (fs.existsSync(outputPath)) {
          const stats = fs.statSync(outputPath);
          if (stats.size > 0) {
            console.log(`파일 다운로드 완료 (ID: ${fileId}, 경로: ${outputPath}, 크기: ${stats.size} 바이트)`);
            return true;
          } else {
            console.error(`파일 다운로드 실패 (ID: ${fileId}): 파일 크기가 0입니다.`);
            fs.unlinkSync(outputPath); // 크기가 0인 파일 삭제
            retryCount++;
            continue;
          }
        } else {
          console.error(`파일 다운로드 실패 (ID: ${fileId}): 파일이 저장되지 않았습니다.`);
          retryCount++;
          continue;
        }
      } catch (innerError) {
        console.error(`파일 다운로드 시도 ${retryCount + 1}/${maxRetries} 중 오류 발생 (ID: ${fileId}):`, innerError);
        retryCount++;
        
        // 재시도 전 잠시 대기
        if (retryCount < maxRetries) {
          console.log(`${retryCount * 2}초 후 재시도...`);
          await new Promise(resolve => setTimeout(resolve, retryCount * 2000));
        }
      }
    }
    
    console.error(`최대 재시도 횟수(${maxRetries})를 초과했습니다. 파일 다운로드 실패 (ID: ${fileId})`);
    return false;
  } catch (error) {
    console.error(`파일 다운로드 중 오류 발생 (ID: ${fileId}):`, error);
    return false;
  }
}

/**
 * 차트 데이터 폴더 JSON 파일을 생성합니다.
 */
function createChartDataFolderJSON(): any[] {
  const now = new Date();
  const year = now.getFullYear();
  const month = String(now.getMonth() + 1).padStart(2, '0');
  const day = String(now.getDate()).padStart(2, '0');
  const dateStr = `${year}${month}${day}`;
  
  // 날짜 기반 파일명 생성
  const chartFileName = `chart_${dateStr}.csv`;
  const marketFileName = `market_${dateStr}.csv`;
  
  return [
    {
      id: chartFileName.replace('.csv', ''),
      name: chartFileName,
      mimeType: 'text/csv',
      modifiedTime: now.toISOString(),
      size: '10000'
    },
    {
      id: marketFileName.replace('.csv', ''),
      name: marketFileName,
      mimeType: 'text/csv',
      modifiedTime: now.toISOString(),
      size: '10000'
    }
  ];
}

/**
 * ETF 인디스톡 리스트 폴더 JSON 파일을 생성합니다.
 */
function createETFIndieStockListFolderJSON(): any[] {
  const now = new Date();
  
  // 기본 파일 목록
  return [
    {
      id: '000250_삼천당제약_97',
      name: '000250_삼천당제약_97.csv',
      mimeType: 'text/csv',
      modifiedTime: now.toISOString(),
      size: '5000'
    },
    {
      id: '000660_SK하이닉스_82',
      name: '000660_SK하이닉스_82.csv',
      mimeType: 'text/csv',
      modifiedTime: now.toISOString(),
      size: '5000'
    },
    {
      id: '000720_현대건설_81',
      name: '000720_현대건설_81.csv',
      mimeType: 'text/csv',
      modifiedTime: now.toISOString(),
      size: '5000'
    }
  ];
}

/**
 * 폴더 ID에 따른 JSON 파일을 생성합니다.
 */
function createFolderJSON(folderId: string): any[] {
  if (folderId === CHART_DATA_FOLDER_ID) {
    return createChartDataFolderJSON();
  } else if (folderId === ETF_INDIESTOCKLIST_FOLDER_ID) {
    return createETFIndieStockListFolderJSON();
  }
  
  return [];
}

/**
 * 자동 동기화 실행 함수
 * 이 함수는 API 요청이 들어올 때마다 호출되어 필요한 경우 파일을 동기화합니다.
 */
async function runAutoSync(): Promise<string[]> {
  const results: string[] = [];
  
  // 필수 파일 중 누락된 파일이 있는지 확인
  for (const fileInfo of FILES_TO_SYNC) {
    const outputPath = path.join(process.cwd(), 'public', fileInfo.folderPath, fileInfo.fileName);
    
    // 파일이 없으면 즉시 다운로드
    if (!fs.existsSync(outputPath)) {
      console.log(`파일이 없음: ${outputPath}, 다운로드 시작...`);
      const result = await syncFile(fileInfo, true);
      results.push(result);
    } else {
      // 파일 크기가 0이면 즉시 다운로드
      try {
        const stats = fs.statSync(outputPath);
        if (stats.size === 0) {
          console.log(`파일이 비어있음: ${outputPath}, 다운로드 시작...`);
          const result = await syncFile(fileInfo, true);
          results.push(result);
          continue;
        }
      } catch (error) {
        console.log(`파일 상태 확인 중 오류 발생: ${outputPath}, 다운로드 시작...`);
        const result = await syncFile(fileInfo, true);
        results.push(result);
        continue;
      }
      
      // 파일이 있으면 정해진 스케줄에 따라 업데이트 여부 결정
      const cacheRegistry = loadCacheRegistry();
      const cacheInfo = cacheRegistry[fileInfo.fileId];
      const shouldUpdate = await needsUpdate(outputPath, cacheInfo, fileInfo.updateSchedule, false);
      
      if (shouldUpdate) {
        const result = await syncFile(fileInfo, false);
        results.push(result);
      } else {
        results.push(`파일 업데이트 불필요: ${fileInfo.fileName}`);
      }
    }
  }
  
  // 폴더 정보 처리
  for (const folderId of FOLDER_IDS) {
    const folderName = folderId === CHART_DATA_FOLDER_ID ? 'chart-data' : 
                      folderId === ETF_INDIESTOCKLIST_FOLDER_ID ? 'etf_indiestocklist' : folderId;
    const outputPath = path.join(process.cwd(), 'public', folderName, `${folderName}_files.json`);
    
    // 폴더 정보 파일이 없으면 생성
    if (!fs.existsSync(outputPath)) {
      console.log(`폴더 정보 파일이 없음: ${outputPath}, 생성 시작...`);
      const result = await handleFolderId(folderId);
      results.push(result);
    }
  }
  
  return results.length > 0 ? results : ['모든 파일이 최신 상태입니다.'];
}

/**
 * 파일을 동기화합니다.
 */
async function syncFile(fileInfo: FileInfo, forceUpdate: boolean = false): Promise<string> {
  try {
    // 파일 경로 생성
    const outputPath = path.join(process.cwd(), 'public', fileInfo.folderPath, fileInfo.fileName);
    
    // 파일 경로 로그 출력 (디버깅용)
    console.log(`파일 경로 확인: ${outputPath}`);
    console.log(`폴더 경로 확인: ${path.dirname(outputPath)}`);
    
    // 캐시 레지스트리 로드
    const cacheRegistry = loadCacheRegistry();
    const cacheInfo = cacheRegistry[fileInfo.fileId];
    
    // 디렉토리가 없으면 생성 (파일 다운로드 전에 먼저 확인)
    const dir = path.dirname(outputPath);
    if (!fs.existsSync(dir)) {
      console.log(`디렉토리 생성: ${dir}`);
      fs.mkdirSync(dir, { recursive: true });
    }
    
    // 업데이트가 필요한지 확인
    const shouldUpdate = await needsUpdate(outputPath, cacheInfo, fileInfo.updateSchedule, forceUpdate);
    
    if (!shouldUpdate) {
      console.log(`파일 업데이트 불필요 (ID: ${fileInfo.fileId}, 경로: ${outputPath})`);
      return `파일 업데이트 불필요: ${fileInfo.fileName}`;
    }
    
    // 구글 드라이브에서 파일 다운로드
    const success = await downloadFromGoogleDrive(fileInfo.fileId, outputPath);
    
    if (success) {
      // 캐시 정보 업데이트
      cacheRegistry[fileInfo.fileId] = {
        cachePath: outputPath,
        lastUpdated: new Date().toISOString()
      };
      
      // 캐시 레지스트리 저장
      saveCacheRegistry(cacheRegistry);
      
      return `파일 업데이트 완료: ${fileInfo.fileName}`;
    } else {
      return `파일 업데이트 실패: ${fileInfo.fileName}`;
    }
  } catch (error) {
    console.error(`파일 동기화 중 오류 발생 (ID: ${fileInfo.fileId}):`, error);
    return `파일 업데이트 오류: ${fileInfo.fileName}`;
  }
}

/**
 * 폴더 ID인 경우 JSON 파일을 생성합니다.
 */
async function handleFolderId(folderId: string): Promise<string> {
  try {
    // 폴더 이름 결정
    let folderName = '';
    if (folderId === CHART_DATA_FOLDER_ID) {
      folderName = 'chart-data';
    } else if (folderId === ETF_INDIESTOCKLIST_FOLDER_ID) {
      folderName = 'etf_indiestocklist';
    } else {
      return `알 수 없는 폴더 ID: ${folderId}`;
    }
    
    // JSON 파일 경로 생성
    const jsonFileName = `${folderName}_files.json`;
    const jsonFilePath = path.join(process.cwd(), 'public', folderName, jsonFileName);
    
    // 디렉토리가 없으면 생성
    const dir = path.dirname(jsonFilePath);
    if (!fs.existsSync(dir)) {
      fs.mkdirSync(dir, { recursive: true });
    }
    
    // JSON 파일 생성
    const folderContents = createFolderJSON(folderId);
    fs.writeFileSync(jsonFilePath, JSON.stringify(folderContents, null, 2), 'utf8');
    
    // 캐시 레지스트리 로드
    const cacheRegistry = loadCacheRegistry();
    
    // 캐시 정보 업데이트
    cacheRegistry[folderId] = {
      cachePath: jsonFilePath,
      lastUpdated: new Date().toISOString()
    };
    
    // 캐시 레지스트리 저장
    saveCacheRegistry(cacheRegistry);
    
    return `폴더 정보 업데이트 완료: ${folderName}`;
  } catch (error) {
    console.error(`폴더 정보 생성 중 오류 발생 (ID: ${folderId}):`, error);
    return `폴더 정보 업데이트 오류: ${folderId}`;
  }
}

/**
 * 모든 파일을 동기화합니다.
 */
async function syncAllFiles(forceUpdate: boolean = false): Promise<string[]> {
  const results: string[] = [];
  
  // 폴더 ID 처리
  for (const folderId of FOLDER_IDS) {
    const result = await handleFolderId(folderId);
    results.push(result);
  }
  
  // 파일 동기화
  for (const fileInfo of FILES_TO_SYNC) {
    const result = await syncFile(fileInfo, forceUpdate);
    results.push(result);
  }
  
  return results;
}

/**
 * 클라이언트에서 주기적으로 호출할 수 있는 API 핸들러
 */
export async function POST(request: NextRequest) {
  try {
    const results = await syncAllFiles();
    return NextResponse.json({ results });
  } catch (error) {
    console.error('API 처리 중 오류 발생:', error);
    return NextResponse.json({ error: '파일 동기화 중 오류가 발생했습니다.' }, { status: 500 });
  }
}

/**
 * API 핸들러
 */
export async function GET(request: NextRequest) {
  try {
    // URL 파라미터 확인
    const { searchParams } = new URL(request.url);
    const fileId = searchParams.get('fileId');
    const forceUpdate = searchParams.get('force') === 'true';
    const autoSync = searchParams.get('autoSync') !== 'false'; // 기본값은 true
    
    let results: string[] = [];
    
    // 특정 파일 ID가 지정된 경우
    if (fileId) {
      const fileInfo = FILES_TO_SYNC.find(file => file.fileId === fileId);
      
      if (fileInfo) {
        // 특정 파일 동기화
        const result = await syncFile(fileInfo, forceUpdate);
        results = [result];
      } else if (FOLDER_IDS.includes(fileId)) {
        // 폴더 ID인 경우
        const result = await handleFolderId(fileId);
        results = [result];
      } else {
        return NextResponse.json({ error: '파일 ID를 찾을 수 없습니다.' }, { status: 404 });
      }
    } 
    // 자동 동기화가 활성화된 경우 (기본값)
    else if (autoSync) {
      // 파일 존재 여부 확인 및 필요한 파일 동기화
      results = await runAutoSync();
      
      // 강제 업데이트 요청된 경우
      if (forceUpdate) {
        results = await syncAllFiles(true);
      }
    } 
    // 자동 동기화가 비활성화되고 파일 ID도 없는 경우
    else {
      results = await syncAllFiles(forceUpdate);
    }
    
    return NextResponse.json({ results });
  } catch (error) {
    console.error('API 처리 중 오류 발생:', error);
    return NextResponse.json({ error: '파일 동기화 중 오류가 발생했습니다.' }, { status: 500 });
  }
}
