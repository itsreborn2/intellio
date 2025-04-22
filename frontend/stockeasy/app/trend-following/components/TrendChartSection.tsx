// 차트 섹션 (더미 차트 3종)
import TrendDummyCharts from './TrendDummyCharts';

export default function TrendChartSection() {
  return (
    <section className="flex flex-col items-center w-full">
      <div className="text-lg font-semibold mb-2">추세 차트</div>
      {/* 3가지 더미 차트가 가로로 나란히 표시됨 */}
      <TrendDummyCharts />
    </section>
  );
}
