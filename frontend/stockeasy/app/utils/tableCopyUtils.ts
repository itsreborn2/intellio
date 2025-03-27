import html2canvas from 'html2canvas';

interface CopyTableOptions {
  copyrightText?: string;
  footerStyle?: Partial<CSSStyleDeclaration>;
  scale?: number;
  backgroundColor?: string;
}

/**
 * 테이블 복사 버튼 컴포넌트 속성 타입
 */
export interface TableCopyButtonProps {
  tableRef: React.RefObject<HTMLDivElement>;
  headerRef: React.RefObject<HTMLDivElement>;
  tableName: string;
  options?: CopyTableOptions;
  className?: string;
  buttonText?: string;
}

/**
 * 테이블을 이미지로 복사하는 유틸리티 함수
 * @param tableRef 테이블 요소에 대한 참조
 * @param headerRef 헤더 요소에 대한 참조
 * @param tableName 테이블 이름 (알림 메시지에 사용)
 * @param options 추가 옵션 (저작권 텍스트, 푸터 스타일 등)
 */
export const copyTableAsImage = async (
  tableRef: React.RefObject<HTMLDivElement>,
  headerRef: React.RefObject<HTMLDivElement>,
  tableName: string,
  options?: CopyTableOptions
) => {
  // 로딩 메시지 즉시 표시 (가장 먼저 실행)
  const loadingToast = document.createElement('div');
  loadingToast.className = 'fixed top-4 right-4 bg-blue-600 text-white px-4 py-2 rounded shadow-lg z-50 animate-pulse';
  loadingToast.innerHTML = '<strong>이미지 생성 중...</strong>';
  // DOM에 즉시 추가하여 즉시 표시되도록 함
  document.body.appendChild(loadingToast);
  
  // 0ms 지연으로 다음 이벤트 루프에서 실행되도록 하여 UI 렌더링 차단 방지
  await new Promise(resolve => setTimeout(resolve, 0));
  
  if (!tableRef.current || !headerRef.current) {
    document.body.removeChild(loadingToast);
    return;
  }
  
  // 기본 옵션 설정
  const defaultOptions: CopyTableOptions = {
    copyrightText: '스탁이지 stockeasy.intellio.kr<br>(주)인텔리오',
    footerStyle: {
      borderTop: '1px solid #e2e8f0',
      marginTop: '10px',
      paddingTop: '5px',
      textAlign: 'center',
      fontSize: '12px',
      color: '#718096'
    },
    scale: 2,
    backgroundColor: '#ffffff'
  };
  
  // 사용자 옵션과 기본 옵션 병합
  const mergedOptions = { ...defaultOptions, ...options };
  
  try {
    // 임시 컨테이너 생성 (테이블 헤더, 테이블, 저작권 정보를 포함)
    const container = document.createElement('div');
    container.style.backgroundColor = mergedOptions.backgroundColor || '#ffffff';
    container.style.padding = '10px';
    container.style.width = tableRef.current.offsetWidth + 'px';
    
    // 헤더 복제
    const headerClone = headerRef.current.cloneNode(true) as HTMLElement;
    
    // 버튼 제거
    const buttons = headerClone.querySelectorAll('button');
    buttons.forEach(button => button.remove());
    
    // 날짜 정보 추가
    const titleElements = headerClone.querySelectorAll('h2');
    if (titleElements.length > 0) {
      const titleElement = titleElements[0];
      const currentDate = new Date();
      const formattedDate = `${currentDate.getFullYear()}-${String(currentDate.getMonth() + 1).padStart(2, '0')}-${String(currentDate.getDate()).padStart(2, '0')}`;
      
      // 날짜 텍스트 요소 생성
      const dateSpan = document.createElement('span');
      dateSpan.textContent = ` (${formattedDate})`;
      dateSpan.style.fontSize = '0.75rem';
      dateSpan.style.fontWeight = 'normal';
      dateSpan.style.color = '#718096';
      dateSpan.style.marginLeft = '5px';
      
      // 제목 요소에 날짜 추가
      titleElement.appendChild(dateSpan);
    }
    
    container.appendChild(headerClone);
    
    // 테이블 복제
    const tableClone = tableRef.current.cloneNode(true) as HTMLElement;
    container.appendChild(tableClone);
    
    // 구분선 및 저작권 정보 추가
    if (mergedOptions.copyrightText) {
      const footer = document.createElement('div');
      
      // 푸터 스타일 적용
      if (mergedOptions.footerStyle) {
        Object.entries(mergedOptions.footerStyle).forEach(([key, value]) => {
          if (value) {
            // @ts-ignore - 동적 스타일 속성 할당
            footer.style[key] = value;
          }
        });
      }
      
      footer.innerHTML = mergedOptions.copyrightText;
      container.appendChild(footer);
    }
    
    // 임시로 DOM에 추가 (스타일 계산을 위해)
    document.body.appendChild(container);
    container.style.position = 'absolute';
    container.style.left = '-9999px';
    
    // 테이블을 이미지로 변환
    const canvas = await html2canvas(container, {
      scale: mergedOptions.scale || 2, // 고해상도 이미지를 위한 스케일
      backgroundColor: mergedOptions.backgroundColor || '#ffffff',
      logging: false
    });
    
    // 임시 컨테이너 제거
    document.body.removeChild(container);
    
    // 이미지를 클립보드에 복사
    canvas.toBlob(async (blob) => {
      if (!blob) {
        console.error('이미지 생성 실패');
        return;
      }
      
      try {
        // 클립보드에 이미지 복사
        const item = new ClipboardItem({ 'image/png': blob });
        await navigator.clipboard.write([item]);
        
        // 성공 메시지 표시
        document.body.removeChild(loadingToast);
        const successToast = document.createElement('div');
        successToast.className = 'fixed top-4 right-4 bg-green-500 text-white px-4 py-2 rounded shadow-lg z-50';
        successToast.textContent = `${tableName} 이미지가 클립보드에 복사되었습니다.`;
        document.body.appendChild(successToast);
        
        // 3초 후 메시지 제거
        setTimeout(() => {
          document.body.removeChild(successToast);
        }, 3000);
      } catch (error) {
        console.error('클립보드 복사 실패:', error);
        alert('클립보드 복사에 실패했습니다. 브라우저 권한을 확인해주세요.');
      }
    });
  } catch (error) {
    console.error('이미지 생성 실패:', error);
    alert('이미지 생성에 실패했습니다.');
  }
};