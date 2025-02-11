import React from 'react';
import NewStockTicker from './NewStockTicker'; // NewStockTicker 컴포넌트 import

const TelegramSummaryArea: React.FC = () => {
  return (
    <div className="telegram-summary-area ml-3">
      <NewStockTicker /> {/* NewStockTicker 컴포넌트 배치 */}
      {/* Telegram 요약 영역 */}
      <div className="telegram-summary-content flex items-center">
        <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="#29A9E1" className="w-6 h-6 mr-1">
          <path fill="none" d="M0 0h24v24H0V0z"/>
          <path d="M4 12l1.41 1.41L11 18.83 18.59 5.29 20 6.7 11 17.7z"/>
          <path d="M2 6l9 12 8-9L2 6zm11 5l-4-4 1.41-1.41 2.59 2.59 2.59-2.59L17 7l-4 4z"/>
        </svg>
        Telegram 요약
      </div>
    </div>
  );
};

export default TelegramSummaryArea;
