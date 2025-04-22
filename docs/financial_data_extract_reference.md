# 요약재무정보 추출 참고 코드

## 1. 요약재무정보 목차 추출 및 페이지 식별

아래 코드는 fitz의 `get_toc()` 메서드를 활용하여 요약재무정보 관련 목차를 찾아 페이지 번호를 식별하는 예시입니다.

```python
import fitz  # PyMuPDF
import pdfplumber
import re
from typing import List, Dict, Optional, Tuple, Any

def extract_summary_financial_page(pdf_path: str) -> Optional[int]:
    """
    PDF 파일에서 요약재무정보 섹션의 페이지 번호를 찾는 함수
    
    Args:
        pdf_path: PDF 파일 경로
        
    Returns:
        요약재무정보 섹션의 페이지 번호 (0부터 시작), 찾지 못하면 None 반환
    """
    try:
        # PDF 문서 열기
        doc = fitz.open(pdf_path)
        
        # 목차 가져오기
        toc = doc.get_toc()
        
        # 요약재무정보 관련 키워드
        keywords = [
            "요약재무정보", "요약 재무정보", "요약 재무 정보", 
            "요약 연결재무정보", "요약재무제표", "요약 재무제표"
        ]
        
        # 목차에서 요약재무정보 페이지 찾기
        for item in toc:
            level, title, page = item
            for keyword in keywords:
                if keyword in title:
                    # 페이지 번호 반환 (목차의 페이지는 1부터 시작하지만 fitz는 0부터 시작)
                    return page - 1
        
        # 목차에서 찾지 못한 경우 본문 내용에서 찾기 시도
        for page_num in range(min(30, len(doc))):  # 처음 30페이지만 검색
            page = doc[page_num]
            text = page.get_text()
            for keyword in keywords:
                if keyword in text and ("5년" in text or "3년" in text):
                    return page_num
        
        return None
    except Exception as e:
        print(f"요약재무정보 페이지 추출 중 오류 발생: {e}")
        return None
    finally:
        if 'doc' in locals():
            doc.close()
```

## 2. 요약재무정보 테이블 추출

아래 코드는 pdfplumber를 사용하여 요약재무정보 테이블을 추출하는 예시입니다.

```python
def extract_summary_financial_tables(pdf_path: str, page_range: Tuple[int, int]) -> List[List[List[str]]]:
    """
    요약재무정보 페이지 범위에서 테이블 데이터를 추출하는 함수
    
    Args:
        pdf_path: PDF 파일 경로
        page_range: 요약재무정보가 있는 페이지 범위 (시작 페이지, 끝 페이지)
        
    Returns:
        추출된 테이블 데이터 리스트
    """
    try:
        start_page, end_page = page_range
        processed_tables = []
        
        with pdfplumber.open(pdf_path) as pdf:
            # 범위 내의 모든 페이지에서 테이블 추출
            for page_num in range(start_page, end_page + 1):
                if page_num >= len(pdf.pages):
                    break
                    
                page = pdf.pages[page_num]
                
                # 테이블 추출 시도
                tables = page.extract_tables()
                
                if not tables:
                    # 테이블 감지 실패 시 수동 테이블 추출 설정 적용
                    tables = page.extract_tables(
                        table_settings={
                            "vertical_strategy": "text",
                            "horizontal_strategy": "text",
                            "intersection_tolerance": 5
                        }
                    )
                
                # 추출된 데이터 전처리
                for table in tables:
                    # 빈 행과 열 제거, None을 빈 문자열로 변환
                    cleaned_table = []
                    for row in table:
                        if any(cell is not None and cell.strip() != "" for cell in row):
                            cleaned_row = []
                            for cell in row:
                                if cell is None:
                                    cleaned_row.append("")
                                else:
                                    cleaned_row.append(cell.strip())
                            cleaned_table.append(cleaned_row)
                    
                    # 전처리 및 구조화
                    if cleaned_table:
                        processed_tables.append(cleaned_table)
            
            logger.info(f"테이블 추출 완료: 총 {len(processed_tables)}개 테이블 발견 (페이지 {start_page+1}~{end_page+1})")
            return processed_tables
    except Exception as e:
        logger.error(f"요약재무정보 테이블 추출 중 오류 발생: {e}")
        return []
```

## 3. LLM을 활용한 테이블 데이터 구조화

테이블 데이터를 LLM을 활용하여 구조화된 형태로 변환하는 예시입니다.

