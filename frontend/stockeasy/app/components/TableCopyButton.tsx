'use client'

import React, { useState } from 'react';
import { TableCopyButtonProps, copyTableAsImage } from '../utils/tableCopyUtils';
import { ClipboardCopy } from 'lucide-react'; // ClipboardCopy 아이콘 import

/**
 * 테이블 복사 버튼 컴포넌트
 * 테이블을 이미지로 복사하는 기능을 제공하는 재사용 가능한 버튼
 * @param props 버튼 속성 (테이블 참조, 헤더 참조, 테이블 이름, 옵션, 클래스명, 버튼 텍스트)
 */
export const TableCopyButton: React.FC<TableCopyButtonProps> = ({
  tableRef,
  headerRef,
  tableName,
  options,
  className = "",
  buttonText = "이미지복사"
}) => {
  const [isLoading, setIsLoading] = useState(false);
  const [showSuccess, setShowSuccess] = useState(false);
  
  // 이미지 복사 핸들러
  const handleCopyImage = async () => {
    // 즉시 로딩 상태로 변경
    setIsLoading(true);
    
    try {
      // 이미지 복사 함수 호출
      await copyTableAsImage(tableRef, headerRef, tableName, options);
    } catch (error) {
      console.error('이미지 복사 중 오류 발생:', error);
      alert('이미지 복사에 실패했습니다. 콘솔을 확인해주세요.');
    } finally {
      // 복사 작업 완료 후 로딩 상태 해제 및 성공 메시지 표시
      setTimeout(() => {
        setIsLoading(false);
        setShowSuccess(true);
        setTimeout(() => setShowSuccess(false), 2000); // 2초 후 성공 메시지 숨김
      }, 500); // 로딩 상태 해제 후 0.5초 지연
    }
  };
  
  // 반응형 스타일 정의
  const buttonStyle = {
    fontSize: 'clamp(0.6rem, 0.7vw, 0.7rem)',
    padding: 'clamp(0.15rem, 0.2vw, 0.25rem) clamp(0.3rem, 0.4vw, 0.5rem)',
  };
  
  return (
    <button 
      onClick={handleCopyImage}
      className={`text-gray-700 text-xs px-2 py-1 rounded ${isLoading ? 'opacity-50 cursor-not-allowed' : 'hover:opacity-80'} bg-[#D8EFE9]`}
      type="button"
      aria-label={`${tableName} 이미지로 복사`}
      disabled={isLoading}
      style={buttonStyle}
    >
      {isLoading ? "생성 중..." : showSuccess ? "복사 완료!" : <ClipboardCopy className="h-3.5 w-3.5" />}
    </button>
  );
};

export default TableCopyButton;