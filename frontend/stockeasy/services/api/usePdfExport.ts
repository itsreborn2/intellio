/**
 * usePdfExport.ts
 * PDF 내보내기 기능을 위한 커스텀 훅
 */
import { useState, useCallback } from 'react';
import { toast } from 'sonner';
import { API_ENDPOINT_STOCKEASY } from '@/services/api/index';

/**
 * PDF 내보내기 훅의 반환값 타입
 */
interface UsePdfExportReturn {
  isPdfLoading: boolean;
  exportToPdf: (sessionId: string, expertMode: boolean) => Promise<void>;
}

/**
 * PDF 내보내기 기능을 제공하는 커스텀 훅
 * 
 * @returns 로딩 상태와 PDF 내보내기 함수
 */
export function usePdfExport(): UsePdfExportReturn {
  // PDF 로딩 상태
  const [isPdfLoading, setIsPdfLoading] = useState<boolean>(false);

  // PDF 내보내기 함수
  const exportToPdf = useCallback(async (sessionId: string, expertMode: boolean = false) => {
    if (!sessionId) {
      toast.error('채팅 세션이 없습니다.');
      return;
    }
    
    try {
      setIsPdfLoading(true);
      
      // 백엔드에 PDF 생성 요청
      const response = await fetch(`${API_ENDPOINT_STOCKEASY}/chat/sessions/${sessionId}/save_pdf`, {
        method: 'POST',
        credentials: 'include',
        headers: {
          'Content-Type': 'application/json'
        },
        body: JSON.stringify({
          expert_mode: expertMode  // 전문가/주린이 모드 상태 전달
        })
      });
      
      if (!response.ok) {
        throw new Error(`PDF 생성 요청 실패: ${response.status}`);
      }
      
      const data = await response.json();
      
      // PDF 다운로드 링크 열기
      if (data.download_url) {
        // 새 탭에서 다운로드 링크 열기
        window.open(data.download_url, '_blank');
        // 성공 메시지는 표시하지 않음 (불필요한 토스트 제거)
      } else {
        toast.error('PDF 다운로드 URL이 제공되지 않았습니다.');
      }
    } catch (error) {
      console.error('PDF 생성 중 오류:', error);
      toast.error('PDF 생성 중 오류가 발생했습니다.');
    } finally {
      setIsPdfLoading(false);
    }
  }, []);

  return {
    isPdfLoading,
    exportToPdf
  };
}

export default usePdfExport; 