```python
def structure_table_with_llm(tables: List[List[List[str]]]) -> Dict[str, Any]:
    """
    LLM을 사용하여 테이블 데이터를 구조화하는 함수
    
    Args:
        tables: 추출된 테이블 데이터 리스트
        
    Returns:
        구조화된 재무 데이터
    """
    from common.services.llm_service import LLMService
    
    # 테이블 데이터를 텍스트로 변환
    table_text = ""
    for i, table in enumerate(tables):
        table_text += f"테이블 {i+1}:\n"
        for row in table:
            table_text += " | ".join([str(cell) for cell in row]) + "\n"
        table_text += "\n"
    
    # LLM 프롬프트 구성
    prompt = f"""
    아래는 기업 요약재무정보 테이블입니다. 이 데이터를 다음 JSON 형식으로 구조화해주세요:
    
    {{
      "financial_summary": [
        {{
          "item_name": "항목명(예: 매출액)",
          "item_code": "표준화된 항목 코드(예: revenue)",
          "values": [
            {{
              "year": 2022,
              "quarter": null,
              "value": 100000000000,
              "unit": "원"
            }},
            // 다른 기간 데이터
          ]
        }},
        // 다른 항목 데이터
      ]
    }}
    
    테이블 데이터:
    {table_text}
    
    다음 항목들에 특히 주의하세요:
    1. 항목명은 원본 그대로 유지하되, item_code는 표준화된 코드로 변환해주세요
    2. 숫자 값에서 쉼표를 제거하고 숫자형으로 변환해주세요
    3. 단위(원, 백만원, 억원 등)를 식별하여 값을 원 단위로 변환해주세요
    4. 누락된 데이터는 null로 표시해주세요
    """
    
    # LLM 서비스 호출
    llm_service = LLMService()
    response = llm_service.chat_completion(
        messages=[{"role": "user", "content": prompt}],
        model="gpt-4"
    )
    
    # JSON 응답 파싱
    import json
    import re
    
    # JSON 부분 추출
    json_match = re.search(r'```json\s*([\s\S]*?)\s*```', response)
    if json_match:
        json_str = json_match.group(1)
    else:
        json_str = response
    
    try:
        return json.loads(json_str)
    except json.JSONDecodeError:
        print("JSON 파싱 오류, 텍스트 응답:", response)
        return {"error": "구조화 실패", "raw_response": response}
```

## 4. 데이터 저장 로직

추출 및 구조화된 데이터를 데이터베이스에 저장하는 예시입니다.

```python
async def save_summary_financial_data(company_code: str, report_type: str, report_year: int, 
                                     report_quarter: Optional[int], structured_data: Dict[str, Any]) -> bool:
    """
    구조화된 요약재무정보를 데이터베이스에 저장하는 함수
    
    Args:
        company_code: 기업 코드
        report_type: 보고서 유형 (annual, semi, quarter)
        report_year: 보고서 연도
        report_quarter: 보고서 분기 (연간보고서는 None)
        structured_data: 구조화된 재무 데이터
        
    Returns:
        저장 성공 여부
    """
    from sqlalchemy.ext.asyncio import AsyncSession
    from common.core.database import get_db
    from stockeasy.models.companies import Company
    from stockeasy.models.financial_reports import FinancialReport
    from stockeasy.models.financial_data import FinancialItemMapping, FinancialItemRawMapping, SummaryFinancialData
    
    async with get_db() as db:
        db_session: AsyncSession = db
        
        try:
            # 회사 정보 조회
            company = await db_session.execute(
                select(Company).where(Company.company_code == company_code)
            )
            company = company.scalar_one_or_none()
            
            if not company:
                print(f"회사 정보가 없습니다: {company_code}")
                return False
            
            # 보고서 정보 생성 또는 조회
            year_month = report_year * 100 + (report_quarter * 3 if report_quarter else 12)
            
            report = await db_session.execute(
                select(FinancialReport).where(
                    and_(
                        FinancialReport.company_id == company.id,
                        FinancialReport.report_year == report_year,
                        FinancialReport.report_quarter == report_quarter
                    )
                )
            )
            report = report.scalar_one_or_none()
            
            if not report:
                report = FinancialReport(
                    company_id=company.id,
                    report_type=report_type,
                    report_year=report_year,
                    report_quarter=report_quarter,
                    year_month=year_month
                )
                db_session.add(report)
                await db_session.flush()
            
            # 재무 데이터 저장
            for item in structured_data.get("financial_summary", []):
                item_name = item.get("item_name")
                item_code = item.get("item_code")
                
                # 항목 매핑 조회 또는 생성
                item_mapping = await db_session.execute(
                    select(FinancialItemMapping).where(FinancialItemMapping.item_code == item_code)
                )
                item_mapping = item_mapping.scalar_one_or_none()
                
                if not item_mapping:
                    item_mapping = FinancialItemMapping(
                        item_code=item_code,
                        category="요약재무정보", 
                        standard_name=item_name
                    )
                    db_session.add(item_mapping)
                    await db_session.flush()
                
                # 원본 항목명 매핑 저장
                raw_mapping = await db_session.execute(
                    select(FinancialItemRawMapping).where(
                        and_(
                            FinancialItemRawMapping.mapping_id == item_mapping.id,
                            FinancialItemRawMapping.raw_name == item_name
                        )
                    )
                )
                raw_mapping = raw_mapping.scalar_one_or_none()
                
                if not raw_mapping and item_name != item_mapping.standard_name:
                    raw_mapping = FinancialItemRawMapping(
                        mapping_id=item_mapping.id,
                        raw_name=item_name
                    )
                    db_session.add(raw_mapping)
                
                # 데이터 값 저장
                for value_data in item.get("values", []):
                    data_year = value_data.get("year")
                    data_quarter = value_data.get("quarter")
                    value = value_data.get("value")
                    unit = value_data.get("unit", "원")
                    
                    if value is None:
                        continue
                    
                    # 연월 계산
                    data_year_month = data_year * 100
                    if data_quarter:
                        data_year_month += data_quarter * 3
                    else:
                        data_year_month += 12
                    
                    # 기존 데이터 확인
                    summary_data = await db_session.execute(
                        select(SummaryFinancialData).where(
                            and_(
                                SummaryFinancialData.report_id == report.id,
                                SummaryFinancialData.company_id == company.id,
                                SummaryFinancialData.item_id == item_mapping.id,
                                SummaryFinancialData.year_month == data_year_month
                            )
                        )
                    )
                    summary_data = summary_data.scalar_one_or_none()
                    
                    if summary_data:
                        # 기존 데이터 업데이트
                        summary_data.value = value
                        summary_data.display_unit = unit
                    else:
                        # 새 데이터 생성
                        summary_data = SummaryFinancialData(
                            report_id=report.id,
                            company_id=company.id,
                            item_id=item_mapping.id,
                            year_month=data_year_month,
                            value=value,
                            display_unit=unit
                        )
                        db_session.add(summary_data)
            
            # 변경사항 커밋
            await db_session.commit()
            return True
            
        except Exception as e:
            await db_session.rollback()
            print(f"요약재무정보 저장 중 오류 발생: {e}")
            return False
```

