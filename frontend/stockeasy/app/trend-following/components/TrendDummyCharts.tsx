
// 더미 차트 3종을 가로로 나란히 보여주는 컴포넌트 (실제 차트 대신 SVG/Div로 대체)
import React from 'react';

export default function TrendDummyCharts() {
  return (
    <div className="flex flex-row gap-4 w-full">
      {/* 실적 차트 더미 */}
      <div className="flex-1 bg-white border border-gray-200 rounded-[6px] p-2 min-w-[220px]">
        <div className="flex justify-between items-center mb-1">
          <span className="text-xs text-gray-500">(십억)</span>
          <span className="text-xs text-gray-400">실적</span>
          <button className="w-5 h-5 text-gray-300">●</button>
        </div>
        <div className="w-full h-56 flex items-center justify-center bg-gray-100 rounded">
          <span className="text-xs text-gray-400">더미 차트</span>
        </div>
        <div className="flex justify-between mt-1 text-[10px] text-gray-400">
          <span>매출액</span><span>영업이익</span><span>순이익</span>
        </div>
      </div>
      {/* 매출액 차트 더미 */}
      <div className="flex-1 bg-white border border-gray-200 rounded-[6px] p-2 min-w-[220px]">
        <div className="flex justify-between items-center mb-1">
          <span className="text-xs text-gray-500">(십억)</span>
          <span className="text-xs text-gray-400">매출액</span>
          <button className="w-5 h-5 text-gray-300">●</button>
        </div>
        <div className="w-full h-56 flex items-center justify-center bg-gray-100 rounded">
          <span className="text-xs text-gray-400">더미 차트</span>
        </div>
      </div>
      {/* 영업이익 차트 더미 */}
      <div className="flex-1 bg-white border border-gray-200 rounded-[6px] p-2 min-w-[220px]">
        <div className="flex justify-between items-center mb-1">
          <span className="text-xs text-gray-500">(십억)</span>
          <span className="text-xs text-gray-400">영업이익</span>
          <button className="w-5 h-5 text-gray-300">●</button>
        </div>
        <div className="w-full h-56 flex items-center justify-center bg-gray-100 rounded">
          <span className="text-xs text-gray-400">더미 차트</span>
        </div>
      </div>
    </div>
  );
}
