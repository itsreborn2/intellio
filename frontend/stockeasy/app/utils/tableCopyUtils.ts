// @ts-ignore
import domtoimage from 'dom-to-image-more';

interface CopyTableOptions {
  copyrightText?: string;
  footerStyle?: Partial<CSSStyleDeclaration>;
  scale?: number;
  backgroundColor?: string;
  watermark?: {
    text?: string;
    opacity?: number;
    fontSize?: string;
    color?: string;
  };
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
      fontSize: '8px',
      color: '#718096'
    },
    scale: 2,
    backgroundColor: '#ffffff',
    watermark: {
      text: '스탁이지\nby (주)인텔리오',
      opacity: 0.08, // 10% 불투명도 (매우 흐리게)
      fontSize: '24px',
      color: '#000000'
    }
  };
  
  // 사용자 옵션과 기본 옵션 병합
  const mergedOptions = { ...defaultOptions, ...options };
  
  try {
    // 임시 컨테이너 생성 (테이블 헤더, 테이블, 저작권 정보를 포함)
    const container = document.createElement('div');
    container.style.backgroundColor = mergedOptions.backgroundColor || '#ffffff';
    container.style.padding = '5px'; // 전체 패딩 축소
    
    // 모바일 사이즈로 고정 (너비 360px)
    container.style.width = '360px';
    
    // 전체 컨테이너에 폰트 크기 조정 적용
    container.style.fontSize = '12px';
    
    // 헤더 복제
    const headerClone = headerRef.current.cloneNode(true) as HTMLElement;
    
    // 헤더 너비 조정
    headerClone.style.width = '100%';
    headerClone.style.marginBottom = '0'; // 헤더 아래 여백 제거
    headerClone.style.paddingBottom = '0'; // 헤더 아래 패딩 제거
    
    // 헤더 내 제목 텍스트 크기 조정
    const headerTitles = headerClone.querySelectorAll('h2');
    headerTitles.forEach(title => {
      (title as HTMLElement).style.fontSize = '11px';
      (title as HTMLElement).style.fontWeight = 'bold';
    });

    // 테이블 행의 텍스트 상하 가운데 정렬
    const tableRows = headerClone.querySelectorAll('tr');
    tableRows.forEach(row => {
      const cells = row.querySelectorAll('td, th');
      cells.forEach(cell => {
        (cell as HTMLElement).style.verticalAlign = 'middle';
      });
    });
    
    // 버튼 제거
    const buttons = headerClone.querySelectorAll('button');
    buttons.forEach(button => button.remove());
    
    // 날짜 정보 추가 (제목 우측에 표시)
    const titleElements = headerClone.querySelectorAll('h2');
    if (titleElements.length > 0) {
      const titleElement = titleElements[0];
      const currentDate = new Date();
      const formattedDate = `${currentDate.getFullYear()}-${String(currentDate.getMonth() + 1).padStart(2, '0')}-${String(currentDate.getDate()).padStart(2, '0')}`;
      
      // 날짜 텍스트 요소 생성
      const dateSpan = document.createElement('span');
      dateSpan.textContent = ` (${formattedDate})`;
      dateSpan.style.fontSize = '9px';
      dateSpan.style.fontWeight = 'normal';
      dateSpan.style.color = '#718096';
      dateSpan.style.marginLeft = '5px';
      
      // 제목 요소에 날짜 추가
      titleElement.appendChild(dateSpan);
    }
    
    // 헤더 내 기존 설명 텍스트 제거 (중복 방지)
    const headerDescriptions = headerClone.querySelectorAll('span.text-xs, span.text-gray-600');
    headerDescriptions.forEach(desc => {
      const parent = desc.parentElement;
      if (parent) {
        parent.removeChild(desc);
      }
    });
    
    // 헤더를 컨테이너에 추가
    container.appendChild(headerClone);
    
    // 설명 텍스트를 별도로 생성하여 헤더 다음에 직접 추가
    const descriptionDiv = document.createElement('div');
    
    // 테이블 이름에 따라 설명 텍스트 설정
    if (tableName.includes('52주 신고가')) {
      descriptionDiv.textContent = '당일 52주 신고가중 RS값이 높은 순서대로 리스트업합니다.';
    } else {
      descriptionDiv.textContent = '상대강도(RS) 기준으로 정렬된 주도 종목 리스트입니다.';
    }
    
    // 설명 텍스트 스타일 설정
    descriptionDiv.style.fontSize = '8px';
    descriptionDiv.style.color = '#718096';
    descriptionDiv.style.padding = '2px 0 4px 0'; // 패딩 축소
    descriptionDiv.style.borderBottom = '1px solid #edf2f7';
    descriptionDiv.style.marginBottom = '4px'; // 여백 축소
    descriptionDiv.style.textAlign = 'left';
    
    // 설명 텍스트를 컨테이너에 추가 (헤더와 테이블 사이)
    container.appendChild(descriptionDiv);
    
    // 테이블 복제
    const tableClone = tableRef.current.cloneNode(true) as HTMLElement;
    
    // 테이블 너비 조정
    tableClone.style.width = '100%';
    tableClone.style.marginTop = '0'; // 테이블 위 여백 제거
    
    // 테이블 내 모든 텍스트 요소 크기 조정
    const allTextElements = tableClone.querySelectorAll('th, td, span, div');
    allTextElements.forEach(el => {
      // clamp 함수를 사용하는 인라인 스타일 제거 (고정 크기로 대체)
      if ((el as HTMLElement).style.fontSize && (el as HTMLElement).style.fontSize.includes('clamp')) {
        (el as HTMLElement).style.fontSize = '';
      }
      
      // 요소 유형에 따라 적절한 폰트 크기 적용
      if (el.tagName === 'TH') {
        (el as HTMLElement).style.fontSize = '11px';
        (el as HTMLElement).style.fontWeight = 'bold';
        (el as HTMLElement).style.padding = '4px';
      } else if (el.tagName === 'TD') {
        (el as HTMLElement).style.fontSize = '10px';
        (el as HTMLElement).style.padding = '3px';
      } else if ((el as HTMLElement).classList.contains('text-xs')) {
        (el as HTMLElement).style.fontSize = '10px';
      }
    });
    
    // 모바일 환경에서 숨겨진 컬럼 처리
    const hiddenCells = tableClone.querySelectorAll('.hidden.md\\:table-cell');
    hiddenCells.forEach(cell => {
      (cell as HTMLElement).style.display = 'none';
    });
    
    // 테이블 셀 정렬 스타일 적용
    // 2개월 차트 가운데 정렬
    const chartCells = tableClone.querySelectorAll('td div.w-full.h-full.flex.items-center');
    chartCells.forEach(cell => {
      (cell as HTMLElement).style.display = 'flex';
      (cell as HTMLElement).style.justifyContent = 'center';
      (cell as HTMLElement).style.alignItems = 'center';
      (cell as HTMLElement).style.height = '100%';
    });
    
    // 20일선 이격 컬럼 가운데 정렬
    const positionCells = tableClone.querySelectorAll('td div.flex.justify-center.items-center.w-full');
    positionCells.forEach(cell => {
      (cell as HTMLElement).style.display = 'flex';
      (cell as HTMLElement).style.justifyContent = 'center';
      (cell as HTMLElement).style.alignItems = 'center';
      (cell as HTMLElement).style.height = '100%';
    });
    
    // 모든 td 요소에 수직 정렬 스타일 적용
    const allCells = tableClone.querySelectorAll('td');
    allCells.forEach(cell => {
      (cell as HTMLElement).style.verticalAlign = 'middle';
    });
    
    container.appendChild(tableClone);
    
    // 워터마크 추가 (중앙에 반투명하게 표시)
    if (mergedOptions.watermark && mergedOptions.watermark.text) {
      const watermarkContainer = document.createElement('div');
      
      // 워터마크 컨테이너 스타일 설정
      watermarkContainer.style.position = 'absolute';
      watermarkContainer.style.top = '0';
      watermarkContainer.style.left = '0';
      watermarkContainer.style.width = '100%';
      watermarkContainer.style.height = '100%';
      watermarkContainer.style.display = 'flex';
      watermarkContainer.style.justifyContent = 'center';
      watermarkContainer.style.alignItems = 'center';
      watermarkContainer.style.pointerEvents = 'none'; // 클릭 이벤트 무시
      watermarkContainer.style.zIndex = '10';
      
      // 워터마크 텍스트 요소 생성
      const watermark = document.createElement('div');
      watermark.style.opacity = String(mergedOptions.watermark.opacity || 0.1);
      watermark.style.fontSize = mergedOptions.watermark.fontSize || '24px';
      watermark.style.fontWeight = 'bold';
      watermark.style.color = mergedOptions.watermark.color || '#000000';
      watermark.style.transform = 'rotate(-30deg)'; // 비스듬히 표시
      watermark.style.whiteSpace = 'pre-line'; // 줄바꿈 허용
      watermark.style.textAlign = 'center';
      watermark.textContent = mergedOptions.watermark.text;
      
      watermarkContainer.appendChild(watermark);
      container.appendChild(watermarkContainer);
    }
    
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
      
      // 저작권 텍스트 크기 추가 조정
      footer.style.fontSize = '8px';
      footer.style.color = '#999999';
      
      footer.innerHTML = mergedOptions.copyrightText;
      container.appendChild(footer);
    }
    
    // 임시로 DOM에 추가 (스타일 계산을 위해)
    document.body.appendChild(container);
    container.style.position = 'absolute';
    container.style.left = '-9999px';
    
    // --- 텍스트 위치 조정 시작 ---
    const textElements = container.querySelectorAll('td, th, span, p, div, caption'); // 텍스트를 포함할 수 있는 주요 요소 선택
    textElements.forEach(el => {
      // HTMLElement 타입인지 확인하고 style 속성에 접근
      if (el instanceof HTMLElement) {
        el.style.position = 'relative';
        el.style.top = '-5px'; // 텍스트를 위로 5px 이동
      }
    });
    // --- 텍스트 위치 조정 끝 ---
    
    // dom-to-image-more 사용
    const dataUrl = await domtoimage.toPng(container, {
      // scale 옵션은 dom-to-image-more에서 직접 지원하지 않음
      // 필요 시 후처리로 크기 조절 필요
      bgcolor: mergedOptions.backgroundColor, // backgroundColor -> bgcolor
      width: container.scrollWidth, // 캡처 영역 너비 명시
      height: container.scrollHeight, // 캡처 영역 높이 명시
      style: {
        // 렌더링 전 스타일 강제 적용 (폰트 로딩 등)
        transform: 'scale(1)', // 스케일 초기화
        transformOrigin: 'top left',
      }
    });

    // 임시 컨테이너 제거
    document.body.removeChild(container);
    
    // 이미지를 클립보드에 복사
    const blob = await fetch(dataUrl).then(res => res.blob());
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
  } catch (error) {
    console.error('이미지 생성 실패:', error);
    alert('이미지 생성에 실패했습니다.');
  } finally {
    // 로딩 메시지 제거 (오류 발생 시에도 제거)
    if (document.body.contains(loadingToast)) {
      document.body.removeChild(loadingToast);
    }
  }
};