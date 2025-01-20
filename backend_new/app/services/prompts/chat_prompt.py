from typing import Dict, Any, List, Set
from .base import BasePrompt
import re
from enum import Enum

class AnalysisType(Enum):
    TIME_SERIES = "시계열"
    COMPARISON = "비교"
    RANKING = "순위"
    PATTERN = "패턴"
    AGGREGATION = "집계"
    RELATIONSHIP = "관계"
    CLASSIFICATION = "분류"
    PREDICTION = "예측"
    STRUCTURE = "구조"
    INTEGRATION = "통합"

class QueryAnalyzer:
    def __init__(self):
        self.analysis_keywords = {
            AnalysisType.TIME_SERIES: [
                r"추세|트렌드|변화|추이",
                r"(전년|전월|전분기)\s*(대비|比)",
                r"YoY|QoQ|MoM",
                r"언제|시기|날짜|기간",
                r"(증가|감소|변화)\s*(했|됐|되었)"
            ],
            AnalysisType.COMPARISON: [
                r"비교|차이|격차|대비",
                r"어떻게\s*(다른가|다른지|다른)",
                r"vs|versus",
                r"차이점|공통점",
                r"어느\s*(쪽|것|곳)"
            ],
            AnalysisType.RANKING: [
                r"순위|등수|석차",
                r"(가장|제일)\s*(높은|낮은|좋은|나쁜)",
                r"top|bottom|\d+위",
                r"최고|최저|최상|최하",
                r"상위|하위"
            ],
            AnalysisType.PATTERN: [
                r"패턴|특징|경향|양상",
                r"반복|주기|규칙",
                r"공통점|유사점",
                r"어떤\s*(특징|패턴)",
                r"규칙성|불규칙"
            ],
            AnalysisType.AGGREGATION: [
                r"평균|중간값|최빈값",
                r"합계|총합|전체",
                r"얼마나|몇|몇개",
                r"분포|비율|퍼센트",
                r"%|％"
            ],
            AnalysisType.RELATIONSHIP: [
                r"관계|연관|상관",
                r"영향|효과|작용",
                r"원인|이유|때문",
                r"어떻게|어떤|왜",
                r"인과|상호작용"
            ],
            AnalysisType.CLASSIFICATION: [
                r"분류|구분|카테고리",
                r"종류|유형|타입",
                r"어떤\s*(종류|유형)",
                r"긍정|부정",
                r"장점|단점"
            ],
            AnalysisType.PREDICTION: [
                r"전망|예상|예측",
                r"향후|미래|앞으로",
                r"될\s*(것|예정|전망)",
                r"가능성|확률|리스크",
                r"시나리오"
            ],
            AnalysisType.STRUCTURE: [
                r"구조|체계|시스템",
                r"프로세스|절차|단계",
                r"어떻게\s*(구성|이루어)",
                r"SWOT|밸류체인",
                r"구성|요소"
            ],
            AnalysisType.INTEGRATION: [
                r"종합|통합|전체",
                r"핵심|요점|포인트",
                r"결론|시사점",
                r"컨센서스|의견",
                r"정리|요약"
            ]
        }
        
    def analyze(self, query: str) -> Set[AnalysisType]:
        """쿼리에서 요구하는 분석 유형들을 식별"""
        analysis_types = set()
        
        for analysis_type, keywords in self.analysis_keywords.items():
            if any(re.search(keyword, query, re.I | re.U) for keyword in keywords):
                analysis_types.add(analysis_type)
                
        # 기본값으로 통합 분석 추가
        if not analysis_types:
            analysis_types.add(AnalysisType.INTEGRATION)
            
        return analysis_types

