"""테이블 처리를 위한 프로세서"""

from typing import List, Dict, Any
import logging

logger = logging.getLogger(__name__)

class TableProcessor:
    """테이블 데이터 처리"""
    
    @staticmethod
    def process_table_data(columns: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        백엔드 테이블 데이터를 프론트엔드에 적합한 형식으로 변환
        
        Args:
            columns: 백엔드의 TableResponse 형식 데이터
            
        Returns:
            Dict[str, Any]: 프론트엔드 테이블 형식 데이터
            {
                columns: [{ name: string, key: string }],
                rows: [{ id: string, [key: string]: string }]
            }
        """
        try:
            # 1. 모든 문서 ID 수집
            doc_ids = [cell["doc_id"] for cell in columns[0]["cells"]]
            
            # 2. 행 데이터 생성
            rows = []
            for idx, doc_id in enumerate(doc_ids):
                row_data = {"id": doc_id}
                
                # 각 컬럼의 내용 추가
                for column in columns:
                    header_name = column["header"]["name"]
                    cell = next(cell for cell in column["cells"] if cell["doc_id"] == doc_id)
                    row_data[header_name] = cell["content"]
                
                rows.append(row_data)
            
            # 3. 컬럼 정보 생성
            column_info = [
                {
                    "name": column["header"]["name"],
                    "key": column["header"]["name"]
                }
                for column in columns
            ]
            
            return {
                "columns": column_info,
                "rows": rows
            }
            
        except Exception as e:
            logger.error(f"테이블 데이터 처리 중 오류 발생: {str(e)}")
            raise
