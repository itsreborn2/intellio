import { useState } from 'react';
import { API_ENDPOINT_STOCKEASY } from './index';
import { toast } from 'sonner';

export interface IShareLinkResponse {
  share_uuid: string;
  share_url: string;
}

export function useChatShare() {
  const [isShareLoading, setIsShareLoading] = useState<boolean>(false);
  
  // 공유 링크 생성 함수
  const createShareLink = async (sessionId: string): Promise<IShareLinkResponse> => {
    setIsShareLoading(true);
    
    try {
      const response = await fetch(`${API_ENDPOINT_STOCKEASY}/chat/share/make_link/${sessionId}`, {
        method: 'GET',
        headers: {
          'Content-Type': 'application/json',
        },
        credentials: 'include',
      });
      
      if (!response.ok) {
        throw new Error('공유 링크 생성 실패');
      }
      
      const data = await response.json();
      return data as IShareLinkResponse;
    } catch (error) {
      console.error('공유 링크 생성 오류:', error);
      throw error;
    } finally {
      setIsShareLoading(false);
    }
  };
  
  // 공유된 채팅 세션 조회 함수
  const getSharedChat = async (shareUuid: string): Promise<any> => {
    try {
      const response = await fetch(`${API_ENDPOINT_STOCKEASY}/chat/share/${shareUuid}`, {
        method: 'GET',
        headers: {
          'Content-Type': 'application/json',
        },
      });
      
      if (!response.ok) {
        throw new Error('공유된 채팅 조회 실패');
      }
      
      return await response.json();
    } catch (error) {
      console.error('공유된 채팅 조회 오류:', error);
      throw error;
    }
  };
  
  return {
    isShareLoading,
    createShareLink,
    getSharedChat,
  };
} 