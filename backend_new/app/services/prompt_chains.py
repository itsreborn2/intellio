"""프롬프트 체인 관리 모듈"""

from enum import Enum
from typing import Dict, Any, List, Optional
from dataclasses import dataclass
import logging
import aiohttp
import json

logger = logging.getLogger(__name__)

class DocumentType(Enum):
    # 학술/연구
    ACADEMIC_PAPER = "academic_paper"
    RESEARCH_REPORT = "research_report"
    
    # 법률/규제
    LEGAL_DOCUMENT = "legal_document"
    REGULATION = "regulation"
    COURT_RULING = "court_ruling"
    
    # 금융/투자
    SECURITIES_FILING = "securities_filing"
    INVESTMENT_PROSPECTUS = "investment_prospectus"
    FINANCIAL_STATEMENT = "financial_statement"
    
    # 기술/IT
    TECHNICAL_SPEC = "technical_spec"
    API_DOC = "api_doc"
    SYSTEM_DESIGN = "system_design"
    
    # 비즈니스
    BUSINESS_PLAN = "business_plan"
    PROPOSAL = "proposal"
    CONTRACT = "contract"
    
    # 의료/헬스케어
    CLINICAL_TRIAL = "clinical_trial"
    MEDICAL_RECORD = "medical_record"
    
    # 정책/행정
    POLICY_REPORT = "policy_report"
    ADMINISTRATIVE_GUIDE = "administrative_guide"

@dataclass
class PromptTemplate:
    """프롬프트 템플릿 정의"""
    name: str
    template: str
    required_context: List[str]
    optional_context: List[str] = None
    
    def format(self, context: Dict[str, Any]) -> str:
        """컨텍스트를 사용하여 프롬프트 생성"""
        try:
            return self.template.format(**context)
        except KeyError as e:
            missing_key = str(e).strip("'")
            if missing_key in (self.optional_context or []):
                # 옵션 컨텍스트가 없으면 빈 문자열로 대체
                context[missing_key] = ""
                return self.template.format(**context)
            raise ValueError(f"필수 컨텍스트 누락: {missing_key}")

class PromptStep:
    """프롬프트 체인의 단일 단계"""
    def __init__(
        self,
        name: str,
        template: PromptTemplate,
        model: str = "gemini",
        temperature: float = 0.3
    ):
        self.name = name
        self.template = template
        self.model = model
        self.temperature = temperature
    
    async def execute(self, context: Dict[str, Any]) -> Dict[str, Any]:
        """단계 실행"""
        try:
            prompt = self.template.format(context)
            # TODO: AI 모델 호출 구현
            return {"result": "실행 결과"}
        except Exception as e:
            logger.error(f"프롬프트 단계 실행 실패: {str(e)}")
            raise

class PromptChain:
    """프롬프트 체인 정의"""
    def __init__(self, name: str, steps: List[PromptStep]):
        self.name = name
        self.steps = steps
        self.context = {}
    
    async def execute(self, input_data: Dict[str, Any]) -> Dict[str, Any]:
        """체인 실행"""
        self.context = input_data.copy()
        
        try:
            for step in self.steps:
                result = await step.execute(self.context)
                self.context.update(result)
            
            return self.context
        except Exception as e:
            logger.error(f"체인 실행 실패: {str(e)}")
            raise

