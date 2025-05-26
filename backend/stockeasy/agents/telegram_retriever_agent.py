"""
텔레그램 메시지 검색 에이전트 모듈

이 모듈은 사용자 질문에 관련된 텔레그램 메시지를 검색하는 에이전트 클래스를 구현합니다.
기존 텔레그램 검색 기능을 QuestionAnalyzerAgent의 결과를 활용하도록 개선합니다.
"""

import re
import json
import asyncio
import hashlib
from datetime import datetime, timezone, timedelta
import time
from zoneinfo import ZoneInfo
from loguru import logger
from typing import Dict, List, Any, Optional, Set, cast, Union


from langchain_openai import ChatOpenAI
from langchain_core.output_parsers import JsonOutputParser
#from sqlalchemy import UUID
from uuid import UUID
from common.services.reranker import PineconeRerankerConfig, Reranker, RerankerConfig, RerankerType
from common.services.retrievers.contextual_bm25 import ContextualBM25Config
from common.services.retrievers.hybrid import HybridRetriever, HybridRetrieverConfig
from stockeasy.prompts.telegram_prompts import TELEGRAM_SUMMARY_PROMPT, TELEGRAM_SUMMARY_PROMPT_2
from common.services.agent_llm import get_agent_llm, get_llm_for_agent
from common.utils.util import async_retry
from common.core.config import settings
from stockeasy.services.telegram.embedding import TelegramEmbeddingService, securities_mapping
from common.models.token_usage import ProjectType

from common.services.vector_store_manager import VectorStoreManager
from common.services.retrievers.semantic import SemanticRetriever, SemanticRetrieverConfig
from common.services.retrievers.models import DocumentWithScore, RetrievalResult
from stockeasy.models.agent_io import RetrievedAllAgentData, RetrievedTelegramMessage
from langchain_core.messages import AIMessage
from stockeasy.agents.base import BaseAgent
from sqlalchemy.ext.asyncio import AsyncSession

