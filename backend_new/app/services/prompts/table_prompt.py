from typing import Dict, Any
from .base import BasePrompt

class TablePrompt(BasePrompt):
    async def analyze(self, content: str, query: str) -> str:
        """테이블 데이터 분석
        
        Args:
            content: 문서 내용
            query: 분석 요청
            
        Returns:
            str: 분석 결과
        """
        context = {
            "content": content,
            "query": query
        }
        
        prompt = self._generate_prompt(content, query)
        return await self.process_prompt(prompt, context)

    def _generate_prompt(self, content: str, query: str) -> str:
        """테이블 분석용 프롬프트 생성
        
        Args:
            content: 문서 내용
            query: 분석 요청
            
        Returns:
            str: 생성된 프롬프트
        """
        return f"""다음 문서에서 요청한 정보를 추출하여 요구형태로 가공해주세요.

문서 내용:
{content}

분석 요청:
{query}

요구사항:
- 문서에서 요청한 정보만을 정확하게 추출해주세요
- 추출한 정보는 테이블 셀에 들어갈 수 있도록 간단명료하게 정리해주세요
- 수치 데이터는 숫자 형태로 변환하여 제시해주세요
- 날짜는 YYYY-MM-DD 형식으로 통일해주세요
- 불필요한 설명이나 부가 정보는 제외해주세요

예시:
[요청] "각 부서의 2023년 4분기 매출액을 알려줘"
[응답] 42000000

[요청] "지난달 입사한 신규 직원의 이름과 부서를 알려줘"
[응답] 홍길동/영업팀

[요청] "이 계약서의 계약기간이 어떻게 되나요?"
[응답] 2024-01-01~2024-12-31

답변 형식:
- 셀에 들어갈 값만 간단히 작성
- 부가 설명 없이 데이터만 제시"""
