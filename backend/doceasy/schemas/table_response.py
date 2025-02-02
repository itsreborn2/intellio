"""테이블 응답 스키마"""

from typing import List, Dict
from pydantic import BaseModel

class TableHeader(BaseModel):
    """테이블 헤더 정보"""
    name: str
    prompt: str  # 각 헤더 셀에 대한 상세 프롬프트

class TableCell(BaseModel):
    """테이블 셀 정보"""
    doc_id: str
    content: str

class TableColumn(BaseModel):
    """테이블 컬럼 정보"""
    header: TableHeader
    cells: List[TableCell]

class TableResponse(BaseModel):
    """테이블 형식의 응답"""
    columns: List[TableColumn]
