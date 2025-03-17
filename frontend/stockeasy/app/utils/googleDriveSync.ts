import axios from 'axios';
import fs from 'fs';
import path from 'path';

// 캐시 정보
interface CacheInfo {
  cachePath: string;
  lastUpdated: string;
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
  updateSchedule: 'regular' | 'market' | 'afternoon'; // regular: 17:50에 한 번, market: 9시-16시 10분마다, afternoon: 16:30에 한 번
}

// 캐시 레지스트리 파일 경로
const CACHE_REGISTRY_PATH = path.join(process.cwd(), 'public', 'last_update.json');

// ETF 관련 파일 정보
const ETF_FILES: DriveFileInfo[] = [
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
 * 현재 시장 거래 시간인지 확인합니다.
 * 9시부터 16시까지를 시장 시간으로 간주합니다.
 */
function isMarketHours(): boolean {
  const now = new Date();
  const hours = now.getHours();
  
  // 9시 ~ 16시 사이 체크
  return hours >= 9 && hours < 16;
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
 * 파일 업데이트가 필요한지 확인합니다.
 */
function needsUpdate(cacheInfo: CacheInfo | undefined, updateSchedule: 'regular' | 'market' | 'afternoon'): boolean {
  // 캐시 정보가 없거나 파일이 존재하지 않으면 업데이트 필요
  if (!cacheInfo || !fs.existsSync(cacheInfo.cachePath)) {
    return true;
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

/**
 * 구글 드라이브에서 파일을 다운로드합니다.
 */
async function downloadFromGoogleDrive(fileId: string, outputPath: string): Promise<boolean> {
  try {
    console.log(`구글 드라이브에서 파일 다운로드 시작 (ID: ${fileId})`);
    
    // 구글 드라이브 다운로드 URL (URL 형식 변경)
    // 더 안정적인 다운로드를 위해 export=download 파라미터 추가
    const url = `https://drive.google.com/uc?id=${fileId}&export=download&confirm=t`;
    
    // 파일 다운로드
    const response = await axios({
      method: 'get',
      url,
      responseType: 'arraybuffer', // stream 대신 arraybuffer 사용 (더 안정적)
      timeout: 60000, // 60초 타임아웃 설정 (더 긴 시간 제공)
      headers: {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
      }
    });
    
    // 응답 상태 코드 확인
    if (response.status !== 200) {
      console.error(`파일 다운로드 실패 (ID: ${fileId}): 상태 코드 ${response.status}`);
      return false;
    }
    
    // 응답 데이터 확인
    if (!response.data || response.data.length === 0) {
      console.error(`파일 다운로드 실패 (ID: ${fileId}): 빈 응답 데이터`);
      return false;
    }
    
    // 디렉토리가 없으면 생성
    const dir = path.dirname(outputPath);
    if (!fs.existsSync(dir)) {
      fs.mkdirSync(dir, { recursive: true });
    }
    
    // 파일 저장 (stream 대신 writeFileSync 사용)
    fs.writeFileSync(outputPath, Buffer.from(response.data));
    
    // 파일이 제대로 저장되었는지 확인
    if (fs.existsSync(outputPath)) {
      const stats = fs.statSync(outputPath);
      if (stats.size > 0) {
        console.log(`파일 다운로드 완료 (ID: ${fileId}, 경로: ${outputPath}, 크기: ${stats.size} 바이트)`);
        return true;
      } else {
        console.error(`파일 다운로드 실패 (ID: ${fileId}): 파일 크기가 0입니다.`);
        return false;
      }
    } else {
      console.error(`파일 다운로드 실패 (ID: ${fileId}): 파일이 저장되지 않았습니다.`);
      return false;
    }
  } catch (error) {
    console.error(`파일 다운로드 실패 (ID: ${fileId}):`, error);
    
    // 에러 세부 정보 로깅
    if (axios.isAxiosError(error) && error.response) {
      console.error(`응답 상태: ${error.response.status}`);
      console.error(`응답 데이터:`, error.response.data);
    }
    
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
  } catch (error) {
    console.error(`파일 백업 실패 (${sourcePath} -> ${backupPath}):`, error);
  }
  
  return false;
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
  const cachePath = path.join(process.cwd(), 'public', fileInfo.folderPath, fileInfo.fileName);
  const backupPath = path.join(process.cwd(), 'public', fileInfo.folderPath, `${fileInfo.fileName}.backup`);
  
  // 파일 경로 로그 출력 (디버깅용)
  console.log(`파일 경로: ${cachePath}`);
  console.log(`백업 경로: ${backupPath}`);
  
  // 휴일 체크 (휴일에는 업데이트하지 않음)
  if (isHoliday()) {
    console.log('오늘은 휴일입니다. 데이터 업데이트를 건너뜁니다.');
    
    // 캐시된 파일이 있으면 그것을 사용
    if (fs.existsSync(cachePath)) {
      const stats = fs.statSync(cachePath);
      if (stats.size > 0) {
        console.log(`기존 캐시 파일 사용 (${cachePath}, 크기: ${stats.size} 바이트)`);
        return cachePath;
      } else {
        console.log(`캐시 파일이 비어 있습니다. 백업 파일 확인 중...`);
      }
    }
    
    // 백업 파일이 있으면 그것을 사용
    if (cacheInfo?.backupPath && fs.existsSync(cacheInfo.backupPath)) {
      const stats = fs.statSync(cacheInfo.backupPath);
      if (stats.size > 0) {
        console.log(`백업 파일 사용 (${cacheInfo.backupPath}, 크기: ${stats.size} 바이트)`);
        return cacheInfo.backupPath;
      } else {
        console.log(`백업 파일이 비어 있습니다. 새로 다운로드 시도...`);
      }
    }
    
    // 둘 다 없으면 새로 다운로드 (휴일이라도 파일이 없으면 다운로드)
  }
  
  // 파일이 없거나 업데이트가 필요한 경우 다운로드
  if (!fs.existsSync(cachePath) || fs.statSync(cachePath).size === 0 || needsUpdate(cacheInfo, fileInfo.updateSchedule)) {
    console.log(`파일 업데이트 필요 (ID: ${fileInfo.fileId})`);
    
    // 기존 파일 백업
    if (fs.existsSync(cachePath) && fs.statSync(cachePath).size > 0) {
      console.log(`기존 파일 백업 중... (${cachePath} -> ${backupPath})`);
      backupFile(cachePath, backupPath);
    } else {
      console.log(`백업할 파일이 없거나 비어 있습니다.`);
    }
    
    // 구글 드라이브에서 다운로드
    console.log(`구글 드라이브에서 다운로드 시도 중... (ID: ${fileInfo.fileId})`);
    const success = await downloadFromGoogleDrive(fileInfo.fileId, cachePath);
    
    if (success) {
      // 다운로드 후 파일 존재 여부 및 크기 확인
      if (fs.existsSync(cachePath) && fs.statSync(cachePath).size > 0) {
        console.log(`다운로드 성공 (${cachePath}, 크기: ${fs.statSync(cachePath).size} 바이트)`);
        
        // 캐시 정보 업데이트
        registry[fileInfo.fileId] = {
          cachePath,
          lastUpdated: new Date().toISOString(),
          backupPath
        };
        
        saveCacheRegistry(registry);
        return cachePath;
      } else {
        console.error(`다운로드 실패: 파일이 없거나 비어 있습니다.`);
      }
    } else {
      console.error(`파일 다운로드 실패 (ID: ${fileInfo.fileId})`);
    }
    
    // 다운로드 실패 시 백업 파일 확인
    if (fs.existsSync(backupPath) && fs.statSync(backupPath).size > 0) {
      console.log(`백업 파일 사용 (${backupPath}, 크기: ${fs.statSync(backupPath).size} 바이트)`);
      return backupPath;
    } else {
      console.error(`백업 파일도 없거나 비어 있습니다.`);
    }
  } else {
    // 업데이트가 필요 없는 경우 캐시 파일 사용
    const stats = fs.statSync(cachePath);
    console.log(`기존 캐시 파일 사용 (${cachePath}, 크기: ${stats.size} 바이트)`);
    return cachePath;
  }
  
  // 모든 시도 실패 시 빈 문자열 반환
  console.error(`모든 시도 실패. 빈 문자열 반환.`);
  return '';
}

/**
 * ETF 현재가 데이터 파일 경로를 가져옵니다.
 * 파일이 없으면 자동으로 다운로드합니다.
 */
export async function getETFCurrentPricesPath(): Promise<string> {
  const filePath = path.join(process.cwd(), 'public', ETF_FILES[0].folderPath, ETF_FILES[0].fileName);
  
  // 파일이 없으면 다운로드
  if (!fs.existsSync(filePath)) {
    console.log('ETF 현재가 데이터 파일이 없습니다. 다운로드를 시도합니다.');
    return await syncFile(ETF_FILES[0]);
  }
  
  return filePath;
}

/**
 * ETF 52주 신고가 데이터 파일 경로를 가져옵니다.
 * 파일이 없으면 자동으로 다운로드합니다.
 */
export async function getETFHighPricesPath(): Promise<string> {
  const filePath = path.join(process.cwd(), 'public', ETF_FILES[1].folderPath, ETF_FILES[1].fileName);
  
  // 파일이 없으면 다운로드
  if (!fs.existsSync(filePath)) {
    console.log('ETF 52주 신고가 데이터 파일이 없습니다. 다운로드를 시도합니다.');
    return await syncFile(ETF_FILES[1]);
  }
  
  return filePath;
}

/**
 * 모든 ETF 관련 파일을 동기화합니다.
 */
export async function syncAllETFFiles(): Promise<void> {
  for (const fileInfo of ETF_FILES) {
    await syncFile(fileInfo);
  }
}
