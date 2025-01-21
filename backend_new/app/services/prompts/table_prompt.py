from typing import Dict, Any, List
from .base import BasePrompt
import asyncio
import logging
from loguru import logger
import json
from app.utils.common import measure_time_async

logger = logging.getLogger(__name__)

class TablePrompt(BasePrompt):
    def __init__(self, *args, **kwargs):
        # patterns 파라미터가 있다면 제거
        if 'patterns' in kwargs:
            del kwargs['patterns']
        super().__init__(*args, **kwargs)

    async def analyze_async(self, content: str, query: str, keywords: Dict[str, Any], query_analysis: Dict[str, Any]) -> str:
        """문서 분석 및 정보 추출
        
        Args:
            content: 문서 내용
            query: 사용자 질문
            keywords: 문서 키워드
            query_analysis: 쿼리 분석 결과
            
        Returns:
            str: 분석 결과 텍스트
        """
        try:
            logger.info(f"analyze_async 진입")
            # 입력값 검증
            if not content or not isinstance(content, str):
                return "문서 내용이 비어있거나 올바르지 않습니다."
            if not query or not isinstance(query, str):
                return "질문이 비어있거나 올바르지 않습니다."
            if not isinstance(keywords, dict):
                return "키워드가 올바르지 않은 형식입니다."
            if not isinstance(query_analysis, dict):
                return "쿼리 분석 결과가 올바르지 않은 형식입니다."
            
            # 컨텍스트 준비 및 검증
            context = {
                "content": content[:1000],  # 컨텍스트 크기 제한
                "query": query,
                "keywords": {k: v for k, v in keywords.items() if v},  # 빈 값 제거
                "query_analysis": {
                    "doc_type": query_analysis.get("doc_type", "general"),
                    "focus_area": query_analysis.get("focus_area", "general"),
                    "analysis_type": query_analysis.get("analysis_type", "basic")
                }
            }
            
            # 프롬프트 생성 및 처리
            try:
                logger.info(f"analyze_async 진입 2")
                prompt = self._generate_prompt(content, query, keywords, query_analysis)
                logger.info(f"prompt : {prompt[:100]}")
                result = await self.process_prompt_async(prompt, context)
                logger.info(f"result : {result[:100]}")
                
                if not result:
                    return "문서에서 관련 내용을 찾을 수 없습니다."
                
                # JSON 문자열인 경우 파싱
                try:
                    if isinstance(result, str) and result.strip().startswith('{'):
                        parsed_result = json.loads(result)
                        if isinstance(parsed_result, dict):
                            # content 키가 있으면 해당 내용만 반환
                            if "content" in parsed_result:
                                result_content = parsed_result["content"]
                            else:
                                result_content = str(parsed_result)
                        else:
                            result_content = str(parsed_result)
                    else:
                        result_content = str(result)
                except json.JSONDecodeError:
                    result_content = str(result)
                except Exception as e:
                    logger.error(f"분석 결과 처리 중 오류 발생: {str(e)}")
                    result_content = str(result)
                
                return result_content
                
            except Exception as e:
                logger.error(f"프롬프트 처리 중 오류 발생: {str(e)}")
                return f"문서 분석 중 오류가 발생했습니다: {str(e)}"
            
        except Exception as e:
            logger.error(f"문서 분석 중 오류 발생: {str(e)}")
            return "문서 분석 중 예상치 못한 오류가 발생했습니다."
    @measure_time_async
    def analyze(self, content: str, query: str, keywords: Dict[str, Any], query_analysis: Dict[str, Any]) -> str:
        """문서 분석 및 정보 추출
        
        Args:
            content: 문서 내용
            query: 사용자 질문
            keywords: 문서 키워드
            query_analysis: 쿼리 분석 결과
            
        Returns:
            str: 분석 결과 텍스트
        """
        try:
            logger.error(f"analyze 진입")
            # 입력값 검증
            if not content or not isinstance(content, str):
                return "문서 내용이 비어있거나 올바르지 않습니다."
            if not query or not isinstance(query, str):
                return "질문이 비어있거나 올바르지 않습니다."
            if not isinstance(keywords, dict):
                return "키워드가 올바르지 않은 형식입니다."
            if not isinstance(query_analysis, dict):
                return "쿼리 분석 결과가 올바르지 않은 형식입니다."
            
            # 컨텍스트 준비 및 검증
            context = {
                "content": content[:1000],  # 컨텍스트 크기 제한
                "query": query,
                "keywords": {k: v for k, v in keywords.items() if v},  # 빈 값 제거
                "query_analysis": {
                    "doc_type": query_analysis.get("doc_type", "general"),
                    "focus_area": query_analysis.get("focus_area", "general"),
                    "analysis_type": query_analysis.get("analysis_type", "basic")
                }
            }
            
            # 프롬프트 생성 및 처리
            try:
                prompt = self._generate_prompt(content, query, keywords, query_analysis)
                result = self.process_prompt(prompt, context)
                
                if not result:
                    return "문서에서 관련 내용을 찾을 수 없습니다."
                
                # JSON 문자열인 경우 파싱
                try:
                    import json
                    if isinstance(result, str) and result.strip().startswith('{'):
                        parsed_result = json.loads(result)
                        if isinstance(parsed_result, dict):
                            # content 키가 있으면 해당 내용만 반환
                            if "content" in parsed_result:
                                result_content = parsed_result["content"]
                            else:
                                result_content = str(parsed_result)
                        else:
                            result_content = str(parsed_result)
                    else:
                        result_content = str(result)
                except json.JSONDecodeError:
                    result_content = str(result)
                except Exception as e:
                    logger.error(f"분석 결과 처리 중 오류 발생: {str(e)}")
                    result_content = str(result)
                
                return result_content
                
            except Exception as e:
                logger.error(f"프롬프트 처리 중 오류 발생: {str(e)}")
                return f"문서 분석 중 오류가 발생했습니다: {str(e)}"
            
        except Exception as e:
            logger.error(f"문서 분석 중 오류 발생: {str(e)}")
            return "문서 분석 중 예상치 못한 오류가 발생했습니다."

    def _get_extraction_context(self, query_analysis: Dict[str, Any], keywords: Dict[str, Any]) -> str:
        """추출 컨텍스트 생성
        
        Args:
            query_analysis: 쿼리 분석 결과
            keywords: 문서 키워드
            
        Returns:
            str: 추출 컨텍스트
        """
        doc_type = query_analysis.get("doc_type", "general")
        focus_area = query_analysis.get("focus_area", "general")
        
        # 금융 관련 컨텍스트를 세분화
        financial_contexts = {
            'financial_statement': """
1. 재무제표 분석:
   - 손익계산서: 매출액, 영업이익, 당기순이익, 증감률
   - 재무상태표: 자산/부채/자본 구조, 유동성/부채비율
   - 현금흐름표: 영업/투자/재무 활동, FCF""",
            
            'investment': """
2. 투자 지표:
   - 수익성: ROE, ROA, ROI, 영업이익률
   - 성장성: CAGR, 매출/이익 성장률
   - 밸류에이션: PER, PBR, PSR, 배당수익률""",
            
            'risk': """
3. 리스크 분석:
   - 시장 리스크: VaR, 베타계수, 변동성
   - 신용 리스크: 신용등급, 부도율
   - 유동성 리스크: LCR, NSFR""",
            
            'industry': """
4. 산업/경쟁 분석:
   - 시장 점유율: 매출/이익 기준, 성장률
   - 경쟁력: 원가, 마진율, 효율성
   - 산업 지표: 경기민감도, 규제영향""",
            
            'esg': """
5. ESG 지표:
   - 환경(E): 탄소배출, 에너지 사용
   - 사회(S): 고용, 산업재해, 사회공헌
   - 지배구조(G): 이사회, 주주권리""",
            
            'financial_metric': """
6. 정량 분석:
   - 신뢰도: 데이터 품질, 검증가능성
   - 시계열: 추세, 계절성, 이상치
   - 상관관계: 변수간 관계, 인과분석"""
        }
        
        # 문서 타입별 기본 컨텍스트
        extraction_contexts = {
            "meeting": """
1. 발화자 정보:
   - 발화자 이름과 직책 추출
   - 소속 정보 포함 (있는 경우)
   - 발화자의 역할이나 참석 목적 포함

2. 발화 내용:
   - 핵심 내용만 간단히 요약
   - 중복 발언 제외
   - 순서대로 정렬
   - 주요 결정사항이나 합의사항 강조

3. 시간 정보:
   - 발언 시점이나 순서 표시
   - 주요 일정이나 마감기한 강조

4. 정보 통합:
   - 동일 인물의 다른 표현 통합
   - 직위/직책은 처음 등장할 때만 포함
   - 발화 순서대로 정렬""",
            
            "report": """
1. 주요 항목:
   - 보고서의 주요 섹션과 항목 식별
   - 각 항목의 핵심 내용 추출
   - 결론이나 권고사항 강조

2. 수치 데이터:
   - 금액, 비율 등 주요 수치 추출
   - 증감률이나 변화 추이 포함
   - 목표 대비 실적 비교
   - 예측이나 전망 수치 포함

3. 시계열 정보:
   - 기간별 데이터 구분
   - 주요 이벤트나 변곡점 표시

4. 정보 통합:
   - 관련 항목끼리 그룹화
   - 시간순 또는 중요도순 정렬
   - 상호 연관된 지표 함께 표시""",
            
            "contract": """
1. 계약 기본 정보:
   - 계약명, 계약일, 계약기간
   - 계약 당사자 정보
   - 계약 목적이나 범위

2. 주요 조항:
   - 권리와 의무 사항
   - 금액이나 대가 관련 조항
   - 계약 해지나 변경 조건
   - 특별 약정 사항

3. 일정/기한:
   - 이행 기간이나 마감일
   - 중간 점검이나 보고 일정
   - 대금 지급 일정

4. 정보 통합:
   - 조항별 그룹화
   - 중요도 순 정렬
   - 연관 조항 함께 표시""",
            
            "financial": financial_contexts.get(focus_area, "일반 금융 분석"),
            
            "technical": """
1. 기술 스펙:
   - 주요 기술 사양
   - 성능이나 용량 정보
   - 호환성이나 제약사항
   - 요구사항 명세

2. 구현 정보:
   - 주요 기능이나 모듈
   - 인터페이스 정의
   - 데이터 구조나 형식
   - 처리 로직이나 알고리즘

3. 환경 정보:
   - 운영 환경이나 플랫폼
   - 필요 리소스나 의존성
   - 설정이나 파라미터

4. 정보 통합:
   - 기능별 그룹화
   - 계층별 구분
   - 연관 항목 통합""",
            
            "general": """
1. 주요 정보:
   - 문서에서 질문과 관련된 핵심 정보 추출
   - 구체적인 수치나 설명 포함
   - 중요도나 우선순위 고려

2. 정보 구조화:
   - 관련 정보끼리 그룹화
   - 논리적 순서로 정렬
   - 계층 구조 표현

3. 세부 정보:
   - 구체적인 예시나 사례
   - 부가 설명이나 참고사항
   - 제약사항이나 예외사항

4. 정보 통합:
   - 중복 내용 제거
   - 핵심 내용 위주로 정리
   - 상호 연관성 표시"""
        }
        
        # 문서 타입과 초점 영역에 따른 추가 지침
        focus_contexts = {
            "hr": """
- 인사 관련 정보 우선 추출
- 개인정보 보호 관련 사항 주의
- 직급/직책 체계 일관성 유지""",
            
            "tech": """
- 기술적 세부사항 상세 추출
- 버전이나 릴리스 정보 포함
- 기술 스택이나 아키텍처 구조화""",
            
            "financial": """
- 재무적 수치 정확성 확인
- 통화 단위 명확히 표시
- 회계기준이나 기준일자 명시"""
        }
        
        # 기본 컨텍스트 선택
        context = extraction_contexts.get(doc_type, extraction_contexts["general"])
        
        # 초점 영역별 추가 지침 적용
        if focus_area in focus_contexts:
            context += "\n\n추가 지침:\n" + focus_contexts[focus_area]
            
        return context

    def _generate_prompt(self, content: str, query: str, keywords: Dict[str, Any], query_analysis: Dict[str, Any]) -> str:
        """테이블 모드용 프롬프트 생성
        
        Args:
            content: 문서 내용
            query: 분석 요청
            keywords: 문서 키워드
            query_analysis: 쿼리 분석 결과
            
        Returns:
            str: 생성된 프롬프트
        """
        base_instruction = """아래 지침에 따라 문서를 분석하고 정보를 추출하세요:

[분석 원칙]
1. 정확성:
   - 요청된 정보만 정확히 추출
   - 추측이나 해석 최소화
   - 원문의 맥락 유지

2. 구조화:
   - 논리적 구조로 정보 정리
   - 관련 정보 그룹화
   - 중요도나 시간순 고려

3. 간결성:
   - 불필요한 설명 제외
   - 중복 정보 제거
   - 핵심 내용 위주 정리

4. 완전성:
   - 누락된 정보 '정보 없음'으로 표시
   - 모든 필수 항목 포함
   - 연관 정보 함께 제시

분석할 내용:
{content}

분석 요청:
{query}

문서 정보:
{doc_info}

추출 지침:
{extraction_context}

응답 형식:
{{
    "content": "분석한 내용을 여기에 작성하세요. 문서에서 찾은 {query}와 관련된 내용을 상세히 서술하되, 불필요한 정보는 제외하세요.",
    "metadata": {{
        "confidence": 0.0,  # 0.0 ~ 1.0 사이의 신뢰도 점수. 내용의 정확도와 관련성에 따라 결정
        "source": "document_content",  # 데이터 출처
        "context": "분석에 사용된 컨텍스트 정보"
    }}
}}

주의사항:
1. 응답은 반드시 위 JSON 형식을 따라야 합니다.
2. confidence는 0.0에서 1.0 사이의 실수여야 합니다.
3. content에는 분석 결과를 자세히 작성하되, 불필요한 정보는 제외하세요.
4. 응답은 한국어로 작성하세요."""

        # 문서 정보 문자열 생성
        doc_info = f"""문서 유형: {keywords.get('document_type', '일반')}
문서 제목: {keywords.get('title', '제목 없음')}
작성일자: {keywords.get('date', '날짜 없음')}
분석 초점: {query_analysis.get('focus_area', '일반')}
분석 유형: {query_analysis.get('doc_type', '일반')}"""

        # 추출 컨텍스트 가져오기
        extraction_context = self._get_extraction_context(query_analysis, keywords)
        
        # 프롬프트 생성
        prompt = base_instruction.format(
            content=content,
            query=query,
            doc_info=doc_info,
            extraction_context=extraction_context
        )
        
        return prompt

    