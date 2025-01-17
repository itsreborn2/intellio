from typing import Dict, Any, List
from .base import BasePrompt
import asyncio

class TablePrompt(BasePrompt):
    async def analyze(self, content: str, query: str, patterns: Dict[str, Any], query_analysis: Dict[str, Any]) -> str:
        """문서 분석 및 정보 추출
        
        Args:
            content: 문서 내용
            query: 사용자 질문
            patterns: 문서 패턴
            query_analysis: 쿼리 분석 결과
            
        Returns:
            str: 분석 결과
        """
        context = {
            "content": content,
            "query": query,
            "patterns": patterns,
            "query_analysis": query_analysis
        }
        
        prompt = self._generate_prompt(content, query, patterns, query_analysis)
        return await self.process_prompt(prompt, context)

    def _get_extraction_context(self, query_analysis: Dict[str, Any], patterns: Dict[str, Any]) -> str:
        """추출 컨텍스트 생성"""
        query_type = query_analysis.get("query_type", "general")
        doc_type = patterns.get("document_type", "general")
        
        # 기본 추출 지침
        base_instruction = """다음 지침에 따라 정보를 추출하세요:
- 요청된 정보만 정확히 추출
- 불필요한 설명이나 부가 정보 제외
- 정보가 없는 경우 '정보 없음' 반환"""
        
        # 쿼리 타입별 추가 지침
        if query_type == "company":
            return base_instruction + """
- 기업명만 추출
- 법인격(주식회사 등) 제외
- 복수 기업은 쉼표로 구분"""
            
        elif query_type == "date":
            return base_instruction + """
- 날짜 정보만 추출
- YYYY.MM.DD 형식 사용"""
            
        elif query_type == "amount":
            return base_instruction + """
- 금액 정보만 추출
- 숫자와 '원' 단위만 표시"""
            
        elif query_type == "person":
            return base_instruction + """
- 이름만 추출
- 직위/직책 제외"""
            
        return base_instruction

    def _generate_prompt(self, content: str, query: str, patterns: Dict[str, Any], query_analysis: Dict[str, Any]) -> str:
        """테이블 모드용 프롬프트 생성
        
        Args:
            content: 문서 내용
            query: 분석 요청
            patterns: 문서 패턴
            query_analysis: 쿼리 분석 결과
            
        Returns:
            str: 생성된 프롬프트
        """
        extraction_context = self._get_extraction_context(query_analysis, patterns)
        
        # RAG 분석 결과 활용
        focus = query_analysis.get("focus", "")
        time_range = query_analysis.get("time_range", "")
        
        context_info = f"""분석 정보:
- 검색 대상: {focus if focus else '전체'}
- 시간 범위: {time_range if time_range else '전체'}
- 문서 유형: {patterns.get('document_type', '일반')}"""
        
        return f"""{extraction_context}

{context_info}

다음 문서에서 '{query}'에 대한 정보를 추출하세요.

문서 내용:
{content}"""

    async def analyze_documents(self, documents: List[Dict[str, str]], query: str, patterns: Dict[str, Any], query_analysis: Dict[str, Any]) -> List[str]:
        """테이블 모드: 여러 문서 동시 분석
        
        Args:
            documents: 분석할 문서 리스트
            query: 분석 요청
            patterns: 문서 패턴
            query_analysis: 쿼리 분석 결과
            
        Returns:
            List[str]: 각 문서별 분석 결과
        """
        tasks = []
        for doc in documents:
            context = {
                "content": doc['content'],
                "query": query,
                "patterns": patterns,
                "query_analysis": query_analysis
            }
            prompt = self._generate_prompt(doc['content'], query, patterns, query_analysis)
            tasks.append(self.process_prompt(prompt, context.copy()))
        
        return await asyncio.gather(*tasks)
