"""
LLM 설정 관리자 모듈

이 모듈은 에이전트별 LLM 설정을 관리하는 기능을 제공합니다.
설정 파일을 로드하고 에이전트별 LLM 설정을 검색할 수 있습니다.
"""

import os
import json
import time
from typing import Dict, Any, Optional
from loguru import logger
from functools import lru_cache
from pathlib import Path

class LLMConfigManager:
    """에이전트별 LLM 설정을 관리하는 클래스"""
    
    _instance = None
    _last_modified_time = 0
    _config_cache = None
    
    def __new__(cls):
        """싱글톤 패턴 구현"""
        if cls._instance is None:
            cls._instance = super(LLMConfigManager, cls).__new__(cls)
            cls._instance._initialized = False
        return cls._instance
    
    def __init__(self):
        """설정 관리자 초기화"""
        if not getattr(self, "_initialized", False):
            self._config_path = os.path.join(
                os.path.dirname(os.path.abspath(__file__)), 
                "agent_llm_config.json"
            )
            self._check_config_file()
            self._config = self._load_config()
            self._initialized = True
            logger.info(f"LLMConfigManager 초기화 완료: {self._config_path}")
            
    def _check_config_file(self) -> None:
        """설정 파일이 존재하는지 확인하고 기본 설정 파일 생성"""
        if not os.path.exists(self._config_path):
            logger.warning(f"설정 파일이 없습니다: {self._config_path}")
            
            # 기본 설정 생성
            default_config = {
                "default": {
                    "provider": "openai",
                    "model_name": "gpt-4o-mini",
                    "temperature": 0,
                    "max_tokens": 2048
                },
                "agents": {}
            }
            
            # 파일 생성
            os.makedirs(os.path.dirname(self._config_path), exist_ok=True)
            with open(self._config_path, "w", encoding="utf-8") as f:
                json.dump(default_config, f, indent=2, ensure_ascii=False)
                
            logger.info(f"기본 설정 파일 생성: {self._config_path}")
    
    def _get_file_modified_time(self) -> float:
        """파일 수정 시간 확인"""
        if not os.path.exists(self._config_path):
            return 0
        return os.path.getmtime(self._config_path)
    
    def _load_config(self) -> Dict[str, Any]:
        """설정 파일 로드"""
        try:
            modified_time = self._get_file_modified_time()
            
            # 캐시된 설정이 있고 파일이 변경되지 않았으면 캐시 사용
            if (self._config_cache is not None and 
                self._last_modified_time >= modified_time):
                return self._config_cache
            
            # 파일 로드
            with open(self._config_path, "r", encoding="utf-8") as f:
                config = json.load(f)
            
            # 캐시 업데이트
            self._config_cache = config
            self._last_modified_time = modified_time
            
            logger.info(f"LLM 설정 파일 로드 완료: {self._config_path}")
            return config
            
        except Exception as e:
            logger.error(f"설정 파일 로드 중 오류 발생: {str(e)}")
            
            # 기본 설정 반환
            return {
                "default": {
                    "provider": "openai",
                    "model_name": "gpt-4o-mini",
                    "temperature": 0,
                    "max_tokens": 2048
                },
                "agents": {}
            }
    
    def refresh(self) -> None:
        """설정 파일 다시 로드"""
        self._config = self._load_config()
        logger.info("LLM 설정 파일 새로고침 완료")
    
    def get_agent_config(self, agent_name: str) -> Dict[str, Any]:
        """
        에이전트별 LLM 설정 반환
        
        Args:
            agent_name: 에이전트 이름
            
        Returns:
            에이전트별 LLM 설정
        """
        # 설정 파일 상태 확인 및 필요 시 재로드
        modified_time = self._get_file_modified_time()
        if modified_time > self._last_modified_time:
            self.refresh()
        
        # 에이전트 설정 확인
        agent_config = self._config.get("agents", {}).get(agent_name, None)
        
        # 에이전트 설정이 없으면 기본 설정 사용
        if agent_config is None:
            logger.info(f"에이전트 {agent_name}의 설정이 없습니다. 기본 설정을 사용합니다.")
            return self._config.get("default", {})
        
        # 기본 설정과 에이전트 설정 병합
        default_config = self._config.get("default", {}).copy()
        default_config.update(agent_config)
        
        return default_config
    
    def get_fallback_settings(self) -> Dict[str, Any]:
        """
        폴백 설정 반환
        
        Returns:
            폴백 설정
        """
        # 설정 파일 상태 확인 및 필요 시 재로드
        modified_time = self._get_file_modified_time()
        if modified_time > self._last_modified_time:
            self.refresh()
            
        return self._config.get("fallback_settings", {
            "enabled": False,
            "max_retries": 3,
            "providers": []
        })
    
    def update_agent_config(self, agent_name: str, config: Dict[str, Any]) -> None:
        """
        에이전트 설정 업데이트
        
        Args:
            agent_name: 에이전트 이름
            config: 새 설정
        """
        # 설정 파일 다시 로드
        self._config = self._load_config()
        
        # 에이전트 설정 업데이트
        self._config.setdefault("agents", {})[agent_name] = config
        
        # 파일 저장
        with open(self._config_path, "w", encoding="utf-8") as f:
            json.dump(self._config, f, indent=2, ensure_ascii=False)
            
        # 캐시 업데이트
        self._config_cache = self._config
        self._last_modified_time = self._get_file_modified_time()
        
        logger.info(f"에이전트 {agent_name} 설정 업데이트 완료")
    
    def get_all_configs(self) -> Dict[str, Any]:
        """
        모든 설정 반환
        
        Returns:
            전체 설정
        """
        # 설정 파일 상태 확인 및 필요 시 재로드
        modified_time = self._get_file_modified_time()
        if modified_time > self._last_modified_time:
            self.refresh()
            
        return self._config
    
    def get_config_path(self) -> str:
        """
        설정 파일 경로 반환
        
        Returns:
            설정 파일 경로
        """
        return self._config_path

# 싱글톤 인스턴스 생성
llm_config_manager = LLMConfigManager()

# 에이전트 설정 가져오기 함수
def get_agent_llm_config(agent_name: str) -> Dict[str, Any]:
    """
    에이전트별 LLM 설정 반환
    
    Args:
        agent_name: 에이전트 이름
        
    Returns:
        에이전트별 LLM 설정
    """
    return llm_config_manager.get_agent_config(agent_name) 