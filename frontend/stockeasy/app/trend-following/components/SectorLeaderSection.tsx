// 주도섹터/주도주 설명 섹션 (임시)
export default function SectorLeaderSection() {
  return (
    <section>
      {/* 제목 폰트 사이즈 18px 고정 (상단 여백 없음, 하단만 mb-4) */}
      <h2 className="font-semibold text-gray-700 mb-4" style={{ fontSize: '18px' }}>주도섹터 / 주도주</h2>
      {/* 주도섹터/주도주 표 (예시 데이터) */}
      <div className="overflow-x-auto rounded-[6px]">
        <table className="min-w-full text-sm border border-gray-200 rounded-[6px]">
          <thead>
            <tr className="bg-gray-100 text-gray-700">
              <th className="px-3 py-2 border-b font-semibold">섹터</th>
              <th className="px-3 py-2 border-b font-semibold">대표주</th>
              <th className="px-3 py-2 border-b font-semibold text-center">등급</th>
              <th className="px-3 py-2 border-b font-semibold text-center">RS</th>
              <th className="px-3 py-2 border-b font-semibold text-center">주요 모멘텀</th>
            </tr>
          </thead>
          <tbody>
            {/* 각 행에 RS 컬럼 추가. 임의의 예시 값 사용 */}
            <tr>
              <td className="px-3 py-2 border-b">방산</td>
              <td className="px-3 py-2 border-b">한화에어로스페이스</td>
              <td className="px-3 py-2 border-b text-center">S</td>
              <td className="px-3 py-2 border-b text-center">99</td>
              <td className="px-3 py-2 border-b text-center">트럼프 수혜, 국방예산 확대</td>
            </tr>
            <tr>
              <td className="px-3 py-2 border-b">조선</td>
              <td className="px-3 py-2 border-b">현대미포조선</td>
              <td className="px-3 py-2 border-b text-center">A</td>
              <td className="px-3 py-2 border-b text-center">95</td>
              <td className="px-3 py-2 border-b text-center">LNG선 수주, 업황 개선</td>
            </tr>
            <tr>
              <td className="px-3 py-2 border-b">피부미용</td>
              <td className="px-3 py-2 border-b">아모레퍼시픽</td>
              <td className="px-3 py-2 border-b text-center">B</td>
              <td className="px-3 py-2 border-b text-center">88</td>
              <td className="px-3 py-2 border-b text-center">중국 리오프닝, 소비 회복</td>
            </tr>
            <tr>
              <td className="px-3 py-2 border-b">정치테마</td>
              <td className="px-3 py-2 border-b">리캠바이오</td>
              <td className="px-3 py-2 border-b text-center">B</td>
              <td className="px-3 py-2 border-b text-center">82</td>
              <td className="px-3 py-2 border-b text-center">리서치TV 언급, 수급 모멘텀</td>
            </tr>
            <tr>
              <td className="px-3 py-2 border-b">테마</td>
              <td className="px-3 py-2 border-b">씨젠</td>
              <td className="px-3 py-2 border-b text-center">C</td>
              <td className="px-3 py-2 border-b text-center">74</td>
              <td className="px-3 py-2 border-b text-center">AI, 바이오 모멘텀</td>
            </tr>
          </tbody>
        </table>
      </div>
    </section>
  );
}
