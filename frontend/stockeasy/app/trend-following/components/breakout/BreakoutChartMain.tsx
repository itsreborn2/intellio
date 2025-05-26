'use client'

import BreakoutCandidatesChart from './BreakoutCandidatesChart';
import BreakoutSustainChart from './BreakoutSustainChart';
import BreakoutFailChart from './BreakoutFailChart';

export default function BreakoutChartMain() {
  return (
    <div className="space-y-8">
      {/* 돌파 성공 차트 */}
      <div className="pb-4">
        <BreakoutSustainChart />
      </div>

      {/* 돌파 실패 차트 */}
      <div className="py-4 border-t border-gray-200">
        <BreakoutFailChart />
      </div>

      {/* 돌파 후보 차트 */}
      <div className="pt-4 border-t border-gray-200">
        <BreakoutCandidatesChart />
      </div>
    </div>
  );
}
