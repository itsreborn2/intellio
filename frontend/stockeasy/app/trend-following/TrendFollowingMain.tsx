// trend-following 페이지 전체 레이아웃 및 섹션 컴포넌트 배치 (임시)
import MarketSignalSection from './components/MarketSignalSection';
import SectorLeaderSection from './components/SectorLeaderSection';
import High52wSection from './components/High52wSection';
import TrendChartSection from './components/TrendChartSection';
import BreakoutCandidatesSection from './components/BreakoutCandidatesSection';
import BreakoutSustainSection from './components/BreakoutSustainSection';
import BreakoutFailSection from './components/BreakoutFailSection';

export default function TrendFollowingMain() {
  return (
    <div className="flex-1 p-0 sm:p-2 md:p-4 overflow-auto w-full">
      <div className="w-full max-w-[1280px] mx-auto">
        {/* 시장 신호 섹션 */}
        <div className="mb-2 md:mb-4">
          <div className="bg-white rounded-[6px] shadow p-2 md:p-4 border border-gray-200">
            <div className="bg-white rounded border border-gray-100 p-2 md:p-4">
              <MarketSignalSection />
            </div>
          </div>
        </div>
        {/* 섹터 리더 섹션 */}
        <div className="mb-2 md:mb-4">
          <div className="bg-white rounded-[6px] shadow p-2 md:p-4 border border-gray-200">
            <div className="bg-white rounded border border-gray-100 p-2 md:p-4">
              <SectorLeaderSection />
            </div>
          </div>
        </div>
        {/* 52주 신고가 주요종목 섹션 */}
        <div className="mb-2 md:mb-4">
          <div className="bg-white rounded-[6px] shadow p-2 md:p-4 border border-gray-200">
            <div className="bg-white rounded border border-gray-100 p-2 md:p-4">
              <High52wSection />
            </div>
          </div>
        </div>
        {/* 트렌드 차트 섹션 */}
        <div className="mb-2 md:mb-4">
          <div className="bg-white rounded-[6px] shadow p-2 md:p-4 border border-gray-200">
            <div className="bg-white rounded border border-gray-100 p-2 md:p-4">
              <TrendChartSection />
            </div>
          </div>
        </div>
        {/* 돌파 후보/성공/실패: 후보는 좌측, 성공+실패는 우측에서 위아래로 */}
        <div className="grid grid-cols-1 md:grid-cols-2 gap-2 md:gap-4 mb-2 md:mb-4">
          {/* 돌파 후보군(좌측) */}
          <div className="bg-white rounded-[6px] shadow p-2 md:p-4 border border-gray-200 h-full">
            <div className="bg-white rounded border border-gray-100 p-2 md:p-4 h-full">
              <BreakoutCandidatesSection />
            </div>
          </div>
          {/* 돌파 성공/실패(우측, 위아래로 분할) */}
          <div className="flex flex-col gap-2 md:gap-4 h-full">
            <div className="bg-white rounded-[6px] shadow p-2 md:p-4 border border-gray-200 flex-1">
              <div className="bg-white rounded border border-gray-100 p-2 md:p-4 h-full">
                <BreakoutSustainSection />
              </div>
            </div>
            <div className="bg-white rounded-[6px] shadow p-2 md:p-4 border border-gray-200 flex-1">
              <div className="bg-white rounded border border-gray-100 p-2 md:p-4 h-full">
                <BreakoutFailSection />
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
