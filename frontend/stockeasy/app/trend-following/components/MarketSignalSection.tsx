// 시장 신호등 섹션 (임시)
// 시장 신호등 단일 신호 표시용 컴포넌트 (크기 18px, 텍스트와 높이 일치)
function SignalLight({ label, colors }: { label: string; colors: [string, string, string] }) {
  return (
    <span className="flex flex-row items-center gap-1 mr-4">
      {/* 신호등 박스 */}
      <span
        className="flex flex-row justify-center items-center bg-gray-900 border border-gray-700 rounded-xl shadow-md px-3 py-1"
        style={{ height: '28px', minWidth: '70px' }}
      >
        {/* 빨간불 */}
        <span
          className="rounded-full border-2 shadow-[0_0_8px_1px_rgba(239,68,68,0.6)] mx-0.5"
          style={{ width: '18px', height: '18px', backgroundColor: colors[0], borderColor: colors[0] + '80' }}
        />
        {/* 노란불 */}
        <span
          className="rounded-full border-2 shadow-[0_0_8px_1px_rgba(253,224,71,0.5)] mx-0.5"
          style={{ width: '18px', height: '18px', backgroundColor: colors[1], borderColor: colors[1] + '80' }}
        />
        {/* 초록불 */}
        <span
          className="rounded-full border-2 shadow-[0_0_8px_1px_rgba(34,197,94,0.5)] mx-0.5"
          style={{ width: '18px', height: '18px', backgroundColor: colors[2], borderColor: colors[2] + '80' }}
        />
      </span>
      {/* 신호등 라벨 (텍스트 18px, 옅은 회색 #ABABAB) */}
      <span className="text-[18px] font-medium ml-2 whitespace-nowrap" style={{ color: '#ABABAB' }}>{label}</span>
    </span>
  );
}

// 시장 신호등 섹션 (임시)
export default function MarketSignalSection() {
  // 단기/장기 신호등 색상 (활성 불만 밝게, 나머지는 흐리게)
  // 단기: 초록불만 활성화, 장기: 빨간불만 활성화
  const shortTermColors: [string, string, string] = ['#e5e7eb', '#e5e7eb', '#22c55e']; // 비활성, 비활성, 활성(초록)
  const longTermColors: [string, string, string] = ['#ef4444', '#e5e7eb', '#e5e7eb']; // 활성(빨강), 비활성, 비활성

  return (
    <div className="bg-white rounded border border-gray-100 px-2 md:px-4 py-1 md:py-2">
      <section className="flex items-center w-full">
        <div className="flex flex-row items-center justify-between w-full">
          <div className="flex flex-row items-center gap-2">
            <h2 className="text-lg font-semibold text-gray-700 my-2">
              시장 신호
            </h2>
            <SignalLight label="단기" colors={shortTermColors} />
            <SignalLight label="장기" colors={longTermColors} />
          </div>
          <div className="flex flex-row items-center gap-6">
            <span className="text-base text-gray-700">
              KOSPI <span className="font-semibold text-red-500">+0.82%</span>
            </span>
            <span className="text-base text-gray-700">
              KOSDAQ <span className="font-semibold text-blue-600">-1.12%</span>
            </span>
          </div>
        </div>
      </section>
    </div>
  );
}
