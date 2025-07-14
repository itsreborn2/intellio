'use client';

import { useEffect, useState } from 'react';
import Papa from 'papaparse';
import { ArrowTrendingDownIcon, CheckCircleIcon } from '@heroicons/react/24/solid';

// CSV 데이터 타입 정의 (부모로부터 전달받는 데이터 타입)
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
  '저장시간'?: string; // 저장시간 컬럼 추가
  [key: string]: string | undefined;
}

// 부모 컴포넌트로부터 받을 Props 정의
interface BreakoutFailSectionProps {
  data: BreakoutData[];
  updateDate: string;
  loading: boolean;
  error: string | null;
}

export default function BreakoutFailSection({ data: failItems, updateDate, loading, error }: BreakoutFailSectionProps) {
  // 내부 상태는 더 이상 필요 없음, props로 데이터를 받음

  const formatPrice = (price: string) => {
    if (!price) return '';
    return Number(price).toLocaleString('ko-KR');
  };

  if (loading) return <div className="text-center py-10 text-sm">돌파 실패 종목 로딩 중...</div>;
  if (error) return <div className="text-center py-10 text-red-500 text-sm">오류: {error}</div>;

  const failItemsToDisplay = failItems.slice(0, 10);

  return (
    <section>
      <div className="flex justify-between items-center mb-2">
        <div className="font-semibold flex items-center mb-1 text-base md:text-lg" style={{ color: 'var(--primary-text-color, var(--primary-text-color-fallback))' }}>
          <span>돌파 실패</span>
          <ArrowTrendingDownIcon className="w-5 h-5 ml-1 text-blue-500" />
        </div>
        {updateDate && (
          <span className="text-xs mr-2" style={{ fontSize: 'clamp(0.7rem, 0.7vw, 0.7rem)', color: 'var(--text-muted-color, var(--text-muted-color-fallback))' }}>
            updated {updateDate}
          </span>
        )}
      </div>
      {!loading && !error && (
        failItemsToDisplay.length > 0 ? (
          <div className="overflow-x-auto rounded-[6px] overflow-hidden">
            <table className="min-w-full text-xs sm:text-sm border border-gray-200 rounded-[6px]">
              <thead className="bg-gray-100">
                <tr className="bg-gray-50">
                  <th className="px-2 py-1 md:px-3 md:py-2 border-b font-medium text-center hidden md:table-cell" style={{ color: 'var(--text-muted-color, var(--text-muted-color-fallback))' }}>종목코드</th>
                  <th className="px-2 py-1 md:px-3 md:py-2 border-b font-medium text-left" style={{ color: 'var(--text-muted-color, var(--text-muted-color-fallback))' }}>종목명</th>
                  <th className="px-2 py-1 md:px-3 md:py-2 border-b font-medium text-right" style={{ color: 'var(--text-muted-color, var(--text-muted-color-fallback))' }}>돌파 가격</th>
                  <th className="px-2 py-1 md:px-3 md:py-2 border-b font-medium text-right" style={{ color: 'var(--text-muted-color, var(--text-muted-color-fallback))' }}>등락률</th>
                  <th className="px-2 py-1 md:px-3 md:py-2 border-b font-medium text-center hidden sm:table-cell" style={{ color: 'var(--text-muted-color, var(--text-muted-color-fallback))' }}>갭</th>
                  <th className="px-2 py-1 md:px-3 md:py-2 border-b font-medium text-center" style={{ color: 'var(--text-muted-color, var(--text-muted-color-fallback))' }}>RS</th>
                  <th className="px-2 py-1 md:px-3 md:py-2 border-b font-medium text-center" style={{ color: 'var(--text-muted-color, var(--text-muted-color-fallback))' }}>MTT</th>
                </tr>
              </thead>
              <tbody>
                {failItemsToDisplay.map((item: BreakoutData, idx: number) => {
                  const rsValue = item['RS'] || '-';
                  const mttValue = item['MTT'] || '-';
                  
                  return (
                    <tr key={idx} className={idx % 2 === 0 ? 'bg-gray-50' : 'bg-white'}>
                      <td className="px-2 py-1 md:px-3 md:py-2 border-b text-center hidden md:table-cell">{item.Code}</td>
                      <td className="px-2 py-1 md:px-3 md:py-2 border-b text-left">{item.Name}</td>
                      <td className="px-2 py-1 md:px-3 md:py-2 border-b text-right">{item['Breakthrough Price'] ? formatPrice(item['Breakthrough Price']) + '원' : '-'}</td>
                      <td className="px-2 py-1 md:px-3 md:py-2 border-b text-right">
                        <span className={ 
                          item['Daily Change %'] && parseFloat(item['Daily Change %']) < 0 ? 'text-blue-500' :
                          item['Daily Change %'] && parseFloat(item['Daily Change %']) > 0 ? 'text-red-500' :
                          'text-gray-500'
                        }>
                          {item['Daily Change %'] && !isNaN(parseFloat(item['Daily Change %'])) ? 
                            `${parseFloat(item['Daily Change %']).toFixed(2)}%` : '-'}
                        </span>
                      </td>
                      <td className="px-2 py-1 md:px-3 md:py-2 border-b text-right hidden sm:table-cell">
                        {item['Gap %'] && !isNaN(parseFloat(item['Gap %'])) ? 
                          `${parseFloat(item['Gap %']).toFixed(2)}%` : '-'}
                      </td>
                      <td className="px-2 py-1 md:px-3 md:py-2 border-b text-center">{rsValue}</td>
                      <td className="px-2 py-1 md:px-3 md:py-2 border-b text-center">
                        {mttValue && mttValue !== '0' ? (
                          <CheckCircleIcon className="h-4 w-4 text-green-500 mx-auto" />
                        ) : null}
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        ) : (
          <div className="text-center py-4 text-sm text-gray-500">
            조건을 만족하는 데이터가 없습니다.
          </div>
        )
      )}
    </section>
  );
}
