"use client";

// 시장 신호등 섹션
import { useEffect, useState } from 'react';
import Papa from 'papaparse';

interface SignalColors {
  red: string;
  yellow: string;
  green: string;
  inactive: string;
}

const signalColorValues: SignalColors = {
  red: '#ef4444', // Tailwind red-500
  yellow: '#fde047', // Tailwind yellow-400
  green: '#22c55e', // Tailwind green-500
  inactive: '#e5e7eb', // Tailwind gray-200
};

// 신호등 단일 표시용 컴포넌트
function SignalLight({ label, colors }: { label: string; colors: [string, string, string] }) {
  return (
    <span className="flex flex-row items-center gap-1 mr-2 md:mr-4">
      <span className="text-sm md:text-base font-medium mr-1 md:mr-2 whitespace-nowrap" style={{ color: '#ABABAB' }}>{label}</span>
      <span
        className="flex flex-row justify-center items-center bg-gray-900 border border-gray-700 rounded-xl shadow-md px-2 md:px-3 h-6 md:h-7 min-w-[60px] md:min-w-[70px]"
      >
        <span
          className="rounded-full border-2 shadow-[0_0_8px_1px_rgba(239,68,68,0.6)] mx-0.5 w-4 h-4 md:w-[18px] md:h-[18px]"
          style={{ backgroundColor: colors[0], borderColor: colors[0] + '80' }}
        />
        <span
          className="rounded-full border-2 shadow-[0_0_8px_1px_rgba(253,224,71,0.5)] mx-0.5 w-4 h-4 md:w-[18px] md:h-[18px]"
          style={{ backgroundColor: colors[1], borderColor: colors[1] + '80' }}
        />
        <span
          className="rounded-full border-2 shadow-[0_0_8px_1px_rgba(34,197,94,0.5)] mx-0.5 w-4 h-4 md:w-[18px] md:h-[18px]"
          style={{ backgroundColor: colors[2], borderColor: colors[2] + '80' }}
        />
      </span>
    </span>
  );
}

