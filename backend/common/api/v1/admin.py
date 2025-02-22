from typing import List, Dict, Any
import logging
from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.responses import HTMLResponse
from sqlalchemy import inspect, text
from sqlalchemy.ext.asyncio import AsyncSession

from common.services.embedding import EmbeddingService
from common.services.embedding_models import EmbeddingModelType
from common.core.database import get_db_async
from common.core.deps import  get_current_session
from common.models.base import Base
from common.models.user import Session
from common.core.config import settings
from common.services.vector_store_manager import VectorStoreManager
import json

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/admin", tags=["admin"])

async def verify_admin(session: Session = Depends(get_current_session)):
    """관리자 권한 확인"""
    #if not session.user or not session.user.is_superuser:
    if not session.user:
        print(f'verify admin1 : {session.user}')
        #print(f'verify admin2 : {session.user.is_superuser}')
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="관리자 권한이 필요합니다."
        )
    return session

@router.get("/pinecone/{namespace}", response_model=List[Dict[str, Any]])
async def get_pinecone_data(
    namespace: str,
    session: Session = Depends(verify_admin)
):
    """특정 namespace의 Pinecone DB 데이터를 반환합니다."""
    try:
        
        
        
            
        # namespace 유효성 검사
        valid_namespaces = {
            "doceasy": settings.PINECONE_NAMESPACE_DOCEASY,
            "stockeasy": settings.PINECONE_NAMESPACE_STOCKEASY,
            "stockeasy_telegram": settings.PINECONE_NAMESPACE_STOCKEASY_TELEGRAM
        }
        
        if namespace not in valid_namespaces:
            raise HTTPException(
                status_code=400,
                detail=f"유효하지 않은 namespace입니다: {namespace}"
            )
            
        # 실제 namespace 값 사용
        actual_namespace = valid_namespaces[namespace]
        
        logger.info(f"Pinecone 데이터 조회 시작 - namespace: {actual_namespace}")
        
        real_project_name = "stockeasy"
        if namespace == "doceasy":  
            real_project_name = "doceasy"
        # VectorStoreManager 초기화
        embedding_service = EmbeddingService()
        vector_store = VectorStoreManager(embedding_model_type=embedding_service.get_model_type(),
                                         project_name=real_project_name)
        
        # 초기화 확인
        if not vector_store.index:
            raise HTTPException(
                status_code=500,
                detail="Pinecone 인덱스 초기화 실패"
            )
            
        # 전체 데이터 조회 (모델 차원에 맞는 벡터 사용)
        response = vector_store.index.query(
            namespace=actual_namespace,
            vector=[0.1] * embedding_service.current_model_config.dimension,  # 임베딩 모델 차원에 맞게 설정
            top_k=10000,
            include_metadata=True
        )
        
        if not response or not hasattr(response, 'matches'):
            logger.warning(f"Pinecone 응답에 matches가 없습니다: {response}")
            return []
        
        # 응답 데이터 가공
        formatted_data = []
        for match in response.matches:
            try:
                formatted_match = {
                    'id': match.id,
                    'score': round(float(match.score), 4)
                }
                
                # metadata가 있는 경우에만 추가
                if hasattr(match, 'metadata') and match.metadata:
                    formatted_match.update(match.metadata)
                    
                formatted_data.append(formatted_match)
            except Exception as e:
                logger.error(f"데이터 포맷 중 오류 발생: {str(e)}, match: {match}")
                continue
        
        logger.info(f"Pinecone 데이터 조회 성공 - 총 {len(formatted_data)}개 데이터")
        return formatted_data
        
    except HTTPException as he:
        raise he
    except Exception as e:
        logger.error(f"Pinecone 데이터 조회 중 오류 발생: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"Pinecone 데이터 조회 실패: {str(e)}"
        )

