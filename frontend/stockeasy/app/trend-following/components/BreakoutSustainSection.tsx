// 돌파 지속 섹션 (임시)
export default function BreakoutSustainSection() {
  return (
    <section>
      {/* 제목 폰트 사이즈 18px 고정 (상단 여백 없음, 하단만 mb-4) */}
      <div className="font-semibold text-gray-700 mb-4" style={{ fontSize: '18px' }}>돌파 지속</div>
      {/* 본문 컨텐츠: 14px(반응형) */}
      <ul className="text-[14px] md:text-[14px] text-gray-700 space-y-1">
        <li>[115180] 큐리언트 - 9,750원 (10,110원, +14.37%)</li>
        <li>[145020] 휴젤 - 353,000원 (357,500원, +5.15%)</li>
      </ul>
    </section>
  );
}
