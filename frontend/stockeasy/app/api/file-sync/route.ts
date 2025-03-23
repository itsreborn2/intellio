import { NextRequest, NextResponse } from 'next/server';
import fs from 'fs';
import path from 'path';
import axios from 'axios';

// 파일 정보 인터페이스
interface FileInfo {
  fileId: string;
  folderPath: string;
  fileName: string;
  updateSchedule: 'regular' | 'market' | 'market_20ma' | 'afternoon' | 'stock_daily' | 'chart_daily' | 'etf_stocks' | 'today_price' | 'etf_indiestocklist' | 'on_demand';
}

// 캐시 정보 인터페이스
interface CacheInfo {
  cachePath: string;
  lastUpdated: string;
  backupPath?: string;
}

// 캐시 레지스트리 인터페이스
interface CacheRegistry {
  [fileId: string]: CacheInfo;
}

// 구글 드라이브 폴더 ID 상수
// const CHART_DATA_FOLDER_ID = '1VFOD15oWpFvzG4rZz8FWWZZT_BGxb4M_';
// const ETF_INDIESTOCKLIST_FOLDER_ID = '1PFBQNJ6qC0iRbZDK_4zI-jKQhTtTKS-V';
// const MARKET_INDEX_FOLDER_ID = '1ks9QkdZMsxV-qEnV6udZZIDfWgYKC1qg';

// 캐시 레지스트리 파일 경로
const CACHE_REGISTRY_PATH = path.join(process.cwd(), 'public', 'last_update.json');

// 동기화할 파일 목록
const FILES_TO_SYNC: FileInfo[] = [
  // ETF 현재가 데이터
  {
    fileId: '1txqtWnVImMAq6vjD4byFiFFgmbM9KrrA',
    folderPath: 'today_price_etf',
    fileName: 'today_price_etf.csv',
    updateSchedule: 'etf_stocks'
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
  },
  // googleDriveSync.ts에서 추가된 ETF 파일들
  {
    fileId: '1u46PGtK4RY4vUOBIXzvrFsk_mUsxznbA', // ETF 현재가 데이터 파일 ID
    folderPath: 'today_price_etf',
    fileName: '1u46PGtK4RY4vUOBIXzvrFsk_mUsxznbA.csv', // 파일 ID를 파일명으로 사용
    updateSchedule: 'market'
  },
  {
    fileId: '1cUcNxRD307dLGQVLiw1snAkX1LY0sEo0', // ETF 52주 신고가 데이터 파일 ID
    folderPath: 'rs_etf',
    fileName: '1cUcNxRD307dLGQVLiw1snAkX1LY0sEo0.csv', // 파일 ID를 파일명으로 사용
    updateSchedule: 'afternoon'  // 16:30에 업데이트
  }
];

// 폴더 ID 목록
const FOLDER_IDS: string[] = [];

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

  // 파일 존재 여부 및 크기 확인
  let fileExists = false;
  let fileSize = 0;
  
  try {
    if (fs.existsSync(filePath)) {
      const stats = fs.statSync(filePath);
      fileExists = true;
      fileSize = stats.size;
    }
  } catch (error) {
    console.log(`파일 상태 확인 중 오류 발생: ${filePath}`);
    fileExists = false;
  }

  // 파일이 존재하지 않으면 업데이트 필요
  if (!fileExists) {
    console.log(`파일이 존재하지 않아 업데이트 필요: ${filePath}`);
    return true;
  }
  
  // 파일이 비어있으면 업데이트 필요
  if (fileSize === 0) {
    console.log(`파일이 비어있어 업데이트 필요: ${filePath}`);
    return true;
  }
  
  // 파일 경로의 디렉토리 확인
  const dir = path.dirname(filePath);
  if (!fs.existsSync(dir)) {
    console.log(`디렉토리가 존재하지 않아 업데이트 필요: ${dir}`);
    return true;
  }
  
  // 캐시 정보가 없으면, 파일이 이미 존재하고 크기가 0이 아니면 업데이트 불필요
  if (!cacheInfo) {
    console.log(`캐시 정보가 없지만 파일이 존재하고 크기가 ${fileSize}바이트로 유효함: ${filePath}`);
    // 캐시 정보 생성 로직을 여기에 추가할 수 있음
    return false;
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
    
    case 'on_demand': {
      // 항상 false 반환 (파일이 없을 때만 별도 로직으로 처리)
      return false;
    }
    
    default:
      return false;
  }
}

