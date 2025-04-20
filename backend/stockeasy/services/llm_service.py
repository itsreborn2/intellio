import json
import re
import logging
from typing import Dict, Any, List, Optional
from common.services.agent_llm import get_agent_llm
#from common.services.llm_service import LLMService as CommonLLMService

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)  # 명시적으로 INFO 레벨 설정

class FinancialLLMService:
    """
    재무데이터 처리를 위한 LLM 서비스
    """
    
    def __init__(self):
        self.agent_llm = get_agent_llm("gemini-2.0-flash")
    
    async def structure_income_statement_table(self, table_text: str) -> Dict[str, Any]:
        """
        LLM을 사용하여 테이블 데이터를 구조화하는 함수
        
        Args:
            table_text: 테이블 데이터 텍스트
            
        Returns:
            구조화된 재무 데이터
        """

        # 루트는 financial_summary로 그냥 통일하자. 아닌가?
        # LLM 프롬프트 구성
        prompt = f"""
        아래는 기업의 연결 포괄손익계산서 페이지입니다. 이 페이지에서 손익계산서 항목과 값을 추출하고 다음 JSON 형식으로 구조화해주세요:
         각 테이블 위에 '(단위: 백만원)' 같은 형식으로 단위가 표시되어 있습니다.
        {{
          "financial_summary": [
            {{
              "item_name": "항목명(예: 매출액)",
              "item_code": "표준화된 항목 코드(예: revenue)",
              "is_cumulative": true, // 손익계산서 항목은 대부분 누적값이므로 true
              "values": [
                {{
                  "year": 2022, // 보고서의 연도
                  "quarter": 1, // 분기 보고서의 경우 1, 2, 3, 4 중 해당하는 분기, 연간 보고서의 경우 null
                  "value": 10000, // 단위 금액
                  "unit": "십억원"
                }}
              ]
            }}
          ]
        }}
        
        포괄손익계산서 페이지:
        {table_text}
        
        다음 항목들에 특히 주의하세요:
        1. 항목명은 원본 그대로 유지하되, item_code는 표준화된 코드로 변환해주세요
           - 매출액 -> revenue
           - 매출원가 -> cost_of_sales
           - 매출총이익 -> gross_profit
           - 판매비와관리비 -> selling_general_administrative_expenses
           - 영업이익 -> operating_income
           - 기타수익 -> other_income
           - 기타비용 -> other_expenses
           - 금융수익 -> financial_income
           - 금융원가 -> financial_costs
           - 법인세비용차감전순이익 -> profit_before_income_tax
           - 법인세비용 -> income_tax_expense
           - 당기순이익 -> net_income
           - 기타포괄손익 -> other_comprehensive_income
           - 총포괄손익 -> total_comprehensive_income
           - 기본주당이익 -> basic_earnings_per_share
           - 희석주당이익 -> diluted_earnings_per_share
        2. 숫자의 단위는 변경하지 말고, 원본 그대로 유지해주세요.
        3. 누락된 데이터는 null로 표시해주세요
        4. 손익계산서 항목은 is_cumulative를 true로 설정하세요
        5. 페이지에서 연도와 분기 정보를 추출하세요
           - "제NN기 3분기"와 같은 형식으로 표시되어 있을 수 있습니다
           - 연간 보고서의 경우 quarter를 null로, 분기 보고서의 경우 해당 분기 번호를 설정하세요
        6. 중요: 최대한 많은 항목을 추출하되, 동일한 항목을 중복해서 추출하지 마세요.
        
        중요: 반드시 유효한 JSON 형식으로 응답해주세요. 오류 없이 JSON.parse()로 파싱될 수 있어야 합니다.
        """
        
        try:
            # LLM 서비스 호출
            logger.info(f"LLM 호출 시작: 입력 텍스트 길이={len(table_text)}자")
            #logger.info(f"{table_text}")
            response = self.agent_llm.invoke_with_fallback(
                [{"role": "user", "content": prompt}],
            )
            
            # AIMessage 객체 처리
            if hasattr(response, 'content'):
                response_text = response.content
            else:
                response_text = str(response)
            
            logger.info(f"LLM 응답 수신: 응답 길이={len(response_text)}자")
            
            # JSON 응답 파싱
            json_match = re.search(r'```(?:json)?\s*([\s\S]*?)\s*```', response_text)
            if json_match:
                json_str = json_match.group(1)
                logger.info(f"JSON 코드 블록 추출: 길이={len(json_str)}자")
            else:
                # 코드 블록 형식이 아닌 경우 전체 텍스트에서 JSON 검색
                json_str = response_text
                logger.info("코드 블록을 찾을 수 없어 전체 텍스트 처리")
            
            # 불필요한 주석 제거
            json_str = re.sub(r'//.*$', '', json_str, flags=re.MULTILINE)
            
            # 불완전한 JSON 복구 시도
            if not self._is_valid_json(json_str):
                logger.warning("불완전한 JSON 감지, 복구 시도 중...")
                json_str = self._attempt_json_fix(json_str)
            
            try:
                parsed_json = json.loads(json_str)
                logger.info("JSON 파싱 성공")
                
                # financial_summary 키가 없는 경우 기본 구조 생성
                if "financial_summary" not in parsed_json:
                    logger.warning("financial_summary 키가 없어 기본 구조 생성")
                    parsed_json = {"financial_summary": []}
                
                # 간소화된 데이터 구조로 변환 (cumulative_value와 period_value는 DB에 저장할 때 필요한 경우 생성)
                for item in parsed_json.get("financial_summary", []):
                    for value in item.get("values", []):
                        if "cumulative_value" not in value and "value" in value:
                            if item.get("is_cumulative", False):
                                value["cumulative_value"] = value["value"]
                                value["period_value"] = value["value"]
                            else:
                                value["cumulative_value"] = value["value"]
                                value["period_value"] = value["value"]
                
                return parsed_json
            except json.JSONDecodeError as e:
                logger.error(f"JSON 파싱 오류, 오류 위치: {e.pos}, 원인: {e.msg}")
                logger.error(f"JSON 문자열 일부: {json_str[:200]}...")
                
                # 에러 데이터 반환
                return {
                    "error": "구조화 실패", 
                    "message": f"JSON 파싱 오류: {str(e)}",
                    "financial_summary": []  # 기본값 제공
                }
                
        except Exception as e:
            logger.error(f"LLM 처리 중 오류 발생: {e}", exc_info=True)
            return {
                "error": "LLM 처리 실패", 
                "message": str(e),
                "financial_summary": []  # 기본값 제공
            }
    
    def _is_valid_json(self, json_str: str) -> bool:
        """
        JSON 문자열이 유효한지 검사합니다.
        
        Args:
            json_str: 검사할 JSON 문자열
            
        Returns:
            유효하면 True, 그렇지 않으면 False
        """
        try:
            json.loads(json_str)
            return True
        except json.JSONDecodeError:
            return False
    
    def _attempt_json_fix(self, json_str: str) -> str:
        """
        불완전한 JSON 문자열을 복구하려고 시도합니다.
        
        Args:
            json_str: 복구할 JSON 문자열
            
        Returns:
            복구된 JSON 문자열
        """
        # 기본 형태 감지
        if json_str.strip().startswith('{'):
            # 중괄호 개수 확인
            open_braces = json_str.count('{')
            close_braces = json_str.count('}')
            
            # 필요한 닫는 중괄호 추가
            if open_braces > close_braces:
                logger.info(f"중괄호 불균형 감지: 여는 중괄호 {open_braces}개, 닫는 중괄호 {close_braces}개")
                json_str = json_str + ('}' * (open_braces - close_braces))
                logger.info("닫는 중괄호 추가로 JSON 복구 시도")
                
            # 불필요한 텍스트 제거 시도
            if not self._is_valid_json(json_str):
                # JSON이 시작하는 위치부터 마지막 중괄호까지만 추출
                match = re.search(r'(\{[\s\S]*\})', json_str)
                if match:
                    json_str = match.group(1)
                    logger.info("정규식으로 유효한 JSON 부분 추출 시도")
        
        return json_str
    
    def normalize_financial_unit(self, value: float, unit: str) -> float:
        """
        재무 데이터 단위를 원 단위로 정규화하는 함수
        
        Args:
            value: 원본 값
            unit: 단위 (원, 백만원, 억원 등)
            
        Returns:
            원 단위로 정규화된 값
        """
        if unit == "원":
            return value
        elif unit == "천원":
            return value * 1000
        elif unit == "백만원":
            return value * 1000000
        elif unit == "십억원":
            return value * 1000000000
        elif unit == "백억원":
            return value * 10000000000
        elif unit == "천억원":
            return value * 100000000000
        elif unit == "억원": # 억원이 가장 마지막에.
            return value * 100000000
        elif unit == "조원":
            return value * 1000000000000
        else:
            # 기본값은 원 단위로 가정
            logger.warning(f"알 수 없는 단위: {unit}, 원 단위로 가정합니다")
            return value 