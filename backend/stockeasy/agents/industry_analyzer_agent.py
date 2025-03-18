"""
산업 및 시장 동향 분석을 위한 에이전트

이 모듈은 산업 및 시장 동향 정보를 검색하고 분석하는 에이전트를 정의합니다.
"""

from typing import Dict, List, Any, Optional, cast
from datetime import datetime
from loguru import logger

from langchain_openai import ChatOpenAI
from langchain_core.output_parsers import JsonOutputParser
from langchain.prompts import PromptTemplate

from stockeasy.prompts.industry_prompts import INDUSTRY_ANALYSIS_PROMPT
# from stockeasy.services.industry.industry_data_service import IndustryDataService
# from stockeasy.services.stock.stock_info_service import StockInfoService
from stockeasy.models.agent_io import RetrievedData, IndustryData
from common.services.agent_llm import get_llm_for_agent

class IndustryAnalyzerAgent:
    """산업 및 시장 동향 분석 에이전트"""

    def __init__(self):
        """
        IndustryAnalyzerAgent를 초기화합니다.
        
        Args:
            model_name: 사용할 LLM 모델 이름
            temperature: 모델 온도(창의성) 설정
        """
        #self.model_name = model_name
        #self.temperature = temperature
        #self.llm = ChatOpenAI(model=model_name, temperature=temperature)

        self.llm, self.model_name, self.provider = get_llm_for_agent("industry_analyzer_agent")
        logger.info(f"IndustryAnalyzerAgent initialized with provider: {self.provider}, model: {self.model_name}")
        
        # 서비스 초기화
        #self.industry_service = IndustryDataService()
        #self.stock_service = StockInfoService()

    async def process(self, state: Dict[str, Any]) -> Dict[str, Any]:
        """
        산업 및 시장 동향 분석을 수행합니다.
        
        Args:
            state: 현재 상태 정보를 포함하는 딕셔너리
            
        Returns:
            업데이트된 상태 딕셔너리
        """
        try:
            # 성능 측정 시작
            start_time = datetime.now()
            logger.info("IndustryAnalyzerAgent starting processing")
            
            # 현재 쿼리 및 세션 정보 추출
            query = state.get("query", "")
            
            # 질문 분석 결과 추출 (새로운 구조)
            question_analysis = state.get("question_analysis", {})
            entities = question_analysis.get("entities", {})
            classification = question_analysis.get("classification", {})
            data_requirements = question_analysis.get("data_requirements", {})
            keywords = question_analysis.get("keywords", [])
            detail_level = question_analysis.get("detail_level", "보통")
            
            # 엔티티에서 종목 정보 추출
            stock_code = entities.get("stock_code", state.get("stock_code"))
            stock_name = entities.get("stock_name", state.get("stock_name"))
            sector = entities.get("sector", "")
            
            logger.info(f"IndustryAnalyzerAgent analyzing: {stock_code or stock_name}")
            logger.info(f"Classification data: {classification}")
            logger.info(f"Data requirements: {data_requirements}")
            
            # 종목 코드 또는 종목명이 없는 경우 처리
            if not stock_code and not stock_name:
                logger.warning("No stock information provided to IndustryAnalyzerAgent")
                self._add_error(state, "산업 분석을 위한 종목 정보가 없습니다.")
                return state
            
            # 산업/섹터 정보가 없는 경우 조회
            if not sector and stock_name:
                try:
                    stock_info = await self.stock_service.get_stock_by_name(stock_name)
                    if stock_info and "sector" in stock_info:
                        sector = stock_info["sector"]
                        logger.info(f"Retrieved sector '{sector}' for {stock_name}")
                    else:
                        # 임시 더미 데이터 사용
                        sector = self._get_dummy_sector(stock_name)
                        logger.info(f"Using dummy sector '{sector}' for {stock_name}")
                except Exception as e:
                    logger.error(f"Error retrieving sector info: {str(e)}")
                    sector = self._get_dummy_sector(stock_name)
            
            # 산업 데이터 조회
            try:
                # 실제 구현에서는 업종/산업 데이터 서비스 활용
                # industry_data = await self.industry_service.get_industry_data(sector)
                
                # 임시 샘플 데이터 사용
                industry_data_raw = self._get_dummy_industry_data(stock_name, sector)
                
                if not industry_data_raw:
                    logger.warning(f"No industry data found for sector: {sector}")
                    
                    # 실행 시간 계산
                    end_time = datetime.now()
                    duration = (end_time - start_time).total_seconds()
                    
                    # 새로운 구조로 상태 업데이트 (결과 없음)
                    state["agent_results"] = state.get("agent_results", {})
                    state["agent_results"]["industry_analyzer"] = {
                        "agent_name": "industry_analyzer",
                        "status": "partial_success",
                        "data": [],
                        "error": "산업 데이터를 찾을 수 없습니다.",
                        "execution_time": duration,
                        "metadata": {
                            "sector": sector,
                            "stock_name": stock_name
                        }
                    }
                    
                    # 타입 주석을 사용한 데이터 할당
                    if "retrieved_data" not in state:
                        state["retrieved_data"] = {}
                    retrieved_data = cast(RetrievedData, state["retrieved_data"])
                    industry_data_result: List[IndustryData] = []
                    retrieved_data["industry"] = industry_data_result
                    
                    state["processing_status"] = state.get("processing_status", {})
                    state["processing_status"]["industry_analyzer"] = "completed_no_data"
                    
                    # 메트릭 기록
                    state["metrics"] = state.get("metrics", {})
                    state["metrics"]["industry_analyzer"] = {
                        "start_time": start_time,
                        "end_time": end_time,
                        "duration": duration,
                        "status": "completed_no_data",
                        "error": None,
                        "model_name": self.model_name
                    }
                    
                    logger.info(f"IndustryAnalyzerAgent completed in {duration:.2f} seconds, no data found")
                    return state
                
                # 산업 데이터 분석
                analysis_results = await self._analyze_industry_data(
                    industry_data_raw, 
                    query,
                    sector,
                    stock_name,
                    classification,
                    detail_level
                )
                
                # 실행 시간 계산
                end_time = datetime.now()
                duration = (end_time - start_time).total_seconds()
                
                # 새로운 구조로 상태 업데이트
                state["agent_results"] = state.get("agent_results", {})
                state["agent_results"]["industry_analyzer"] = {
                    "agent_name": "industry_analyzer",
                    "status": "success",
                    "data": {
                        "raw_data": industry_data_raw,
                        "analysis": analysis_results
                    },
                    "error": None,
                    "execution_time": duration,
                    "metadata": {
                        "sector": sector,
                        "stock_name": stock_name
                    }
                }
                
                # 타입 주석을 사용한 데이터 할당
                if "retrieved_data" not in state:
                    state["retrieved_data"] = {}
                retrieved_data = cast(RetrievedData, state["retrieved_data"])
                industry_data_result: List[IndustryData] = [{
                    "raw_data": industry_data_raw,
                    "analysis": analysis_results
                }]
                retrieved_data["industry"] = industry_data_result
                
                state["processing_status"] = state.get("processing_status", {})
                state["processing_status"]["industry_analyzer"] = "completed"
                
                # 메트릭 기록
                state["metrics"] = state.get("metrics", {})
                state["metrics"]["industry_analyzer"] = {
                    "start_time": start_time,
                    "end_time": end_time,
                    "duration": duration,
                    "status": "completed",
                    "error": None,
                    "model_name": self.model_name
                }
                
                logger.info(f"IndustryAnalyzerAgent completed in {duration:.2f} seconds")
                return state
                
            except Exception as e:
                logger.exception(f"Error in industry data processing: {str(e)}")
                self._add_error(state, f"산업 데이터 처리 오류: {str(e)}")
                
                # 오류 상태 업데이트
                state["agent_results"] = state.get("agent_results", {})
                state["agent_results"]["industry_analyzer"] = {
                    "agent_name": "industry_analyzer",
                    "status": "failed",
                    "data": [],
                    "error": str(e),
                    "execution_time": 0,
                    "metadata": {}
                }
                
                # 타입 주석을 사용한 데이터 할당
                if "retrieved_data" not in state:
                    state["retrieved_data"] = {}
                retrieved_data = cast(RetrievedData, state["retrieved_data"])
                industry_data_result: List[IndustryData] = []
                retrieved_data["industry"] = industry_data_result
                
                state["processing_status"] = state.get("processing_status", {})
                state["processing_status"]["industry_analyzer"] = "error"
                
                return state
                
        except Exception as e:
            logger.exception(f"Error in IndustryAnalyzerAgent: {str(e)}")
            self._add_error(state, f"산업 분석 에이전트 오류: {str(e)}")
            
            # 오류 상태 업데이트
            state["agent_results"] = state.get("agent_results", {})
            state["agent_results"]["industry_analyzer"] = {
                "agent_name": "industry_analyzer",
                "status": "failed",
                "data": [],
                "error": str(e),
                "execution_time": 0,
                "metadata": {}
            }
            
            # 타입 주석을 사용한 데이터 할당
            if "retrieved_data" not in state:
                state["retrieved_data"] = {}
            retrieved_data = cast(RetrievedData, state["retrieved_data"])
            industry_data_result: List[IndustryData] = []
            retrieved_data["industry"] = industry_data_result
            
            state["processing_status"] = state.get("processing_status", {})
            state["processing_status"]["industry_analyzer"] = "error"
            
            return state
    
    def _add_error(self, state: Dict[str, Any], error_message: str) -> None:
        """
        상태 객체에 오류 정보를 추가합니다.
        
        Args:
            state: 상태 객체
            error_message: 오류 메시지
        """
        state["errors"] = state.get("errors", [])
        state["errors"].append({
            "agent": "industry_analyzer",
            "error": error_message,
            "type": "processing_error",
            "timestamp": datetime.now(),
            "context": {"query": state.get("query", "")}
        })
    
    def _get_dummy_sector(self, stock_name: str) -> str:
        """종목명으로부터 더미 산업/섹터 정보를 반환합니다.

        Args:
            stock_name: 종목명

        Returns:
            str: 더미 산업/섹터 정보
        """
        # 실제로는 DB나 API를 통해 산업 정보를 조회해야 함
        sectors = {
            "삼성전자": "전자/반도체",
            "SK하이닉스": "반도체",
            "네이버": "인터넷/플랫폼",
            "카카오": "인터넷/플랫폼",
            "현대차": "자동차",
            "기아": "자동차",
            "LG화학": "화학/배터리",
            "삼성바이오로직스": "바이오/제약",
            "셀트리온": "바이오/제약",
            "POSCO홀딩스": "철강/금속"
        }
        
        return sectors.get(stock_name, "IT/소프트웨어")  # 기본값

    def _get_dummy_industry_data(self, stock_name: str, sector: str) -> List[Dict[str, Any]]:
        """더미 산업 동향 데이터를 반환합니다.

        Args:
            stock_name: 종목명
            sector: 산업/섹터

        Returns:
            List[Dict[str, Any]]: 더미 산업 동향 데이터
        """
        return [
            {
                "source": "산업 동향 보고서",
                "date": "2024-04-15",
                "title": f"{sector} 산업 동향 분석",
                "content": f"{sector} 산업은 2024년 상반기에 글로벌 수요 회복과 함께 성장세를 보이고 있습니다. 특히 {stock_name}이 속한 세부 분야는 전년 대비 약 12% 성장이 예상됩니다. 주요 성장 동력은 기술 혁신과 규제 환경 변화로 분석됩니다.",
                "key_trends": [
                    "디지털 전환 가속화로 인한 수요 증가",
                    "친환경 기술 투자 확대",
                    "글로벌 공급망 재편",
                    "핵심 원자재 가격 안정화"
                ]
            },
            {
                "source": "시장 조사 리포트",
                "date": "2024-03-20",
                "title": f"{sector} 시장 전망",
                "content": f"{sector} 시장은 2024-2028년 연평균 8.5% 성장이 전망됩니다. {stock_name}을 포함한 국내 기업들의 시장 점유율은 글로벌 시장에서 약 15%를 차지하고 있으며, 향후 기술 경쟁력 강화를 통해 20%까지 확대될 것으로 예상됩니다.",
                "market_data": {
                    "시장규모": "50조원 (2023년 기준)",
                    "연평균성장률": "8.5% (2024-2028 전망)",
                    "국내기업 점유율": "15%",
                    "주요 경쟁사": "글로벌 Top 5 기업 및 주요 점유율"
                }
            },
            {
                "source": "산업 뉴스 분석",
                "date": "2024-04-01",
                "title": f"{sector} 최근 이슈 및 정책 동향",
                "content": f"최근 정부는 {sector} 산업 경쟁력 강화를 위한 지원책을 발표했습니다. 약 2조원 규모의 R&D 지원과 세제 혜택이 포함되어 있어 {stock_name}을 포함한 국내 기업들에게 긍정적 영향이 예상됩니다. 또한 규제 완화를 통한 신사업 진출 기회도 확대될 전망입니다.",
                "policy_changes": [
                    "산업 지원 펀드 조성",
                    "기술 개발 세제 혜택 확대",
                    "신산업 규제 샌드박스 도입",
                    "해외 진출 지원 강화"
                ]
            }
        ]
        
    async def _analyze_industry_data(self, 
                                    industry_data: List[Dict[str, Any]],
                                    query: str,
                                    sector: str,
                                    stock_name: str,
                                    classification: Dict[str, Any],
                                    detail_level: str) -> Dict[str, Any]:
        """
        산업 데이터에 대한 분석을 수행합니다.
        
        Args:
            industry_data: 산업 데이터
            query: 사용자 쿼리
            sector: 산업/섹터
            stock_name: 종목명
            classification: 질문 분류 정보
            detail_level: 분석 세부 수준
            
        Returns:
            분석 결과
        """
        try:
            # 간단한 분석일 경우
            if detail_level == "간단" or classification.get("complexity", "") == "단순":
                return {
                    "summary": f"{sector} 산업 분석",
                    "highlights": [
                        f"{sector} 산업은 2024년 상반기 성장세를 보이고 있음",
                        f"{stock_name}이 속한 세부 분야는 전년 대비 12% 성장 예상",
                        "기술 혁신과 규제 환경 변화가 주요 성장 동력",
                        "디지털 전환 가속화와 친환경 기술 투자 확대가 주요 트렌드"
                    ],
                    "market_trends": {
                        "시장규모": "50조원 (2023년 기준)",
                        "성장률": "8.5% (2024-2028 전망)",
                        "주요 트렌드": "디지털 전환, 친환경, 공급망 재편"
                    }
                }
            
            # 상세 분석일 경우 - LLM을 통한 분석 수행
            # 프롬프트 생성
            prompt = PromptTemplate(
                template=INDUSTRY_ANALYSIS_PROMPT,
                input_variables=["industry_data", "query", "stock_name", "sector", "primary_intent"]
            )
            
            # JSON 파서 생성
            parser = JsonOutputParser()
            
            # 체인 구성 및 실행
            chain = prompt | self.llm | parser
            
            analysis = await chain.ainvoke({
                "industry_data": industry_data,
                "query": query,
                "stock_name": stock_name,
                "sector": sector,
                "primary_intent": classification.get("primary_intent", "일반")
            })
            
            return analysis
            
        except Exception as e:
            logger.error(f"산업 데이터 분석 중 오류 발생: {str(e)}")
            return {
                "summary": "산업 데이터 분석 중 오류가 발생했습니다.",
                "error": str(e)
            } 