'use client';

import React from 'react';

const EquityManagementPage = () => {
  const GCS_EXCEL_FILE_URL = 'https://storage.cloud.google.com/intellio-stockeasy-storage/Stockeasy/stockList/Stocklist.csv?authuser=1';

  const handleDownload = () => {
    if (!GCS_EXCEL_FILE_URL) {
      alert('GCS 파일 URL을 설정해주세요.');
      return;
    }
    window.open(GCS_EXCEL_FILE_URL, '_blank');
  };

  return (
    <section className="bg-white dark:bg-gray-900 rounded-lg shadow-md p-6">
      <div className="container mx-auto px-4">
        <div className="flex justify-between items-center mb-6">
          <h1 className="text-xl font-semibold text-gray-900 dark:text-white">
            자금 관리 excel 파일 다운로드
          </h1>
        </div>
        <div className="flex flex-col items-center justify-center">
          <p className="text-gray-700 dark:text-gray-300 mb-4">
            아래 버튼을 클릭하여 자금 관리 Excel 파일을 다운로드하세요.
          </p>
          <button
            onClick={handleDownload}
            className="px-6 py-3 bg-blue-600 text-white font-medium rounded-lg hover:bg-blue-700 focus:outline-none focus:ring-2 focus:ring-blue-500 focus:ring-offset-2 dark:bg-blue-500 dark:hover:bg-blue-600 dark:focus:ring-blue-400 transition-colors duration-150"
          >
            Excel 파일 다운로드
          </button>
        </div>
      </div>
    </section>
  );
};

export default EquityManagementPage;