## 5. 전체 파이프라인 통합

위 기능들을 통합한 전체 요약재무정보 추출 파이프라인입니다.

```python
async def process_financial_summary(company_code: str, report_file_path: str, report_type: str, report_year: int, 
                                    report_quarter: Optional[int] = None) -> bool:
    """
    요약재무정보 처리 파이프라인 함수
    
    Args:
        company_code: 기업 코드
        report_file_path: 보고서 파일 경로
        report_type: 보고서 유형 (annual, semi, quarter)
        report_year: 보고서 연도
        report_quarter: 보고서 분기
        
    Returns:
        처리 성공 여부
    """
    try:
        # 1. 요약재무정보 페이지 범위 찾기
        page_range = self.pdf_extractor.extract_summary_financial_pages(report_file_path)
        if page_range is None:
            print(f"요약재무정보 페이지를 찾을 수 없습니다: {company_code}")
            return False
        
        # 2. 테이블 추출
        tables = self.pdf_extractor.extract_summary_financial_tables(report_file_path, page_range)
        if not tables:
            print(f"요약재무정보 테이블 추출에 실패했습니다: {company_code}")
            return False
        
        # 3. LLM으로 데이터 구조화
        structured_data = structure_table_with_llm(tables)
        if "error" in structured_data:
            print(f"데이터 구조화에 실패했습니다: {company_code}")
            return False
        
        # 4. 데이터베이스 저장
        success = await save_summary_financial_data(
            company_code=company_code,
            report_type=report_type,
            report_year=report_year,
            report_quarter=report_quarter,
            structured_data=structured_data
        )
        
        return success
        
    except Exception as e:
        print(f"요약재무정보 처리 중 오류 발생: {company_code}, {e}")
        return False
```

## 6. 참고사항

1. 위 코드는 예시이며, 실제 환경에 맞게 수정이 필요합니다.
2. 오류 처리 및 로깅은 실제 프로젝트의 로깅 시스템을 활용하여 보완해야 합니다.
3. LLM 프롬프트는 실제 데이터 형태에 맞게 최적화가 필요합니다.
4. PDF 문서마다 구조가 다를 수 있으므로 예외 처리와 다양한 형태 대응이 필요합니다.
5. `extract_revenue_breakdown_data()` 함수 패턴을 참고하여 추가 개선하세요. 