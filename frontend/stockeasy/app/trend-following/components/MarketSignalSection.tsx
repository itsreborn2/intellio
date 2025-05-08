"use client";

// 시장 신호등 섹션 (임시)
// 시장 신호등 단일 신호 표시용 컴포넌트 (크기 18px, 텍스트와 높이 일치)
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
  yellow: '#fde047', // Tailwind yellow-400 (기존 yellow-500은 #eab308로 너무 어두움)
  green: '#22c55e', // Tailwind green-500
  inactive: '#e5e7eb', // Tailwind gray-200
};

function SignalLight({ label, colors }: { label: string; colors: [string, string, string] }) {
  return (
    <span className="flex flex-row items-center gap-1 mr-4">
      {/* 신호등 박스 */}
      <span
        className="flex flex-row justify-center items-center bg-gray-900 border border-gray-700 rounded-xl shadow-md px-3 py-1"
        style={{ height: '28px', minWidth: '70px' }}
      >
        {/* 빨간불 */}
        <span
          className="rounded-full border-2 shadow-[0_0_8px_1px_rgba(239,68,68,0.6)] mx-0.5"
          style={{ width: '18px', height: '18px', backgroundColor: colors[0], borderColor: colors[0] + '80' }}
        />
        {/* 노란불 */}
        <span
          className="rounded-full border-2 shadow-[0_0_8px_1px_rgba(253,224,71,0.5)] mx-0.5"
          style={{ width: '18px', height: '18px', backgroundColor: colors[1], borderColor: colors[1] + '80' }}
        />
        {/* 초록불 */}
        <span
          className="rounded-full border-2 shadow-[0_0_8px_1px_rgba(34,197,94,0.5)] mx-0.5"
          style={{ width: '18px', height: '18px', backgroundColor: colors[2], borderColor: colors[2] + '80' }}
        />
      </span>
      {/* 신호등 라벨 (텍스트 18px, 옅은 회색 #ABABAB) */}
      <span className="text-[18px] font-medium ml-2 whitespace-nowrap" style={{ color: '#ABABAB' }}>{label}</span>
    </span>
  );
}

// 시장 신호등 섹션 (임시)
export default function MarketSignalSection() {
  const [shortTermSignal, setShortTermSignal] = useState<string | null>(null);
  const [longTermSignal, setLongTermSignal] = useState<string | null>(null);
  const [kospiChange, setKospiChange] = useState<string | null>(null);
  const [kosdaqChange, setKosdaqChange] = useState<string | null>(null);

  useEffect(() => {
    async function fetchMarketSignalData() {
      try {
        const response = await fetch('/requestfile/trend-following/marketsignal.csv');
        const csvText = await response.text();
        
        Papa.parse(csvText, {
          header: true,
          skipEmptyLines: true,
          complete: (results) => {
            const data = results.data as Array<{[key: string]: string}>;
            if (data && data.length > 0) {
              const lastRow = data[data.length - 1];
              setShortTermSignal(lastRow.short_term_signal?.toLowerCase() || null);
              setLongTermSignal(lastRow.long_term_signal?.toLowerCase() || null);

              // KOSPI 및 KOSDAQ 등락률 처리 (마지막에서 두 번째 데이터가 가장 최신일 수 있음)
              // KOSPI_등락률과 KOSDAQ_등락률은 같은 행에 없을 수도 있으므로, 각 지표별 최신 값을 찾습니다.
              let latestKospiData = null;
              let latestKosdaqData = null;

              for (let i = data.length - 1; i >= 0; i--) {
                if (!latestKospiData && data[i].KOSPI_등락률 && data[i].종목명 === 'KOSPI') {
                  latestKospiData = data[i].KOSPI_등락률;
                }
                if (!latestKosdaqData && data[i].KOSDAQ_등락률 && data[i].종목명 === 'KOSPI') { // CSV 데이터에서 KOSDAQ 등락률도 KOSPI 행에 있음
                  latestKosdaqData = data[i].KOSDAQ_등락률;
                }
                if (latestKospiData && latestKosdaqData) break;
              }

              if (latestKospiData) {
                const kospiChangeValue = parseFloat(latestKospiData);
                setKospiChange(`${kospiChangeValue >= 0 ? '+' : ''}${kospiChangeValue.toFixed(2)}%`);
              }
              if (latestKosdaqData) {
                const kosdaqChangeValue = parseFloat(latestKosdaqData);
                setKosdaqChange(`${kosdaqChangeValue >= 0 ? '+' : ''}${kosdaqChangeValue.toFixed(2)}%`);
              }
            }
          },
        });
      } catch (error) {
        console.error("Error fetching or parsing market signal CSV:", error);
        // 에러 발생 시 기본값 또는 에러 상태 처리
        setShortTermSignal('inactive'); // 예시: 에러 시 'inactive'로 설정
        setLongTermSignal('inactive');
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
      default: // null 또는 'inactive' 등 예상치 못한 값
        return [signalColorValues.inactive, signalColorValues.inactive, signalColorValues.inactive];
    }
  };

  const shortTermColors = getColorBySignal(shortTermSignal);
  const longTermColors = getColorBySignal(longTermSignal);

  return (
    <div className="bg-white rounded border border-gray-100 px-2 md:px-4 py-1 md:py-2">
      <section className="flex items-center w-full">
        <div className="flex flex-row items-center justify-between w-full">
          <div className="flex flex-row items-center gap-2">
            <h2 className="text-lg font-semibold text-gray-700 my-2">
              시장 신호
            </h2>
            <SignalLight label="단기" colors={shortTermColors} />
            <SignalLight label="장기" colors={longTermColors} />
          </div>
          <div className="flex flex-row items-center gap-6">
            {kospiChange && (
              <span className="text-base text-gray-700">
                KOSPI{' '}
                <span className={`font-semibold ${parseFloat(kospiChange) >= 0 ? 'text-red-500' : 'text-blue-600'}`}>
                  {kospiChange}
                </span>
              </span>
            )}
            {kosdaqChange && (
              <span className="text-base text-gray-700">
                KOSDAQ{' '}
                <span className={`font-semibold ${parseFloat(kosdaqChange) >= 0 ? 'text-red-500' : 'text-blue-600'}`}>
                  {kosdaqChange}
                </span>
              </span>
            )}
          </div>
        </div>
      </section>
    </div>
  );
}
