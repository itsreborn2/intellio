/**
 * useKeyboardVisibility.ts
 * 모바일 가상 키보드의 가시성을 감지하는 커스텀 훅
 */
import { useState, useEffect } from 'react';
import { useIsMobile } from './useIsMobile';

/**
 * 모바일 가상 키보드의 가시성을 감지하는 훅
 * @returns 키보드 표시 여부(boolean)와 키보드 높이(숫자, 픽셀)
 */
export function useKeyboardVisibility() {
  const [isKeyboardVisible, setIsKeyboardVisible] = useState<boolean>(false);
  const [keyboardHeight, setKeyboardHeight] = useState<number>(0);
  const isMobile = useIsMobile();

  useEffect(() => {
    // 모바일 환경에서만 실행
    if (!isMobile || typeof window === 'undefined') return;

    const handleResize = () => {
      // 화면 높이 계산을 통한 키보드 가시성 감지
      const visualViewport = window.visualViewport;
      
      if (visualViewport) {
        // VisualViewport API 사용 가능 시 (모던 브라우저)
        const windowHeight = window.innerHeight;
        const viewportHeight = visualViewport.height;
        
        // 뷰포트 높이가 창 높이보다 작아지면 키보드가 표시된 것으로 간주
        const keyboardHeight = windowHeight - viewportHeight;
        const isKeyboardOpen = keyboardHeight > 150; // 150px 이상 차이가 나면 키보드 표시로 판단
        
        setIsKeyboardVisible(isKeyboardOpen);
        setKeyboardHeight(isKeyboardOpen ? keyboardHeight : 0);
        
        // 키보드 상태에 따라 body 클래스 설정
        if (isKeyboardOpen) {
          document.body.classList.add('keyboard-open');
        } else {
          document.body.classList.remove('keyboard-open');
        }
      } else {
        // Fallback: 입력 요소에 포커스가 있을 때 키보드가 표시되었다고 가정
        const activeElement = document.activeElement;
        const isInput = activeElement && (
          activeElement.tagName === 'INPUT' || 
          activeElement.tagName === 'TEXTAREA' || 
          activeElement.getAttribute('contenteditable') === 'true'
        );
        
        // isInput이 null이 될 수 없도록 Boolean으로 확실하게 변환
        setIsKeyboardVisible(Boolean(isInput));
        // 정확한 높이는 알 수 없으므로 대략적인 값 사용
        setKeyboardHeight(isInput ? 270 : 0);
        
        // 키보드 상태에 따라 body 클래스 설정
        if (isInput) {
          document.body.classList.add('keyboard-open');
        } else {
          document.body.classList.remove('keyboard-open');
        }
      }
    };

    // 초기 실행
    handleResize();

    // 이벤트 리스너 등록
    window.addEventListener('resize', handleResize);
    
    // iOS Safari에서 더 정확한 감지를 위한 추가 이벤트
    if (window.visualViewport) {
      window.visualViewport.addEventListener('resize', handleResize);
      window.visualViewport.addEventListener('scroll', handleResize);
    }
    
    // 포커스 이벤트도 추가
    document.addEventListener('focusin', handleResize);
    document.addEventListener('focusout', handleResize);

    // 정리 함수
    return () => {
      window.removeEventListener('resize', handleResize);
      
      if (window.visualViewport) {
        window.visualViewport.removeEventListener('resize', handleResize);
        window.visualViewport.removeEventListener('scroll', handleResize);
      }
      
      document.removeEventListener('focusin', handleResize);
      document.removeEventListener('focusout', handleResize);
      
      // 클래스 정리
      document.body.classList.remove('keyboard-open');
    };
  }, [isMobile]);

  return { isKeyboardVisible, keyboardHeight };
}

export default useKeyboardVisibility; 