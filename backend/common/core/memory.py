"""대화 메모리 관리 모듈

Redis를 사용하여 대화 컨텍스트를 분산 환경에서 관리합니다.
"""
import json
import time
from typing import List, Dict, Any, Optional
from uuid import UUID
from loguru import logger
from langchain.schema import AIMessage, HumanMessage, BaseMessage, SystemMessage
from common.core.redis import async_redis_client
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

# 대화 메모리 만료 시간 (1시간)
CHAT_MEMORY_EXPIRY = 60 * 60

class DistributedMemoryManager:
    """분산 환경에서 대화 컨텍스트를 관리하는 클래스"""
    
    _instance = None
    
    def __new__(cls, *args, **kwargs):
        """싱글톤 패턴 구현"""
        if cls._instance is None:
            cls._instance = super(DistributedMemoryManager, cls).__new__(cls)
            cls._instance.redis = async_redis_client
            logger.info("DistributedMemoryManager 인스턴스 생성")
        return cls._instance
    
    async def get_memory_key(self, session_id: str) -> str:
        """세션 ID로부터 Redis 키를 생성합니다."""
        return f"{async_redis_client.CHAT_MEMORY_PREFIX}{session_id}"
    
    async def add_user_message(self, session_id: str, message: str) -> bool:
        """사용자 메시지를 대화 히스토리에 추가합니다."""
        try:
            key = await self.get_memory_key(session_id)
            msg_obj = {"role": "user", "content": message, "timestamp": time.time()}
            await self.redis.rpush(key, msg_obj)
            
            # 메모리 만료 시간 설정 (1시간)
            await self.redis.redis.expire(key, CHAT_MEMORY_EXPIRY)
            
            # 최근 20개 메시지만 보관
            await self.redis.ltrim(key, -20, -1)
            logger.debug(f"사용자 메시지 추가: 세션={session_id}, 메시지='{message[:30]}...'")
            return True
        except Exception as e:
            logger.error(f"사용자 메시지 추가 실패: {str(e)}")
            return False
    
    async def add_ai_message(self, session_id: str, message: str) -> bool:
        """AI 메시지를 대화 히스토리에 추가합니다."""
        try:
            key = await self.get_memory_key(session_id)
            msg_obj = {"role": "assistant", "content": message, "timestamp": time.time()}
            await self.redis.rpush(key, msg_obj)
            
            # 메모리 만료 시간 설정 (1시간)
            await self.redis.redis.expire(key, CHAT_MEMORY_EXPIRY)
            
            # 최근 20개 메시지만 보관
            await self.redis.ltrim(key, -20, -1)
            logger.debug(f"AI 메시지 추가: 세션={session_id}, 메시지='{message[:30]}...'")
            return True
        except Exception as e:
            logger.error(f"AI 메시지 추가 실패: {str(e)}")
            return False
    
    async def add_system_message(self, session_id: str, message: str) -> bool:
        """시스템 메시지를 대화 히스토리에 추가합니다."""
        try:
            key = await self.get_memory_key(session_id)
            msg_obj = {"role": "system", "content": message, "timestamp": time.time()}
            await self.redis.rpush(key, msg_obj)
            
            # 메모리 만료 시간 설정 (1시간)
            await self.redis.redis.expire(key, CHAT_MEMORY_EXPIRY)
            logger.debug(f"시스템 메시지 추가: 세션={session_id}")
            return True
        except Exception as e:
            logger.error(f"시스템 메시지 추가 실패: {str(e)}")
            return False
    
    async def get_messages(self, session_id: str, limit: int = 20, db: Optional[AsyncSession] = None) -> List[BaseMessage]:
        """세션의 대화 메시지를 가져옵니다.
        
        Redis에 메시지가 없는 경우 DB에서 메시지를 조회하여 Redis에 저장합니다.
        
        Args:
            session_id: 채팅 세션 ID
            limit: 가져올 메시지 수
            db: 데이터베이스 세션 (선택, Redis에 데이터가 없을 경우 사용)
            
        Returns:
            List[BaseMessage]: 채팅 메시지 목록
        """
        try:
            key = await self.get_memory_key(session_id)
            raw_messages = await self.redis.lrange(key, -limit, -1)
            
            # Redis에 메시지가 없고 DB 세션이 제공된 경우 DB에서 조회
            if not raw_messages and db is not None:
                logger.info(f"Redis에 메시지가 없어 DB에서 조회합니다: 세션={session_id}")
                try:
                    # StockChatMessage 모델이 현재 네임스페이스에 없으므로 동적으로 가져옵니다
                    from stockeasy.models.chat import StockChatMessage
                    
                    # DB에서 메시지 조회
                    query = (
                        select(StockChatMessage)
                        .where(StockChatMessage.chat_session_id == session_id)
                        .order_by(StockChatMessage.created_at)
                        .limit(limit)
                    )
                    
                    result = await db.execute(query)
                    db_messages = result.scalars().all()
                    
                    if db_messages:
                        logger.info(f"DB에서 {len(db_messages)}개 메시지를 찾았습니다: 세션={session_id}")
                        
                        # DB 메시지를 Redis에 추가
                        for msg in db_messages:
                            msg_obj = {
                                "role": msg.role,
                                "content": msg.content,
                                "timestamp": msg.created_at.timestamp() if msg.created_at else time.time()
                            }
                            await self.redis.rpush(key, msg_obj)
                        
                        # 메모리 만료 시간 설정
                        await self.redis.redis.expire(key, CHAT_MEMORY_EXPIRY)
                        
                        # Redis에서 다시 조회
                        raw_messages = await self.redis.lrange(key, -limit, -1)
                    else:
                        logger.info(f"DB에서 메시지를 찾을 수 없습니다: 세션={session_id}")
                
                except Exception as e:
                    logger.error(f"DB에서 메시지 조회 실패: {str(e)}")
            
            # 메시지를 LangChain 형식으로 변환
            messages = []
            for raw_msg in raw_messages:
                msg = raw_msg  # JSON 파싱은 이미 redis.lrange 내에서 처리됨
                
                if msg["role"] == "user":
                    messages.append(HumanMessage(content=msg["content"]))
                elif msg["role"] == "assistant":
                    messages.append(AIMessage(content=msg["content"]))
                elif msg["role"] == "system":
                    messages.append(SystemMessage(content=msg["content"]))
            
            return messages
        except Exception as e:
            logger.error(f"대화 메시지 조회 실패: {str(e)}")
            return []
    
    async def get_messages_as_dict(self, session_id: str, limit: int = 20, db: Optional[AsyncSession] = None) -> List[Dict[str, Any]]:
        """세션의 대화 메시지를 딕셔너리 형태로 가져옵니다.
        
        Redis에 메시지가 없는 경우 DB에서 메시지를 조회하여 Redis에 저장합니다.
        
        Args:
            session_id: 채팅 세션 ID
            limit: 가져올 메시지 수
            db: 데이터베이스 세션 (선택, Redis에 데이터가 없을 경우 사용)
            
        Returns:
            List[Dict[str, Any]]: 채팅 메시지 목록
        """
        try:
            key = await self.get_memory_key(session_id)
            raw_messages = await self.redis.lrange(key, -limit, -1)
            
            # Redis에 메시지가 없고 DB 세션이 제공된 경우 DB에서 조회
            if not raw_messages and db is not None:
                # get_messages 메서드를 호출하여 DB에서 조회하고 Redis에 저장
                await self.get_messages(session_id, limit, db)
                
                # Redis에서 다시 조회
                raw_messages = await self.redis.lrange(key, -limit, -1)
            
            return raw_messages  # JSON 파싱은 이미 redis.lrange 내에서 처리됨
        except Exception as e:
            logger.error(f"대화 메시지 딕셔너리 조회 실패: {str(e)}")
            return []
    
    async def clear_memory(self, session_id: str) -> bool:
        """세션의 대화 메모리를 초기화합니다."""
        try:
            key = await self.get_memory_key(session_id)
            await self.redis.delete_key(key)
            logger.info(f"대화 메모리 초기화: 세션={session_id}")
            return True
        except Exception as e:
            logger.error(f"대화 메모리 초기화 실패: {str(e)}")
            return False
    
    async def get_chat_history_text(self, session_id: str, limit: int = 10, db: Optional[AsyncSession] = None) -> str:
        """대화 히스토리를 텍스트 형태로 가져옵니다."""
        messages = await self.get_messages_as_dict(session_id, limit, db)
        
        if not messages:
            return ""
        
        history_text = ""
        for msg in messages:
            role = "사용자" if msg["role"] == "user" else "AI"
            history_text += f"{role}: {msg['content']}\n\n"
        
        return history_text.strip()

# 메모리 관리자 싱글톤 인스턴스
chat_memory_manager = DistributedMemoryManager()

async def get_memory_manager() -> DistributedMemoryManager:
    """메모리 관리자 의존성 주입 함수"""
    return chat_memory_manager 