@router.get("", response_class=HTMLResponse)
async def admin_page(
    request: Request,
    session: Session = Depends(verify_admin)
):
    """관리자 페이지 HTML을 반환합니다."""
    print('admin_page 호출됨')
    html_content = """
    <!DOCTYPE html>
    <html>
    <head>
        <title>데이터베이스 관리</title>
        <style>
            body { 
                font-family: Arial, sans-serif; 
                margin: 20px;
                box-sizing: border-box;
            }
            h1 { color: #333; }
            .table-list { 
                margin-bottom: 20px;
                display: flex;
                align-items: center;
                gap: 10px;
            }
            .controls {
                display: flex;
                align-items: center;
                gap: 10px;
            }
            select {
                padding: 8px;
                border: 1px solid #ddd;
                border-radius: 4px;
                background-color: white;
            }
            .table-container {
                position: relative;
                max-height: calc(100vh - 200px);
                overflow: auto;
                border: 1px solid #ddd;
                margin: 0 auto;
                width: 100%;
            }
            .table-data {
                width: 100%;
                border-collapse: separate;
                border-spacing: 0;
            }
            .table-data thead th {
                position: sticky;
                top: 0;
                z-index: 2;
                background-color: #f4f4f4;
                border-bottom: 2px solid #ddd;
                white-space: nowrap;
                padding: 12px 8px;
            }
            .table-data tbody td {
                border: 1px solid #ddd;
                padding: 8px;
                background-color: #fff;
            }
            .table-data tr:hover td {
                background-color: #f5f5f5;
            }
            button { 
                margin: 5px; 
                padding: 8px 16px;
                background-color: #f0f0f0;
                border: 1px solid #ddd;
                border-radius: 4px;
                cursor: pointer;
            }
            button:hover {
                background-color: #e0e0e0;
            }
            #tableContent { 
                margin-top: 20px;
                width: 100%;
                overflow-x: auto;
            }
            * {
                box-sizing: border-box;
            }
        </style>
    </head>
    <body>
        <h1>데이터베이스 관리</h1>
        <div class="table-list">
            <h2 id="tableListTitle">테이블 목록</h2>
            <div id="tables"></div>
            <div class="controls">
                <select id="namespaceSelect">
                    <option value="">Namespace 선택</option>
                    <option value="doceasy">DOCEASY</option>
                    <option value="stockeasy">STOCKEASY</option>
                    <option value="stockeasy_telegram">STOCKEASY_TELEGRAM</option>
                </select>
                <button onclick="loadPineconeData()">Pinecone DB 조회</button>
            </div>
        </div>
        <div id="tableContent"></div>

        <script>
            // 페이지 로드 시 테이블 목록 로드
            document.addEventListener('DOMContentLoaded', () => {
                loadTables();
            });

            async function loadTables() {
                try {
                    const response = await fetch('/api/v1/admin/tables');
                    const tables = await response.json();
                    const tablesDiv = document.getElementById('tables');
                    tablesDiv.innerHTML = ''; // 기존 버튼들 제거
                    tables.forEach(table => {
                        const button = document.createElement('button');
                        button.textContent = table;
                        button.onclick = () => loadTableData(table);
                        tablesDiv.appendChild(button);
                    });
                } catch (error) {
                    console.error('테이블 목록 로드 실패:', error);
                }
            }

            async function loadPineconeData() {
                const namespace = document.getElementById('namespaceSelect').value;
                if (!namespace) {
                    alert('네임스페이스를 선택해주세요.');
                    return;
                }

                try {
                    document.getElementById('tableListTitle').textContent = `Pinecone DB - ${namespace}`;
                    const response = await fetch(`/api/v1/admin/pinecone/${namespace}`);
                    const data = await response.json();
                    
                    const tableDiv = document.getElementById('tableContent');
                    tableDiv.innerHTML = '';
                    
                    if (data.length === 0) {
                        tableDiv.innerHTML = `<p>Pinecone DB ${namespace}에 데이터가 없습니다.</p>`;
                        return;
                    }

                    const tableContainer = document.createElement('div');
                    tableContainer.className = 'table-container';

                    const table = document.createElement('table');
                    table.className = 'table-data';
                    
                    // 헤더 생성
                    const thead = document.createElement('thead');
                    const headerRow = document.createElement('tr');
                    Object.keys(data[0]).forEach(key => {
                        const th = document.createElement('th');
                        th.textContent = key;
                        headerRow.appendChild(th);
                    });
                    thead.appendChild(headerRow);
                    table.appendChild(thead);

                    // 데이터 행 생성
                    const tbody = document.createElement('tbody');
                    data.forEach(row => {
                        const tr = document.createElement('tr');
                        Object.entries(row).forEach(([key, value]) => {
                            const td = document.createElement('td');
                            if (typeof value === 'object' && value !== null) {
                                // 객체인 경우 JSON 문자열로 변환하고 일부만 표시
                                const text = JSON.stringify(value);
                                td.textContent = text.length > 50 ? text.substring(0, 50) + '...' : text;
                                td.title = text; // 마우스 오버 시 전체 텍스트 표시
                            } else {
                                td.textContent = value === null ? '' : value.toString();
                            }
                            tr.appendChild(td);
                        });
                        tbody.appendChild(tr);
                    });
                    table.appendChild(tbody);
                    tableContainer.appendChild(table);
                    tableDiv.appendChild(tableContainer);
                } catch (error) {
                    console.error('Pinecone 데이터 로드 실패:', error);
                    document.getElementById('tableContent').innerHTML = 
                        `<p>Pinecone 데이터를 불러오는 중 오류가 발생했습니다.</p>`;
                }
            }

            async function loadTableData(tableName) {
                try {
                    document.getElementById('tableListTitle').textContent = `테이블 목록 - ${tableName}`;
                    
                    const response = await fetch(`/api/v1/admin/table/${tableName}`);
                    const data = await response.json();
                    
                    const tableDiv = document.getElementById('tableContent');
                    tableDiv.innerHTML = '';
                    
                    if (data.length === 0) {
                        tableDiv.innerHTML = `<p>테이블 ${tableName}에 데이터가 없습니다.</p>`;
                        return;
                    }

                    const tableContainer = document.createElement('div');
                    tableContainer.className = 'table-container';

                    const table = document.createElement('table');
                    table.className = 'table-data';
                    
                    const thead = document.createElement('thead');
                    const headerRow = document.createElement('tr');
                    Object.keys(data[0]).forEach(key => {
                        const th = document.createElement('th');
                        th.textContent = key;
                        headerRow.appendChild(th);
                    });
                    thead.appendChild(headerRow);
                    table.appendChild(thead);

                    const tbody = document.createElement('tbody');
                    data.forEach(row => {
                        const tr = document.createElement('tr');
                        Object.entries(row).forEach(([key, value]) => {
                            const td = document.createElement('td');
                            if (tableName === 'documents' && key === 'extracted_text' && value) {
                                const text = value.toString();
                                td.textContent = text.length > 20 ? text.substring(0, 20) + '...' : text;
                                td.title = text;
                            } else {
                                td.textContent = value === null ? '' : value.toString();
                            }
                            tr.appendChild(td);
                        });
                        tbody.appendChild(tr);
                    });
                    table.appendChild(tbody);
                    tableContainer.appendChild(table);
                    tableDiv.appendChild(tableContainer);
                } catch (error) {
                    console.error('테이블 데이터 로드 실패:', error);
                    document.getElementById('tableContent').innerHTML = 
                        `<p>테이블 데이터를 불러오는 중 오류가 발생했습니다.</p>`;
                }
            }
        </script>
    </body>
    </html>
    """
    return html_content

@router.get("/tables", response_model=List[str])
async def get_tables(
    db: AsyncSession = Depends(get_db_async),
    session: Session = Depends(verify_admin)
):
    """데이터베이스의 모든 테이블 목록을 반환합니다."""
    query = text("SELECT tablename FROM pg_tables WHERE schemaname = 'public'")
    result = await db.execute(query)
    tables = [row[0] for row in result.fetchall()]
    return tables

@router.get("/table/{table_name}", response_model=List[Dict[str, Any]])
async def get_table_data(
    table_name: str,
    db: AsyncSession = Depends(get_db_async),
    session: Session = Depends(verify_admin)
):
    """특정 테이블의 모든 데이터를 반환합니다."""
    try:
        query = text(f"SELECT * FROM {table_name}")
        result = await db.execute(query)
        rows = result.fetchall()
        return [dict(row._mapping) for row in rows]
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e)) 