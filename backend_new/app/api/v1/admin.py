from typing import List, Dict, Any
from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.responses import HTMLResponse
from sqlalchemy import inspect, text
from sqlalchemy.ext.asyncio import AsyncSession
from app.core.deps import get_db, get_current_session
from app.models.base import Base
from app.models.user import Session
import json

router = APIRouter(tags=["admin"])

async def verify_admin(session: Session = Depends(get_current_session)):
    """관리자 권한 확인"""
    #if not session.user or not session.user.is_superuser:
    if not session.user:
        print(f'verify admin1 : {session.user}')
        print(f'verify admin2 : {session.user.is_superuser}')
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="관리자 권한이 필요합니다."
        )
    return session

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
            body { font-family: Arial, sans-serif; margin: 20px; }
            h1 { color: #333; }
            .table-list { margin-bottom: 20px; }
            .table-data { border-collapse: collapse; width: 100%; }
            .table-data th, .table-data td { 
                border: 1px solid #ddd; 
                padding: 8px; 
                text-align: left; 
            }
            .table-data th { background-color: #f4f4f4; }
            button { margin: 5px; padding: 5px 10px; }
            #tableContent { margin-top: 20px; overflow-x: auto; }
        </style>
    </head>
    <body>
        <h1>데이터베이스 관리</h1>
        <div class="table-list">
            <h2>테이블 목록</h2>
            <div id="tables"></div>
        </div>
        <div id="tableContent"></div>

        <script>
            async function loadTables() {
                const response = await fetch('/api/v1/admin/tables');
                const tables = await response.json();
                const tablesDiv = document.getElementById('tables');
                tables.forEach(table => {
                    const button = document.createElement('button');
                    button.textContent = table;
                    button.onclick = () => loadTableData(table);
                    tablesDiv.appendChild(button);
                });
            }

            async function loadTableData(tableName) {
                const response = await fetch(`/api/v1/admin/table/${tableName}`);
                const data = await response.json();
                
                const tableDiv = document.getElementById('tableContent');
                if (data.length === 0) {
                    tableDiv.innerHTML = `<p>테이블 ${tableName}에 데이터가 없습니다.</p>`;
                    return;
                }

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
                    Object.values(row).forEach(value => {
                        const td = document.createElement('td');
                        td.textContent = JSON.stringify(value);
                        tr.appendChild(td);
                    });
                    tbody.appendChild(tr);
                });
                table.appendChild(tbody);

                tableDiv.innerHTML = '';
                tableDiv.appendChild(table);
            }

            loadTables();
        </script>
    </body>
    </html>
    """
    return html_content

@router.get("/tables", response_model=List[str])
async def get_tables(
    db: AsyncSession = Depends(get_db),
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
    db: AsyncSession = Depends(get_db),
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