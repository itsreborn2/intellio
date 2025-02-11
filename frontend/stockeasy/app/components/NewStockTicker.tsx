import React from 'react';

const NewStockTicker: React.FC = () => {
  return (
    <div className="font-mono text-sm text-gray-700 bg-gray-100 p-2 rounded-md flex items-center">
      <span className="text-xs text-gray-500 mr-2">당일 최다 언급:</span>
      <span className="font-bold">삼성전자</span> <span className="text-red-500">(-1.23%)</span> (150)
      <span className="ml-2 font-bold">하이닉스</span> <span className="text-green-500">(+0.5%)</span> (120)
      <span className="ml-2 font-bold">LG화학</span> <span className="text-red-500">(-0.8%)</span> (90)
    </div>
  );
};

export default NewStockTicker;
