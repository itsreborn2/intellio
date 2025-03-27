'use client'

import React, { RefObject } from 'react';
import { toPng } from 'html-to-image';

/**
 * 테이블 복사 버튼 속성 인터페이스
 */
export interface TableCopyButtonProps {
  /** 테이블 요소에 대한 참조 */
  tableRef: RefObject<HTMLElement>;
  /** 헤더 요소에 대한 참조 (옵션) */
  headerRef?: RefObject<HTMLElement>;
  /** 테이블 이름 (이미지 파일명으로 사용) */
  tableName: string;
  /** 복사 옵션 */
  options?: TableCopyOptions;
  /** 버튼 클래스명 */
  className?: string;
  /** 버튼 텍스트 */
  buttonText?: string;
}

/**
 * 테이블 복사 옵션 인터페이스
 */
export interface TableCopyOptions {
  /** 저작권 텍스트 */
  copyright?: string;
  /** 알림 표시 여부 */
  showNotificationMessage?: boolean;
  /** 모바일 스타일 적용 여부 */
  applyMobileStyles?: boolean;
  /** 이미지 스케일 (해상도) */
  scale?: number;
}

/**
 * 알림 메시지 표시 함수
 * @param message 메시지 내용
 * @param type 메시지 타입 (success, error, info)
 * @param showNotification 알림 표시 여부
 */
const showNotificationMessage = (
  message: string, 
  type: 'success' | 'error' | 'info',
  showNotification: boolean = true
): void => {
  // 알림 표시 여부 확인
  if (!showNotification) return;
  
  // 알림 컨테이너 생성
  const notification = document.createElement('div');
  
  // 타입에 따른 배경색 설정
  let backgroundColor = '#4CAF50'; // success (녹색)
  if (type === 'error') {
    backgroundColor = '#F44336'; // 오류 (빨간색)
  } else if (type === 'info') {
    backgroundColor = '#2196F3'; // 정보 (파란색)
  }
  
  // 스타일 적용
  Object.assign(notification.style, {
    position: 'fixed',
    bottom: '20px',
    right: '20px',
    padding: '10px 20px',
    backgroundColor,
    color: 'white',
    borderRadius: '4px',
    boxShadow: '0 2px 5px rgba(0,0,0,0.2)',
    zIndex: '9999',
    fontSize: '14px',
    opacity: '0',
    transition: 'opacity 0.3s ease'
  });
  
  // 메시지 설정
  notification.textContent = message;
  
  // body에 추가
  document.body.appendChild(notification);
  
  // 애니메이션 효과
  setTimeout(() => {
    notification.style.opacity = '1';
  }, 10);
  
  // 3초 후 제거
  setTimeout(() => {
    notification.style.opacity = '0';
    setTimeout(() => {
      document.body.removeChild(notification);
    }, 300);
  }, 3000);
};

/**
 * 테이블을 이미지로 복사하는 함수
 * @param tableRef 테이블 요소에 대한 참조
 * @param headerRef 헤더 요소에 대한 참조 (옵션)
 * @param tableName 테이블 이름 (이미지 파일명으로 사용)
 * @param options 복사 옵션
 */
