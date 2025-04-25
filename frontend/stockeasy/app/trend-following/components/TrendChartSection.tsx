// 차트 섹션 (더미 차트 3종)
import TrendDummyCharts from './TrendDummyCharts';

export default function TrendChartSection() {
  return (
    <section className="flex flex-col items-center w-full">
      {/* 제목 폰트 사이즈 18px 고정 (상단 여백 없음, 하단만 mb-4) */}
      <div className="font-semibold text-gray-700 mb-4" style={{ fontSize: '18px' }}>추세 차트</div>
      {/* 3가지 더미 차트가 가로로 나란히 표시됨 */}
      <TrendDummyCharts />
    </section>
  );
}
