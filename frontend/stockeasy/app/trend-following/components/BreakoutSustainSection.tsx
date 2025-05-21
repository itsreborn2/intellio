'use client';

import { useEffect, useState } from 'react';
import Papa from 'papaparse';
import { ArrowTrendingUpIcon, CheckCircleIcon } from '@heroicons/react/24/solid';

// CSV 데이터 타입 정의
interface BreakoutData {
  'Type'?: string;
  'Code': string;
  'Name': string;
  'Breakthrough Price': string;
  'Current Price'?: string;
  'Daily Change %'?: string;
  'Remaining %'?: string;
  'Gap %'?: string;
  'RS'?: string;
  'MTT'?: string;
  [key: string]: string | undefined;
}

// 돌파 지속 섹션
export default function BreakoutSustainSection() {
  // 데이터 상태 관리
  const [breakoutData, setBreakoutData] = useState<BreakoutData[]>([]);
  const [loading, setLoading] = useState<boolean>(true);
  const [error, setError] = useState<string | null>(null);
  const [updateDate, setUpdateDate] = useState<string>('');

  // CSV 파일 가져오기
  useEffect(() => {
    async function fetchData() {
      try {
        setLoading(true);
        
        // CSV 파일 로드 및 파싱
        const response = await fetch('/requestfile/trend-following/breakout.csv', { cache: 'no-store' });
        if (!response.ok) {
          throw new Error(`CSV 파일 로드 실패: ${response.status}`);
        }
        
        // 업데이트 날짜 처리
        const lastModified = response.headers.get('Last-Modified');
        if (lastModified) {
          const date = new Date(lastModified);
          const month = date.getMonth() + 1;
          const day = date.getDate();
          const hours = date.getHours();
          const minutes = date.getMinutes();
          const formattedDate = `${month}/${day.toString().padStart(2, '0')} ${hours.toString().padStart(2, '0')}:${minutes.toString().padStart(2, '0')}`;
          setUpdateDate(formattedDate);
        }
        
        const csvText = await response.text();
        Papa.parse<BreakoutData>(csvText, {
          header: true,
          skipEmptyLines: true,
          complete: (results) => {
            const sustainData = results.data.filter(row => row.Type === '돌파 지속');
            setBreakoutData(sustainData);
            setLoading(false);
          },
          error: (err: any) => {
            console.error('CSV 파싱 오류:', err);
            setError('CSV 데이터를 파싱하는 중 오류가 발생했습니다.');
            setLoading(false);
          },
        });
      } catch (err) {
        console.error('데이터 로드 오류:', err);
        setError('데이터를 불러오는 중 오류가 발생했습니다.');
        setLoading(false);
      }
    }
    
    fetchData();
  }, []);

  // 가격 포맷팅 함수
  const formatPrice = (price: string) => {
    if (!price) return '';
    return Number(price).toLocaleString('ko-KR');
  };

  return (
    <section>
      {/* 제목과 업데이트 시간 */}
      <div className="flex justify-between items-center mb-2">
        <div className="font-semibold flex items-center mb-1" style={{ fontSize: '18px', color: 'var(--primary-text-color, var(--primary-text-color-fallback))' }}>
          <span>돌파 성공</span>
          <ArrowTrendingUpIcon className="w-5 h-5 ml-1 text-red-600" />
        </div>
        {updateDate && (
          <span className="text-xs mr-2" style={{ fontSize: 'clamp(0.7rem, 0.7vw, 0.7rem)', color: 'var(--text-muted-color, var(--text-muted-color-fallback))' }}>
            updated {updateDate}
          </span>
        )}
      </div>
      
      {/* 로딩 상태 표시 */}
      {loading && <div className="text-sm" style={{ color: 'var(--primary-text-color, var(--primary-text-color-fallback))' }}>데이터를 불러오는 중입니다...</div>}
      
      {/* 에러 메시지 표시 */}
      {error && <div className="text-red-500 text-sm">{error}</div>}
      
      {/* 데이터가 없을 경우 */}
      {!loading && !error && breakoutData.length === 0 && (
        <div className="text-sm" style={{ color: 'var(--primary-text-color, var(--primary-text-color-fallback))' }}>표시할 데이터가 없습니다.</div>
      )}
      
      {/* 데이터 표시 - 테이블 형식으로 변경 */}
      {!loading && !error && breakoutData.length > 0 && (
        <div className="overflow-x-auto rounded-[6px] overflow-hidden">
          <table className="min-w-full text-sm border border-gray-200 rounded-[6px]">
            <thead className="bg-gray-100">
              <tr className="bg-gray-50">
                <th className="px-3 py-2 border-b font-medium text-center" style={{ color: 'var(--text-muted-color, var(--text-muted-color-fallback))' }}>종목코드</th>
                <th className="px-3 py-2 border-b font-medium text-left" style={{ color: 'var(--text-muted-color, var(--text-muted-color-fallback))' }}>종목명</th>
                <th className="px-3 py-2 border-b font-medium text-right" style={{ color: 'var(--text-muted-color, var(--text-muted-color-fallback))' }}>돌파 가격</th>
                <th className="px-3 py-2 border-b font-medium text-right" style={{ color: 'var(--text-muted-color, var(--text-muted-color-fallback))' }}>등락률</th>
                <th className="px-3 py-2 border-b font-medium text-center" style={{ color: 'var(--text-muted-color, var(--text-muted-color-fallback))' }}>RS</th>
                <th className="px-3 py-2 border-b font-medium text-center" style={{ color: 'var(--text-muted-color, var(--text-muted-color-fallback))' }}>MTT</th>
              </tr>
            </thead>
            <tbody>
              {breakoutData.map((item, index) => {
                const rsValue = item['RS'] || '-';
                const mttValue = item['MTT'] || '-';
                const dailyChange = item['Daily Change %'];
                const dailyChangeNumeric = dailyChange && !isNaN(parseFloat(dailyChange)) ? parseFloat(dailyChange) : null;
                const dailyChangeColorClass = dailyChangeNumeric === null ? '' : dailyChangeNumeric > 0 ? 'text-red-500' : dailyChangeNumeric < 0 ? 'text-blue-500' : '';
                
                return (
                  <tr key={index} className={index % 2 === 0 ? 'bg-gray-50' : 'bg-white'}>
                    <td className="px-3 py-2 border-b text-center">{item.Code}</td>
                    <td className="px-3 py-2 border-b text-left">{item.Name}</td>
                    <td className="px-3 py-2 border-b text-right">{item['Breakthrough Price'] ? formatPrice(item['Breakthrough Price']) + '원' : '-'}</td>
                    <td className={`px-3 py-2 border-b text-right ${dailyChangeColorClass}`}>
                      {dailyChangeNumeric !== null ? `${dailyChangeNumeric.toFixed(2)}%` : '-'}
                    </td>
                    <td className="px-3 py-2 border-b text-center">{rsValue}</td>
                    <td className="px-3 py-2 border-b text-center">
                      {mttValue && mttValue !== '0' ? (
                        <CheckCircleIcon className="h-5 w-5 text-green-500 mx-auto" />
                      ) : null}
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      )}
    </section>
  );
}
