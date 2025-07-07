"use client";

import React, { useEffect, useState, useRef } from 'react';
import Papa from 'papaparse';
import Chart2 from './MarketMonitorChart/Chart2';
import Chart3 from './MarketMonitorChart/Chart3';
import Chart4 from './MarketMonitorChart/Chart4';
import Chart5 from './MarketMonitorChart/Chart5';
import { TableCopyButton } from '@/app/components/TableCopyButton';

// CSV 데이터 타입 정의 (간단하게 정의, 필요시 구체화)
interface MarketMonitorData {
  [key: string]: any;
}

export default function MarketMonitor() {
  const [updateDate, setUpdateDate] = useState<string>('');
  const [marketData, setMarketData] = useState<MarketMonitorData[]>([]);
  const [loading, setLoading] = useState<boolean>(true);
  const [error, setError] = useState<string | null>(null);
  const headerContainerRef = useRef<HTMLDivElement>(null);
  
  // 데이터 로드 (업데이트 날짜 포함)
  useEffect(() => {
    async function loadMarketData() {
      try {
        // marketmonitor.csv 파일에서 마지막 수정 날짜 가져오기
        const cacheFilePath = '/requestfile/trend-following/marketmonitor.csv';
        
        setLoading(true);
        setError(null);
        const response = await fetch(cacheFilePath, { cache: 'no-store' });

        if (!response.ok) {
          throw new Error(`marketmonitor.csv 파일 로드 실패: ${response.status}`);
        }

        const csvText = await response.text();
        Papa.parse<MarketMonitorData>(csvText, {
          header: true,
          skipEmptyLines: true,
          complete: (results) => {
            setMarketData(results.data);
            // 저장시간으로 업데이트 날짜 설정
            if (results.data.length > 0 && results.data[0]['저장시간']) {
              const firstRowDate = results.data[0]['저장시간'];
              try {
                const dateObj = new Date(firstRowDate.replace(/-/g, '/')); // YYYY-MM-DD HH:MM:SS 형식을 Date가 인식하도록 변경
                if (!isNaN(dateObj.getTime())) {
                  const month = dateObj.getMonth() + 1;
                  const day = dateObj.getDate();
                  const hours = dateObj.getHours();
                  const minutes = dateObj.getMinutes();
                  const formattedDate = `${month.toString().padStart(2, '0')}/${day.toString().padStart(2, '0')} ${hours.toString().padStart(2, '0')}:${minutes.toString().padStart(2, '0')}`;
                  setUpdateDate(formattedDate);
                } else {
                  throw new Error('Invalid date format in 저장시간');
                }
              } catch (e) {
                console.warn(`'저장시간' (${firstRowDate}) 파싱 오류, Last-Modified 헤더 사용:`, e);
                const lastModifiedHeader = response.headers.get('Last-Modified');
                if (lastModifiedHeader) {
                  const date = new Date(lastModifiedHeader);
                  const month = date.getMonth() + 1;
                  const day = date.getDate();
                  const hours = date.getHours();
                  const minutes = date.getMinutes();
                  const formattedDate = `${month.toString().padStart(2, '0')}/${day.toString().padStart(2, '0')} ${hours.toString().padStart(2, '0')}:${minutes.toString().padStart(2, '0')}`;
                  setUpdateDate(formattedDate);
                } else {
                  const now = new Date();
                  const month = now.getMonth() + 1;
                  const day = now.getDate();
                  const hours = now.getHours();
                  const minutes = now.getMinutes();
                  const formattedDate = `${month.toString().padStart(2, '0')}/${day.toString().padStart(2, '0')} ${hours.toString().padStart(2, '0')}:${minutes.toString().padStart(2, '0')}`;
                  setUpdateDate(formattedDate);
                  console.warn(`${cacheFilePath} 파일에 '저장시간' 컬럼 또는 Last-Modified 헤더가 없습니다. 현재 시간으로 대체합니다.`);
                }
              }
            } else {
              const lastModifiedHeader = response.headers.get('Last-Modified');
              if (lastModifiedHeader) {
                const date = new Date(lastModifiedHeader);
                const month = date.getMonth() + 1;
                const day = date.getDate();
                const hours = date.getHours();
                const minutes = date.getMinutes();
                const formattedDate = `${month.toString().padStart(2, '0')}/${day.toString().padStart(2, '0')} ${hours.toString().padStart(2, '0')}:${minutes.toString().padStart(2, '0')}`;
                setUpdateDate(formattedDate);
              } else {
                const now = new Date();
                const month = now.getMonth() + 1;
                const day = now.getDate();
                const hours = now.getHours();
                const minutes = now.getMinutes();
                const formattedDate = `${month.toString().padStart(2, '0')}/${day.toString().padStart(2, '0')} ${hours.toString().padStart(2, '0')}:${minutes.toString().padStart(2, '0')}`;
                setUpdateDate(formattedDate);
                console.warn(`${cacheFilePath} 파일에 '저장시간' 컬럼 또는 Last-Modified 헤더가 없습니다. 현재 시간으로 대체합니다.`);
              }
            }
            setLoading(false);
          },
          error: (parseError: any) => {
            console.error('CSV 파싱 오류:', parseError);
            setError('CSV 데이터를 파싱하는 중 오류가 발생했습니다.');
            setLoading(false);
          },
        });
      } catch (e) {
        console.error('데이터 로드 중 오류 발생:', e instanceof Error ? e.message : e);
        setError('데이터를 불러오는 중 오류가 발생했습니다.');
        setLoading(false);
      }
    }
    loadMarketData();
  }, []);
  return (
    <div className="bg-white rounded border border-gray-100 px-2 md:px-4 py-3 md:py-4">
      <div ref={headerContainerRef} className="flex flex-col sm:flex-row justify-between items-start sm:items-center mb-3">
        <h3 className="text-base md:text-lg font-semibold mb-1 sm:mb-0" style={{ color: 'var(--primary-text-color, var(--primary-text-color-fallback))' }}>시장 지표</h3>
        {updateDate && (
          <span className="text-xs sm:mr-2" style={{ fontSize: 'clamp(0.7rem, 0.7vw, 0.7rem)', color: 'var(--text-muted-color, var(--text-muted-color-fallback))' }}>
            updated {updateDate}
          </span>
        )}
      </div>
      
      {loading && <div className="text-sm" style={{ color: 'var(--primary-text-color, var(--primary-text-color-fallback))' }}>데이터를 불러오는 중입니다...</div>}
      {error && <div className="text-red-500 text-sm">{error}</div>}
      {!loading && !error && marketData.length === 0 && (
        <div className="text-sm" style={{ color: 'var(--primary-text-color, var(--primary-text-color-fallback))' }}>표시할 데이터가 없습니다.</div>
      )}
      {!loading && !error && marketData.length > 0 && (
        <div className="space-y-6">
        {/* 두 번째 차트: KOSPI vs 20일선 하락비율 및 200일선 하락비율 */}
        <div className="bg-white rounded border border-gray-200 p-3 md:p-4 shadow-sm">
          <h3 className="text-sm font-medium text-gray-700 mb-2">KOSPI 지수와 20일선/200일선 하락비율</h3>
          <div className="h-[300px]">
            <Chart2 data={marketData} />
          </div>
        </div>
        
        {/* 세 번째 차트: KOSPI vs 52주 신고가/신저가 비율 */}
        <div className="bg-white rounded border border-gray-200 p-3 md:p-4 shadow-sm">
          <h3 className="text-sm font-medium text-gray-700 mb-2">KOSPI 지수와 52주 신고가/신저가 비율</h3>
          <div className="h-[300px]">
            <Chart3 data={marketData} />
          </div>
        </div>
        
        {/* 네 번째 차트: KOSPI vs ADR */}
        <div className="bg-white rounded border border-gray-200 p-3 md:p-4 shadow-sm">
          <h3 className="text-sm font-medium text-gray-700 mb-2">KOSPI 지수와 ADR</h3>
          <div className="h-[300px]">
            <Chart4 data={marketData} />
          </div>
        </div>
        
        {/* 다섯 번째 차트: KOSDAQ vs ADR */}
        <div className="bg-white rounded border border-gray-200 p-3 md:p-4 shadow-sm">
          <h3 className="text-sm font-medium text-gray-700 mb-2">KOSDAQ 지수와 ADR</h3>
          <div className="h-[300px]">
            <Chart5 data={marketData} />
          </div>
        </div>
        </div>
      )}
    </div>
  );
}
