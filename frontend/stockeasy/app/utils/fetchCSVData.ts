/**
 * fetchCSVData.ts
 * CSV 파일을 가져오는 유틸리티 함수
 * 모든 파일은 public 폴더에서 로드하거나 API를 통해 다운로드합니다.
 */
import Papa from 'papaparse';

/**
 * CSV 데이터를 가져오는 함수
 * 
 * public 폴더에서 CSV 파일을 로드합니다.
 * 
 * @param filePath 파일 경로 (public 폴더 기준)
 * @returns CSV 데이터 문자열
 */
export const fetchCSVData = async (filePath: string): Promise<string> => {
  try {
    // 파일 경로가 /로 시작하지 않으면 추가
    const normalizedPath = filePath.startsWith('/') ? filePath : `/${filePath}`;
    
    // URL 인코딩 적용 - 한글 및 특수문자 처리
    const encodedPath = encodeURI(normalizedPath);
    console.log(`파일 로드 시도: ${filePath}`);
    
    // public 폴더에서 파일 로드
    const response = await fetch(encodedPath, { cache: 'no-store' });
    
    if (!response.ok) {
      throw new Error(`파일을 찾을 수 없습니다: ${filePath}`);
    }
    
    const data = await response.text();
    
    return data;
  } catch (error) {
    console.error(`파일 로드 실패: ${filePath}`, error);
    throw error;
  }
}
