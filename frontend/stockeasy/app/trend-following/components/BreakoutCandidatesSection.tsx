'use client'
// 돌파 종목 후보군 섹션 (CSV 연동함)
import { useEffect, useState } from 'react';
import Papa from 'papaparse';
import { CheckCircleIcon } from '@heroicons/react/24/solid';

// CSV 데이터 타입 정의 (부모로부터 전달받는 데이터 타입)
interface BreakoutData {
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
  '저장시간'?: string; // 저장시간 컬럼 추가
  [key: string]: string | undefined;
}

// 부모 컴포넌트로부터 받을 Props 정의
interface BreakoutCandidatesSectionProps {
  data: BreakoutData[];
  updateDate: string;
  loading: boolean;
  error: string | null;
}

export default function BreakoutCandidatesSection({ data: candidatesData, updateDate, loading, error }: BreakoutCandidatesSectionProps) {
  // 내부 상태는 더 이상 필요 없음, props로 데이터를 받음
  const candidatesToDisplay = candidatesData.slice(0, 10);

  if (loading) return <div className="text-center py-10 text-sm">돌파 후보군 로딩 중...</div>;

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
              {candidatesToDisplay.map((item: BreakoutData, idx: number) => {
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