export const copyTableAsImage = async (
  tableRef: RefObject<HTMLElement>,
  headerRef?: RefObject<HTMLElement>,
  tableName: string = '테이블',
  options: TableCopyOptions = {}
): Promise<void> => {
  try {
    // 기본 옵션 설정
    const defaultOptions: TableCopyOptions = {
      copyright: '© intellio.kr',
      showNotificationMessage: true,
      applyMobileStyles: true,
      scale: 2 // 스케일 2로 낮춤 (CORS 오류 방지)
    };
    
    // 사용자 옵션과 기본 옵션 병합
    const mergedOptions = { ...defaultOptions, ...options };
    
    // 대상 요소가 없는 경우 오류 처리
    if (!tableRef.current) {
      console.error('테이블 요소를 찾을 수 없습니다:', tableRef);
      showNotificationMessage(
        '이미지로 변환할 테이블을 찾을 수 없습니다.', 
        'error',
        mergedOptions.showNotificationMessage
      );
      return;
    }
    
    console.log('캡처할 테이블 요소:', tableRef.current);
    
    // 임시 컨테이너 생성
    const container = document.createElement('div');
    container.style.position = 'absolute';
    container.style.left = '-9999px';
    container.style.top = '-9999px';
    container.style.backgroundColor = '#ffffff';
    container.style.padding = '10px';
    container.style.maxWidth = '800px';
    
    // 헤더와 테이블 클론 생성
    if (headerRef?.current) {
      const headerClone = headerRef.current.cloneNode(true) as HTMLElement;
      container.appendChild(headerClone);
    }
    
    const tableClone = tableRef.current.cloneNode(true) as HTMLElement;
    container.appendChild(tableClone);
    
    // 저작권 텍스트 추가
    if (mergedOptions.copyright) {
      const copyrightDiv = document.createElement('div');
      copyrightDiv.textContent = mergedOptions.copyright;
      
      // 스타일 적용
      Object.assign(copyrightDiv.style, {
        fontSize: '8px',
        color: '#999',
        textAlign: 'center',
        padding: '2px',
        marginTop: '5px'
      });
      
      // 컨테이너에 추가
      container.appendChild(copyrightDiv);
    }
    
    // 문서에 임시 추가
    document.body.appendChild(container);
    
    try {
      // html2canvas 대신 간단한 방법으로 시도
      const canvas = document.createElement('canvas');
      const rect = container.getBoundingClientRect();
      const scale = mergedOptions.scale || 2;
      
      canvas.width = rect.width * scale;
      canvas.height = rect.height * scale;
      
      const ctx = canvas.getContext('2d');
      if (!ctx) {
        throw new Error('캔버스 컨텍스트를 생성할 수 없습니다.');
      }
      
      // 배경색 설정
      ctx.fillStyle = '#ffffff';
      ctx.fillRect(0, 0, canvas.width, canvas.height);
      
      // 스케일 적용
      ctx.scale(scale, scale);
      
      // HTML을 이미지로 변환 (html2canvas 대신 SVG 방식 사용)
      const data = `
        <svg xmlns="http://www.w3.org/2000/svg" width="${rect.width}" height="${rect.height}">
          <foreignObject width="100%" height="100%">
            <div xmlns="http://www.w3.org/1999/xhtml">
              ${container.innerHTML}
            </div>
          </foreignObject>
        </svg>
      `;
      
      // SVG를 이미지로 변환
      const img = new Image();
      const blob = new Blob([data], { type: 'image/svg+xml' });
      const url = URL.createObjectURL(blob);
      
      // 이미지 로드 완료 후 처리
      img.onload = () => {
        // 이미지 그리기
        ctx.drawImage(img, 0, 0);
        URL.revokeObjectURL(url);
        
        // 캔버스를 이미지로 변환
        const imgData = canvas.toDataURL('image/png');
        
        // 클립보드에 복사 시도
        try {
          // 클립보드 API 사용
          const blobFromCanvas = dataURLToBlob(imgData);
          navigator.clipboard.write([
            new ClipboardItem({ 'image/png': blobFromCanvas })
          ]).then(() => {
            showNotificationMessage(
              '이미지가 클립보드에 복사되었습니다.', 
              'success',
              mergedOptions.showNotificationMessage
            );
          }).catch((clipboardError) => {
            console.error('클립보드 복사 오류:', clipboardError);
            
            // 대체 방법: 다운로드 링크 생성
            const link = document.createElement('a');
            link.href = imgData;
            link.download = `${tableName}.png`;
            link.click();
            
            showNotificationMessage(
              '이미지를 다운로드합니다.', 
              'info',
              mergedOptions.showNotificationMessage
            );
          });
        } catch (clipboardError) {
          console.error('클립보드 복사 오류:', clipboardError);
          
          // 대체 방법: 다운로드 링크 생성
          const link = document.createElement('a');
          link.href = imgData;
          link.download = `${tableName}.png`;
          link.click();
          
          showNotificationMessage(
            '이미지를 다운로드합니다.', 
            'info',
            mergedOptions.showNotificationMessage
          );
        }
      };
      
      // 이미지 로드 오류 처리
      img.onerror = (error) => {
        console.error('이미지 로드 오류:', error);
        throw new Error('SVG를 이미지로 변환하는 데 실패했습니다.');
      };
      
      // 이미지 로드 시작
      img.src = url;
      
    } catch (error) {
      console.error('이미지 생성 오류:', error);
      
      // html-to-image 라이브러리 사용 (대체 방법)
      try {
        const toPngOptions = {
          quality: 1.0,
          pixelRatio: mergedOptions.scale || 2,
          backgroundColor: '#ffffff',
          skipAutoScale: true,
          cacheBust: true,
          // CORS 오류 방지 옵션
          skipFonts: true,
          includeQueryParams: true,
          imagePlaceholder: 'data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mP8z8BQDwAEhQGAhKmMIQAAAABJRU5ErkJggg=='
        };
        
        toPng(container, toPngOptions)
          .then(dataUrl => {
            // 클립보드에 복사 시도
            try {
              const blob = dataURLToBlob(dataUrl);
              navigator.clipboard.write([
                new ClipboardItem({ 'image/png': blob })
              ]).then(() => {
                showNotificationMessage(
                  '이미지가 클립보드에 복사되었습니다.', 
                  'success',
                  mergedOptions.showNotificationMessage
                );
              }).catch((clipboardError) => {
                console.error('클립보드 복사 오류:', clipboardError);
                
                // 대체 방법: 다운로드 링크 생성
                const link = document.createElement('a');
                link.href = dataUrl;
                link.download = `${tableName}.png`;
                link.click();
                
                showNotificationMessage(
                  '이미지를 다운로드합니다.', 
                  'info',
                  mergedOptions.showNotificationMessage
                );
              });
            } catch (clipboardError) {
              console.error('클립보드 복사 오류:', clipboardError);
              
              // 대체 방법: 다운로드 링크 생성
              const link = document.createElement('a');
              link.href = dataUrl;
              link.download = `${tableName}.png`;
              link.click();
              
              showNotificationMessage(
                '이미지를 다운로드합니다.', 
                'info',
                mergedOptions.showNotificationMessage
              );
            }
          })
          .catch(err => {
            console.error('toPng 오류:', err);
            showNotificationMessage(
              '이미지 생성에 실패했습니다.', 
              'error',
              mergedOptions.showNotificationMessage
            );
          });
      } catch (fallbackError) {
        console.error('대체 이미지 생성 방법도 실패:', fallbackError);
        showNotificationMessage(
          '이미지 생성에 실패했습니다.', 
          'error',
          mergedOptions.showNotificationMessage
        );
      }
    } finally {
      // 임시 요소 제거
      document.body.removeChild(container);
    }
  } catch (error) {
    console.error('테이블 복사 중 오류 발생:', error);
    showNotificationMessage(
      '이미지 생성 중 오류가 발생했습니다.', 
      'error',
      options.showNotificationMessage
    );
  }
};

/**
 * Data URL을 Blob으로 변환하는 유틸리티 함수
 * @param dataUrl Data URL 문자열
 * @returns Blob 객체
 */
function dataURLToBlob(dataUrl: string): Blob {
  const arr = dataUrl.split(',');
  const mime = arr[0].match(/:(.*?);/)?.[1] || 'image/png';
  const bstr = atob(arr[1]);
  let n = bstr.length;
  const u8arr = new Uint8Array(n);
  
  while (n--) {
    u8arr[n] = bstr.charCodeAt(n);
  }
  
  return new Blob([u8arr], { type: mime });
}