class PromptChainManager:
    """프롬프트 체인 관리자"""
    
    # 문서 유형 키워드 매핑
    DOCUMENT_TYPE_KEYWORDS = {
        DocumentType.ACADEMIC_PAPER: [
            "논문", "연구", "실험", "가설", "방법론", "데이터", "분석", "결과", 
            "통계", "유의성", "선행연구", "학술", "연구자", "저자"
        ],
        DocumentType.LEGAL_DOCUMENT: [
            "계약", "법률", "조항", "규정", "의무", "권리", "당사자", "위반", 
            "책임", "손해배상", "법적", "준수", "해지", "효력"
        ],
        DocumentType.FINANCIAL_STATEMENT: [
            "재무제표", "대차대조표", "손익계산서", "현금흐름표", "자산", "부채", 
            "자본", "매출", "이익", "손실", "재무", "회계", "감사"
        ],
        DocumentType.TECHNICAL_SPEC: [
            "기술", "명세", "스펙", "요구사항", "아키텍처", "시스템", "설계", 
            "인터페이스", "API", "데이터베이스", "성능", "보안"
        ],
        DocumentType.MEDICAL_RECORD: [
            "진료", "의무기록", "환자", "증상", "진단", "처방", "검사", "치료", 
            "병력", "수술", "투약", "예후", "의사", "간호"
        ],
        DocumentType.BUSINESS_PLAN: [
            "사업계획", "비즈니스", "시장", "전략", "마케팅", "수익", "고객", 
            "경쟁", "성장", "투자", "운영", "조직", "목표"
        ],
        DocumentType.POLICY_REPORT: [
            "정책", "보고서", "제도", "방안", "개선", "추진", "시행", "평가", 
            "영향", "예산", "집행", "성과", "모니터링"
        ]
    }

    # 분석 요청 유형 키워드 매핑
    ANALYSIS_TYPE_KEYWORDS = {
        "요약": ["요약", "정리", "핵심", "중요", "주요", "key", "main"],
        "비교": ["비교", "차이", "대조", "유사", "다른", "compare", "vs"],
        "평가": ["평가", "검토", "분석", "진단", "심사", "review", "assess"],
        "예측": ["예측", "전망", "추세", "향후", "예상", "forecast", "predict"],
        "제안": ["제안", "추천", "권고", "방안", "대책", "suggest", "recommend"]
    }

    def __init__(self):
        self.chain_factory = DocumentChainFactory()
        self.document_analyzer = DocumentAnalyzer()

    def analyze_user_prompt(self, prompt: str) -> Dict[str, Any]:
        """사용자 프롬프트 분석"""
        return {
            "doc_type": self._detect_document_type(prompt),
            "analysis_types": self._detect_analysis_types(prompt),
            "keywords": self._extract_keywords(prompt)
        }

    def _detect_document_type(self, text: str) -> DocumentType:
        """문서 유형 감지"""
        max_score = 0
        detected_type = DocumentType.RESEARCH_REPORT  # 기본값

        for doc_type, keywords in self.DOCUMENT_TYPE_KEYWORDS.items():
            score = sum(1 for keyword in keywords if keyword in text)
            if score > max_score:
                max_score = score
                detected_type = doc_type

        return detected_type

    def _detect_analysis_types(self, text: str) -> List[str]:
        """분석 유형 감지"""
        detected_types = []
        for analysis_type, keywords in self.ANALYSIS_TYPE_KEYWORDS.items():
            if any(keyword in text for keyword in keywords):
                detected_types.append(analysis_type)
        return detected_types or ["요약"]  # 기본값은 요약

    def _extract_keywords(self, text: str) -> List[str]:
        """주요 키워드 추출"""
        # TODO: 자연어 처리 라이브러리를 사용하여 키워드 추출 구현
        return []

    async def process_prompt(self, prompt: str, content: str) -> Dict[str, Any]:
        """프롬프트 처리 및 체인 실행"""
        try:
            # 프롬프트 분석
            analysis = self.analyze_user_prompt(prompt)
            
            # 문서 유형에 맞는 프롬프트 생성
            template = self._get_prompt_template(analysis["doc_type"])
            
            # 분석 유형에 따른 프롬프트 생성
            analysis_prompt = template.format(
                content=content,
                perspective=self.ANALYSIS_PERSPECTIVES.get(analysis["analysis_types"][0], ""),
                user_prompt=prompt
            )
            
            # Gemini로 분석 수행
            async with aiohttp.ClientSession() as session:
                headers = {
                    "Content-Type": "application/json",
                    "x-goog-api-key": "YOUR_GEMINI_API_KEY"
                }
                
                payload = {
                    "contents": [{
                        "parts": [{
                            "text": analysis_prompt
                        }]
                    }],
                    "generationConfig": {
                        "temperature": 0.2,
                        "topK": 40,
                        "topP": 0.8,
                        "maxOutputTokens": 2048,
                    }
                }
                
                async with session.post(
                    "https://generativelanguage.googleapis.com/v1beta/models/gemini-pro:generateContent",
                    headers=headers,
                    json=payload
                ) as response:
                    result = await response.json()
                    
                    if "error" in result:
                        raise Exception(f"Gemini API 오류: {result['error']}")
                        
                    analysis_result = result["candidates"][0]["content"]["parts"][0]["text"]
            
            return {
                "result": analysis_result,
                "analysis": analysis
            }
            
        except Exception as e:
            logger.error(f"프롬프트 처리 실패: {str(e)}")
            raise

    def _get_prompt_template(self, doc_type: DocumentType) -> str:
        """문서 유형별 프롬프트 템플릿"""
        templates = {
            DocumentType.ACADEMIC_PAPER: """
다음 학술 논문을 {perspective} 분석하세요.

사용자 질문: {user_prompt}

분석 규칙:
1. 숫자는 <np>+값</np> 또는 <nn>-값</nn> 형식으로 표시
2. 중요도는 [❗] ~ [❗❗❗]로 표시
3. 평가는 [✓], [✗], [─]로 표시

논문 내용:
{content}
""",
            DocumentType.LEGAL_DOCUMENT: """
다음 법률 문서를 {perspective} 분석하세요.

사용자 질문: {user_prompt}

분석 규칙:
1. 숫자는 <np>+값</np> 또는 <nn>-값</nn> 형식으로 표시
2. 중요도는 [❗] ~ [❗❗❗]로 표시
3. 평가는 [✓], [✗], [─]로 표시

문서 내용:
{content}
""",
            # 다른 문서 유형 템플릿...
        }
        return templates.get(doc_type, templates[DocumentType.ACADEMIC_PAPER])

    ANALYSIS_PERSPECTIVES = {
        "요약": "핵심 내용을 간단히 정리하여",
        "평가": "객관적인 기준으로 평가하여",
        "비교": "유사 사례나 기준과 비교하여",
        "예측": "향후 영향과 전망을 중심으로",
        "제안": "개선점과 대안을 제시하며"
    }

