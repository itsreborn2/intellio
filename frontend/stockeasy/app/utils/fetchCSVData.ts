/**
 * fetchCSVData.ts
 * 구글 드라이브에서 CSV 파일을 가져오는 유틸리티 함수
 */
import Papa from 'papaparse';

/**
 * CSV 파일을 가져오는 함수
 * @param fileUrl - CSV 파일의 URL 또는 파일 ID
 * @returns CSV 텍스트 데이터
 */
export const fetchCSVData = async (fileUrl: string): Promise<string> => {
  try {
    // 구글 드라이브 파일 ID인지 확인하고 URL로 변환
    const isGoogleDriveFileId = !fileUrl.includes('http') && fileUrl.length > 20;
    const url = isGoogleDriveFileId 
      ? `https://drive.google.com/uc?export=download&id=${fileUrl}`
      : fileUrl;
    
    console.log(`CSV 다운로드 시작: ${isGoogleDriveFileId ? '구글 드라이브 ID' : 'URL'} - ${fileUrl}`);
    
    // 파일 다운로드
    const response = await fetch(url);
    
    if (!response.ok) {
      throw new Error(`CSV 파일을 다운로드하는데 실패했습니다: ${response.statusText}`);
    }
    
    // 텍스트로 변환
    const csvText = await response.text();
    console.log(`CSV 다운로드 완료: ${csvText.length}자`);
    
    return csvText;
  } catch (error) {
    console.error('CSV 데이터 로딩 오류:', error);
    throw error;
  }
};
