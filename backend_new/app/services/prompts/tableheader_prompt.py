from typing import Dict, Any
from .base import BasePrompt
from app.utils.common import measure_time_async

class TableHeaderPrompt(BasePrompt):
    @measure_time_async
    async def generate_title(self, query: str) -> str:
        """테이블 제목 생성
        
        Args:
            query: 사용자 요청
            
        Returns:
            str: 생성된 테이블 제목
        """
        context = {
            "query": query
        }
        
        prompt = self._generate_prompt(query)
        return await self.process_prompt_async(prompt, context)

    def _generate_prompt(self, query: str) -> str:
        """테이블 제목 생성용 프롬프트 생성
        
        Args:
            query: 사용자 요청
            
        Returns:
            str: 생성된 프롬프트
        """
        return f"""사용자의 요청을 테이블 제목으로 변환해주세요.

요청 내용:
{query}

요구사항:
- 요청 내용을 2-3단어로 된 간단한 테이블 제목으로 만들어주세요
- 테이블의 목적과 내용을 잘 나타내는 단어를 선택해주세요
- 불필요한 조사나 부가 설명은 제외해주세요
- 한글로 작성해주세요

예시:
- "2023년도 분기별 매출액과 영업이익을 보여줘" -> "분기실적현황"
- "부서별 직원 수와 평균 연봉을 알려줘" -> "부서인력현황"
- "컨퍼런스콜 참석자 명단을 보여줘" -> "참석자목록"
- "Q&A 세션의 발표자와 질문 내용" -> "질의응답현황"
- "각 세션별 발표자와 토론자 목록" -> "발표자명단"
- "컨퍼런스 참가자들의 소속과 직책" -> "참가자정보"

답변 형식:
제목만 2-3단어로 작성해주세요."""
