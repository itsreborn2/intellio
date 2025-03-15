/**
 * Google Drive 파일 동기화 및 캐싱 유틸리티
 * 
 * 이 모듈은 Google Drive에서 파일을 다운로드하고 로컬 캐시에 저장하는 기능을 제공합니다.
 * 주요 기능:
 * - 구글 드라이브 파일 다운로드
 * - 캐시 관리 (저장 및 로드)
 * - 휴일 판단 로직
 * - 정해진 시간에 데이터 업데이트
 */

import axios from 'axios';
import fs from 'fs';
import path from 'path';

// 캐시 정보를 저장할 타입 정의
interface CacheInfo {
  fileId: string;
  lastUpdated: string; // ISO 날짜 문자열
  cachePath: string;
  backupPath?: string;
}

// 캐시 정보를 관리하는 객체
interface CacheRegistry {
  [fileId: string]: CacheInfo;
}

// 구글 드라이브 파일 정보
interface DriveFileInfo {
  fileId: string;
  folderPath: string;
  fileName: string;
  updateSchedule: 'regular' | 'market'; // regular: 17:50에 한 번, market: 9시-16시 10분마다
}

// 캐시 레지스트리 파일 경로
const CACHE_REGISTRY_PATH = path.join(process.cwd(), 'public', 'cache', 'cache-registry.json');

// ETF 관련 파일 정보
const ETF_FILES: DriveFileInfo[] = [
  {
    fileId: '1u46PGtK4RY4vUOBIXzvrFsk_mUsxznbA',
    folderPath: 'today_price_etf',
    fileName: 'etf_current_prices.csv',
    updateSchedule: 'market'
  },
  // 여기에 rs_etf 폴더의 파일들을 추가할 수 있습니다
  {
    fileId: '1cUcNxRD307dLGQVLiw1snAkX1LY0sEo0', // 폴더 ID
    folderPath: 'rs_etf',
    fileName: 'etf_high_prices.csv',
    updateSchedule: 'regular'
  }
];

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
    const dirPath = path.dirname(CACHE_REGISTRY_PATH);
    if (!fs.existsSync(dirPath)) {
      fs.mkdirSync(dirPath, { recursive: true });
    }
    fs.writeFileSync(CACHE_REGISTRY_PATH, JSON.stringify(registry, null, 2));
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

/**
 * 오늘이 휴일인지 확인합니다.
 * 코스피 거래대금이 0인 경우 휴일로 판단합니다.
 */
async function isHoliday(): Promise<boolean> {
  try {
    // 코스피 거래대금 데이터를 가져오는 API 호출
    // 실제 구현에서는 적절한 API 엔드포인트로 교체해야 합니다
    const response = await axios.get('/api/market-status');
    return response.data.kospiVolume === 0;
  } catch (error) {
    console.error('휴일 확인 실패:', error);
    // 에러 발생 시 안전하게 휴일이 아니라고 가정
    return false;
  }
}

/**
 * 파일 업데이트가 필요한지 확인합니다.
 */
function needsUpdate(cacheInfo: CacheInfo | undefined, updateSchedule: 'regular' | 'market'): boolean {
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
  
  return false;
}

/**
 * 구글 드라이브에서 파일을 다운로드합니다.
 */
async function downloadFromGoogleDrive(fileId: string, outputPath: string): Promise<boolean> {
  try {
    // 구글 드라이브 다운로드 URL
    const url = `https://drive.google.com/uc?export=download&id=${fileId}`;
    
    // 파일 다운로드
    const response = await axios({
      method: 'get',
      url,
      responseType: 'stream'
    });
    
    // 디렉토리가 없으면 생성
    const dir = path.dirname(outputPath);
    if (!fs.existsSync(dir)) {
      fs.mkdirSync(dir, { recursive: true });
    }
    
    // 파일 저장
    const writer = fs.createWriteStream(outputPath);
    response.data.pipe(writer);
    
    return new Promise((resolve, reject) => {
      writer.on('finish', () => resolve(true));
      writer.on('error', reject);
    });
  } catch (error) {
    console.error(`파일 다운로드 실패 (ID: ${fileId}):`, error);
    return false;
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

/**
 * 파일을 동기화합니다.
 * 필요한 경우에만 구글 드라이브에서 다운로드합니다.
 */
export async function syncFile(fileInfo: DriveFileInfo): Promise<string> {
  // 캐시 레지스트리 로드
  const registry = loadCacheRegistry();
  const cacheInfo = registry[fileInfo.fileId];
  
  // 캐시 파일 경로
  const cachePath = path.join(process.cwd(), 'public', 'cache', fileInfo.folderPath, fileInfo.fileName);
  const backupPath = path.join(process.cwd(), 'public', 'cache', fileInfo.folderPath, `${fileInfo.fileName}.backup`);
  
  // 휴일 체크
  const holiday = await isHoliday();
  if (holiday) {
    console.log('오늘은 휴일입니다. 데이터 업데이트를 건너뜁니다.');
    
    // 캐시된 파일이 있으면 그것을 사용
    if (cacheInfo && fs.existsSync(cacheInfo.cachePath)) {
      return cacheInfo.cachePath;
    }
    
    // 백업 파일이 있으면 그것을 사용
    if (cacheInfo?.backupPath && fs.existsSync(cacheInfo.backupPath)) {
      return cacheInfo.backupPath;
    }
    
    // 둘 다 없으면 새로 다운로드
  }
  
  // 업데이트가 필요한지 확인
  if (needsUpdate(cacheInfo, fileInfo.updateSchedule)) {
    console.log(`파일 업데이트 필요 (ID: ${fileInfo.fileId})`);
    
    // 기존 파일 백업
    if (fs.existsSync(cachePath)) {
      backupFile(cachePath, backupPath);
    }
    
    // 파일 다운로드
    const success = await downloadFromGoogleDrive(fileInfo.fileId, cachePath);
    
    if (success) {
      // 캐시 정보 업데이트
      registry[fileInfo.fileId] = {
        fileId: fileInfo.fileId,
        lastUpdated: new Date().toISOString(),
        cachePath,
        backupPath
      };
      saveCacheRegistry(registry);
      return cachePath;
    } else if (fs.existsSync(backupPath)) {
      // 다운로드 실패 시 백업 파일 사용
      console.log(`다운로드 실패, 백업 파일 사용 (ID: ${fileInfo.fileId})`);
      return backupPath;
    }
  } else if (cacheInfo && fs.existsSync(cacheInfo.cachePath)) {
    // 업데이트가 필요 없고 캐시 파일이 있으면 그것을 사용
    return cacheInfo.cachePath;
  }
  
  // 모든 시도 실패 시 빈 문자열 반환
  return '';
}

/**
 * ETF 현재가 데이터 파일 경로를 가져옵니다.
 */
export async function getETFCurrentPricesPath(): Promise<string> {
  return await syncFile(ETF_FILES[0]);
}

/**
 * ETF 52주 신고가 데이터 파일 경로를 가져옵니다.
 */
export async function getETFHighPricesPath(): Promise<string> {
  return await syncFile(ETF_FILES[1]);
}

/**
 * 모든 ETF 관련 파일을 동기화합니다.
 */
export async function syncAllETFFiles(): Promise<void> {
  for (const fileInfo of ETF_FILES) {
    await syncFile(fileInfo);
  }
}