class ChatPrompt(BasePrompt):
    def __init__(self, *args, **kwargs):
        # patterns 파라미터가 있다면 제거
        if 'patterns' in kwargs:
            del kwargs['patterns']
        super().__init__(*args, **kwargs)
        self.query_analyzer = QueryAnalyzer()
        
    async def analyze(self, content: str, query: str, keywords: Dict[str, Any], query_analysis: Dict[str, Any]) -> str:
        """문서 분석 및 질문 답변"""
        # 쿼리 분석 수행
        analysis_types = self.query_analyzer.analyze(query)
        
        # 분석 결과를 query_analysis에 추가
        query_analysis["analysis_types"] = [at.value for at in analysis_types]
        
        context = {
            "content": content,
            "query": query,
            "keywords": keywords,
            "query_analysis": query_analysis
        }
        
        prompt = self._generate_prompt(content, query, keywords, query_analysis)
        result = await self.process_prompt(prompt, context)
        
        # 결과를 문자열로 변환
        if isinstance(result, (dict, list)):
            if isinstance(result, dict):
                # 딕셔너리를 줄바꿈으로 구분된 "키: 값" 형태로 변환
                result = "\n".join([f"{k}: {v}" for k, v in result.items()])
            else:  # list인 경우
                # 리스트를 줄바꿈으로 구분된 문자열로 변환
                result = "\n".join(str(item) for item in result)
        else:
            # 다른 타입인 경우 str() 사용
            result = str(result)
            
        return result

    def _get_analysis_type_prompt(self, analysis_type: AnalysisType) -> str:
        """분석 유형별 프롬프트 생성"""
        prompts = {
            AnalysisType.TIME_SERIES: """시계열 분석 지침:
- 시간 순서대로 데이터를 정렬하여 분석하세요
- 주요 변화 시점과 변화율을 명시하세요
- 추세와 패턴을 식별하여 설명하세요
- 계절성이나 주기성이 있다면 언급하세요""",

            AnalysisType.COMPARISON: """비교 분석 지침:
- 항목별로 명확한 비교 기준을 설정하세요
- 공통점과 차이점을 구체적으로 나열하세요
- 차이가 발생한 원인을 분석하세요
- 비교 결과의 시사점을 도출하세요""",

            AnalysisType.RANKING: """순위 분석 지침:
- 순위 기준을 명확히 제시하세요
- 상위/하위 항목의 특징을 설명하세요
- 순위 변동이 있다면 원인을 분석하세요
- 전체 분포 속에서의 위치를 설명하세요""",

            AnalysisType.PATTERN: """패턴 분석 지침:
- 반복되는 패턴을 식별하세요
- 패턴의 주기와 강도를 분석하세요
- 예외적인 패턴을 찾아 설명하세요
- 패턴의 의미와 시사점을 도출하세요""",

            AnalysisType.AGGREGATION: """집계 분석 지침:
- 데이터의 분포를 파악하세요
- 대표값(평균, 중앙값, 최빈값)을 제시하세요
- 이상치가 있다면 별도로 표시하세요
- 전체적인 경향성을 설명하세요""",

            AnalysisType.RELATIONSHIP: """관계 분석 지침:
- 변수 간의 관계를 파악하세요
- 인과관계가 있다면 근거와 함께 설명하세요
- 직접/간접적 영향을 구분하여 설명하세요
- 관계의 강도와 방향을 명시하세요""",

            AnalysisType.CLASSIFICATION: """분류 분석 지침:
- 분류 기준을 명확히 제시하세요
- 각 분류별 특징을 설명하세요
- 분류 간 경계가 모호한 경우를 언급하세요
- 분류 결과의 의미를 해석하세요""",

            AnalysisType.PREDICTION: """예측 분석 지침:
- 현재 상황을 정확히 진단하세요
- 주요 변수와 영향 요인을 분석하세요
- 가능한 시나리오를 제시하세요
- 예측의 불확실성 요인을 명시하세요""",

            AnalysisType.STRUCTURE: """구조 분석 지침:
- 전체 구조를 개관적으로 설명하세요
- 주요 구성 요소를 분석하세요
- 요소 간 관계를 설명하세요
- 구조적 특징과 의미를 도출하세요""",

            AnalysisType.INTEGRATION: """통합 분석 지침:
- 핵심 메시지를 명확히 도출하세요
- 주요 발견사항을 종합하세요
- 상충되는 내용을 조율하여 설명하세요
- 전체적인 시사점을 제시하세요"""
        }
        
        return prompts.get(analysis_type, "")

    def _get_time_range_prompt(self, query_analysis: Dict[str, Any]) -> str:
        """시간 범위에 따른 프롬프트 생성"""
        if not query_analysis.get("focus") == "financial":
            return ""
            
        prompts = []
        
        # 시간 범위가 있는 경우
        if query_analysis.get("time_range"):
            prompts.append(f"- {query_analysis['time_range']} 기간의 데이터를 분석하세요")
            
        # 시간 비교가 필요한 경우
        if query_analysis.get("time_comparison"):
            prompts.append("- 기간별 변화를 다음 순서로 분석하세요:")
            prompts.append("  1. 절대적 변화량")
            prompts.append("  2. 상대적 변화율")
            prompts.append("  3. 변화 추세")
            
        # YoY, QoQ, MoM 분석이 필요한 경우
        if query_analysis.get("period_comparison"):
            periods = query_analysis["period_comparison"]
            comparisons = []
            if "YoY" in periods:
                comparisons.append("전년 동기 대비(YoY)")
            if "QoQ" in periods:
                comparisons.append("전분기 대비(QoQ)")
            if "MoM" in periods:
                comparisons.append("전월 대비(MoM)")
            if comparisons:
                prompts.append(f"- {', '.join(comparisons)} 변화를 분석하세요")
        
        return "\n".join(prompts) if prompts else ""

    def _get_keyword_prompt(self, keywords: Dict[str, Any]) -> str:
        """키워드 관련 프롬프트 생성"""
        prompts = []
        
        # 문서 수 불일치 확인
        if keywords.get("total_documents") != keywords.get("found_documents"):
            prompts.append(f"- 총 {keywords['total_documents']}개의 문서 중 {keywords['found_documents']}개만 분석되었습니다. 누락된 문서가 없는지 확인하세요.")
        
        # 주요 용어 분석
        if keywords.get("common_terms"):
            terms = ", ".join(keywords["common_terms"])
            if len(keywords["common_terms"]) > 1:
                prompts.append(f"- 주요 용어들: {terms}")
            else:
                prompts.append(f"- 주요 용어: {terms}")

        # 표 데이터 분석
        if keywords.get("has_tables"):
            prompts.append("""- 표 데이터 분석 지침:
  1. 표의 구조와 의미 설명
  2. 주요 수치 해석
  3. 데이터 간 관계 분석
  4. 특이사항 도출""")
        
        # 날짜 범위 분석
        if keywords.get("date_range"):
            date_range = keywords["date_range"]
            prompts.append(f"- {date_range} 기간 동안의 변화를 분석하세요")
            prompts.append("- 주요 변화 시점과 원인을 식별하세요")
        
        # 반복 패턴 분석
        if keywords.get("recurring_patterns"):
            prompts.append("""- 반복 패턴 분석:
  1. 패턴의 주기와 강도
  2. 예외적인 상황
  3. 패턴의 의미""")
            
        return "\n".join(prompts) if prompts else ""

    def _get_response_format(self, analysis_types: Set[AnalysisType]) -> str:
        """분석 유형에 따른 응답 형식 생성
        
        Args:
            analysis_types: 분석 유형 집합
            
        Returns:
            응답 형식 지침을 포함한 문자열
        """
        # 기본 응답 지침
        guidelines = [
            "# 응답 작성 지침",
            
            "## 1. 마크다운 활용",
            "- 상황에 맞는 마크다운 요소를 자유롭게 활용해주세요:",
            "  - 제목/소제목(#, ##, ###): 주제 구분이 필요할 때",
            "  - 강조(**bold**): 핵심 수치나 중요 정보",
            "  - 기울임(*italic*): 부가 설명이나 맥락",
            "  - 목록(-, 1.): 여러 항목을 나열할 때",
            "  - 테이블: 데이터 비교나 정리가 필요할 때",
            "  - 인용(>): 원문이나 중요 인용구",
            
            "## 2. 응답 구조화",
            "- 내용의 복잡도에 따라 적절한 구조 선택",
            "- 간단한 질문: 핵심을 간단명료하게",
            "- 복잡한 질문: 논리적 구조로 단계적 설명",
            
            "## 3. 데이터 표현",
            "- 수치 데이터: 테이블이나 목록 형태로 명확하게",
            "- 비교 분석: 차이점을 강조하여 구조화",
            "- 시계열 데이터: 추세와 변화를 잘 보여주는 형식으로",
            
            "## 4. 사용자 요청 준수",
            "- 사용자가 특정 형식을 요청하면 해당 형식 우선",
            "- 질문의 의도에 가장 적합한 표현 방식 선택"
        ]
        
        # 분석 유형별 추가 지침
        if AnalysisType.TIME_SERIES in analysis_types:
            guidelines.extend([
                "## 시계열 분석 표현",
                "- 기간별 변화는 단계적으로 설명",
                "- 주요 변곡점과 특이사항 강조"
            ])
            
        if AnalysisType.COMPARISON in analysis_types:
            guidelines.extend([
                "## 비교 분석 표현",
                "- 핵심 차이점을 명확하게 구조화",
                "- 공통점과 차이점을 구분하여 설명"
            ])
            
        if AnalysisType.PATTERN in analysis_types:
            guidelines.extend([
                "## 패턴 분석 표현",
                "- 반복되는 패턴을 체계적으로 설명",
                "- 예외적인 패턴이나 특이점 강조"
            ])
            
        return "\n".join(guidelines)

    def _format_table_data(self, data: str) -> str:
        """테이블 형식 데이터를 마크다운 테이블로 변환"""
        lines = data.split('\n')
        if len(lines) < 2:  # 헤더와 데이터가 최소 1줄씩 필요
            return data
            
        # 구분자 행 생성
        headers = [h.strip() for h in lines[0].split('|')]
        separator = '|' + '|'.join(['---' for _ in headers]) + '|'
        
        # 헤더 행과 구분자 행을 결합
        formatted_lines = [lines[0], separator]
        
        # 데이터 행 추가
        formatted_lines.extend(lines[1:])
        
        return '\n'.join(formatted_lines)

    def _generate_prompt(self, content: str, query: str, keywords: Dict[str, Any], query_analysis: Dict[str, Any]) -> str:
        """분석용 프롬프트 생성"""
        # 분석 유형 확인
        analysis_types = {AnalysisType(at) for at in query_analysis.get("analysis_types", [])}
        
        # 기본 프롬프트
        base_prompt = """당신은 문서를 분석하고 사용자의 질문에 답변하는 AI 어시스턴트입니다.
주어진 문서의 내용만을 기반으로 답변해야 하며, 문서에 없는 내용은 답변하지 마세요."""

        # 분석 유형별 프롬프트 생성
        analysis_prompts = []
        for analysis_type in analysis_types:
            prompt = self._get_analysis_type_prompt(analysis_type)
            if prompt:
                analysis_prompts.append(prompt)
        
        # 시간 범위 프롬프트
        time_prompt = self._get_time_range_prompt(query_analysis)
        
        # 키워드 프롬프트
        keyword_prompt = self._get_keyword_prompt(keywords)
        
        # 응답 형식
        response_format = self._get_response_format(analysis_types)
        
        # 최종 프롬프트 조합
        parts = [
            base_prompt,
            f"\n문서 내용:\n{content}",
            f"\n질문:\n{query}"
        ]
        
        # 분석 지침 결합
        analysis_instructions = "\n\n".join(filter(None, [
            "\n".join(analysis_prompts),
            time_prompt,
            keyword_prompt
        ]))
        
        if analysis_instructions:
            parts.append(f"\n분석 지침:\n{analysis_instructions}")
            
        parts.append(f"\n응답 형식:\n{response_format}")
        
        return "\n".join(parts)
