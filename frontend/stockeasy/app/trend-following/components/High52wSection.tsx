// 52주 신고가 주요 종목 섹션 (더미 데이터)
import React from 'react';

export default function High52wSection() {
  return (
    <section>
      <div className="text-lg font-semibold mb-2">52주 신고가 주요 종목</div>
      <table className="min-w-full text-sm border border-gray-200 rounded-[6px]">
        <thead>
          <tr className="bg-gray-100 text-gray-700">
            <th className="px-3 py-2 border-b font-semibold text-center">종목명</th>
            <th className="px-3 py-2 border-b font-semibold text-center">현재가</th>
            <th className="px-3 py-2 border-b font-semibold text-center">52주 신고가</th>
            <th className="px-3 py-2 border-b font-semibold text-center">등락률</th>
          </tr>
        </thead>
        <tbody>
          <tr>
            <td className="px-3 py-2 border-b text-center">삼성전자</td>
            <td className="px-3 py-2 border-b text-center">81,200</td>
            <td className="px-3 py-2 border-b text-center">81,200</td>
            <td className="px-3 py-2 border-b text-center text-red-500 font-semibold">+2.41%</td>
          </tr>
          <tr>
            <td className="px-3 py-2 border-b text-center">LG에너지솔루션</td>
            <td className="px-3 py-2 border-b text-center">430,000</td>
            <td className="px-3 py-2 border-b text-center">430,000</td>
            <td className="px-3 py-2 border-b text-center text-red-500 font-semibold">+1.13%</td>
          </tr>
          <tr>
            <td className="px-3 py-2 border-b text-center">에코프로비엠</td>
            <td className="px-3 py-2 border-b text-center">310,000</td>
            <td className="px-3 py-2 border-b text-center">310,000</td>
            <td className="px-3 py-2 border-b text-center text-red-500 font-semibold">+3.02%</td>
          </tr>
        </tbody>
      </table>
    </section>
  );
}