/**
 * 파일 동기화 함수
 * @param fileInfo 파일 정보
 * @param forceUpdate 강제 업데이트 여부
 * @returns 동기화 결과 메시지
 */
async function syncFile(fileInfo: FileInfo, forceUpdate: boolean = false): Promise<string> {
  const { fileId, folderPath, fileName } = fileInfo;
  
  try {
    // 폴더 경로 생성
    const folderFullPath = path.join(process.cwd(), 'public', folderPath);
    
    if (!fs.existsSync(folderFullPath)) {
      fs.mkdirSync(folderFullPath, { recursive: true });
      console.log(`폴더 생성됨: ${folderFullPath}`);
    }
    
    // 파일 경로 설정
    const filePath = path.join(folderFullPath, fileName);
    
    // 파일 다운로드 URL 생성
    const urls = [
      `https://drive.google.com/uc?export=download&id=${fileId}`,
      `https://drive.google.com/uc?export=download&confirm=t&id=${fileId}`,
      `https://docs.google.com/uc?export=download&id=${fileId}`
    ];
    
    // 파일 다운로드 시도
    let success = false;
    let error: any = null;
    
    for (const url of urls) {
      if (success) break;
      
      try {
        console.log(`다운로드 시도: ${url}`);
        
        // 응답 요청
        const response = await axios({
          method: 'get',
          url: url,
          responseType: 'arraybuffer',
          timeout: 120000, // 2분 타임아웃
          headers: {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,image/apng,*/*;q=0.8',
            'Accept-Encoding': 'gzip, deflate, br',
            'Cache-Control': 'no-cache',
            'Pragma': 'no-cache',
            'Cookie': 'download_warning_13058876669=yes' // 다운로드 경고 우회 시도
          },
          maxRedirects: 5 // 리다이렉트 허용 증가
        });
        
        // 응답 상태 코드 확인
        if (response.status !== 200) {
          console.error(`URL ${url} 시도 실패: 상태 코드 ${response.status}`);
          continue;
        }
        
        // 응답 데이터 확인
        if (!response.data || response.data.length === 0) {
          console.error(`URL ${url} 시도 실패: 빈 응답 데이터`);
          continue;
        }
        
        // HTML 응답 확인 (오류 응답일 수 있음)
        const dataString = Buffer.from(response.data).toString('utf8').slice(0, 500);
        
        // HTML 응답이지만 다운로드 링크가 포함된 경우 처리 시도
        if (dataString.includes('<!DOCTYPE html>') || dataString.includes('<html')) {
          console.error(`URL ${url} 시도 실패: HTML 응답 받음`);
          
          // HTML에서 다운로드 링크 추출 시도
          const downloadUrlMatch = dataString.match(/href="(\/uc\?export=download[^"]+)/);
          if (downloadUrlMatch && downloadUrlMatch[1]) {
            const extractedUrl = `https://drive.google.com${downloadUrlMatch[1].replace(/&amp;/g, '&')}`;
            console.log(`HTML에서 다운로드 링크 추출: ${extractedUrl}`);
            
            try {
              const directResponse = await axios({
                method: 'get',
                url: extractedUrl,
                responseType: 'arraybuffer',
                timeout: 120000,
                headers: {
                  'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
                  'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,image/apng,*/*;q=0.8',
                  'Cache-Control': 'no-cache'
                },
                maxRedirects: 5
              });
              
              if (directResponse.status === 200 && directResponse.data && directResponse.data.length > 0) {
                const directDataString = Buffer.from(directResponse.data).toString('utf8').slice(0, 100);
                if (!directDataString.includes('<!DOCTYPE html>') && !directDataString.includes('<html')) {
                  // 직접 다운로드 성공
                  fs.writeFileSync(filePath, directResponse.data);
                  success = true;
                  
                  // 캐시 정보 업데이트
                  updateCacheInfo(fileId, filePath);
                  
                  console.log(`파일 다운로드 성공 (직접 링크): ${fileName}`);
                  break;
                }
              }
            } catch (directError: any) {
              console.error(`직접 링크 다운로드 실패: ${directError.message}`);
            }
          }
          continue;
        }
        
        // 파일 저장
        fs.writeFileSync(filePath, response.data);
        success = true;
        
        // 캐시 정보 업데이트
        updateCacheInfo(fileId, filePath);
        
        console.log(`파일 다운로드 성공: ${fileName}`);
        break;
      } catch (err: any) {
        error = err;
        console.error(`URL ${url} 다운로드 중 오류 발생:`, err.message);
      }
    }
    
    // 디버깅을 위한 파일 크기 확인
    if (success && fs.existsSync(filePath)) {
      const stats = fs.statSync(filePath);
      console.log(`다운로드된 파일 크기: ${stats.size} 바이트`);
      
      // 파일 크기가 0이면 실패로 간주
      if (stats.size === 0) {
        success = false;
        fs.unlinkSync(filePath); // 빈 파일 삭제
        console.error(`다운로드된 파일이 비어 있습니다: ${fileName}`);
      }
      
      // 파일 내용 확인 (JSON 파일인 경우)
      if (fileName.endsWith('.json') && stats.size > 0) {
        try {
          const content = fs.readFileSync(filePath, 'utf8');
          console.log(`JSON 파일 내용 확인: ${content.substring(0, 100)}...`);
          
          // JSON 파싱 시도
          JSON.parse(content);
        } catch (jsonError: any) {
          console.error(`JSON 파일 파싱 오류: ${jsonError.message}`);
          success = false;
        }
      }
    }
    
    if (success) {
      return `파일 다운로드 성공: ${fileName}`;
    } else {
      return `파일 다운로드 실패: ${fileName}, 오류: ${error ? error.message : '알 수 없는 오류'}`;
    }
  } catch (error: any) {
    console.error(`파일 동기화 중 오류 발생: ${fileName}`, error);
    return `파일 동기화 오류: ${fileName}, ${error.message}`;
  }
}