class TelegramRetrieverAgent(BaseAgent):
    """텔레그램 메시지 검색 에이전트"""
    
    def __init__(self, name: Optional[str] = None, db: Optional[AsyncSession] = None):
        """
        텔레그램 메시지 검색 에이전트 초기화
        
        Args:
            name: 에이전트 이름 (지정하지 않으면 클래스명 사용)
            db: 데이터베이스 세션 객체 (선택적)
        """
        super().__init__(name, db)
        self.retrieved_str = "telegram_messages"
        self.embedding_service = TelegramEmbeddingService()
        start_time = time.time()
        self.agent_llm = get_agent_llm("telegram_retriever_agent")
        end_time = time.time()
        duration = end_time - start_time
        logger.info(f"TelegramRetrieverAgent initialization time only llm: {duration:.2f} seconds")
        self.parser = JsonOutputParser()
        self.prompt_template = TELEGRAM_SUMMARY_PROMPT
        logger.info(f"TelegramRetrieverAgent initialized with provider: {self.agent_llm.get_provider()}, model: {self.agent_llm.get_model_name()}")
        # VectorStoreManager 캐시된 인스턴스 사용 (지연 초기화)
        self.vs_manager = None  # 실제 사용 시점에 AgentRegistry에서 가져옴
    
    def _parse_source_date(self, source_str: str) -> Optional[datetime]:
        """
        "내부DB, YYYY-MM-DD" 또는 "내부DB, 메세지일자 YYYYMMDD" 등 형식에서 날짜를 파싱합니다.
        성공하면 datetime 객체를, 실패하면 None을 반환합니다.
        파싱된 datetime은 Asia/Seoul timezone으로 localize됩니다.
        """
        if not source_str:
            return None
        
        # 예시 패턴: "YYYY-MM-DD", "YYYYMMDD"
        # 정규 표현식으로 날짜 부분 추출 시도
        match = re.search(r'(\d{4}-\d{2}-\d{2})|(\d{8})', source_str)
        if match:
            date_part = match.group(1) or match.group(2)
            try:
                if '-' in date_part:
                    dt = datetime.strptime(date_part, "%Y-%m-%d")
                else:
                    dt = datetime.strptime(date_part, "%Y%m%d")
                # ZoneInfo는 localize 메서드가 없으므로 replace 사용
                return dt.replace(tzinfo=ZoneInfo("Asia/Seoul"))
            except ValueError:
                logger.warning(f"소스 문자열에서 날짜 파싱 실패: '{source_str}' -> '{date_part}'")
                return None
        logger.warning(f"소스 문자열에서 날짜 패턴을 찾지 못함: '{source_str}'")
        return None

    async def process(self, state: Dict[str, Any]) -> Dict[str, Any]:
        """
        텔레그램 메시지 검색 및 처리를 수행합니다.
        
        Args:
            state: 현재 상태 정보
            
        Returns:
            업데이트된 상태 정보
        """
        try:
            start_time = datetime.now()
            
            # 상태 업데이트 - 콜백 함수 사용
            if "update_processing_status" in state and "agent_name" in state:
                state["update_processing_status"](state["agent_name"], "processing")
            else:
                # 기존 방식으로 상태 업데이트 (콜백 함수가 없는 경우)
                state["processing_status"] = state.get("processing_status", {})
                state["processing_status"]["telegram_retriever"] = "processing"
                
            query = state.get("query", "")
            
            question_analysis = state.get("question_analysis", {})
            entities = question_analysis.get("entities", {})
            classification = question_analysis.get("classification", {})
            data_requirements = question_analysis.get("data_requirements", {})
            keywords = question_analysis.get("keywords", [])
            detail_level = question_analysis.get("detail_level", "보통")
            
            stock_code = entities.get("stock_code", state.get("stock_code"))
            stock_name = entities.get("stock_name", state.get("stock_name"))
            sector = entities.get("sector", "")
            subgroup = question_analysis.get("subgroup", [])
            subgroup.append(stock_code)
            subgroup.append(stock_name)
            
            if not query:
                logger.warning("Empty query provided to TelegramRetrieverAgent")
                self._add_error(state, "검색 쿼리가 제공되지 않았습니다.")
                state["agent_results"] = state.get("agent_results", {})
                state["agent_results"]["telegram_retriever"] = {
                    "agent_name": "telegram_retriever", "status": "failed", 
                    "data": {"summary_text": "검색 쿼리 없음", "main_query_results": [], "toc_results": {}},
                    "error": "검색 쿼리가 제공되지 않았습니다.", "execution_time": 0,
                    "metadata": {"model_name": self.agent_llm.get_model_name(), "provider": self.agent_llm.get_provider()}
                }
                if "retrieved_data" not in state: state["retrieved_data"] = {}
                state["retrieved_data"][self.retrieved_str] = {
                    "main_query_results": [],
                    "toc_results": {}
                }
                return state
            
            logger.info(f"TelegramRetrieverAgent processing query: {query}")

            
            threshold = self._calculate_dynamic_threshold(classification)
            message_count = self._get_message_count(classification)
            
            search_query = self._make_search_query(query, stock_code, stock_name, classification, sector)
            
            user_context = state.get("user_context", {})
            user_id = user_context.get("user_id", None)

            messages:List[RetrievedTelegramMessage] = await self._search_messages(
                user_id=user_id,
                search_query=search_query,
                k=message_count, 
                threshold=threshold,
                subgroup=subgroup
            )
            
            
            custom_prompt_from_state = state.get("custom_prompt_template")
            custom_prompt_from_attr = getattr(self, "prompt_template_test", None)
            system_prompt_override = custom_prompt_from_state or custom_prompt_from_attr
            if system_prompt_override:
                logger.info(f"TelegramRetrieverAgent using custom prompt (from state or attribute)")
                
            final_report_toc = state.get("final_report_toc", {})
            
            summary_data: Dict[str, Any] = await self.summarize(
                query, stock_code, stock_name, messages, classification, user_id, system_prompt_override, final_report_toc
            )

            overall_summary_text = summary_data.get("overall_summary", "텔레그램 메시지에 대한 전체 요약 정보가 생성되지 않았습니다. 목차별 세부 내용을 참고하세요.")
            processed_main_results = summary_data.get("main_query_results", messages) 
            processed_toc_results = summary_data.get("toc_results", {})


            if not processed_main_results and not processed_toc_results :
                logger.warning("텔레그램 메시지 검색 결과가 없거나 요약 데이터가 없습니다.")
                end_time = datetime.now()
                duration = (end_time - start_time).total_seconds()
                
                state["agent_results"] = state.get("agent_results", {})
                state["agent_results"]["telegram_retriever"] = {
                    "agent_name": "telegram_retriever",
                    "status": "partial_success_no_data",
                    "data": {"summary_text": overall_summary_text, "main_query_results": [], "toc_results": {}},
                    "error": "텔레그램 메시지 검색 결과가 없거나 요약 데이터가 없습니다.",
                    "execution_time": duration,
                    "metadata": {"message_count": 0, "threshold": threshold, "model_name": self.agent_llm.get_model_name(), "provider": self.agent_llm.get_provider()}
                }
                
                if "retrieved_data" not in state: state["retrieved_data"] = {}
                state["retrieved_data"][self.retrieved_str] = {
                    "main_query_results": [],
                    "toc_results": {} 
                }
                
                # 상태 업데이트 - 콜백 함수 사용
                if "update_processing_status" in state and "agent_name" in state:
                    state["update_processing_status"](state["agent_name"], "completed_no_data")
                else:
                    # 기존 방식으로 상태 업데이트 (콜백 함수가 없는 경우)
                    state["processing_status"] = state.get("processing_status", {})
                    state["processing_status"]["telegram_retriever"] = "completed_no_data"
                
                logger.info(f"TelegramRetrieverAgent completed in {duration:.2f} seconds, found 0 messages or no summary data.")
                return state
                
            end_time = datetime.now()
            duration = (end_time - start_time).total_seconds()
            
            state["agent_results"] = state.get("agent_results", {})
            state["agent_results"]["telegram_retriever"] = {
                "agent_name": "telegram_retriever",
                "status": "success",
                "data": {
                    "summary_text": overall_summary_text,
                    "main_query_results": processed_main_results,
                    "toc_results": processed_toc_results        
                },
                "error": None,
                "execution_time": duration,
                "metadata": {
                    "message_count": len(processed_main_results),
                    "threshold": threshold,
                    "model_name": self.agent_llm.get_model_name(), "provider": self.agent_llm.get_provider()
                }
            }
            
            if "retrieved_data" not in state: state["retrieved_data"] = {}
            state["retrieved_data"][self.retrieved_str] = {
                "main_query_results": processed_main_results,
                "toc_results": processed_toc_results
            }
            
            # 상태 업데이트 - 콜백 함수 사용
            if "update_processing_status" in state and "agent_name" in state:
                state["update_processing_status"](state["agent_name"], "completed")
            else:
                # 기존 방식으로 상태 업데이트 (콜백 함수가 없는 경우)
                state["processing_status"] = state.get("processing_status", {})
                state["processing_status"]["telegram_retriever"] = "completed"
                
            logger.info(f"TelegramRetrieverAgent completed in {duration:.2f} seconds, found {len(processed_main_results)} messages")
            return state
            
        except Exception as e:
            logger.exception(f"Error in TelegramRetrieverAgent: {str(e)}")
            self._add_error(state, f"텔레그램 메시지 검색 에이전트 오류: {str(e)}")
            
            state["agent_results"] = state.get("agent_results", {})
            state["agent_results"]["telegram_retriever"] = {
                "agent_name": "telegram_retriever",
                "status": "failed",
                "data": {"summary_text": "", "main_query_results": [], "toc_results": {}},
                "error": str(e),
                "execution_time": 0,
                "metadata": {}
            }
            
            if "retrieved_data" not in state: state["retrieved_data"] = {}
            state["retrieved_data"][self.retrieved_str] = {"summary_text": "", "main_query_results": [], "toc_results": {} }
            
            # 상태 업데이트 - 콜백 함수 사용
            if "update_processing_status" in state and "agent_name" in state:
                state["update_processing_status"](state["agent_name"], "error")
            else:
                # 기존 방식으로 상태 업데이트 (콜백 함수가 없는 경우)
                state["processing_status"] = state.get("processing_status", {})
                state["processing_status"]["telegram_retriever"] = "error"
            
            return state

    @async_retry(retries=0, delay=2.0, exceptions=(Exception,))
    async def summarize(self, query:str, stock_code: str, stock_name: str, 
                        found_messages: List[RetrievedTelegramMessage], 
                        classification: Dict[str, Any], 
                        user_id: Optional[Union[str, UUID]] = None, 
                        system_prompt_override: Optional[str] = None,
                        final_report_toc: Optional[Dict[str, Any]] = None
                        ) -> Dict[str, Any]:
        
        default_overall_summary = "텔레그램 메시지에 대한 전체 요약 정보가 생성되지 않았습니다. 목차별 세부 내용을 참고하세요."
        default_summary_output = {
            "overall_summary": default_overall_summary,
            "toc_results": {},
            "main_query_results": found_messages 
        }

        if not found_messages:
            logger.warning("요약을 위한 메시지가 제공되지 않았습니다.")
            return default_summary_output
        
        # final_report_toc 로깅 - 디버깅용
        if final_report_toc:
            logger.info(f"final_report_toc 제공됨: {len(str(final_report_toc))}자")
        else:
            logger.warning("final_report_toc이 제공되지 않았습니다.")

        try:
            # title과 section_id 매핑 생성
            title_to_section_id = {}
            section_id_to_title = {}
            
            if final_report_toc and isinstance(final_report_toc, dict) and "sections" in final_report_toc:
                sections = final_report_toc.get("sections", [])
                if isinstance(sections, list):
                    # 최상위 섹션 매핑
                    for section in sections:
                        if isinstance(section, dict):
                            title = section.get("title")
                            section_id = section.get("section_id")
                            if title and section_id:
                                title_to_section_id[title] = section_id
                                section_id_to_title[section_id] = title
                            
                            # 하위 섹션 매핑
                            subsections = section.get("subsections", [])
                            if isinstance(subsections, list):
                                for subsection in subsections:
                                    if isinstance(subsection, dict):
                                        sub_title = subsection.get("title")
                                        sub_id = subsection.get("subsection_id")
                                        if sub_title and sub_id:
                                            title_to_section_id[sub_title] = sub_id
                                            section_id_to_title[sub_id] = sub_title
                
                logger.info(f"TOC title -> section_id 매핑 생성 완료: {len(title_to_section_id)}개 항목")
                if title_to_section_id:
                    logger.info(f"매핑 예시: {list(title_to_section_id.items())[:2]}")
                
                # 메시지가 있고 TOC가 있지만 매핑이 없는 경우 - 폴백으로 기본 목차 구조 생성
                if not title_to_section_id and isinstance(sections, list) and sections:
                    logger.warning("유효한 title과 section_id 매핑을 생성할 수 없어 기본 매핑 생성")
                    # 최소한 기본 section_id를 생성
                    for i, section in enumerate(sections):
                        if isinstance(section, dict) and "title" in section:
                            title = section["title"]
                            default_id = f"s{i+1}"
                            title_to_section_id[title] = default_id
                            section_id_to_title[default_id] = title
                            logger.info(f"기본 매핑 생성: '{title}' -> '{default_id}'")

            # 매핑이 없는 경우에 대한 폴백 처리
            if not title_to_section_id and found_messages:
                logger.warning("TOC 매핑이 없어 기본 목차 구조 생성")
                # 간단한 기본 목차 생성
                title_to_section_id = {
                    "종목 관련 주요 소식": "s1",
                    "실적 및 전망": "s2",
                    "투자 의견": "s3",
                    "기타 정보": "s4"
                }
                section_id_to_title = {v: k for k, v in title_to_section_id.items()}

            # LLM에 전달할 메시지 포맷팅
            formatted_messages_for_llm = []
            if found_messages:
                for i, msg in enumerate(found_messages):
                    created_at_dt = msg.get("message_created_at")
                    created_at_str = created_at_dt.strftime("%Y-%m-%d") if isinstance(created_at_dt, datetime) else "날짜정보없음"
                    content = msg.get("content", "")
                    score_val = msg.get("final_score", 0.0)
                    try:
                        score = float(score_val)
                    except (ValueError, TypeError):
                        score = 0.0

                    formatted_messages_for_llm.append(f"--- 메시지 인덱스: {i} ---")
                    formatted_messages_for_llm.append(f"- 메시지 일자: {created_at_str}\n- 내부점수: {score:.2f}\n- 메시지 내용:\n {content}")
                    formatted_messages_for_llm.append(f"--- 메시지 끝 ---")
            
            messages_text_for_llm = "\n".join(formatted_messages_for_llm)
            
            if system_prompt_override:
                prompt_context = system_prompt_override
            else:
                prompt_context = self.MakeSummaryPrompt2(stock_code, stock_name, final_report_toc)
            
            combined_prompt = f"{prompt_context}\n\n<메세지모음>\n{messages_text_for_llm}\n</메세지모음>\n\n"
            # 프롬프트 길이 로깅
            logger.info(f"LLM 요청 프롬프트 길이: {len(combined_prompt)}자")

            parsed_user_id = None
            if user_id and user_id != "test_user":
                parsed_user_id = UUID(user_id) if isinstance(user_id, str) else user_id
            
            response: AIMessage = await self.agent_llm.ainvoke_with_fallback(
                input=combined_prompt, user_id=parsed_user_id, project_type=ProjectType.STOCKEASY, db=self.db
            )

            if not response or not response.content or not isinstance(response.content, str):
                logger.error("LLM이 빈 응답 또는 문자열이 아닌 응답을 반환했습니다.")
                return self._fallback_toc_results(default_overall_summary, found_messages, section_id_to_title)

            llm_output_str = response.content
            # 응답 길이 로깅
            logger.info(f"LLM 응답 길이: {len(llm_output_str)}자")
            
            match = re.search(r"```json\s*([\s\S]*?)\s*```", llm_output_str, re.IGNORECASE)
            json_str = match.group(1) if match else llm_output_str

            try:
                parsed_llm_output = json.loads(json_str)
                if not parsed_llm_output:
                    logger.warning("LLM이 빈 JSON 객체를 반환했습니다.")
                    return self._fallback_toc_results(default_overall_summary, found_messages, section_id_to_title)
            except json.JSONDecodeError as json_e:
                logger.error(f"LLM 응답 JSON 파싱 실패: {json_e}. 응답 내용 (앞 500자): {llm_output_str[:500]}")
                return self._fallback_toc_results(default_overall_summary, found_messages, section_id_to_title)
            
            # LLM의 출력은 title을 키로 사용
            llm_toc_data = parsed_llm_output
            logger.info(f"LLM 응답 구조: {len(llm_toc_data)} 최상위 키, type:{type(llm_toc_data)}")
            
            # LLM 응답 키 로깅
            if isinstance(llm_toc_data, dict):
                top_keys = list(llm_toc_data.keys())
                if top_keys:
                    logger.info(f"LLM 응답 최상위 키 예시: {top_keys[:3]}")

            toc_results_structured: Dict[str, List[RetrievedTelegramMessage]] = {}
            if isinstance(llm_toc_data, dict):
                # 각 title 키를 처리
                for title_key, content_items in llm_toc_data.items():
                    # title_key를 section_id로 변환 (매핑에 없으면 title_key 그대로 사용)
                    section_id = title_to_section_id.get(title_key, title_key)
                    
                    # # 변환 로그 기록
                    # if section_id != title_key:
                    #     logger.info(f"Title '{title_key}' -> section_id '{section_id}' 매핑됨")
                    # else:
                    #     logger.info(f"Title '{title_key}' 매핑 없음, 원본 사용")
                    
                    if isinstance(content_items, list):
                        messages_for_this_section: List[RetrievedTelegramMessage] = []
                        for item in content_items:
                            if isinstance(item, dict):
                                #logger.info(f"item: {item}")
                                content = item.get("content", "내용 없음")
                                source = item.get("source", "")
                                msg_date = self._parse_source_date(source) or datetime.now(ZoneInfo("Asia/Seoul"))
                                
                                structured_msg: RetrievedTelegramMessage = {
                                    "content": content,
                                    "message_created_at": msg_date,
                                    "final_score": 0.5,
                                    "metadata": {
                                        "source_type": item.get("type", "unknown"),
                                        "original_source_string": source,
                                        "llm_generated_for_toc": True,
                                        "toc_key": section_id,
                                        "original_title": title_key
                                    }
                                }
                                messages_for_this_section.append(structured_msg)
                        if messages_for_this_section:
                            toc_results_structured[section_id] = messages_for_this_section
            
            # 결과가 비어있는지 확인
            # if not toc_results_structured:
            #     logger.warning("LLM이 생성한 TOC 결과가 비어있어 대체 결과 생성")
            #     return self._fallback_toc_results(default_overall_summary, found_messages, section_id_to_title)
            
            logger.info(f"TOC 결과 생성 완료: {len(toc_results_structured)}개 섹션")
            
            return {
                "overall_summary": default_overall_summary,
                "toc_results": toc_results_structured,
                "main_query_results": found_messages
            }
            
        except Exception as e:
            error_msg = f"메시지 요약 및 구조화 중 오류 발생: {str(e)}"
            logger.error(error_msg, exc_info=True)
            return self._fallback_toc_results(default_overall_summary, found_messages, {})

    def _fallback_toc_results(
        self, summary: str, messages: List[RetrievedTelegramMessage], 
        section_id_to_title: Dict[str, str]
    ) -> Dict[str, Any]:
        """LLM 응답이 실패했을 때 대체 결과를 생성합니다"""
        logger.info("폴백 TOC 결과 생성 시작")
        
        fallback_toc_results: Dict[str, List[RetrievedTelegramMessage]] = {}
        
        # 섹션 ID가 없으면 기본 섹션 생성
        if not section_id_to_title:
            section_id_to_title = {
                "s1": "종목 관련 주요 소식",
                "s2": "실적 및 전망",
                "s3": "투자 의견",
                "s4": "기타 정보"
            }
        
        # 메시지가 없으면 빈 결과 반환
        if not messages:
            logger.warning("폴백 생성을 위한 메시지가 없습니다")
            return {
                "overall_summary": summary,
                "toc_results": {},
                "main_query_results": []
            }
        
        # 1. 메시지를 시간순으로 정렬
        sorted_msgs = sorted(messages, 
                            key=lambda x: x.get("message_created_at", datetime.now()) 
                            if isinstance(x.get("message_created_at"), datetime) 
                            else datetime.now())
        
        # 2. 전체 메시지 수
        total_msgs = len(sorted_msgs)
        
        # 3. 각 섹션에 메시지 할당
        section_ids = list(section_id_to_title.keys())
        msgs_per_section = max(1, total_msgs // len(section_ids))
        
        for i, section_id in enumerate(section_ids):
            start_idx = i * msgs_per_section
            end_idx = (i + 1) * msgs_per_section if i < len(section_ids) - 1 else total_msgs
            
            if start_idx >= total_msgs:
                continue
                
            section_msgs = sorted_msgs[start_idx:end_idx]
            
            if section_msgs:
                # 각 메시지에 메타데이터 추가
                enhanced_msgs = []
                for msg in section_msgs:
                    msg_copy = msg.copy()
                    if "metadata" not in msg_copy:
                        msg_copy["metadata"] = {}
                    
                    msg_copy["metadata"]["llm_generated_for_toc"] = False
                    msg_copy["metadata"]["toc_key"] = section_id
                    msg_copy["metadata"]["assigned_by_fallback"] = True
                    enhanced_msgs.append(msg_copy)
                
                fallback_toc_results[section_id] = enhanced_msgs
        
        logger.info(f"폴백 TOC 결과 생성 완료: {len(fallback_toc_results)}개 섹션")
        
        return {
            "overall_summary": summary,
            "toc_results": fallback_toc_results,
            "main_query_results": messages
        }

    def MakeSummaryPrompt2(self,stock_code: str, stock_name: str, final_report_toc: Optional[Dict[str, Any]]) -> str:
        """
        제공된 TELEGRAM_SUMMARY_PROMPT_2를 사용하여 최종 프롬프트를 구성합니다.
        """
        toc_string = json.dumps(final_report_toc, indent=2, ensure_ascii=False) if final_report_toc else "제공된 목차 없음"
        
        # TELEGRAM_SUMMARY_PROMPT_2는 사용자가 제공한 내용을 그대로 사용합니다.
        # 이 프롬프트는 LLM이 JSON을 반환하도록 하는 상세 지침을 포함해야 합니다.
        # 예시 JSON 구조 (TELEGRAM_SUMMARY_PROMPT_2에 명시되어야 함):
        # {
        #   "섹션제목_1": [ {"type": "text", "content": "...", "source": "내부DB, 메세지일자"} ],
        #   ...
        # }
        # 만약 "overall_summary"도 필요하다면, TELEGRAM_SUMMARY_PROMPT_2에 해당 내용도 포함시켜야 합니다.
        core_extraction_guidance = TELEGRAM_SUMMARY_PROMPT_2 
        
        final_prompt = f"""{core_extraction_guidance}

<추가 컨텍스트 정보>
종목명: {stock_name}
종목코드: {stock_code}
최종 보고서 목차:
{toc_string}
</추가 컨텍스트 정보>

위 정보를 바탕으로, <메세지모음> 단락에 제공될 메시지들을 분석하여 요청된 JSON 형식으로 출력을 생성해주십시오.
"""
        # 실제로는 TELEGRAM_SUMMARY_PROMPT_2에 {{stock_name}}, {{stock_code}}, {{final_report_toc}} 같은 플레이스홀더를 두고
        # .format()을 사용하는 것이 더 일반적입니다. 여기서는 문자열 결합으로 처리.
        return final_prompt
    
    # MakeSummaryPrompt 함수는 현재 summarize 로직에서 직접 사용되지 않으므로 그대로 둡니다.
    def MakeSummaryPrompt(self, classification: Dict[str, Any]) -> str:
        base_prompt = self.prompt_template # self.prompt_template 사용
        primary_intent = classification.get("primary_intent", "기타")
        intent_prompt = ""
        if primary_intent == "종목기본정보": intent_prompt = "종목 기본 정보에 관한 질문입니다..." 
        elif primary_intent == "성과전망": intent_prompt = "해당 종목의 성과 및 전망에 관한 질문입니다..."
        elif primary_intent == "재무분석": intent_prompt = "재무 분석에 관한 질문입니다..."
        elif primary_intent == "산업동향": intent_prompt = "산업 동향에 관한 질문입니다..."
        
        complexity = classification.get("complexity", "중간")
        complexity_prompt = ""
        if complexity == "단순": complexity_prompt = "간결하고 직접적인 요약을 제공하세요..."
        elif complexity == "중간": complexity_prompt = "균형 잡힌 요약을 제공하세요..."
        elif complexity == "복합": complexity_prompt = "상세한 요약을 제공하세요..."
        elif complexity == "전문가급": complexity_prompt = "심층적이고 전문적인 분석 요약을 제공하세요..."
        
        answer_type = classification.get("expected_answer_type", "사실형")
        answer_type_prompt = ""
        if answer_type == "사실형": answer_type_prompt = "사실에 기반한 객관적인 정보 중심으로 요약하세요..."
        elif answer_type == "추론형": answer_type_prompt = "주어진 정보를 바탕으로 논리적 추론을 제공하세요..."
        elif answer_type == "비교형": answer_type_prompt = "비교 분석을 중심으로 요약하세요..."
        elif answer_type == "예측형": answer_type_prompt = "미래 전망에 초점을 맞춰 요약하세요..."
        elif answer_type == "설명형": answer_type_prompt = "개념과 관계를 명확히 설명하는 요약을 제공하세요..."
        elif answer_type == "종합형": answer_type_prompt = "다양한 관점과 정보를 종합적으로 분석하여 전체적인 상황을 요약하세요..."
        else: answer_type_prompt = "다양한 관점과 정보를 종합적으로 분석하여 전체적인 상황을 요약하세요..." # 기본값
        
        additional_prompt = f"\n{intent_prompt}\n{complexity_prompt}\n{answer_type_prompt}\n종합적으로, 이 메시지들을 분석하여 질문에 대한 명확하고 유용한 답변을 제공하세요. 답변 시에는 메시지의 신뢰도, 최신성, 관련성을 고려하여 가중치를 부여하세요."
        final_prompt = base_prompt + additional_prompt
        return final_prompt

    def _add_error(self, state: Dict[str, Any], error_message: str) -> None:
        """
        상태 객체에 오류 정보를 추가합니다.
        
        Args:
            state: 상태 객체
            error_message: 오류 메시지
        """
        state["errors"] = state.get("errors", [])
        state["errors"].append({
            "agent": "telegram_retriever",
            "error": error_message,
            "type": "processing_error",
            "timestamp": datetime.now(),
            "context": {"query": state.get("query", "")}
        })
    
    def _calculate_dynamic_threshold(self, classification: Dict[str, Any]) -> float:
        """
        질문 복잡도에 따른 동적 유사도 임계값 계산
        
        Args:
            classification: 분류 결과
            
        Returns:
            유사도 임계값
        """
        complexity = classification.get("complexity", "중간")
        
        # 복잡도에 따른 임계값 설정
        if complexity == "단순":
            return 0.5  # 단순 질문일수록 높은 임계값 (정확한 결과 필요)
        elif complexity == "중간":
            return 0.35
        elif complexity == "복합":
            return 0.25
        else:  # "전문가급"
            return 0.21  # 복잡한 질문일수록 낮은 임계값 (폭넓은 결과 수집)
    
    def _get_message_count(self, classification: Dict[str, Any]) -> int:
        """
        복잡도에 따른 검색 메시지 수 결정
        
        Args:
            classification: 분류 결과
            
        Returns:
            검색할 메시지 수
        """
        complexity = classification.get("complexity", "중간")
        
        if complexity == "단순":
            return 5
        elif complexity == "중간":
            return 10
        elif complexity == "복합":
            return 15
        else:  # "전문가급"
            return 20
    
    def _calculate_message_importance(self, message: str) -> float:
        """
        메시지의 중요도를 계산합니다.
        
        Args:
            message: 중요도를 계산할 메시지
            
        Returns:
            0~1 사이의 중요도 점수
        """
        importance_score = 0.0
        
        # 1. 금액/수치 정보 포함 여부 (40%)
        if re.search(r'[0-9]+(?:,[0-9]+)*(?:\.[0-9]+)?%?원?', message):
            importance_score += 0.4
            
        # 2. 주요 키워드 포함 여부 (40%)
        important_keywords = [
            '실적', '공시', '매출', '영업이익', '순이익',
            '계약', '특허', '인수', '합병', 'M&A',
            '상한가', '하한가', '급등', '급락',
            '목표가', '투자의견', '리포트'
        ]
        keyword_count = sum(1 for keyword in important_keywords if keyword in message)
        if keyword_count > 0:
            importance_score += min(0.4, keyword_count * 0.2)  # 키워드당 0.2점, 최대 0.4점
        
        # 3. 메시지 길이 가중치 (20%)
        msg_length = len(message)
        if 50 <= msg_length <= 500:
            importance_score += 0.2
        elif 20 <= msg_length < 50 or 500 < msg_length <= 1000:
            importance_score += 0.1
            
        return importance_score
    
    def _is_duplicate(self, message_content_hash: str, seen_content_hashes: Set[str]) -> bool:
        """
        메시지가 이미 처리된 메시지 중 중복인지 확인합니다.
        
        Args:
            message_content_hash: 검사할 메시지의 해시값
            seen_content_hashes: 이미 처리된 메시지 해시 집합
            
        Returns:
            중복 여부
        """
        return message_content_hash in seen_content_hashes
    
    def _calculate_time_weight(self, created_at: datetime) -> float:
        """
        메시지 생성 시간 기반의 가중치를 계산합니다.
        
        Args:
            created_at: 메시지 생성 시간 (datetime 객체)
            
        Returns:
            시간 기반 가중치 (0.4 ~ 1.0)
        """
        try:
            seoul_tz = timezone(timedelta(hours=9), 'Asia/Seoul')
        
            # naive datetime인 경우 서버 로컬 시간(Asia/Seoul)으로 간주
            if created_at.tzinfo is None:
                created_at = created_at.replace(tzinfo=ZoneInfo("Asia/Seoul"))
                
            # now도 timezone 정보를 포함하도록 수정
            now = datetime.now(seoul_tz)
            delta = now - created_at
            
            # 시간 차이에 따른 가중치 설정
            if delta.days < 1:  # 24시간 이내
                return 1.0
            elif delta.days < 7:  # 1주일 이내
                return 0.9
            elif delta.days < 14:  # 2주일 이내
                return 0.8
            elif delta.days < 30:  # 1개월 이내
                return 0.6
            else:  # 1개월 이상
                return 0.4
                
        except Exception as e:
            logger.warning(f"시간 가중치 계산 오류: {str(e)}")
            return 0.5  # 오류 시 중간값 반환
    
    def _make_search_query(self, query: str, stock_code: Optional[str], 
                          stock_name: Optional[str], classification: Dict[str, Any],
                          sector: Optional[str] = None) -> str:
        """
        검색 쿼리를 구성합니다.
        
        Args:
            query: 원본 사용자 쿼리
            stock_code: 종목 코드
            stock_name: 종목 이름
            classification: 질문 분류 정보
            sector: 산업 섹터 정보

        Returns:
            검색을 위한 향상된 쿼리 문자열
        """
        primary_intent = classification.get("primary_intent", "")
        important_keywords = []
        if primary_intent == "현재가치": important_keywords.extend(["현재가", "주가", "시세", "시가총액"])
        elif primary_intent == "성과전망": important_keywords.extend(["전망", "예측", "기대", "목표가"])
        elif primary_intent == "투자의견": important_keywords.extend(["투자의견", "매수", "매도", "보유", "추천"])
        elif primary_intent == "재무정보": important_keywords.extend(["실적", "매출", "영업이익", "순이익", "재무"])
        elif primary_intent == "기업정보": important_keywords.extend(["기업", "사업", "제품", "서비스"])
        
        query_parts = [query]
        if stock_name and isinstance(stock_name, str): query_parts.append(stock_name)
        if stock_code and isinstance(stock_code, str): query_parts.append(stock_code)
        if sector and isinstance(sector, str): query_parts.append(sector)
        query_parts.extend(k for k in important_keywords if k) # None이나 빈 문자열 제외
        return " ".join(list(dict.fromkeys(query_parts))) # 중복제거 및 순서유지
    
    @async_retry(retries=0, delay=1.0, exceptions=(Exception,))
    async def _search_messages(self, search_query: str, k: int, threshold: float, user_id: Optional[Union[str, UUID]] = None, subgroup: Optional[List[str]] = None) -> List[RetrievedTelegramMessage]:
        """
        텔레그램 메시지 검색을 수행합니다.
        
        Args:
            search_query: 검색 쿼리
            k: 검색할 메시지 수
            threshold: 유사도 임계값
            user_id: 사용자 ID (문자열 또는 UUID 객체)
            
        Returns:
            검색된 텔레그램 메시지 목록
        """
        try:
            logger.info(f"Generated search query: {search_query}")
            
            # VectorStoreManager 캐시된 인스턴스 사용 (지연 초기화)
            if self.vs_manager is None:
                logger.debug("글로벌 캐시에서 VectorStoreManager 가져오기 시작 (TelegramRetriever)")
                
                # 글로벌 캐시 함수를 직접 사용
                from stockeasy.graph.agent_registry import get_cached_vector_store_manager
                
                self.vs_manager = get_cached_vector_store_manager(
                    embedding_model_type=self.embedding_service.get_model_type(),
                    namespace=settings.PINECONE_NAMESPACE_STOCKEASY_TELEGRAM,
                    project_name="stockeasy"
                )
                logger.debug("글로벌 캐시에서 VectorStoreManager 가져오기 완료 (TelegramRetriever)")
            
            initial_k = min(k * 3, 40) # 최대 가져올 문서 수 약간 늘림
            
            parsed_user_id = None
            if user_id and user_id != "test_user":
                parsed_user_id = UUID(user_id) if isinstance(user_id, str) else user_id
            
            semantic_retriever_config = SemanticRetrieverConfig(min_score=threshold,
                                                    user_id=parsed_user_id,
                                                    project_type=ProjectType.STOCKEASY    )
            # 시맨틱 검색 설정
            semantic_retriever = SemanticRetriever(
                config=semantic_retriever_config,
                vs_manager=self.vs_manager
            )
            
            # 외국계 증권사 필터 준비
            # dict_values는 직렬화할 수 없으므로 list로 변환해야 함
            securities_values = list(securities_mapping.values())
            # 중복 제거
            unique_securities = list(set(securities_values))
            foreign_filters = {"keywords": {"$in": unique_securities}}
            
            # 병렬 검색 태스크 준비
            search_tasks = [
                # 일반 검색
                semantic_retriever.retrieve(
                    query=search_query, 
                    top_k=initial_k
                ),
                # 외국계 증권사 필터 검색
                semantic_retriever.retrieve(
                    query=search_query, 
                    top_k=initial_k,
                    filters=foreign_filters
                )
            ]
            
            # subgroup이 존재하고 비어있지 않을 때만 subgroup 필터 검색 추가
            subgroup_task_added = False
            if subgroup and len(subgroup) > 0:
                subgroup_filters = {"keywords": {"$in": subgroup}}
                logger.info(f"[텔레검색] subgroup_filters: {subgroup_filters}")
                
                search_tasks.append(
                    semantic_retriever.retrieve(
                        query=search_query, 
                        top_k=initial_k,
                        filters=subgroup_filters
                    )
                )
                subgroup_task_added = True
            else:
                logger.info("[텔레검색] subgroup이 없거나 비어있어 subgroup 검색 제외")
            
            # 병렬 검색 실행
            search_results = await asyncio.gather(*search_tasks)
            
            # 결과 분리
            result = search_results[0]  # 일반 검색
            result_foreign = search_results[1]  # 외국계 증권사 검색
            result_subgroup = search_results[2] if subgroup_task_added else None  # 서브그룹 검색
            
            logger.info(f"[병렬검색 완료] 일반: {len(result.documents)}개, 외국계: {len(result_foreign.documents)}개, 서브그룹: {len(result_subgroup.documents) if result_subgroup else 0}개")

            # 검색 결과 통합
            combined_documents = []
            doc_ids = set()  # 문서 ID 중복 방지를 위한 집합
            
            # 일반 검색 결과 추가
            for doc in result.documents:
                doc_id = f"{doc.metadata.get('channel_id')}_{doc.metadata.get('message_id')}"
                if doc_id not in doc_ids:
                    combined_documents.append(doc)
                    doc_ids.add(doc_id)
            
            # 외국계 증권사 필터 검색 결과 추가 (중복 제외)
            for doc in result_foreign.documents:
                doc_id = f"{doc.metadata.get('channel_id')}_{doc.metadata.get('message_id')}"
                if doc_id not in doc_ids:
                    combined_documents.append(doc)
                    doc_ids.add(doc_id)
            
            # 서브그룹 필터 검색 결과 추가 (중복 제외)
            if result_subgroup:
                for doc in result_subgroup.documents:
                    doc_id = f"{doc.metadata.get('channel_id')}_{doc.metadata.get('message_id')}"
                    if doc_id not in doc_ids:
                        combined_documents.append(doc)
                        doc_ids.add(doc_id)
            
            if len(combined_documents) == 0:
                logger.warning(f"No telegram messages found for query: {search_query}")
                return []
            logger.info(f"Found {len(combined_documents)} telegram messages after combining results (general: {len(result.documents)}, foreign securities: {len(result_foreign.documents)})")
            
            # 중복 메시지 필터링 및 점수 계산
            processed_messages = []
            seen_messages = set()  # 중복 확인용
            remove_duplicated_result = []
            
            for doc in combined_documents:
                doc_metadata = doc.metadata
                content = doc.page_content# doc_metadata.get("text", "")
                
                # 내용이 없거나 너무 짧은 메시지 제외
                if not content or len(content) < 20:
                    continue
                
                normalized_content = re.sub(r'\s+', ' ', content).strip().lower()
                # 중복 메시지 확인
                if self._is_duplicate(normalized_content, seen_messages):
                    #logger.info(f"중복 메시지 제외: {normalized_content[:50]}")
                    continue
                    
                seen_messages.add(self._get_message_hash(normalized_content))
                remove_duplicated_result.append(doc)
            
            # 중복 제거된 청크로. 리랭킹 수행

            # 2. 리랭킹 수행
            async with Reranker(
                RerankerConfig(
                    reranker_type=RerankerType.PINECONE,
                    pinecone_config=PineconeRerankerConfig(
                        api_key=settings.PINECONE_API_KEY_STOCKEASY,
                        min_score=0.2  # 낮은 임계값으로 더 많은 결과 포함
                    )
                )
            ) as reranker:
                reranked_results = await reranker.rerank(
                    query=search_query,
                    documents=remove_duplicated_result,
                    top_k=k
                )

            logger.info(f"리랭킹 완료 - 결과: {len(result.documents)} -> {len(reranked_results.documents)} 문서")

            # 종복 제거된 것으로
            for doc in reranked_results.documents:
                doc_metadata = doc.metadata
                content = doc.page_content
                # 메시지 중요도 계산
                importance_score = self._calculate_message_importance(content)
                
                # 시간 기반 가중치 계산
                message_created_at_data = doc.metadata.get("message_created_at")
                message_created_at = None
                
                # message_created_at을 datetime 객체로 변환 (다양한 형식 지원)
                if isinstance(message_created_at_data, str):
                    # ISO 형식 문자열인 경우
                    try:
                        message_created_at = datetime.fromisoformat(message_created_at_data)
                    except (ValueError, TypeError):
                        # ISO 형식이 아닌 경우 다른 형식 시도
                        logger.warning(f"ISO 형식이 아닌 문자열: {message_created_at_data}, 다른 형식 시도")
                        try:
                            # 유닉스 타임스탬프 문자열인지 확인
                            message_created_at = datetime.fromtimestamp(float(message_created_at_data))
                        except (ValueError, TypeError):
                            # 기본값으로 현재 시간 사용
                            logger.error(f"시간 형식 변환 실패: {message_created_at_data}, 현재 시간 사용")
                            message_created_at = datetime.now()
                elif isinstance(message_created_at_data, (int, float)):
                    # 유닉스 타임스탬프인 경우
                    try:
                        # 밀리초를 초 단위로 변환
                        timestamp_in_seconds = float(message_created_at_data) / 1000.0
                        message_created_at = datetime.fromtimestamp(timestamp_in_seconds)
                    except (ValueError, TypeError):
                        # 변환 실패 시 현재 시간 사용
                        logger.error(f"타임스탬프 변환 실패: {message_created_at_data}, 현재 시간 사용")
                        message_created_at = datetime.now()
                else:
                    # 지원되지 않는 형식인 경우 현재 시간 사용
                    logger.error(f"지원되지 않는 시간 형식: {type(message_created_at_data)}, 현재 시간 사용")
                    message_created_at = datetime.now()
                
                time_weight = self._calculate_time_weight(message_created_at)
                
                # 최종 점수 = 유사도 * 중요도 * 시간 가중치
                #final_score = doc.score * importance_score * time_weight
                final_score = (doc.score * 0.65) + (time_weight * 0.35)
                # 메시지 데이터 구성
                message:RetrievedTelegramMessage = {
                    "content": content,
                    #"channel_name": doc_metadata.get("channel_title", "알 수 없음"), # 그러나 숨겨야함
                    "message_created_at": message_created_at,
                    "final_score": final_score,
                    "metadata": doc_metadata
                }
                
                processed_messages.append(message)
            
            # 최종 점수 기준으로 정렬하고 상위 k개 선택
            processed_messages.sort(key=lambda x: x["final_score"], reverse=True)
            logger.info(f"최종 점수 기준으로 정렬된 메시지 수: {len(processed_messages)}")
            result_messages = processed_messages[:k]
            
            # 점수 분포 정규화
            if result_messages:
                max_score = max(msg["final_score"] for msg in result_messages)
                min_score = min(msg["final_score"] for msg in result_messages)
                score_range = max_score - min_score if max_score > min_score else 1.0
                
                for msg in result_messages:
                    msg["normalized_score"] = (msg["final_score"] - min_score) / score_range
            
            return result_messages
            
        except Exception as e:
            logger.exception(f"Error searching telegram messages: {str(e)}")
            raise 

    def _get_message_hash(self, content: str) -> str:
        """
        메시지 내용의 해시값을 생성합니다.
        
        Args:
            content: 메시지 내용
            
        Returns:
            메시지 해시값
        """
        # 메시지 전처리 (공백 제거, 소문자 변환)
        normalized_content = re.sub(r'\s+', ' ', content).strip().lower()
        
        # 너무 긴 메시지는 앞부분만 사용
        if len(normalized_content) > 200:
            normalized_content = normalized_content[:200]
            
        # SHA-256 해시 생성하여 반환
        return hashlib.sha256(normalized_content.encode('utf-8')).hexdigest() 