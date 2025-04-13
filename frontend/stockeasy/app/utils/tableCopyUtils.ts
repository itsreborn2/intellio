import { toPng } from 'html-to-image';

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
    copyrightText: '', // 저작권 텍스트 제거
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
    // 임시 컨테이너 생성
    const container = document.createElement('div');
    // 디버깅을 위해 화면에 보이도록 설정 (나중에 다시 숨김 처리)
    container.style.position = 'fixed';
    container.style.top = '10px';
    container.style.left = '10px';
    container.style.zIndex = '9999';
    container.style.width = 'fit-content'; // 내용에 맞게 자동 조정
    container.style.maxWidth = '480px'; // 최대 너비 제한
    container.style.height = 'fit-content'; // 내용에 맞게 자동 조정
    container.style.backgroundColor = mergedOptions.backgroundColor || '#ffffff';
    container.style.padding = '10px';
    container.style.boxSizing = 'border-box';
    container.style.fontFamily = 'Arial, sans-serif';
    container.style.overflow = 'visible'; // 스크롤 방지
    container.style.border = '1px solid #ccc'; // 디버깅을 위한 테두리
    
    // 테이블 컨테이너 생성
    const tableContainer = document.createElement('div');
    tableContainer.style.width = 'fit-content'; // 내용에 맞게 자동 조정
    tableContainer.style.overflow = 'visible'; // 스크롤 방지
    
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
    
    // 모바일에서 숨겨지는 컬럼 제거 (.hidden.md\:table-cell 클래스를 가진 요소)
    try {
      const hiddenCells = tableClone.querySelectorAll('.hidden.md\\:table-cell');
      hiddenCells.forEach(cell => {
        if (cell.parentNode) {
          cell.parentNode.removeChild(cell);
        }
      });
      
      // 테이블 스타일 직접 적용
      tableClone.style.width = 'auto';
      tableClone.style.borderCollapse = 'collapse';
      tableClone.style.fontSize = '10px';
    } catch (error) {
      console.error('테이블 요소 처리 중 오류:', error);
    }
    
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
      } else if (el.tagName === 'TD') {
        (el as HTMLElement).style.fontSize = '10px';
      } else if ((el as HTMLElement).classList.contains('text-xs')) {
        (el as HTMLElement).style.fontSize = '10px';
      }
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
    
    // 복사된 테이블의 각 셀에 스타일 적용 (수직 정렬 및 텍스트 위치 조정)
    const clonedCells = tableClone.querySelectorAll('th, td');
    clonedCells.forEach((cell) => {
      const htmlCell = cell as HTMLElement;
      
      // 수직 정렬 스타일 적용
      htmlCell.style.verticalAlign = 'middle';
      htmlCell.style.lineHeight = '1.2';
      
      // 내부 div 요소의 수직 정렬만 적용
      const innerDivs = htmlCell.querySelectorAll('div');
      innerDivs.forEach(div => {
        (div as HTMLElement).style.alignItems = 'center';
      });
      
      // 산업 컴포넌트의 버튼 요소 제거
      // 산업 컴포넌트에 있는 버튼 요소 찾기
      if (htmlCell.textContent?.includes('산업') || htmlCell.querySelector('span.px-1.sm\\:px-2.py-0\\.5.sm\\:py-1.bg-white.text-gray-700.border.border-gray-200.shadow-sm')) {
        // 버튼 요소 찾기
        const industryButtons = htmlCell.querySelectorAll('span.px-1.sm\\:px-2.py-0\\.5.sm\\:py-1.bg-white.text-gray-700.border.border-gray-200.shadow-sm');
        
        // 버튼 요소의 스타일 제거
        industryButtons.forEach(btn => {
          (btn as HTMLElement).style.border = 'none';
          (btn as HTMLElement).style.backgroundColor = 'transparent';
          (btn as HTMLElement).style.boxShadow = 'none';
          (btn as HTMLElement).style.padding = '0';
        });
      }
      
      // 버튼 요소의 수직 정렬 및 좌측 정렬 적용
      const buttons = htmlCell.querySelectorAll('button, .flex');
      buttons.forEach(btn => {
        (btn as HTMLElement).style.alignItems = 'center';
        (btn as HTMLElement).style.justifyContent = 'flex-start';
      });
      
      // 테이블 셀 내부의 좌측 정렬 요소 처리
      const leftAlignedItems = htmlCell.querySelectorAll('.items-start, .justify-start');
      leftAlignedItems.forEach(item => {
        (item as HTMLElement).style.justifyContent = 'flex-start';
        (item as HTMLElement).style.alignItems = 'flex-start';
      });
    });

    // 종목명 컬럼 너비 조정 (예: 두 번째 컬럼, 인덱스 1)
    const stockNameColumnIndex = 1; // 실제 종목명 컬럼 인덱스로 조정하세요.

    try {
      // 헤더 셀 조정
      const headerCells = tableClone.querySelectorAll('thead th');
      if (headerCells.length > stockNameColumnIndex) {
        const headerCell = headerCells[stockNameColumnIndex] as HTMLElement;
        if (headerCell) {
          // 기존 패딩 값을 가져와서 조정하거나 고정값 설정
          headerCell.style.paddingRight = '5px'; // 오른쪽 패딩 축소
          console.log(`DEBUG: 종목명 헤더 셀[${stockNameColumnIndex}] 패딩 조정됨`);
        }
      }

      // 데이터 셀 조정
      const dataRows = tableClone.querySelectorAll('tbody tr');
      dataRows.forEach((row, rowIndex) => {
        const cells = row.querySelectorAll('td');
        if (cells.length > stockNameColumnIndex) {
          const cell = cells[stockNameColumnIndex] as HTMLElement;
          if (cell) {
            cell.style.paddingRight = '5px'; // 오른쪽 패딩 축소
            // console.log(`DEBUG: Row ${rowIndex}, 종목명 데이터 셀[${stockNameColumnIndex}] 패딩 조정됨`); // 너무 많은 로그 방지
          }
        }
      });
      console.log(`DEBUG: 총 ${dataRows.length}개 데이터 행의 종목명 컬럼 패딩 조정 완료`);
    } catch(e) {
      console.error("종목명 컬럼 너비 조정 중 오류 발생:", e);
    }

    // 임시 컨테이너 생성 (스타일 적용 및 중앙 정렬을 위해)
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
    
    // 컨테이너를 DOM에 추가 (화면에 보이도록)
    document.body.appendChild(container);

    // 렌더링 완료를 위해 약간의 지연 추가
    await new Promise(resolve => setTimeout(resolve, 100));

    try {

      // 로깅 추가: 컨테이너 크기 및 내용 확인
      console.log('DEBUG: Container dimensions before toPng:', container.offsetWidth, container.offsetHeight);
      console.log('DEBUG: Container innerHTML start:', container.innerHTML.substring(0, 500));

      // 컨테이너 크기를 내용에 맞게 조정
      container.style.width = 'fit-content';
      container.style.height = 'fit-content';
      
      // 내부 요소들의 스크롤 방지 및 스타일 직접 적용
      const allElements = container.querySelectorAll('*');
      allElements.forEach((el) => {
        if (el instanceof HTMLElement) {
          el.style.overflow = 'visible';
          
          // 테이블 셀에 직접 스타일 적용
          if (el.tagName === 'TD' || el.tagName === 'TH') {
            el.style.padding = '2px 4px';
            el.style.border = '1px solid #ddd';
          }
          
          // 버튼 스타일 적용
          if (el.tagName === 'BUTTON') {
            el.style.padding = '2px 4px';
            el.style.margin = '2px';
            el.style.fontSize = '9px';
          }
        }
      });
      
      // 충분한 지연으로 스타일 적용 및 렌더링 보장
      await new Promise(resolve => setTimeout(resolve, 500));
      
      console.log('컨테이너 크기:', container.offsetWidth, container.offsetHeight);
      console.log('컨테이너 내용 크기:', container.scrollWidth, container.scrollHeight);
      
      // 이미지 생성 전에 컨테이너가 제대로 보이는지 확인 (디버깅용)
      // 2초 대기하여 화면에 보이는 그대로 이미지 저장
      // 이 시간을 더 늘리면 이미지가 더 정확하게 저장될 수 있음
      console.log('컨테이너 렌더링을 위해 2초 대기 시작...');
      await new Promise(resolve => setTimeout(resolve, 2000));
      console.log('대기 완료, 이미지 캡처 시작');
      
      // 화면에 보이는 그대로 이미지 생성 (화면 캡처 방식)
      let dataUrl;

      try {
        // 화면에 보이는 그대로 직접 컨테이너를 캡처
        console.log('미리보기 요소 캡처 시도:', container.offsetWidth, 'x', container.offsetHeight);
        
        // html2canvas 대신 html-to-image의 toPng 사용
        // 이미 화면에 보이는 컨테이너를 그대로 캡처
        dataUrl = await toPng(container, {
          pixelRatio: 2, // 해상도 설정
          backgroundColor: '#ffffff',
          skipFonts: true, // 웹폰트 문제 해결을 위해 건너뛰기
          cacheBust: true, // 캡시 문제 해결
          quality: 1.0, // 최고 품질
          canvasWidth: container.offsetWidth * 2,
          canvasHeight: container.offsetHeight * 2,
          // 스타일 문제 해결을 위한 필터
          filter: (node) => {
            // 스크립트와 스타일 요소 제외
            return node.tagName !== 'SCRIPT';
          }
        });
        
        console.log('이미지 생성 성공:', dataUrl.substring(0, 50) + '...');
      } catch (error) {
        console.error('이미지 생성 오류:', error);
        
        // 대체 방법: 스크린샷 API 사용 시도 (브라우저에서 지원하는 경우)
        try {
          // 더 단순한 설정으로 재시도
          dataUrl = await toPng(container, {
            pixelRatio: 2,
            backgroundColor: '#ffffff',
            skipFonts: true,
            cacheBust: true,
            includeQueryParams: true,
            // 추가 옵션 제거
            style: undefined,
            width: undefined,
            height: undefined
          });
        } catch (fallbackError) {
          console.error('대체 방법도 실패:', fallbackError);
          throw new Error('이미지 생성 실패');
        }
      }

      // 데이터 URL이 없으면 오류 발생
      if (!dataUrl) {
        throw new Error('이미지 데이터 URL을 생성하지 못했습니다.');
      }
      
      // 데이터 URL을 Blob으로 변환
      const response = await fetch(dataUrl);
      const blob = await response.blob();

      // 클립보드에 복사
      await navigator.clipboard.write([
        new ClipboardItem({ 'image/png': blob })
      ]);
      
      // 임시 컨테이너 제거
      document.body.removeChild(container);
      
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
      console.error('이미지 생성 실패:', error);
      document.body.removeChild(loadingToast);
      alert(`이미지 생성에 실패했습니다: ${error instanceof Error ? error.message : String(error)}`);
    } finally {
      // 임시 컨테이너 제거 (finally 블록으로 이동하여 에러 발생 시에도 제거되도록 보장)
      if (document.body.contains(container)) {
        document.body.removeChild(container);
      }
      // 로딩 메시지 제거 (성공/실패 여부와 관계없이 항상 제거)
      if (document.body.contains(loadingToast)) {
        document.body.removeChild(loadingToast);
      }
    }
  } catch (error) {
    console.error('이미지 생성 실패:', error);
    document.body.removeChild(loadingToast);
    alert(`이미지 생성에 실패했습니다: ${error instanceof Error ? error.message : String(error)}`);
  }
};