/**
 * 캐시 정보를 업데이트합니다.
 * @param fileId 파일 ID
 * @param filePath 파일 경로
 */
function updateCacheInfo(fileId: string, filePath: string): void {
  const cacheRegistry = loadCacheRegistry();
  cacheRegistry[fileId] = {
    cachePath: filePath,
    lastUpdated: new Date().toISOString()
  };
  saveCacheRegistry(cacheRegistry);
}

/**
 * 모든 파일을 동기화합니다.
 */
async function syncAllFiles(): Promise<string[]> {
  const results: string[] = [];
  
  // 모든 파일 동기화 실행
  for (const fileInfo of FILES_TO_SYNC) {
    try {
      const result = await syncFile(fileInfo);
      results.push(result);
    } catch (error: any) {
      console.error(`파일 동기화 중 오류 발생 (${fileInfo.fileName}):`, error);
      results.push(`파일 동기화 오류: ${fileInfo.fileName}`);
    }
  }
  
  return results;
}

/**
 * 자동 동기화 실행 함수
 * 이 함수는 API 요청이 들어올 때마다 호출되어 필요한 경우 파일을 동기화합니다.
 */
async function runAutoSync(forceUpdate: boolean = false): Promise<string[]> {
  const now = Date.now();
  
  // 마지막 실행 후 5초 이내에는 다시 실행하지 않음 (중복 호출 방지)
  if (now - lastRunTime < 5000 && !forceUpdate) {
    console.log('최근에 이미 실행되었습니다. 5초 후에 다시 시도하세요.');
    return ['최근에 이미 실행되었습니다. 5초 후에 다시 시도하세요.'];
  }
  
  lastRunTime = now;
  console.log(`자동 동기화 시작: ${new Date().toISOString()}`);
  
  try {
    // 파일 목록 동기화
    const results: string[] = [];
    
    // ETF 인디스톡 리스트 file_list.json 파일 먼저 확인 및 동기화
    const fileListInfo = FILES_TO_SYNC.find(file => file.fileName === 'file_list.json');
    if (fileListInfo) {
      const filePath = path.join(process.cwd(), 'public', fileListInfo.folderPath, fileListInfo.fileName);
      const fileExists = fs.existsSync(filePath);
      
      if (!fileExists || forceUpdate) {
        console.log(`file_list.json 파일이 ${fileExists ? '존재하지만 강제 업데이트 요청됨' : '존재하지 않음'}, 다운로드 시도...`);
        const result = await syncFile(fileListInfo, forceUpdate);
        results.push(result);
      }
    }
    
    // 다른 모든 파일 동기화
    for (const fileInfo of FILES_TO_SYNC) {
      // file_list.json은 이미 처리했으므로 건너뜀
      if (fileInfo.fileName === 'file_list.json') continue;
      
      const filePath = path.join(process.cwd(), 'public', fileInfo.folderPath, fileInfo.fileName);
      const cacheRegistry = loadCacheRegistry();
      const cacheInfo = cacheRegistry[fileInfo.fileId];
      
      // 파일 업데이트가 필요한지 확인
      const shouldUpdate = await needsUpdate(filePath, cacheInfo, fileInfo.updateSchedule, forceUpdate);
      
      if (shouldUpdate) {
        console.log(`파일 업데이트 필요: ${fileInfo.fileName}`);
        const result = await syncFile(fileInfo, forceUpdate);
        results.push(result);
      } else {
        console.log(`파일 업데이트 불필요: ${fileInfo.fileName}`);
      }
    }
    
    // 폴더 ID 처리
    for (const folderId of FOLDER_IDS) {
      const result = await handleFolderId(folderId);
      results.push(`폴더 ID ${folderId} 처리 완료: ${result.length}개 파일 발견`);
    }
    
    console.log(`자동 동기화 완료: ${new Date().toISOString()}`);
    return results;
  } catch (error: any) {
    console.error('자동 동기화 중 오류 발생:', error);
    return [`오류 발생: ${error.message}`];
  }
}

