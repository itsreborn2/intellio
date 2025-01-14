from typing import Dict, Any, List
from .base import BasePrompt

class ChatPrompt(BasePrompt):
    async def analyze(self, content: str, query: str, patterns: Dict[str, Any], query_analysis: Dict[str, Any]) -> str:
        """문서 분석 및 질문 답변
        
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

    def _get_query_type_prompt(self, query_analysis: Dict[str, Any]) -> str:
        """쿼리 타입에 따른 프롬프트 생성"""
        prompts = []
        
        if query_analysis.get("requires_all_docs"):
            prompts.append("""문서 분석 지침:
- 제공된 모든 문서를 순차적으로 분석하세요
- 각 문서의 핵심 정보를 명확히 구분하여 제시하세요
- 문서 간 상충되는 정보가 있다면 반드시 표시하세요
- 누락된 정보가 있다면 명시하세요""")

        if query_analysis.get("type") == "comparison":
            prompts.append("""비교 분석 지침:
- 각 증권사의 의견을 다음 순서로 정리하세요:
  1. 투자의견/등급
  2. 목표가
  3. 핵심 논거
- 증권사별 차이점을 구체적으로 비교하세요
- 의견이 크게 다른 경우 그 이유를 분석하세요""")
        elif query_analysis.get("type") == "extraction":
            prompts.append("""정보 추출 지침:
- 요청된 정보를 문서별로 정확히 추출하세요
- 정보의 출처(증권사/날짜)를 함께 표시하세요
- 추출한 정보의 맥락도 간단히 설명하세요""")
        elif query_analysis.get("type") == "summary":
            prompts.append("""요약 지침:
- 각 문서의 핵심 주장을 한 줄로 요약하세요
- 중요한 수치와 변경사항을 포함하세요
- 전체 문서의 공통된 관점을 도출하세요""")
            
        if query_analysis.get("focus") == "financial":
            prompts.append("""재무 분석 지침:
- 모든 수치는 단위와 함께 정확히 표시하세요
- 변경된 수치는 변경 폭과 방향을 명시하세요
- 증권사별 전망과 근거를 구분하여 설명하세요
- 업종 및 시장 상황도 함께 고려하세요""")
            
        return "\n\n".join(prompts) if prompts else ""

    def _get_time_range_prompt(self, query_analysis: Dict[str, Any]) -> str:
        """시간 범위에 따른 프롬프트 생성"""
        # 시간 관련 프롬프트는 선택적으로 적용
        if not query_analysis.get("focus") == "financial":
            return ""
            
        return """시간 분석 지침:
- 제시된 기간의 데이터를 명확히 구분하여 분석하세요
- 시간에 따른 변화가 있다면 구체적으로 설명하세요"""

    def _get_pattern_prompt(self, patterns: Dict[str, Any]) -> str:
        """패턴 분석 결과에 따른 프롬프트 생성"""
        prompts = []
        
        if patterns.get("total_documents") != patterns.get("found_documents"):
            prompts.append(f"- 총 {patterns['total_documents']}개의 문서 중 {patterns['found_documents']}개만 분석되었습니다. 누락된 문서가 없는지 확인하세요.")
        
        if patterns.get("common_terms"):
            terms = ", ".join(patterns["common_terms"])
            prompts.append(f"- 다음 주요 용어들의 맥락을 설명하세요: {terms}")
            
        if patterns.get("has_tables"):
            prompts.append("- 표의 데이터를 체계적으로 분석하세요")
            
        if patterns.get("date_range"):
            prompts.append("- 제시된 기간 내의 변화를 분석하세요")
            
        return "\n".join(prompts) if prompts else ""

    def _generate_prompt(self, content: str, query: str, patterns: Dict[str, Any], query_analysis: Dict[str, Any]) -> str:
        """분석용 프롬프트 생성"""
        # 기본 프롬프트
        base_prompt = """당신은 문서를 분석하고 사용자의 질문에 답변하는 AI 어시스턴트입니다.
주어진 문서의 내용만을 기반으로 답변해야 하며, 문서에 없는 내용은 답변하지 마세요."""

        # 쿼리 타입별 프롬프트
        type_prompt = self._get_query_type_prompt(query_analysis)
        
        # 시간 범위별 프롬프트
        time_prompt = self._get_time_range_prompt(query_analysis)
        
        # 패턴 분석 프롬프트
        pattern_prompt = self._get_pattern_prompt(patterns)
        
        # 응답 형식
        response_format = """1. 핵심 답변
   - 질문에 대한 직접적인 답변을 1-2줄로 제시하세요.

2. 상세 설명
   - 답변의 근거가 되는 문서의 내용을 인용하세요.
   - 관련된 맥락과 배경을 설명하세요.

3. 결론
   - 답변을 간단히 요약하세요."""

        # 분석 지침 결합
        analysis_instructions = "\n\n".join(filter(None, [
            type_prompt,
            time_prompt,
            pattern_prompt
        ]))
        
        # 최종 프롬프트 조합
        parts = [
            base_prompt,
            f"\n문서 내용:\n{content}",
            f"\n질문:\n{query}"
        ]
        
        if analysis_instructions:
            parts.append(f"\n분석 지침:\n{analysis_instructions}")
            
        parts.append(f"\n응답 형식:\n{response_format}")
        
        return "\n".join(parts)
