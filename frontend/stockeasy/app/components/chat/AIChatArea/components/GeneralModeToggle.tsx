import React from 'react';
import { useStockSelector } from '../context/StockSelectorContext';

interface GeneralModeToggleProps {
  className?: string;
}

export function GeneralModeToggle({ className = '' }: GeneralModeToggleProps) {
  const { state, setGeneralMode } = useStockSelector();
  
  // 관리자가 아니면 렌더링하지 않음
  if (!state.isAdminUser) {
    return null;
  }
  
  const handleToggle = (checked: boolean) => {
    setGeneralMode(checked);
    console.log('일반 질문 모드 변경:', checked);
  };
  
  return (
    <div className={`flex items-center space-x-2 bg-yellow-50 border border-yellow-200 rounded-lg p-3 ${className}`}>
      <div className="flex items-center space-x-2">
        <input
          type="checkbox"
          id="general-mode-toggle"
          checked={state.isGeneralMode}
          onChange={(e) => handleToggle(e.target.checked)}
          className="h-4 w-4 rounded border-gray-300 text-blue-600 focus:ring-blue-500"
        />
        <label 
          htmlFor="general-mode-toggle" 
          className="text-sm font-medium text-gray-700 cursor-pointer"
        >
          일반 질문 모드 (종목 선택 스킵)
        </label>
      </div>
      <div className="text-xs text-yellow-600 bg-yellow-100 px-2 py-1 rounded">
        관리자 전용
      </div>
    </div>
  );
}

export default GeneralModeToggle; 