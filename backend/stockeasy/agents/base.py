"""
기본 에이전트 인터페이스 정의

이 모듈은 모든 에이전트가 구현해야 하는 기본 인터페이스를 정의합니다.
각 에이전트는 이 기본 클래스를 상속받아 구현합니다.
"""

from abc import ABC, abstractmethod
from typing import Dict, Any, Optional
from sqlalchemy.ext.asyncio import AsyncSession

class BaseAgent(ABC):
    """모든 에이전트의 기본 인터페이스를 정의하는 추상 클래스"""
    
    def __init__(self, name: Optional[str] = None, db: Optional[AsyncSession] = None):
        """에이전트 초기화
        
        Args:
            name: 에이전트 이름 (지정하지 않으면 클래스명 사용)
            db: 데이터베이스 세션 객체 (선택적)
        """
        self._name = name or self.__class__.__name__
        self.db = db
        self.prompt_template = None
        self.prompt_template_test = None
    
    @abstractmethod
    async def process(self, state: Dict[str, Any]) -> Dict[str, Any]:
        """상태를 입력받아 처리하고 업데이트된 상태를 반환
        
        Args:
            state: 현재 에이전트 상태
            
        Returns:
            업데이트된 에이전트 상태
        """
        pass
    
    def get_name(self) -> str:
        """에이전트 이름 반환
        
        Returns:
            에이전트 이름
        """
        return self._name
    
    async def __call__(self, state: Dict[str, Any]) -> Dict[str, Any]:
        """에이전트를 함수처럼 호출할 수 있게 함
        
        이 메서드는 process 메서드를 호출하고 오류 처리를 수행합니다.
        
        Args:
            state: 현재 에이전트 상태
            
        Returns:
            업데이트된 에이전트 상태
        """
        try:
            # 성능 측정 시작 (향후 구현)
            
            # 에이전트 처리 수행
            updated_state = await self.process(state)
            
            # 성능 측정 종료 (향후 구현)
            
            return updated_state
        except Exception as e:
            # 오류 발생 시 원래 상태에 오류 정보 추가
            errors = state.get("errors", [])
            errors.append({
                "agent": self.get_name(),
                "error": str(e),
                "type": type(e).__name__
            })
            
            return {
                **state,
                "errors": errors
            } 
    
    def _add_error(self, state: Dict[str, Any], error_message: str) -> None:
        """상태에 오류 정보를 추가
        
        Args:
            state: 현재 상태
            error_message: 오류 메시지
        """
        errors = state.get("errors", [])
        errors.append({
            "agent": self.get_name(),
            "error": error_message,
            "type": "ProcessingError",
            "timestamp": None  # 호출자가 필요시 타임스탬프 추가
        })
        state["errors"] = errors 