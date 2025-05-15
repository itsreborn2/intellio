"use client";

import Chart1 from './MarketMonitorChart/Chart1';
import Chart2 from './MarketMonitorChart/Chart2';
import Chart3 from './MarketMonitorChart/Chart3';

export default function MarketMonitor() {
  return (
    <div className="bg-white rounded border border-gray-100 px-2 md:px-4 py-3 md:py-4">
      <h2 className="text-lg font-semibold text-gray-700 mb-4">시장지표</h2>
      
      <div className="space-y-6">
        {/* 첫 번째 차트: KOSPI vs 200일선 하락비율 */}
        <div className="bg-white rounded border border-gray-200 p-3 md:p-4 shadow-sm">
          <h3 className="text-sm font-medium text-gray-700 mb-2">KOSPI 지수와 200일선 하락비율</h3>
          <div className="h-[300px]">
            <Chart1 />
          </div>
        </div>
        
        {/* 두 번째 차트: KOSPI vs 20일선 하락비율 및 200일선 하락비율 */}
        <div className="bg-white rounded border border-gray-200 p-3 md:p-4 shadow-sm">
          <h3 className="text-sm font-medium text-gray-700 mb-2">KOSPI 지수와 20일선/200일선 하락비율</h3>
          <div className="h-[300px]">
            <Chart2 />
          </div>
        </div>
        
        {/* 세 번째 차트: KOSPI vs 52주 신고가/신저가 비율 */}
        <div className="bg-white rounded border border-gray-200 p-3 md:p-4 shadow-sm">
          <h3 className="text-sm font-medium text-gray-700 mb-2">KOSPI 지수와 52주 신고가/신저가 비율</h3>
          <div className="h-[300px]">
            <Chart3 />
          </div>
        </div>
      </div>
    </div>
  );
}
