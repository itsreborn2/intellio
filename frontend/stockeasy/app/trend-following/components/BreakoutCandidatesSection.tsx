'use client'
// 돌파 종목 후보군 섹션 (CSV 연동)
import { useEffect, useState } from 'react';
import Papa from 'papaparse';
import { CheckCircleIcon } from '@heroicons/react/24/solid';

// CSV 데이터 타입 정의
interface WatchlistData {
  'Type'?: string;
  'Code': string;
  'Name': string;
  'Breakthrough Price': string;
  'Current Price'?: string;
  'Daily Change %'?: string;
  'Remaining %'?: string; // CSV에 있지만 테이블 표시는 미요청
  'Gap %'?: string;
  'RS'?: string;
  'MTT'?: string;
  [key: string]: string | undefined;
}

export default function BreakoutCandidatesSection() {
  const [candidates, setCandidates] = useState<WatchlistData[]>([]);
  const [loading, setLoading] = useState<boolean>(true);
  const [error, setError] = useState<string | null>(null);
  const [updateDate, setUpdateDate] = useState<string>('');

  useEffect(() => {
    async function fetchCandidates() {
      try {
        setLoading(true);
        const response = await fetch('/requestfile/trend-following/breakout.csv', { cache: 'no-store' });
        if (!response.ok) throw new Error(`CSV 로드 실패: ${response.status}`);
        
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
        
        // CSV 데이터 전처리 - 첫 줄을 제외한 나머지 줄에서 작은따옴표 문제 해결
        const lines = csvText.split('\n');
        const header = lines[0];
        const processedLines = [header];
        
        for (let i = 1; i < lines.length; i++) {
          if (lines[i].trim()) {
            // 작은따옴표로 시작하는 종목코드 처리
            const line = lines[i];
            const fixedLine = line.replace(/^'([^,]+),/, '$1,');
            processedLines.push(fixedLine);
          }
        }
        
        const processedCsvText = processedLines.join('\n');
        console.log('전처리된 CSV 데이터 일부:', processedCsvText.substring(0, 200));
        
        Papa.parse<WatchlistData>(processedCsvText, {
          header: true,
          skipEmptyLines: true,
          complete: (results) => {
            // 디버깅을 위해 파싱된 데이터의 첫 번째 항목 출력
            if (results.data.length > 0) {
              console.log('파싱된 CSV 데이터 첫 번째 항목:', results.data[0]);
              console.log('사용 가능한 컬럼명:', Object.keys(results.data[0]));
            }
            // 'Type' 컬럼이 '돌파 임박'인 데이터만 필터링
            const filteredData = results.data.filter(item => item['Type']?.trim() === '돌파 임박');
            console.log('필터링된 데이터 (Type: 돌파 임박) 개수:', filteredData.length);
            if (filteredData.length > 0) {
              console.log('필터링된 데이터 첫 번째 항목:', filteredData[0]);
            }
            setCandidates(filteredData);
            setLoading(false);
          },
          error: (err: any) => {
            console.error('CSV 파싱 오류:', err);
            setError('CSV 파싱 중 오류 발생');
            setLoading(false);
          },
        });
      } catch (err) {
        console.error('데이터 로드 오류:', err);
        setError('데이터 로드 중 오류 발생');
        setLoading(false);
      }
    }
    fetchCandidates();
  }, []);

  return (
    <section>
      <div className="flex justify-between items-center mb-2">
        <div className="font-semibold flex items-center mb-1" style={{ fontSize: '18px', color: 'var(--primary-text-color, var(--primary-text-color-fallback))' }}>돌파 임박</div>
        {updateDate && (
          <span className="text-xs mr-2" style={{ fontSize: 'clamp(0.7rem, 0.7vw, 0.7rem)', color: 'var(--text-muted-color, var(--text-muted-color-fallback))' }}>
            updated {updateDate}
          </span>
        )}
      </div>
      {loading && <div style={{ color: 'var(--text-muted-color, var(--text-muted-color-fallback))' }}>데이터를 불러오는 중입니다...</div>}
      {error && <div className="text-red-500">{error}</div>}
      {!loading && !error && (
        <div className="overflow-x-auto rounded-[6px] overflow-hidden">
          <table className="min-w-full text-sm border border-gray-200 rounded-[6px]">
            <thead className="bg-gray-100">
              <tr className="bg-gray-50">
                <th className="px-3 py-2 border-b font-medium text-center" style={{ color: 'var(--text-muted-color, var(--text-muted-color-fallback))' }}>종목코드</th>
                <th className="px-3 py-2 border-b font-medium text-left" style={{ color: 'var(--text-muted-color, var(--text-muted-color-fallback))' }}>종목명</th>
                <th className="px-3 py-2 border-b font-medium text-right" style={{ color: 'var(--text-muted-color, var(--text-muted-color-fallback))' }}>돌파 가격</th>
                <th className="px-3 py-2 border-b font-medium text-right" style={{ color: 'var(--text-muted-color, var(--text-muted-color-fallback))' }}>등락률</th>
                <th className="px-3 py-2 border-b font-medium text-center" style={{ color: 'var(--text-muted-color, var(--text-muted-color-fallback))' }}>갭</th>
                <th className="px-3 py-2 border-b font-medium text-center" style={{ color: 'var(--text-muted-color, var(--text-muted-color-fallback))' }}>RS</th>
                <th className="px-3 py-2 border-b font-medium text-center" style={{ color: 'var(--text-muted-color, var(--text-muted-color-fallback))' }}>MTT</th>
              </tr>
            </thead>
            <tbody>
              {candidates.map((item, idx) => {
                const stockCode = item['Code'] || '-';
                const stockName = item['Name'] || '-';
                const breakoutPriceValue = item['Breakthrough Price'];
                const dailyChange = item['Daily Change %'];
                const dailyChangeNumeric = dailyChange && !isNaN(Number(dailyChange)) ? Number(dailyChange) : null;
                const dailyChangeColorClass = dailyChangeNumeric === null ? '' : dailyChangeNumeric > 0 ? 'text-red-500' : dailyChangeNumeric < 0 ? 'text-blue-500' : '';
                const gapPercentValue = item['Remaining %'];
                const rsValue = item['RS'] || '-';
                const mttValue = item['MTT'] || '-';

                // 디버깅 로그 (필요시 주석 해제)
                // if (idx < 2) { // 처음 2개 항목만 로그 출력
                //   console.log(`항목 ${idx} 원본 데이터:`, item);
                //   console.log(`항목 ${idx} 테이블 표시용 값:`, {
                //     stockCode, stockName, currentPriceValue, breakoutPriceValue, dailyChange, gapPercentValue, rsValue, mttValue
                //   });
                // }

                return (
                  <tr key={idx} className={idx % 2 === 0 ? 'bg-gray-50' : 'bg-white'}>
                    <td className="px-3 py-2 border-b text-center">{stockCode}</td>
                    <td className="px-3 py-2 border-b text-left">{stockName}</td>
                    <td className="px-3 py-2 border-b text-right">
                      {breakoutPriceValue && !isNaN(Number(breakoutPriceValue)) ? Number(breakoutPriceValue).toLocaleString('ko-KR') + '원' : '-'}
                    </td>
                    <td className={`px-3 py-2 border-b text-right ${dailyChangeColorClass}`}>
                      {dailyChangeNumeric !== null ? `${dailyChangeNumeric.toFixed(2)}%` : (dailyChange || '-')}
                    </td>
                    <td className="px-3 py-2 border-b text-right">
                      {gapPercentValue && !isNaN(Number(gapPercentValue)) ? `${Number(gapPercentValue).toFixed(2)}%` : (gapPercentValue || '-')}
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
