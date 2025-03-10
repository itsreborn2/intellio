'use client'

import { Suspense, useState, useEffect, useMemo } from 'react'
import Select from 'react-select'
import Papa from 'papaparse'

// 종목 타입 정의
interface StockOption {
  value: string;
  label: string;
}

// 컨텐츠 컴포넌트
function AIChatAreaContent() {
  // 종목 리스트 상태
  const [stockOptions, setStockOptions] = useState<StockOption[]>([]);
  const [selectedStock, setSelectedStock] = useState<StockOption | null>(null);
  const [isLoading, setIsLoading] = useState<boolean>(false);
  const [inputMessage, setInputMessage] = useState<string>('');
  const [isMounted, setIsMounted] = useState<boolean>(false); // 클라이언트 사이드 렌더링 확인용 상태
  const [error, setError] = useState<string | null>(null); // 오류 메시지 상태 추가
  const [lastFetchTime, setLastFetchTime] = useState<number>(0);
  const [cachedStockData, setCachedStockData] = useState<StockOption[]>([]);
  const CACHE_DURATION = 3600000; // 캐시 유효 시간 (1시간 = 3600000ms)

  // 클라이언트 사이드 렌더링 확인
  useEffect(() => {
    setIsMounted(true);
  }, []);

  // CSV 파일에서 종목 리스트 가져오기
  useEffect(() => {
    // 클라이언트 사이드에서만 실행
    if (!isMounted) return;

    const fetchStockList = async () => {
      try {
        // 캐시가 유효한지 확인 (캐시된 데이터가 있고, 캐시 유효 시간이 지나지 않았는지)
        const currentTime = Date.now();
        if (cachedStockData.length > 0 && (currentTime - lastFetchTime) < CACHE_DURATION) {
          console.log('캐시된 종목 데이터 사용:', cachedStockData.length);
          setStockOptions(cachedStockData);
          return;
        }

        setIsLoading(true);
        setError(null); // 요청 시작 시 오류 상태 초기화
        
        // 구글 드라이브 파일 ID
        const fileId = '1idVB5kIo0d6dChvOyWE7OvWr-eZ1cbpB';
        
        // API 라우트를 통해 구글 드라이브에서 종목 리스트 가져오기
        const response = await fetch('/api/stocks', {
          method: 'POST',
          headers: {
            'Content-Type': 'application/json',
          },
          body: JSON.stringify({ fileId }),
        });
        
        if (!response.ok) {
          throw new Error(`API 응답 오류: ${response.status}`);
        }
        
        // CSV 파일 내용 가져오기
        const csvContent = await response.text();
        
        // CSV 파싱
        const parsedData = Papa.parse(csvContent, {
          header: true,
          skipEmptyLines: true
        });
        
        console.log('파싱된 데이터 샘플:', parsedData.data.slice(0, 3));
        
        // 중복 제거를 위한 Set 생성
        const uniqueStocks = new Set();
        
        // 종목 데이터 추출 (종목명(종목코드) 형식으로 변경)
        const stockData = parsedData.data
          .filter((row: any) => row.종목명 && row.종목코드) // 종목명과 종목코드가 있는 행만 필터링
          .filter((row: any) => {
            // 중복 제거 (같은 종목코드는 한 번만 포함)
            if (uniqueStocks.has(row.종목코드)) {
              return false;
            }
            uniqueStocks.add(row.종목코드);
            return true;
          })
          .map((row: any) => ({
            value: row.종목코드, // 값은 종목코드로 설정
            label: `${row.종목명}(${row.종목코드})` // 라벨은 종목명(종목코드)로 설정
          }));
        
        if (stockData.length > 0) {
          console.log(`종목 데이터 ${stockData.length}개 로드 완료`);
          setStockOptions(stockData);
          
          // 캐시 업데이트
          setCachedStockData(stockData);
          setLastFetchTime(currentTime);
          
          // 로컬 스토리지에도 캐싱 (페이지 새로고침 시에도 유지)
          try {
            localStorage.setItem('cachedStockData', JSON.stringify(stockData));
            localStorage.setItem('lastFetchTime', currentTime.toString());
          } catch (storageError) {
            console.warn('로컬 스토리지 저장 실패:', storageError);
          }
        } else {
          const errorMsg = '유효한 종목 데이터를 받지 못했습니다.';
          console.error(errorMsg);
          setError(errorMsg);
        }
        
        setIsLoading(false);
      } catch (error) {
        const errorMsg = error instanceof Error ? error.message : '종목 리스트를 가져오는 중 오류가 발생했습니다.';
        console.error('종목 리스트 가져오기 오류:', error);
        setError(errorMsg);
        setIsLoading(false);
      }
    };

    // 로컬 스토리지에서 캐시된 데이터 불러오기 시도
    try {
      const cachedDataStr = localStorage.getItem('cachedStockData');
      const cachedTimeStr = localStorage.getItem('lastFetchTime');
      
      if (cachedDataStr && cachedTimeStr) {
        const cachedData = JSON.parse(cachedDataStr);
        const cachedTime = parseInt(cachedTimeStr, 10);
        
        if (Array.isArray(cachedData) && cachedData.length > 0) {
          console.log('로컬 스토리지에서 캐시된 종목 데이터 불러옴:', cachedData.length);
          setCachedStockData(cachedData);
          setLastFetchTime(cachedTime);
          
          // 캐시가 유효한지 확인
          const currentTime = Date.now();
          if ((currentTime - cachedTime) < CACHE_DURATION) {
            console.log('유효한 캐시 사용');
            setStockOptions(cachedData);
            setIsLoading(false);
            return;
          } else {
            console.log('캐시 만료됨, 새로운 데이터 가져오기');
          }
        }
      }
    } catch (storageError) {
      console.warn('로컬 스토리지 읽기 실패:', storageError);
    }

    fetchStockList();
  }, [isMounted]); // 의존성 배열에서 cachedStockData와 lastFetchTime 제거

  // 메시지 전송 핸들러 (나중에 구현)
  const handleSendMessage = () => {
    if (!inputMessage.trim()) return;
    
    // 선택된 종목과 메시지 처리 로직 (나중에 구현)
    console.log('선택된 종목:', selectedStock?.value);
    console.log('메시지:', inputMessage);
    
    // 메시지 전송 후 입력 필드 초기화
    setInputMessage('');
  };

  // 종목 선택 변경 핸들러
  const handleStockChange = (option: any) => {
    setSelectedStock(option as StockOption);
    console.log('선택된 종목:', option);
  };

  // Select 컴포넌트 스타일 메모이제이션
  const selectStyles = useMemo(() => ({
    control: (baseStyles: any) => ({
      ...baseStyles,
      minHeight: '2.475rem',
      height: '2.475rem',
      textAlign: 'center',
      borderColor: error ? 'red' : '#ccc',
      borderRadius: '4px',
      boxShadow: 'none', // 포커스 시 그림자 제거
      '&:hover': {
        borderColor: '#aaa' // 호버 시 테두리 색상
      }
    }),
    placeholder: (baseStyles: any) => ({
      ...baseStyles,
      textAlign: 'center',
      color: error ? 'red' : '#757575', // 플레이스홀더 색상 통일
      overflow: 'hidden',
      textOverflow: 'ellipsis',
      whiteSpace: 'nowrap'
    }),
    menuPortal: (base: any) => ({ ...base, zIndex: 9999 }),
    menu: (base: any) => ({
      ...base,
      maxHeight: '300px', // 메뉴 최대 높이 증가
      marginTop: '4px', // 메뉴와 컨트롤 사이 간격
      borderRadius: '4px' // 메뉴 모서리 라운드 처리
    }),
    menuList: (base: any) => ({
      ...base,
      maxHeight: '300px', // 메뉴 리스트 최대 높이 증가
      overflowY: 'auto',
      '&::-webkit-scrollbar': {
        width: '6px'
      },
      '&::-webkit-scrollbar-thumb': {
        backgroundColor: '#c1c1c1',
        borderRadius: '3px'
      }
    }),
    option: (base: any, state: any) => ({
      ...base,
      backgroundColor: state.isFocused ? '#e0e0e0' : 'transparent', // 기본 배경색을 투명으로 설정
      color: 'black',
      fontSize: '0.81rem', // 기존 0.9rem에서 10% 줄임
      padding: '6px 8px', // 패딩 최적화
      cursor: 'pointer', // 커서 스타일 추가
      transition: 'none', // 트랜지션 효과 제거하여 즉시 반응하도록 함
      userSelect: 'none', // 텍스트 선택 방지
      overflow: 'hidden',
      textOverflow: 'ellipsis',
      whiteSpace: 'nowrap',
      ':active': {
        backgroundColor: '#d0d0d0'
      },
      ':hover': {
        backgroundColor: '#e0e0e0'
      },
      // 이전 선택 항목의 스타일이 남아있는 문제 해결
      '&:not(:hover)': {
        backgroundColor: state.isFocused ? '#e0e0e0' : 'transparent'
      }
    }),
    singleValue: (base: any) => ({
      ...base,
      fontSize: '0.81rem', // 선택된 값의 폰트 사이즈도 동일하게 줄임
      overflow: 'hidden',
      textOverflow: 'ellipsis',
      whiteSpace: 'nowrap'
    }),
    valueContainer: (base: any) => ({
      ...base,
      padding: '0 8px', // 패딩 조정
      overflow: 'hidden'
    }),
    input: (base: any) => ({
      ...base,
      margin: 0,
      padding: 0
    })
  }), [error]);

  // 최적화된 Select 컴포넌트 옵션
  const selectProps = useMemo(() => ({
    value: selectedStock,
    onChange: handleStockChange,
    options: stockOptions,
    isLoading: isLoading,
    placeholder: error ? "오류 발생" : "종목 선택",
    isClearable: false, // X 표시 제거
    isSearchable: true,
    classNamePrefix: "stock-select",
    menuPortalTarget: typeof document !== 'undefined' ? document.body : null,
    maxMenuHeight: 300,
    pageSize: 10, // 한 번에 표시할 옵션 수 더 감소 (성능 향상)
    noOptionsMessage: () => "종목이 없습니다",
    loadingMessage: () => "종목 로딩 중...",
    blurInputOnSelect: true,
    closeMenuOnSelect: true,
    isOptionDisabled: () => isLoading,
    components: {
      IndicatorSeparator: () => null, // 구분선 제거
      // 커스텀 옵션 컴포넌트 추가
      Option: ({ children, ...props }: any) => (
        <div
          {...props.innerProps}
          style={{
            padding: '6px 8px',
            cursor: 'pointer',
            backgroundColor: props.isFocused ? '#e0e0e0' : 'transparent',
            fontSize: '0.81rem'
          }}
          onMouseEnter={(e) => {
            // 모든 옵션 요소의 배경색 초기화
            const options = document.querySelectorAll('.stock-select__option');
            options.forEach((opt) => {
              (opt as HTMLElement).style.backgroundColor = 'transparent';
            });
            // 현재 요소의 배경색 설정
            e.currentTarget.style.backgroundColor = '#e0e0e0';
          }}
        >
          {children}
        </div>
      )
    }
  }), [selectedStock, stockOptions, isLoading, error, handleStockChange]);

  return (
    <div className="ai-chat-area">
      {/* 입력 영역 컨테이너 - 사이드바 영역을 침범하지 않도록 최대 너비 설정 */}
      <div className="input-area" style={{ 
        display: 'flex', 
        alignItems: 'flex-start',
        width: '100%', // 전체 너비 사용
        paddingLeft: '65px', // 사이드바 너비(59px)보다 약간 더 여백 추가
        boxSizing: 'border-box' // 패딩을 포함한 너비 계산
      }}> 
        <div className="stock-selector" style={{ 
          width: 'auto', 
          minWidth: '144px', 
          maxWidth: '216px', 
          marginRight: '4px', 
          position: 'relative', 
          marginTop: '5px',
          overflow: 'visible' // 드롭다운이 컨테이너 밖으로 표시될 수 있도록 변경
        }}> 
          {isMounted ? (
            <>
              <Select
                {...selectProps}
                styles={selectStyles}
                className="stock-select-container" 
              />
              {error && (
                <div style={{ 
                  color: 'red', 
                  fontSize: '0.75rem', 
                  position: 'absolute', 
                  width: '200px',
                  backgroundColor: 'white',
                  border: '1px solid red',
                  padding: '4px',
                  zIndex: 1000,
                  borderRadius: '4px',
                  top: '100%',
                  left: 0
                }}>
                  {error}
                </div>
              )}
              {isLoading && !error && (
                <div style={{ 
                  position: 'absolute', 
                  right: '10px', 
                  top: '50%', 
                  transform: 'translateY(-50%)', 
                  color: '#666',
                  fontSize: '0.75rem'
                }}>
                  로딩 중...
                </div>
              )}
            </>
          ) : (
            // 서버 사이드 렌더링 시 보여줄 대체 UI
            <div style={{ 
              height: '2.475rem', 
              border: '1px solid #ccc', 
              borderRadius: '4px', 
              display: 'flex', 
              alignItems: 'center', 
              justifyContent: 'center',
              backgroundColor: '#fff',
              padding: '0 8px',
              overflow: 'hidden',
              textOverflow: 'ellipsis',
              whiteSpace: 'nowrap'
            }}>
              종목 선택
            </div>
          )}
        </div>
        <div className="chat-input" style={{ 
          flex: 1, 
          marginRight: '4px', 
          marginTop: '5px',
          maxWidth: 'calc(100% - 170px)' // 종목 선택 박스 너비를 고려하여 최대 너비 설정
        }}> 
          <input 
            type="text" 
            placeholder="메세지를 입력하세요" 
            style={{ 
              width: '100%', // 부모 컨테이너의 너비에 맞춤
              height: '2.475rem',
              border: '1px solid #ccc',
              borderRadius: '4px',
              padding: '0 8px',
              fontSize: '0.81rem',
              outline: 'none', // 포커스 시 기본 아웃라인 제거
              boxSizing: 'border-box' // 패딩을 포함한 너비 계산
            }} 
            className="chat-input-field"
            value={inputMessage}
            onChange={(e) => setInputMessage(e.target.value)}
            onKeyPress={(e) => e.key === 'Enter' && handleSendMessage()}
          /> 
        </div>
      </div>
      {/* AI 채팅 영역 */}
    </div>
  );
}

// 메인 컴포넌트
export default function AIChatArea() {
  return (
    <Suspense fallback={<div className="ai-chat-area animate-pulse">
      <div className="h-10 bg-gray-200 rounded"></div>
    </div>}>
      <AIChatAreaContent />
    </Suspense>
  )
}
