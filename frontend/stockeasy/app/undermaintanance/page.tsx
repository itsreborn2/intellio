import React from 'react';
import { Wrench } from 'lucide-react';

/**
 * 서비스 점검 안내 페이지 컴포넌트
 */
const UnderMaintenancePage = () => {
  return (
    <div className="flex items-center justify-center min-h-screen bg-gray-100 dark:bg-gray-900 p-4">
      {/* Card 대신 div와 Tailwind 사용 */}
      <div className="w-full max-w-md text-center bg-white dark:bg-gray-800 rounded-lg shadow-lg p-6">
        {/* Header 영역 */}
        <div className="mb-6">
          <div className="flex justify-center mb-4">
            {/* 점검 아이콘 */}
            <Wrench className="h-12 w-12 text-blue-600 dark:text-blue-400" /> {/* 아이콘 색상 변경 */}
          </div>
          {/* Title */}
          <h2 className="text-2xl font-bold mb-2 text-gray-800 dark:text-gray-100">서비스 점검 중</h2>
          {/* Description */}
          <p className="text-gray-500 dark:text-gray-400">보다 나은 서비스 제공을 위해 점검을 진행하고 있습니다.</p>
        </div>

        {/* Content 영역 */}
        <div className="space-y-4">
          <p className="text-lg font-semibold text-orange-500">🚧 점검중... 🚧</p>
          <p className="text-gray-700 dark:text-gray-300">
            최대한 빠르게 서버 업데이트를 마치고 안정적인 서비스를 제공하겠습니다.
            <br />
            이용에 불편을 드려 죄송합니다.
          </p>
        </div>
      </div>
    </div>
  );
};

export default UnderMaintenancePage;