export default function MarketSignalSection() {
  const [shortTermSignal, setShortTermSignal] = useState<string | null>(null);
  const [longTermSignal, setLongTermSignal] = useState<string | null>(null);
  const [kospiChange, setKospiChange] = useState<string | null>(null);
  const [kosdaqChange, setKosdaqChange] = useState<string | null>(null);
  const [lastUpdated, setLastUpdated] = useState<string | null>(null);

  useEffect(() => {
    async function fetchMarketSignalData() {
      try {
        const response = await fetch('/requestfile/trend-following/marketsignal.csv', { cache: 'no-store' });
        const csvText = await response.text();
        
        Papa.parse(csvText, {
          header: true,
          skipEmptyLines: true,
          complete: (results) => {
            const data = results.data as Array<{[key: string]: string}>;
            if (data && data.length > 0) {
              const firstRow = data[0]; // CSV의 첫 번째 행에서 모든 데이터를 가져옵니다.
              
              setLastUpdated(firstRow.저장시간 || null);
              setShortTermSignal(firstRow.short_term_signal?.toLowerCase() || null);
              setLongTermSignal(firstRow.long_term_signal?.toLowerCase() || null);

              if (firstRow.KOSPI_등락률) {
                const kospiChangeValue = parseFloat(firstRow.KOSPI_등락률);
                const formattedChange = `${kospiChangeValue >= 0 ? '+' : ''}${kospiChangeValue.toFixed(2)}%`;
                setKospiChange(formattedChange);
              } else {
                setKospiChange(null);
              }

              if (firstRow.KOSDAQ_등락률) {
                const kosdaqChangeValue = parseFloat(firstRow.KOSDAQ_등락률);
                const formattedChange = `${kosdaqChangeValue >= 0 ? '+' : ''}${kosdaqChangeValue.toFixed(2)}%`;
                setKosdaqChange(formattedChange);
              } else {
                setKosdaqChange(null);
              }
            } else {
              // 데이터가 없거나 형식이 잘못된 경우 모든 상태를 초기화/에러 상태로 설정
              setLastUpdated(null);
              setShortTermSignal('inactive');
              setLongTermSignal('inactive');
              setKospiChange(null);
              setKosdaqChange(null);
            }
          },
          error: (error: any) => {
            console.error("Error parsing market signal CSV:", error);
            setLastUpdated(null);
            setShortTermSignal('inactive');
            setLongTermSignal('inactive');
            setKospiChange(null);
            setKosdaqChange(null);
          }
        });
      } catch (error) {
        console.error("Error fetching market signal CSV:", error);
        setLastUpdated(null);
        setShortTermSignal('inactive'); 
        setLongTermSignal('inactive');
        setKospiChange(null);
        setKosdaqChange(null);
      }
    }

    fetchMarketSignalData();
  }, []);

  const getColorBySignal = (signal: string | null): [string, string, string] => {
    switch (signal) {
      case 'red':
        return [signalColorValues.red, signalColorValues.inactive, signalColorValues.inactive];
      case 'yellow':
        return [signalColorValues.inactive, signalColorValues.yellow, signalColorValues.inactive];
      case 'green':
        return [signalColorValues.inactive, signalColorValues.inactive, signalColorValues.green];
      default:
        return [signalColorValues.inactive, signalColorValues.inactive, signalColorValues.inactive];
    }
  };

  const shortTermColors = getColorBySignal(shortTermSignal);
  const longTermColors = getColorBySignal(longTermSignal);

  return (
    <div className="bg-white rounded border border-gray-100 px-2 md:px-4 py-2 md:py-3">
      <section className="flex items-center w-full">
        <div className="flex flex-col md:flex-row md:items-center justify-between w-full">
          {/* 좌측: 시장 신호 제목, 단기/장기 신호등 */}
          <div className="flex flex-col md:flex-row items-start md:items-center gap-2">
            <div className="flex items-baseline justify-between w-full md:flex-wrap md:w-auto md:justify-start mb-2 md:mb-0 md:mr-6">
              <div className="flex items-baseline">
                <div className="font-semibold mr-2 text-base md:text-lg" style={{ color: 'var(--primary-text-color, var(--primary-text-color-fallback))' }}>
                  시장 신호
                </div>
                <div className="flex items-baseline gap-2 md:hidden">
                  {kospiChange && (
                    <span className="mr-2" style={{ fontSize: 'clamp(0.6rem, 0.6vw, 0.6rem)', color: 'var(--primary-text-color, var(--primary-text-color-fallback))' }}>
                      KOSPI{' '}
                      {kospiChange.startsWith('+') ? (
                        <span className="font-semibold text-red-500">{kospiChange}</span>
                      ) : (
                        <span className="font-semibold text-blue-500">{kospiChange}</span>
                      )}
                    </span>
                  )}
                  {kosdaqChange && (
                    <span style={{ fontSize: 'clamp(0.6rem, 0.6vw, 0.6rem)', color: 'var(--primary-text-color, var(--primary-text-color-fallback))' }}>
                      KOSDAQ{' '}
                      {kosdaqChange.startsWith('+') ? (
                        <span className="font-semibold text-red-500">{kosdaqChange}</span>
                      ) : (
                        <span className="font-semibold text-blue-500">{kosdaqChange}</span>
                      )}
                    </span>
                  )}
                </div>
              </div>
              {lastUpdated && (
                <span className="text-xs md:hidden" style={{ fontSize: 'clamp(0.6rem, 0.6vw, 0.6rem)', color: 'var(--text-muted-color, var(--text-muted-color-fallback))' }}>
                  {lastUpdated}
                </span>
              )}
            </div>
            <div className="flex flex-row items-center gap-2">
              <SignalLight label="단기" colors={shortTermColors} />
              <SignalLight label="장기" colors={longTermColors} />
            </div>
          </div>



          {/* 우측: 업데이트 시간, KOSPI/KOSDAQ 등락률 (데스크톱) */}
          <div className="hidden md:flex flex-row items-center gap-4"> 
            {lastUpdated && (
              <span className="hidden md:inline text-xs mr-2 js-remove-for-capture" style={{ fontSize: 'clamp(0.6rem, 0.6vw, 0.6rem)', color: 'var(--text-muted-color, var(--text-muted-color-fallback))' }}>
                updated {lastUpdated}
              </span>
            )}
            {kospiChange && (
              <span className="text-base" style={{ color: 'var(--primary-text-color, var(--primary-text-color-fallback))' }}>
                KOSPI{' '}
                {kospiChange.startsWith('+') ? (
                  <span className="font-semibold text-red-500">
                    {kospiChange}
                  </span>
                ) : (
                  <span className="font-semibold text-blue-500">
                    {kospiChange}
                  </span>
                )}
              </span>
            )}
            {kosdaqChange && (
              <span className="text-base ml-4" style={{ color: 'var(--primary-text-color, var(--primary-text-color-fallback))' }}> {/* KOSPI와 간격 추가 */}
                KOSDAQ{' '}
                {kosdaqChange.startsWith('+') ? (
                  <span className="font-semibold text-red-500">
                    {kosdaqChange}
                  </span>
                ) : (
                  <span className="font-semibold text-blue-500">
                    {kosdaqChange}
                  </span>
                )}
              </span>
            )}
          </div>
        </div>
      </section>
    </div>
  );
}
