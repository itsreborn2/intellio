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
  // market-index 폴더 파일들 추가
  {
    fileId: '1ks9QkdZMsxV-qEnV6udZZIDfWgYKC1qg',
    folderPath: 'market-index',
    fileName: '1ks9QkdZMsxV-qEnV6udZZIDfWgYKC1qg.csv',
    updateSchedule: 'chart_daily'  // 17:10에 한 번 업데이트 (휴일 제외)
  },
  {
    fileId: '1Dzf65fZ6elQ6b5zNvhUAFtN10HqJBE_c',
    folderPath: 'market-index',
    fileName: '1Dzf65fZ6elQ6b5zNvhUAFtN10HqJBE_c.csv',
    updateSchedule: 'chart_daily'  // 17:10에 한 번 업데이트 (휴일 제외)
  }
];

// 폴더 ID 목록
const FOLDER_IDS: string[] = [];

// 마지막 실행 시간을 저장하는 변수
let lastRunTime = 0;

/**
 * 캐시 레지스트리를 로드합니다.
 * 파일이 없으면 빈 객체를 반환.
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
 * 파일 존재 여부를 확인합니다.
 * @param filePath 파일 경로
 * @returns 파일 존재 여부
 */
function fileExists(filePath: string): boolean {
  return fs.existsSync(filePath);
}

/**
 * 파일 동기화 함수
 * @param fileInfo 파일 정보
 * @param forceUpdate 강제 업데이트 여부
 * @returns 동기화 결과 메시지
 */
async function syncFile(fileInfo: FileInfo, forceUpdate: boolean = false): Promise<string> {
  const { fileId, folderPath, fileName } = fileInfo;
  
  // 파일 경로 생성
  const publicDir = path.join(process.cwd(), 'public');
  const targetDir = path.join(publicDir, folderPath);
  const filePath = path.join(targetDir, fileName);
  
  // 파일이 이미 존재하는 경우 업데이트하지 않음
  if (fileExists(filePath) && !forceUpdate) {
    return `파일이 이미 존재합니다: ${filePath}`;
  }
  
  try {
    // 디렉토리가 없으면 생성
    if (!fs.existsSync(targetDir)) {
      fs.mkdirSync(targetDir, { recursive: true });
    }
    
    // Google Drive API를 통해 파일 다운로드
    const response = await axios({
      method: 'GET',
      url: `https://drive.google.com/uc?id=${fileId}&export=download`,
      responseType: 'stream'
    });
    
    // 파일 저장
    const writer = fs.createWriteStream(filePath);
    response.data.pipe(writer);
    
    return new Promise<string>((resolve, reject) => {
      writer.on('finish', () => {
        // 캐시 정보 업데이트
        updateCacheInfo(fileId, filePath);
        resolve(`파일 다운로드 완료: ${filePath}`);
      });
      
      writer.on('error', (error) => {
        reject(`파일 다운로드 실패: ${error.message}`);
      });
    });
  } catch (error: any) {
    console.error(`파일 다운로드 실패 (${fileId}):`, error.message);
    return `파일 다운로드 실패: ${error.message}`;
  }
}

/**
 * 모든 파일을 동기화합니다.
 */
async function syncAllFiles(): Promise<string[]> {
  const results: string[] = [];
  
  for (const fileInfo of FILES_TO_SYNC) {
    try {
      // 파일 경로 생성
      const publicDir = path.join(process.cwd(), 'public');
      const targetDir = path.join(publicDir, fileInfo.folderPath);
      const filePath = path.join(targetDir, fileInfo.fileName);
      
      // 파일이 없을 때만 동기화
      if (!fileExists(filePath)) {
        const result = await syncFile(fileInfo);
        results.push(result);
      }
    } catch (error: any) {
      results.push(`파일 동기화 실패 (${fileInfo.fileId}): ${error.message}`);
    }
  }
  
  return results;
}

/**
 * 자동 동기화 실행 함수
 * 이 함수는 API 요청이 들어올 때 파일이 없는 경우에만 파일을 동기화합니다.
 */
async function runAutoSync(forceUpdate: boolean = false): Promise<string[]> {
  // 파일이 없는 경우에만 동기화
  return await syncAllFiles();
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
 * ETF 현재가 데이터 파일 경로를 가져옵니다.
 * 파일이 없으면 자동으로 다운로드합니다.
 * @returns 파일 경로
 */
async function getETFCurrentPricesPath(): Promise<string> {
  const publicDir = path.join(process.cwd(), 'public');
  const targetDir = path.join(publicDir, 'today_price_etf');
  const filePath = path.join(targetDir, 'today_price_etf.csv');
  
  // 파일이 없으면 다운로드
  if (!fileExists(filePath)) {
    const fileInfo = FILES_TO_SYNC.find(f => f.fileName === 'today_price_etf.csv');
    if (fileInfo) {
      await syncFile(fileInfo);
    }
  }
  
  return filePath;
}

/**
 * ETF 52주 신고가 데이터 파일 경로를 가져옵니다.
 * 파일이 없으면 자동으로 다운로드합니다.
 * @returns 파일 경로
 */
async function getETFHighPricesPath(): Promise<string> {
  const publicDir = path.join(process.cwd(), 'public');
  const targetDir = path.join(publicDir, 'etf_stocklist');
  const filePath = path.join(targetDir, 'etf_stocklist.csv');
  
  // 파일이 없으면 다운로드
  if (!fileExists(filePath)) {
    const fileInfo = FILES_TO_SYNC.find(f => f.fileName === 'etf_stocklist.csv');
    if (fileInfo) {
      await syncFile(fileInfo);
    }
  }
  
  return filePath;
}

/**
 * 모든 ETF 관련 파일을 동기화합니다.
 */
async function syncAllETFFiles(): Promise<void> {
  // ETF 관련 파일만 필터링
  const etfFiles = FILES_TO_SYNC.filter(f => 
    f.updateSchedule === 'etf_stocks' || 
    f.fileName === 'today_price_etf.csv' || 
    f.fileName === 'etf_stocklist.csv'
  );
  
  // 파일이 없는 경우에만 동기화
  for (const fileInfo of etfFiles) {
    const publicDir = path.join(process.cwd(), 'public');
    const targetDir = path.join(publicDir, fileInfo.folderPath);
    const filePath = path.join(targetDir, fileInfo.fileName);
    
    if (!fileExists(filePath)) {
      await syncFile(fileInfo);
    }
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
