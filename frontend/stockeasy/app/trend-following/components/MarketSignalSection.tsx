// 시장 신호등 섹션 (임시)
export default function MarketSignalSection() {
  return (
    <section className="flex items-center w-full">
      {/* 시장 신호등+등락률: 좌우 분할 배치 */}
      <div className="flex flex-row items-center justify-between w-full">
        <div className="flex flex-row items-center gap-4">
          <span className="text-lg font-semibold">시장 신호등</span>
          {/* 신호등 */}
          <span className="flex flex-row justify-center items-center bg-gray-900 border border-gray-700 rounded-xl shadow-md px-4 py-2 w-28 h-10">
            {/* 빨간불 */}
            <span className="w-5 h-5 rounded-full bg-red-500 border-2 border-red-300 shadow-[0_0_8px_1px_rgba(239,68,68,0.6)] mx-1" />
            {/* 노란불 */}
            <span className="w-5 h-5 rounded-full bg-yellow-300 border-2 border-yellow-200 shadow-[0_0_8px_1px_rgba(253,224,71,0.5)] mx-1" />
            {/* 초록불 */}
            <span className="w-5 h-5 rounded-full bg-green-500 border-2 border-green-300 shadow-[0_0_8px_1px_rgba(34,197,94,0.5)] mx-1" />
          </span>
        </div>
        {/* KOSPI/KOSDAQ 등락률 정보: 우측 끝 */}
        <div className="flex flex-row gap-6 items-center">
          <span className="text-[16px] text-gray-700">KOSPI <span className="font-semibold text-red-500">+0.82%</span></span>
          <span className="text-[16px] text-gray-700">KOSDAQ <span className="font-semibold text-blue-600">-1.12%</span></span>
        </div>
      </div>
    </section>
  );
}
