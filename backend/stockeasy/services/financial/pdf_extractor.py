import fitz  # PyMuPDF
import pdfplumber
import re
import os
from typing import List, Dict, Optional, Tuple, Any, Union
from loguru import logger


# logger = logging.getLogger(__name__)


class FinancialPDFExtractor:
    """
    재무 보고서 PDF에서 데이터를 추출하는 클래스
    """
    
    def __init__(self):
        self.summary_keywords = [
            "요약재무정보", "요약 재무정보", "요약 재무 정보", 
            "요약 연결재무정보", "요약재무제표", "요약 재무제표"
        ]
    
    def extract_summary_financial_pages(self, pdf_path: str) -> Optional[Tuple[int, int]]:
        """
        PDF 파일에서 요약재무정보 섹션의 페이지 범위를 찾는 함수
        
        Args:
            pdf_path: PDF 파일 경로
            
        Returns:
            튜플 (시작 페이지, 끝 페이지) 또는 찾지 못하면 None 반환
        """
        try:
            # PDF 문서 열기
            doc = fitz.open(pdf_path)
            
            # 목차 가져오기
            toc = doc.get_toc()
            
            # 시작 페이지와 끝 페이지
            start_page = None
            end_page = None
            
            # 목차 항목들을 순회하며 요약재무정보 섹션 찾기
            for i, item in enumerate(toc):
                level, title, page = item
                
                for keyword in self.summary_keywords:
                    if keyword in title:
                        # 시작 페이지 설정 (목차의 페이지는 1부터 시작하지만 fitz는 0부터 시작)
                        start_page = page - 1
                        
                        # 다음 동일 레벨 또는 상위 레벨 목차 항목 찾기
                        for next_item in toc[i+1:]:
                            next_level, next_title, next_page = next_item
                            if next_level <= level:
                                # 다음 섹션 시작 직전 페이지를 끝 페이지로 설정
                                end_page = next_page - 2
                                break
                        
                        # 다음 섹션을 찾지 못한 경우 기본적으로 시작 페이지 + 3으로 설정
                        if end_page is None:
                            end_page = min(start_page + 3, len(doc) - 1)
                            
                logger.info(f"요약재무정보 섹션 찾음: 페이지 {start_page+1}~{end_page+1}")
                return (start_page, end_page)
            
            # 목차에서 찾지 못한 경우 본문 내용에서 찾기 시도
            for page_num in range(min(30, len(doc))):  # 처음 30페이지만 검색
                page = doc[page_num]
                text = page.get_text()
                for keyword in self.summary_keywords:
                    if keyword in text and ("5년" in text or "3년" in text):
                        # 발견된 페이지부터 3페이지를 범위로 설정
                        start_page = page_num
                        end_page = min(start_page + 3, len(doc) - 1)
                logger.info(f"본문에서 요약재무정보 섹션 찾음: 페이지 {start_page+1}~{end_page+1}")
                return (start_page, end_page)
            
            logger.warning(f"요약재무정보 페이지를 찾을 수 없습니다: {pdf_path}")
            return None
        except Exception as e:
            logger.error(f"요약재무정보 페이지 추출 중 오류 발생: {e}")
            return None
        finally:
            if 'doc' in locals():
                doc.close()
    
    # 기존 단일 페이지 처리 함수 유지 (호환성을 위해)
    def extract_summary_financial_page(self, pdf_path: str) -> Optional[int]:
        """
        PDF 파일에서 요약재무정보 섹션의 시작 페이지 번호를 찾는 함수 (호환성 유지)
        
        Args:
            pdf_path: PDF 파일 경로
            
        Returns:
            요약재무정보 섹션의 시작 페이지 번호 (0부터 시작), 찾지 못하면 None 반환
        """
        page_range = self.extract_summary_financial_pages(pdf_path)
        if page_range:
            return page_range[0]  # 시작 페이지만 반환
        return None
    
    def extract_summary_financial_tables(self, pdf_path: str, page_range: Tuple[int, int]) -> List[Dict[str, Any]]:
        """
        요약재무정보 테이블 추출
        
        Args:
            pdf_path: PDF 파일 경로
            page_range: 추출할 페이지 범위 (시작, 끝)
            
        Returns:
            추출된 테이블 목록 (단위 정보 포함)
        """
        start_page, end_page = page_range
        print_first = True
        try:
            with pdfplumber.open(pdf_path) as pdf:
                # 전체 페이지 컨텍스트 미리 추출
                page_contexts = []
                for page_num in range(start_page, end_page + 1):
                    if page_num >= len(pdf.pages):
                        break
                    
                    page = pdf.pages[page_num]
                    page_text = page.extract_text()
                    print(page_text)
                    unit_info = self._extract_unit_info(page_text)
                    
                    # 요약재무정보 관련 키워드 확인
                    is_summary_financial = any(keyword in page_text for keyword in self.summary_keywords)
                    
                    page_contexts.append({
                        "page_num": page_num,
                        "text": page_text,
                        "unit": unit_info,
                        "is_summary_financial": is_summary_financial
                    })
                
                # 페이지별로 테이블 추출
                raw_tables = []
                for ctx in page_contexts:
                    page_num = ctx["page_num"]
                    page = pdf.pages[page_num]
                    logger.info(f"페이지 {page_num+1}에서 테이블 추출 시도")
                    
                    # 테이블 추출 시도
                    tables = page.extract_tables()
                    
                    if not tables:
                        # 테이블 감지 실패 시 수동 테이블 추출 설정 적용
                        logger.info(f"기본 설정으로 테이블을 찾지 못해 수동 설정 적용: {pdf_path}, 페이지: {page_num+1}")
                        tables = page.extract_tables(
                            table_settings={
                                "vertical_strategy": "text",
                                "horizontal_strategy": "text",
                                "intersection_tolerance": 5
                            }
                        )
                    
                    # 추출된 데이터 전처리
                    for table_idx, table in enumerate(tables):
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
                            # 테이블 컨텍스트 분석
                            before_text, after_text = self._extract_table_context(ctx["text"], table_idx, tables)
                            
                            # 테이블과 컨텍스트 정보를 함께 저장
                            raw_tables.append({
                                "data": cleaned_table,
                                "unit": ctx["unit"],
                                "page": page_num + 1,
                                "before_text": before_text,
                                "after_text": after_text,
                                "is_summary_financial": ctx["is_summary_financial"]
                            })
                
                # 연속된 테이블 병합 처리
                processed_tables = self._merge_continuous_tables(raw_tables)
                
                total_range = f"{start_page+1}~{end_page+1}" if start_page != end_page else f"{start_page+1}"
                logger.info(f"테이블 추출 완료: 원본 {len(raw_tables)}개 테이블, 병합 후 {len(processed_tables)}개 테이블 (페이지 {total_range})")
                return processed_tables
                
        except Exception as e:
            logger.exception(f"테이블 추출 중 오류 발생: {pdf_path}, 오류: {str(e)}")
            return []
    
    def _extract_table_context(self, page_text: str, table_idx: int, tables: List) -> Tuple[str, str]:
        """
        페이지 텍스트에서 테이블 전후 컨텍스트 추출
        
        Args:
            page_text: 페이지 전체 텍스트
            table_idx: 현재 테이블 인덱스
            tables: 페이지의 모든 테이블
            
        Returns:
            (테이블 이전 텍스트, 테이블 이후 텍스트)
        """
        lines = page_text.split('\n')
        table_lines = []
        
        # 테이블에 포함된 텍스트 행 식별 (대략적으로)
        for table in tables:
            for row in table:
                for cell in row:
                    if cell:
                        cell_text = str(cell).strip()
                        # 테이블 행과 일치하거나 포함하는 페이지 행 찾기
                        for i, line in enumerate(lines):
                            if cell_text in line:
                                table_lines.append(i)
        
        table_lines = sorted(list(set(table_lines)))
        
        # 테이블 이전/이후 텍스트 분리
        if table_lines:
            before_start = max(0, min(table_lines) - 3)  # 테이블 시작 3줄 전부터
            after_end = min(len(lines), max(table_lines) + 3)  # 테이블 끝 3줄 후까지
            
            before_text = '\n'.join(lines[before_start:min(table_lines)])
            after_text = '\n'.join(lines[max(table_lines)+1:after_end])
            
            return before_text.strip(), after_text.strip()
        
        return "", ""
    
    def _merge_continuous_tables(self, tables: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        연속된 페이지에 걸친 테이블을 하나로 병합
        
        Args:
            tables: 원본 테이블 목록
            
        Returns:
            병합된 테이블 목록
        """
        if not tables or len(tables) < 2:
            return tables
            
        # 1. 테이블 그룹 후보 생성 (페이지 순서대로 인접한 테이블들)
        table_groups = []
        current_group = [tables[0]]
        
        for i in range(1, len(tables)):
            prev_table = tables[i-1]
            current_table = tables[i]
            
            # 페이지가 연속적인지 확인
            if current_table["page"] == prev_table["page"] + 1:
                current_group.append(current_table)
            else:
                # 연속되지 않는 페이지면 새 그룹 시작
                if current_group:
                    table_groups.append(current_group)
                current_group = [current_table]
        
        # 마지막 그룹 추가
        if current_group:
            table_groups.append(current_group)
        
        # 2. 각 그룹 내에서 테이블 병합 평가
        merged_tables = []
        
        for group in table_groups:
            if len(group) == 1:
                # 단일 테이블 그룹은 그대로 유지
                merged_tables.append(group[0])
                continue
            
            # 그룹 내 테이블들의 병합 가능성 평가
            merge_candidates = []
            current_candidate = [group[0]]
            
            for i in range(1, len(group)):
                prev_table = group[i-1]
                current_table = group[i]
                
                # 병합 점수 계산
                merge_score, reason = self._calculate_merge_score(prev_table, current_table)
                logger.info(f"테이블 병합 점수: {merge_score:.2f}, 이유: {reason}, 페이지: {prev_table['page']}→{current_table['page']}")
                
                # 점수가 임계값을 넘으면 병합 후보에 추가
                if merge_score >= 0.6:  # 60% 이상의 확신도
                    current_candidate.append(current_table)
                else:
                    # 낮은 점수면 이전 후보 완료하고 새 후보 시작
                    if current_candidate:
                        merge_candidates.append(current_candidate)
                    current_candidate = [current_table]
            
            # 마지막 후보 추가
            if current_candidate:
                merge_candidates.append(current_candidate)
            
            # 3. 병합 후보들을 실제로 병합
            for candidate in merge_candidates:
                if len(candidate) == 1:
                    merged_tables.append(candidate[0])
                else:
                    # 여러 테이블 병합
                    merged_table = self._merge_table_group(candidate)
                    merged_tables.append(merged_table)
        
        return merged_tables
    
    def _calculate_merge_score(self, table1: Dict[str, Any], table2: Dict[str, Any]) -> Tuple[float, str]:
        """
        두 테이블의 병합 가능성 점수 계산
        
        Args:
            table1: 첫 번째 테이블
            table2: 두 번째 테이블
            
        Returns:
            (병합 점수 0~1, 주요 판단 이유)
        """
        scores = []
        reasons = []
        
        # 1. 구조적 유사성 평가 (30%)
        structure_score = 0.0
        
        # 1.1 헤더 일치 확인
        if len(table1["data"]) > 0 and len(table2["data"]) > 0:
            header_similarity = self._calculate_header_similarity(table1["data"][0], table2["data"][0])
            if header_similarity > 0.8:
                structure_score += 0.15
                reasons.append(f"헤더 일치도 높음({header_similarity:.2f})")
            elif header_similarity > 0.5:
                structure_score += 0.1
                reasons.append(f"헤더 부분 일치({header_similarity:.2f})")
        
        # 1.2 열 개수 일치 확인
        if len(table1["data"]) > 0 and len(table2["data"]) > 0:
            cols1 = len(table1["data"][0])
            cols2 = len(table2["data"][0])
            
            if cols1 == cols2:
                structure_score += 0.15
                reasons.append(f"열 개수 일치({cols1})")
            elif abs(cols1 - cols2) <= 1:  # 하나 정도 차이는 허용
                structure_score += 0.05
                reasons.append(f"열 개수 유사({cols1}vs{cols2})")
        
        scores.append(structure_score)
        
        # 2. 내용 연속성 평가 (40%)
        content_score = 0.0
        
        # 2.1 행 내용 연속성 확인
        row_continuity = self._check_row_continuity(table1, table2)
        if row_continuity > 0.8:
            content_score += 0.25
            reasons.append("행 연속성 높음")
        elif row_continuity > 0.5:
            content_score += 0.15
            reasons.append("행 연속성 중간")
        elif row_continuity > 0.3:
            content_score += 0.05
            reasons.append("행 연속성 낮음")
        
        # 2.2 데이터 유형 일관성
        if self._check_data_type_consistency(table1, table2):
            content_score += 0.15
            reasons.append("데이터 유형 일관성 있음")
        
        scores.append(content_score)
        
        # 3. 컨텍스트 평가 (30%)
        context_score = 0.0
        
        # 3.1 단위 정보 일치
        if table1.get("unit") == table2.get("unit"):
            context_score += 0.1
            reasons.append("단위 일치")
        
        # 3.2 테이블 전후 문맥 연속성
        text_continuity = self._check_text_continuity(table1, table2)
        if text_continuity:
            context_score += 0.2
            reasons.append("문맥 연속성 있음")
        
        scores.append(context_score)
        
        # 4. 최종 점수 계산 (가중 평균)
        weights = [0.3, 0.4, 0.3]  # 구조 30%, 내용 40%, 컨텍스트 30%
        final_score = sum(s * w for s, w in zip(scores, weights))
        
        # 5. 주요 이유 요약
        if not reasons:
            main_reason = "병합 기준 미달"
        else:
            main_reason = ", ".join(reasons[:3])  # 상위 3개 이유만
        
        return final_score, main_reason
    
    def _check_row_continuity(self, table1: Dict[str, Any], table2: Dict[str, Any]) -> float:
        """
        두 테이블 간의 행 연속성 점수 계산
        
        Args:
            table1: 첫 번째 테이블
            table2: 두 번째 테이블
            
        Returns:
            연속성 점수 (0~1)
        """
        # 빈 테이블 처리
        if not table1["data"] or not table2["data"]:
            return 0.0
        
        # 테이블 데이터
        table1_data = table1["data"]
        table2_data = table2["data"]
        
        # 첫 테이블의 마지막 행과 두 번째 테이블의 첫 행 사이의 연속성 체크
        continuity_signals = 0
        total_signals = 5  # 검사할 신호 총 개수
        
        # 1. 첫 열 기준 연속성 (목차 항목 등의 연속성)
        if len(table1_data) >= 1 and len(table2_data) >= 1:
            last_rows = table1_data[-min(3, len(table1_data)):]
            first_rows = table2_data[:min(3, len(table2_data))]
            
            first_col_pattern = self._detect_first_column_pattern(last_rows, first_rows)
            if first_col_pattern > 0:
                continuity_signals += first_col_pattern
        
        # 2. 숫자 데이터 연속성 (년도, 시퀀스 등)
        if self._check_numeric_continuity(table1_data, table2_data):
            continuity_signals += 1
        
        # 3. 테이블 컨텐츠 유형 일치
        if self._check_content_type_similarity(table1_data, table2_data):
            continuity_signals += 1
        
        # 4. 테이블 형태(행/열 수) 유사성
        if self._check_table_shape_similarity(table1_data, table2_data):
            continuity_signals += 1
        
        # 정규화된 점수 반환
        return continuity_signals / total_signals
    
    def _detect_first_column_pattern(self, last_rows: List[List[str]], first_rows: List[List[str]]) -> float:
        """
        첫 번째 열의 패턴 연속성 감지
        
        Args:
            last_rows: 첫 번째 테이블의 마지막 몇 행
            first_rows: 두 번째 테이블의 첫 몇 행
            
        Returns:
            연속성 점수 (0~2)
        """
        # 양쪽 테이블의 첫 열 텍스트 추출
        last_col_texts = []
        for row in last_rows:
            if row and len(row) > 0:
                text = row[0].strip()
                if text:
                    last_col_texts.append(text.lower())
        
        first_col_texts = []
        for row in first_rows:
            if row and len(row) > 0:
                text = row[0].strip()
                if text:
                    first_col_texts.append(text.lower())
        
        if not last_col_texts or not first_col_texts:
            return 0
        
        # 패턴 유형 감지
        pattern_score = 0
        
        # 1. 계층적 목차 패턴 (들여쓰기, 기호 등)
        hierarchy_markers = [
            ('ㆍ', 'ㆍ'),  # 둘 다 세부 항목
            ('[', '['),    # 둘 다 분류 항목
            ('ㆍ', '['),   # 세부 항목 다음 분류 항목
            ('[', 'ㆍ')    # 분류 항목 다음 세부 항목
        ]
        
        for last, first in hierarchy_markers:
            if (any(t.startswith(last) for t in last_col_texts[-2:]) and
                any(t.startswith(first) for t in first_col_texts[:2])):
                pattern_score += 1
                break
        
        # 2. 항목 흐름 패턴 (재무제표 항목 순서)
        financial_sequences = [
            # 손익계산서 → 재무상태표
            (['매출', '수익', '이익', '손실', '영업', '순이익'], ['자산', '부채', '자본', '유동', '비유동']),
            # 재무상태표 항목 → 주당 지표
            (['자산', '부채', '자본', '유동', '비유동'], ['주당', '수익', '이익']),
            # 주당 지표 → 기타 정보
            (['주당', '순이익'], ['회사', '연결', '종속'])
        ]
        
        for seq_last, seq_first in financial_sequences:
            if (any(any(term in t for term in seq_last) for t in last_col_texts[-2:]) and
                any(any(term in t for term in seq_first) for t in first_col_texts[:2])):
                pattern_score += 1
                break
        
        return pattern_score
    
    def _check_numeric_continuity(self, table1_data: List[List[str]], table2_data: List[List[str]]) -> bool:
        """
        두 테이블 간에 숫자 데이터의 연속성 확인
        
        Args:
            table1_data: 첫 번째 테이블 데이터
            table2_data: 두 번째 테이블 데이터
            
        Returns:
            숫자 데이터 연속성 여부
        """
        # 헤더 행에서 연도 패턴 확인
        if len(table1_data) > 0 and len(table2_data) > 0:
            # 헤더 행
            header1 = table1_data[0]
            header2 = table2_data[0]
            
            # 연도 패턴 검출
            years1 = self._extract_years(header1)
            years2 = self._extract_years(header2)
            
            # 동일한 연도 패턴이면 연속성 높음
            if years1 and years2 and years1 == years2:
                return True
        
        return False
    
    def _extract_years(self, row: List[str]) -> List[int]:
        """
        행에서 연도 정보 추출
        
        Args:
            row: 테이블 행
            
        Returns:
            추출된 연도 목록
        """
        years = []
        for cell in row:
            # 연도를 나타내는 패턴 찾기
            year_matches = re.findall(r'20\d{2}|19\d{2}', cell)
            for match in year_matches:
                try:
                    year = int(match)
                    if 1900 <= year <= 2100:  # 유효한 연도 범위
                        years.append(year)
                except ValueError:
                    continue
        
        return sorted(years)
    
    def _check_content_type_similarity(self, table1_data: List[List[str]], table2_data: List[List[str]]) -> bool:
        """
        두 테이블의 컨텐츠 유형 유사성 확인
        
        Args:
            table1_data: 첫 번째 테이블 데이터
            table2_data: 두 번째 테이블 데이터
            
        Returns:
            컨텐츠 유형 유사 여부
        """
        # 각 테이블의 데이터 유형 분석 (숫자 비율)
        def get_numeric_ratio(table_data):
            total_cells = 0
            numeric_cells = 0
            
            # 헤더 제외
            for row_idx, row in enumerate(table_data):
                if row_idx == 0:  # 첫 행 건너뛰기 (헤더)
                    continue
                    
                for cell in row:
                    if not cell.strip():
                        continue
                        
                    total_cells += 1
                    # 숫자로 변환 가능한지 확인 (쉼표, 소수점 제거)
                    cell_clean = re.sub(r'[,\s]', '', cell)
                    if re.match(r'^-?\d+(\.\d+)?$', cell_clean):
                        numeric_cells += 1
            
            return numeric_cells / max(1, total_cells)
        
        ratio1 = get_numeric_ratio(table1_data)
        ratio2 = get_numeric_ratio(table2_data)
        
        # 비율 차이가 20% 이내면 유사하다고 판단
        return abs(ratio1 - ratio2) <= 0.2
    
    def _check_table_shape_similarity(self, table1_data: List[List[str]], table2_data: List[List[str]]) -> bool:
        """
        두 테이블의 형태(행/열 수) 유사성 확인
        
        Args:
            table1_data: 첫 번째 테이블 데이터
            table2_data: 두 번째 테이블 데이터
            
        Returns:
            테이블 형태 유사 여부
        """
        # 열 개수 확인
        if len(table1_data) > 0 and len(table2_data) > 0:
            cols1 = len(table1_data[0])
            cols2 = len(table2_data[0])
            
            # 열 개수가 같거나 ±1 차이면 유사
            if abs(cols1 - cols2) <= 1:
                return True
        
        return False
    
    def _check_data_type_consistency(self, table1: Dict[str, Any], table2: Dict[str, Any]) -> bool:
        """
        두 테이블의 데이터 유형 일관성 확인
        
        Args:
            table1: 첫 번째 테이블
            table2: 두 번째 테이블
            
        Returns:
            데이터 유형 일관성 여부
        """
        # 테이블의 셀 데이터 유형 패턴 분석 (텍스트, 숫자, 날짜 등)
        table1_data = table1["data"]
        table2_data = table2["data"]
        
        if not table1_data or not table2_data:
            return False
        
        # 각 열의 데이터 유형 분석
        def get_column_type_signature(table_data):
            if not table_data or len(table_data) <= 1:
                return []
                
            # 첫 행은 헤더로 간주하고 건너뜀
            data_rows = table_data[1:]
            
            # 열 개수
            if not data_rows or not data_rows[0]:
                return []
                
            col_count = len(data_rows[0])
            col_signatures = []
            
            for col_idx in range(col_count):
                text_count = 0
                number_count = 0
                date_count = 0
                total_count = 0
                
                for row in data_rows:
                    if col_idx < len(row):
                        cell = row[col_idx].strip()
                        if not cell:
                            continue
                            
                        total_count += 1
                        
                        # 숫자 여부 확인
                        cell_clean = re.sub(r'[,\s%]', '', cell)
                        if re.match(r'^-?\d+(\.\d+)?$', cell_clean):
                            number_count += 1
                        # 날짜 여부 확인
                        elif re.match(r'\d{4}[/\-\.]\d{1,2}[/\-\.]\d{1,2}', cell):
                            date_count += 1
                        else:
                            text_count += 1
                
                # 우세한 유형 결정
                if total_count > 0:
                    type_ratios = {
                        'text': text_count / total_count,
                        'number': number_count / total_count,
                        'date': date_count / total_count
                    }
                    dominant_type = max(type_ratios, key=type_ratios.get)
                    col_signatures.append(dominant_type)
                else:
                    col_signatures.append('unknown')
            
            return col_signatures
        
        sig1 = get_column_type_signature(table1_data)
        sig2 = get_column_type_signature(table2_data)
        
        # 시그니처 길이가 다르면 일관성 없음
        if not sig1 or not sig2 or len(sig1) != len(sig2):
            return False
        
        # 시그니처 일치 비율 계산
        match_count = sum(1 for t1, t2 in zip(sig1, sig2) if t1 == t2)
        match_ratio = match_count / len(sig1)
        
        # 70% 이상 일치하면 일관성 있다고 판단
        return match_ratio >= 0.7
    
    def _check_text_continuity(self, table1: Dict[str, Any], table2: Dict[str, Any]) -> bool:
        """
        두 테이블 간의 텍스트 문맥 연속성 확인
        
        Args:
            table1: 첫 번째 테이블
            table2: 두 번째 테이블
            
        Returns:
            텍스트 연속성 여부
        """
        # 테이블 전후 텍스트 분석
        after_text = table1.get("after_text", "").lower()
        before_text = table2.get("before_text", "").lower()
        
        # 페이지 번호, 빈 줄 등 무시
        if re.match(r'^[\d\s\.\-페이지page]+$', after_text):
            after_text = ""
        if re.match(r'^[\d\s\.\-페이지page]+$', before_text):
            before_text = ""
        
        # 연속성 힌트 확인
        continuity_hints = ["계속", "이어서", "다음", "계속됨", "연결", "관련", "continued"]
        section_markers = ["요약", "재무", "정보", "현황", "자료", "실적", "보고서"]
        
        # 기본 연속성 힌트
        basic_continuity = any(hint in after_text or hint in before_text for hint in continuity_hints)
        
        # 섹션 연속성 (두 번째 테이블 앞에 섹션 마커가 없으면 연속일 가능성)
        no_section_break = not any(marker in before_text for marker in section_markers)
        
        # 페이지 번호 이외에 텍스트가 거의 없으면 연속일 가능성
        minimal_text = len(before_text.strip()) < 20
        
        return basic_continuity or (no_section_break and minimal_text)
    
    def _calculate_header_similarity(self, header1: List[str], header2: List[str]) -> float:
        """
        두 테이블 헤더의 유사도 계산
        
        Args:
            header1: 첫 번째 테이블 헤더
            header2: 두 번째 테이블 헤더
            
        Returns:
            헤더 유사도 (0~1)
        """
        # 빈 헤더 처리
        if not header1 or not header2:
            return 0.0
        
        # 헤더 정규화
        norm_header1 = [cell.strip().lower() for cell in header1 if cell.strip()]
        norm_header2 = [cell.strip().lower() for cell in header2 if cell.strip()]
        
        if not norm_header1 or not norm_header2:
            return 0.0
        
        # 최소 비교 길이 (양쪽 중 짧은 쪽)
        min_len = min(len(norm_header1), len(norm_header2))
        
        # 일치하는 셀 개수
        matches = 0
        for i in range(min_len):
            # 정확히 일치하는 경우
            if norm_header1[i] == norm_header2[i]:
                matches += 1
            # 부분 일치하는 경우 (한쪽이 다른 쪽의 부분 문자열)
            elif norm_header1[i] in norm_header2[i] or norm_header2[i] in norm_header1[i]:
                matches += 0.5
            # 유사도 높은 경우 (편집 거리 기준)
            elif self._normalized_levenshtein(norm_header1[i], norm_header2[i]) <= 0.25:  # 25% 이내 차이
                matches += 0.3
        
        # 전체 셀 대비 일치 비율
        return matches / min_len
    
    def _normalized_levenshtein(self, s1: str, s2: str) -> float:
        """
        정규화된 레벤슈타인 거리 계산 (0~1, 값이 낮을수록 유사)
        
        Args:
            s1: 첫 번째 문자열
            s2: 두 번째 문자열
            
        Returns:
            정규화된 편집 거리
        """
        # 빈 문자열 처리
        if not s1 and not s2:
            return 0.0
        if not s1 or not s2:
            return 1.0
            
        # 레벤슈타인 거리 계산
        m, n = len(s1), len(s2)
        
        # 한 문자열이 다른 것의 부분 문자열이면 빠른 결과
        if s1 in s2 or s2 in s1:
            return abs(m - n) / max(m, n)
            
        # 전체 계산
        d = [[0] * (n + 1) for _ in range(m + 1)]
        
        for i in range(m + 1):
            d[i][0] = i
        for j in range(n + 1):
            d[0][j] = j
            
        for j in range(1, n + 1):
            for i in range(1, m + 1):
                if s1[i-1] == s2[j-1]:
                    d[i][j] = d[i-1][j-1]
                else:
                    d[i][j] = min(
                        d[i-1][j] + 1,  # 삭제
                        d[i][j-1] + 1,  # 삽입
                        d[i-1][j-1] + 1 # 대체
                    )
        
        # 최대 가능 편집 거리로 정규화
        return d[m][n] / max(m, n)
    
    def _merge_table_group(self, table_group: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        테이블 그룹을 하나의 테이블로 병합
        
        Args:
            table_group: 병합할 테이블 그룹
            
        Returns:
            병합된 테이블
        """
        if len(table_group) == 1:
            return table_group[0]
        
        # 첫 번째 테이블을 기준으로 병합
        merged_table = table_group[0].copy()
        merged_data = merged_table["data"].copy()
        
        # 페이지 범위 설정
        merged_table["page_range"] = [merged_table["page"], table_group[-1]["page"]]
        
        # 이후 테이블들을 병합
        for i in range(1, len(table_group)):
            next_table = table_group[i]
            next_data = next_table["data"]
            
            # 헤더가 같은지 확인하여 중복 헤더 제거
            if (len(merged_data) > 0 and len(next_data) > 0 and 
                self._calculate_header_similarity(merged_data[0], next_data[0]) > 0.7):
                next_data = next_data[1:]  # 첫 번째 행(헤더) 제거
            
            # 데이터 병합
            merged_data.extend(next_data)
        
        # 빈 행 제거
        cleaned_data = []
        for row in merged_data:
            if any(cell.strip() for cell in row):
                cleaned_data.append(row)
        
        merged_table["data"] = cleaned_data
        
        # 병합 로그
        source_pages = [t["page"] for t in table_group]
        logger.info(f"테이블 병합 완료: 페이지 {source_pages}, 최종 행 수: {len(cleaned_data)}")
        
        return merged_table
    
    def _extract_unit_info(self, page_text: str) -> str:
        """
        페이지 텍스트에서 단위 정보 추출
        
        Args:
            page_text: 페이지 전체 텍스트
            
        Returns:
            추출된 단위 정보 (기본값: '원')
        """
        # 다양한 단위 패턴 탐색 (예: "단위: 백만원", "(단위: 천원)", "단위 : 억원" 등)
        unit_patterns = [
            r'단위\s*:\s*(\S+원)',
            r'\(\s*단위\s*:\s*(\S+원)\s*\)',
            r'단위\s*-\s*(\S+원)',
            r'\(\s*단위\s*\S*\s*(\S+원)\s*\)'
        ]
        
        for pattern in unit_patterns:
            match = re.search(pattern, page_text)
            if match:
                return match.group(1)
        
        # 일반적인 단위 키워드 검색
        common_units = ["백만원", "천원", "억원", "조원", "만원"]
        for unit in common_units:
            if unit in page_text:
                logger.info(f"키워드 검색으로 단위 감지: {unit}")
                return unit
        
        # 기본값 반환
        return "원"
    
    def preprocess_table_data(self, tables: List[Dict[str, Any]]) -> str:
        """
        추출된 테이블 데이터 전처리하여 텍스트로 변환
        
        Args:
            tables: 추출된 테이블 목록 (단위 정보 포함)
            
        Returns:
            전처리된 텍스트
        """
        result = []
        
        for i, table_info in enumerate(tables):
            table = table_info["data"]
            unit = table_info["unit"]
            page = table_info["page"]
            
            # 테이블 헤더 추가
            result.append(f"\n--- 테이블 {i+1} (페이지 {page}, 단위: {unit}) ---\n")
            
            # 테이블 내용 추가
            for row in table:
                result.append("\t".join(row))
            
        return "\n".join(result) 