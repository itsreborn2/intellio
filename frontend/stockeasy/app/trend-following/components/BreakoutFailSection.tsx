// 돌파 실패 섹션 (임시)
export default function BreakoutFailSection() {
  return (
    <section>
      {/* 제목 폰트 사이즈 18px 고정 (상단 여백 없음, 하단만 mb-4) */}
      <div className="font-semibold text-gray-700 mb-4" style={{ fontSize: '18px' }}>돌파 실패 (Squat)</div>
      {/* 본문 컨텐츠: 14px(반응형) */}
      <ul className="text-[14px] md:text-[14px] text-gray-700 space-y-1">
        <li>[259960] 크래프톤 - 390,000원 (384,000원, -1.54%)</li>
        <li>[419530] SAMG엔터 - 36,000원 (35,550원, -1.25%)</li>
      </ul>
    </section>
  );
}
