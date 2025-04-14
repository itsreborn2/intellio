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
  updateDateText?: string; // updateDateText 추가
}

/**
 * 테이블을 이미지로 복사하는 유틸리티 함수
 * @param tableRef 테이블 요소에 대한 참조
 * @param headerRef 헤더 요소에 대한 참조
 * @param tableName 테이블 이름 (알림 메시지에 사용)
 * @param options 추가 옵션 (저작권 텍스트, 푸터 스타일 등)
 * @param updateDateText 테이블 컴포넌트에서 전달받은 업데이트 날짜/시간 텍스트
 */
export const copyTableAsImage = async (
  tableRef: React.RefObject<HTMLDivElement>,
  headerRef: React.RefObject<HTMLDivElement>,
  tableName: string,
  options?: CopyTableOptions,
  updateDateText?: string // 인자 추가
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
      text: '스탁이지\nby (주)인텔리오\nhttps://stockeasy.intellio.kr',
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
    container.style.maxWidth = '600px'; // 최대 너비를 늘려서 우측 잘림 방지
    container.style.height = 'fit-content'; // 내용에 맞게 자동 조정
    container.style.backgroundColor = mergedOptions.backgroundColor || '#ffffff';
    container.style.padding = '0px 20px 20px 0px'; // 좌측 패딩 제거, 우측과 하단 패딩 추가로 잘림 방지
    container.style.margin = '0px'; // 모든 마진 제거
    container.style.boxSizing = 'border-box';
    container.style.fontFamily = 'Arial, sans-serif';
    container.style.overflow = 'visible'; // 스크롤 방지
    container.style.border = 'none'; // 디버깅을 위한 테두리 제거
    container.style.paddingBottom = '20px'; // 하단 여백 추가로 이미지 잘림 방지
    container.style.paddingLeft = '0px'; // 좌측 여백 제거로 테이블 시작점에 맞춤
    
    // 테이블 컨테이너 생성
    const tableContainer = document.createElement('div');
    tableContainer.style.width = 'fit-content'; // 내용에 맞게 자동 조정
    tableContainer.style.overflow = 'visible'; // 스크롤 방지
    tableContainer.style.padding = '0px'; // 테이블 컨테이너 패딩 제거
    tableContainer.style.margin = '0px'; // 테이블 컨테이너 마진 제거
    
    // 헤더 복제
    const headerClone = headerRef.current.cloneNode(true) as HTMLElement;
    
    // 헤더 너비 조정
    headerClone.style.width = '100%';
    headerClone.style.marginBottom = '0'; // 헤더 아래 여백 제거
    headerClone.style.paddingBottom = '0'; // 헤더 아래 패딩 제거
    headerClone.style.paddingRight = '20px'; // 우측 여백 추가로 잘림 방지
    
    // 헤더 내 제목 텍스트 크기 및 중앙 정렬
    const headerTitles = headerClone.querySelectorAll('h2');
    headerTitles.forEach(title => {
      (title as HTMLElement).style.fontSize = '11px';
      (title as HTMLElement).style.textAlign = 'center'; // 헤더 텍스트 중앙 정렬
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
    
    // 업데이트 날짜 텍스트 추가 (updateDateText가 있을 경우)
    if (updateDateText) {
      const titleElements = headerClone.querySelectorAll('h2');
      if (titleElements.length > 0) {
        const titleElement = titleElements[0];
        const dateSpan = document.createElement('span');
        dateSpan.textContent = ` (${updateDateText})`;
        dateSpan.style.fontSize = '9px';
        dateSpan.style.fontWeight = 'normal';
        dateSpan.style.color = '#718096';
        dateSpan.style.marginLeft = '5px';
        titleElement.appendChild(dateSpan);
      }
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
      tableClone.style.minWidth = '100%'; // 테이블이 컨테이너 너비를 채우도록
      tableClone.style.borderCollapse = 'collapse'; // 테두리 겹침 제거
      tableClone.style.fontSize = '10px';
    } catch (error) {
      console.error('테이블 요소 처리 중 오류:', error);
    }
    
    // 포지션 셀 처리 함수 - try-catch 블록 외부로 이동
    const processPositionCell = (cell: HTMLTableCellElement) => {
      try {
        // 셀 내용 저장
        const cellText = cell.textContent || '';
        
        // 모든 버튼 요소 명시적 제거
        const buttons = cell.querySelectorAll('button, .btn, [class*="button"], [class*="badge"]');
        buttons.forEach(button => button.remove());
        
        // 남은 모든 자식 요소 제거
        while (cell.firstChild) {
          cell.removeChild(cell.firstChild);
        }
        
        // 새 텍스트 노드 추가
        cell.appendChild(document.createTextNode(cellText.trim()));
        
        // 스타일 적용
        cell.style.textAlign = 'center';
        cell.style.verticalAlign = 'middle';
        cell.style.backgroundColor = 'transparent';
        cell.style.padding = '4px';
        
        // '유지'가 포함된 경우만 초록색 텍스트 처리, 그 외에는 기본 색상(검은색) 사용
        if (cellText.includes('유지')) {
          cell.style.color = 'green'; // 초록색
        } else {
          cell.style.color = '#000000'; // 기본 검은색
        }
        
        cell.style.border = '1px solid #e2e8f0'; // 테이블 셀 테두리 유지
        
        // 모든 기존 클래스 제거 및 기본 클래스만 적용
        cell.className = 'text-center';
      } catch (cellError) {
        console.error("Error processing individual position cell:", cellError);
      }
    };
    
    // '포지션' 컬럼 처리 로직 추가
    try {
      // 1. 헤더를 기반으로 '포지션'과 '등락율' 컬럼 인덱스 찾기
      const headers = Array.from(tableClone.querySelectorAll('thead th, thead td'));
      let positionColumnIndices: number[] = [];
      let changeRateColumnIndices: number[] = [];
      
      headers.forEach((header, index) => {
        const headerText = header.textContent?.trim() || '';
        if (headerText === '포지션') {
          positionColumnIndices.push(index);
        }
        if (headerText === '등락율') {
          changeRateColumnIndices.push(index);
        }
      });
      
      // 2. 모든 테이블 행 처리
      const rows = tableClone.querySelectorAll('tbody tr');
      rows.forEach(row => {
        const rowElement = row as HTMLTableRowElement;
        
        // 3. 인덱스 기반으로 '포지션' 셀 처리
        for (const index of positionColumnIndices) {
          if (index < rowElement.cells.length) {
            processPositionCell(rowElement.cells[index]);
          }
        }
        
        // '등락율' 셀 처리 - 셀 내용 완전히 재구성
        for (const index of changeRateColumnIndices) {
          if (index < rowElement.cells.length) {
            const cell = rowElement.cells[index];
            
            // 셀 내용 저장 및 텍스트 색상 확인
            const cellText = cell.textContent || '';
            let textColor = 'black';
            
            // 양수/음수 확인하여 색상 결정
            if (cellText.includes('+') || cellText.match(/[1-9][0-9]*\.[0-9]+%/) || cellText.match(/[1-9][0-9]*%/)) {
              textColor = 'red';
            } else if (cellText.includes('-')) {
              textColor = 'blue';
            }
            
            // 모든 자식 요소 제거
            while (cell.firstChild) {
              cell.removeChild(cell.firstChild);
            }
            
            // 새 텍스트 노드 추가
            cell.appendChild(document.createTextNode(cellText.trim()));
            
            // 스타일 완전히 재설정
            cell.style.textAlign = 'center';
            cell.style.verticalAlign = 'middle';
            cell.style.color = textColor;
            cell.style.padding = '4px';
            
            // 클래스 완전히 재설정
            cell.className = 'text-center tabular-nums';
          }
        }
        
        // 4. 내용 기반으로 '포지션' 셀 처리 (추가 안전장치)
        for (let i = 0; i < rowElement.cells.length; i++) {
          const cell = rowElement.cells[i];
          const cellText = cell.textContent || '';
          
          // '유지' 또는 '이탈' 텍스트를 포함하는 셀 처리
          if (cellText.includes('유지') || cellText.includes('이탈')) {
            processPositionCell(cell);
          }
          
          // 셀 내부에 버튼 요소가 있는지 확인하고 처리
          const buttons = cell.querySelectorAll('button, .btn, [class*="button"], [class*="badge"]');
          if (buttons.length > 0) {
            processPositionCell(cell);
          }
        }
      });
      
      // 5. 헤더 셀도 가운데 정렬
      positionColumnIndices.forEach(index => {
        if (index < headers.length) {
          const header = headers[index] as HTMLElement;
          header.style.textAlign = 'center';
        }
      });
      
      // '등락율' 헤더 셀도 가운데 정렬
      changeRateColumnIndices.forEach(index => {
        if (index < headers.length) {
          const header = headers[index] as HTMLElement;
          header.style.textAlign = 'center';
        }
      });
      
      // 6. 추가 안전장치: 모든 테이블 셀을 검사하여 퍼센트 값이 포함된 셀을 가운데 정렬 ('산업' 컬럼 제외)
      const allCells = tableClone.querySelectorAll('td');
      
      // 테이블 헤더 검사하여 '산업' 컬럼 인덱스 확인
      const tableHeaders = tableClone.querySelectorAll('thead th, thead td');
      let industryColumnIndex = -1;
      
      tableHeaders.forEach((header, index) => {
        const headerText = header.textContent?.trim() || '';
        if (headerText === '산업' || headerText === '업종') {
          industryColumnIndex = index;
        }
      });
      
      allCells.forEach((cell, index) => {
        // 셀의 열 인덱스 찾기 (행에서의 위치)
        let cellColumnIndex = 0;
        let currentCell = cell;
        while (currentCell.previousElementSibling) {
          currentCell = currentCell.previousElementSibling as HTMLTableCellElement;
          cellColumnIndex++;
        }
        
        // '산업' 컬럼이면 처리하지 않음
        if (industryColumnIndex !== -1 && cellColumnIndex === industryColumnIndex) {
          return; // 산업 컬럼은 건너뛼
        }
        
        // 첫 번째 컬럼이거나 텍스트로 산업 컬럼으로 판단되는 경우 처리하지 않음
        if (cellColumnIndex === 0 || cell.textContent?.includes('산업') || cell.textContent?.includes('반도체') || 
            cell.textContent?.includes('은행') || cell.textContent?.includes('자동차') || 
            cell.textContent?.includes('바이오') || cell.textContent?.includes('인터넷')) {
          return; // 산업 컬럼으로 판단되는 경우 건너뛼
        }
        
        const cellText = cell.textContent || '';
        
        // 퍼센트 값이 포함된 셀이나 '등락율' 컬럼의 셀인지 확인
        if (cellText.includes('%') || 
            (cell.previousElementSibling && 
             cell.previousElementSibling.textContent && 
             cell.previousElementSibling.textContent.includes('종목명'))) {
          
          // 강제 가운데 정렬 적용
          cell.style.cssText += 'text-align: center !important; vertical-align: middle !important;';
          
          // 텍스트 색상 처리
          let textColor = 'black';
          if (cellText.includes('+') || (cellText.match(/[1-9][0-9]*\.?[0-9]*%/) && !cellText.includes('-'))) {
            textColor = 'red';
          } else if (cellText.includes('-')) {
            textColor = 'blue';
          }
          
          // 셀 내용 재구성 (선택적)
          if (cellText.match(/[+-]?[0-9]+\.?[0-9]*%/)) {
            // 모든 자식 요소 제거
            while (cell.firstChild) {
              cell.removeChild(cell.firstChild);
            }
            
            // 새 텍스트 노드 추가
            const textNode = document.createTextNode(cellText.trim());
            cell.appendChild(textNode);
            
            // 스타일 적용
            cell.style.color = textColor;
          }
        }
      });
      
    } catch (error) {
      console.error("Error processing '포지션' column for image copy:", error);
      // 오류 발생 시에도 이미지 생성은 계속 시도할 수 있도록 처리
    }
    
    // 테이블 너비 고정 및 레이아웃 고정
    tableClone.style.tableLayout = 'fixed'; // 고정 레이아웃 사용
    tableClone.style.width = '100%'; // 전체 너비 사용
    
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
    
    // 테이블 헤더 셀 중앙 정렬
    const headerCells = tableClone.querySelectorAll('thead tr th');
    headerCells.forEach(cell => {
      (cell as HTMLElement).style.textAlign = 'center !important'; // 헤더 셀 텍스트 중앙 정렬 (우선순위 높임)
      (cell as HTMLElement).style.display = 'table-cell';
      (cell as HTMLElement).style.width = 'auto';
      (cell as HTMLElement).style.cssText += 'text-align: center !important; justify-content: center !important; align-items: center !important;'; // 추가적인 중앙 정렬 속성
      // 내부 요소에도 중앙 정렬 적용
      const innerElements = cell.querySelectorAll('*');
      innerElements.forEach(el => {
        (el as HTMLElement).style.textAlign = 'center !important';
        (el as HTMLElement).style.display = 'inline-block';
      });
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
      try {
        console.log('클립보드에 이미지 쓰기 시도');
        await navigator.clipboard.write([
          new ClipboardItem({ 'image/png': blob })
        ]);
        console.log('클립보드에 이미지 쓰기 성공');
      } catch (err) {
        console.error('클립보드 쓰기 오류:', err);
        throw new Error(`클립보드 쓰기 실패: ${(err as Error).message}`);
      }
      
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