/**
 * 폴더 ID에 따른 처리를 수행합니다.
 */
async function handleFolderId(folderId: string): Promise<string[]> {
  try {
    console.log(`폴더 처리 시작 (ID: ${folderId})`);
    return [`폴더 처리 기능이 비활성화되었습니다 (ID: ${folderId})`];
  } catch (error: any) {
    console.error(`폴더 처리 중 오류 발생 (ID: ${folderId}):`, error);
    return [`폴더 처리 오류 (ID: ${folderId})`];
  }
}

/**
 * 폴더 ID에 따른 JSON 파일을 생성합니다.
 */
function createFolderJSON(folderId: string): any[] {
  console.log(`폴더 JSON 생성 기능이 비활성화되었습니다 (ID: ${folderId})`);
  return [];
}

/**
 * ETF 인디스톡 리스트 폴더 JSON 파일을 생성합니다.
 */
function createETFIndieStockListFolderJSON(): any[] {
  console.log(`ETF 인디스톡 리스트 폴더 JSON 생성 기능이 비활성화되었습니다`);
  return [];
}

/**
 * 파일을 백업합니다.
 * @param sourcePath 원본 파일 경로
 * @param backupPath 백업 파일 경로
 * @returns 백업 성공 여부
 */
function backupFile(sourcePath: string, backupPath: string): boolean {
  try {
    if (!fs.existsSync(sourcePath)) {
      console.error(`백업 실패: 원본 파일이 존재하지 않습니다 (${sourcePath})`);
      return false;
    }
    
    const dir = path.dirname(backupPath);
    if (!fs.existsSync(dir)) {
      fs.mkdirSync(dir, { recursive: true });
    }
    
    fs.copyFileSync(sourcePath, backupPath);
    console.log(`파일 백업 완료: ${sourcePath} -> ${backupPath}`);
    return true;
  } catch (error: any) {
    console.error(`파일 백업 중 오류 발생: ${error}`);
    return false;
  }
}

/**
 * ETF 현재가 데이터 파일 경로를 가져옵니다.
 * 파일이 없으면 자동으로 다운로드합니다.
 * @returns 파일 경로
 */