class DocumentChainFactory:
    """문서 유형별 체인 생성 팩토리"""
    
    @staticmethod
    def create_chain(doc_type: DocumentType) -> PromptChain:
        """문서 유형에 따른 체인 생성"""
        # 기본 분석 템플릿
        base_template = PromptTemplate(
            name="기본 분석",
            template="",
            required_context=["content"],
            optional_context=["perspective"]
        )
        
        # 체인 구성
        steps = [
            PromptStep(
                name="문서 분석",
                template=base_template,
                model="gemini",
                temperature=0.3
            )
        ]
        
        return PromptChain(
            name=f"{doc_type.value}_chain",
            steps=steps
        )

class DocumentAnalyzer:
    """문서 분석 실행기"""
    
    def __init__(self):
        self.chain_factory = DocumentChainFactory()
    
    async def analyze(
        self,
        content: str,
        doc_type: DocumentType
    ) -> Dict[str, Any]:
        """문서 분석 실행"""
        try:
            # 체인 생성
            chain = self.chain_factory.create_chain(doc_type)
            
            # 분석 실행
            result = await chain.execute({
                "content": content,
                "doc_type": doc_type.value,
                "perspective": ""
            })
            
            return result
        except Exception as e:
            logger.error(f"문서 분석 실패: {str(e)}")
            raise

class PromptChainResponse:
    """프롬프트 체인 응답 포맷팅"""
    
    @staticmethod
    def format_response(result: Dict[str, Any]) -> str:
        """응답 포맷팅"""
        try:
            # 최종 결과가 이미 포맷팅되어 있으면 그대로 반환
            if "result" in result and isinstance(result["result"], str):
                return result["result"]
            
            # 그렇지 않으면 기본 포맷팅 적용
            analysis = result.get("analysis", {})
            doc_analysis = result.get("doc_analysis", {})
            chain_result = result.get("chain_result", {})
            
            return f"""
# {analysis.get('doc_type', '문서')} 분석 결과

## 분석 유형
{', '.join(f'`{t}`' for t in analysis.get('analysis_types', []))}

## 분석 내용
{chain_result.get('result', '')}

## 주요 지표
{PromptChainResponse._format_metrics(doc_analysis.get('metrics', {}))}

## 특이사항
{PromptChainResponse._format_issues(doc_analysis.get('issues', []))}
""".strip()
            
        except Exception as e:
            logger.error(f"응답 포맷팅 실패: {str(e)}")
            return str(e)

    @staticmethod
    def _format_metrics(metrics: Dict) -> str:
        """지표 포맷팅"""
        if not metrics:
            return "지표 정보가 없습니다."
            
        formatted = []
        for key, value in metrics.items():
            if isinstance(value, (int, float)):
                if value > 0:
                    formatted.append(f"- {key}: <np>+{value}</np>")
                elif value < 0:
                    formatted.append(f"- {key}: <nn>{value}</nn>")
                else:
                    formatted.append(f"- {key}: <n>{value}</n>")
            else:
                formatted.append(f"- {key}: {value}")
        
        return "\n".join(formatted)

    @staticmethod
    def _format_issues(issues: List) -> str:
        """특이사항 포맷팅"""
        if not issues:
            return "특이사항이 없습니다."
            
        formatted = []
        for issue in issues:
            severity = issue.get("severity", "low")
            if severity == "high":
                formatted.append(f"- [❗❗❗] {issue.get('description', '')}")
            elif severity == "medium":
                formatted.append(f"- [❗❗] {issue.get('description', '')}")
            else:
                formatted.append(f"- [❗] {issue.get('description', '')}")
        
        return "\n".join(formatted)