export async function getETFCurrentPricesPath(): Promise<string> {
  const fileInfo = FILES_TO_SYNC.find(file => file.fileId === '1u46PGtK4RY4vUOBIXzvrFsk_mUsxznbA');
  if (!fileInfo) {
    throw new Error('ETF 현재가 데이터 파일 정보를 찾을 수 없습니다.');
  }
  
  const filePath = path.join(process.cwd(), 'public', fileInfo.folderPath, fileInfo.fileName);
  await syncFile(fileInfo);
  return filePath;
}

/**
 * ETF 52주 신고가 데이터 파일 경로를 가져옵니다.
 * 파일이 없으면 자동으로 다운로드합니다.
 * @returns 파일 경로
 */
export async function getETFHighPricesPath(): Promise<string> {
  const fileInfo = FILES_TO_SYNC.find(file => file.fileId === '1cUcNxRD307dLGQVLiw1snAkX1LY0sEo0');
  if (!fileInfo) {
    throw new Error('ETF 52주 신고가 데이터 파일 정보를 찾을 수 없습니다.');
  }
  
  const filePath = path.join(process.cwd(), 'public', fileInfo.folderPath, fileInfo.fileName);
  await syncFile(fileInfo);
  return filePath;
}

/**
 * 모든 ETF 관련 파일을 동기화합니다.
 */
export async function syncAllETFFiles(): Promise<void> {
  const etfFiles = FILES_TO_SYNC.filter(file => 
    file.folderPath.includes('etf') || 
    file.folderPath.includes('rs_etf') || 
    file.folderPath.includes('today_price_etf')
  );
  
  for (const fileInfo of etfFiles) {
    await syncFile(fileInfo);
  }
}

/**
 * POST 요청 처리 핸들러
 */
export async function POST(request: NextRequest) {
  try {
    const body = await request.json();
    const { fileId, folderId, forceUpdate } = body;
    
    // 파일 ID가 제공된 경우
    if (fileId) {
      // 파일 ID에 해당하는 파일 정보 찾기
      const fileInfo = FILES_TO_SYNC.find(f => f.fileId === fileId);
      
      if (!fileInfo) {
        return NextResponse.json({ error: `알 수 없는 파일 ID: ${fileId}` }, { status: 404 });
      }
      
      // 파일 동기화 실행
      const result = await syncFile(fileInfo, forceUpdate === true);
      return NextResponse.json({ result });
    }
    
    // 폴더 ID가 제공된 경우
    if (folderId) {
      // 폴더 ID 처리는 비활성화되었습니다
      return NextResponse.json({ 
        result: [`폴더 ID 처리 기능이 비활성화되었습니다 (ID: ${folderId})`] 
      });
    }
    
    // 파일 ID나 폴더 ID가 제공되지 않은 경우 자동 동기화 실행
    const results = await runAutoSync(forceUpdate === true);
    return NextResponse.json({ result: results });
  } catch (error: any) {
    console.error('API 요청 처리 중 오류 발생:', error);
    return NextResponse.json(
      { error: '파일 동기화 중 오류가 발생했습니다.' },
      { status: 500 }
    );
  }
}

/**
 * GET 요청 처리 핸들러
 */
export async function GET(request: NextRequest) {
  try {
    const { searchParams } = new URL(request.url);
    const folderId = searchParams.get('folderId');
    const forceUpdate = searchParams.get('force') === 'true';
    
    // 폴더 ID가 제공된 경우
    if (folderId) {
      // 폴더 ID 처리는 비활성화되었습니다
      return NextResponse.json({ 
        result: [`폴더 ID 처리 기능이 비활성화되었습니다 (ID: ${folderId})`] 
      });
    }
    
    // 파일 동기화 실행
    const results = await runAutoSync(forceUpdate);
    
    return NextResponse.json({ result: results });
  } catch (error: any) {
    console.error('API 요청 처리 중 오류 발생:', error);
    return NextResponse.json(
      { error: '파일 동기화 중 오류가 발생했습니다.' },
      { status: 500 }
    );
  }
}
