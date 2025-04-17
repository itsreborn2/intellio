"""
채팅 서비스 모듈.

이 모듈은 채팅 세션 및 메시지 관리를 위한 기능을 제공합니다.
"""
from typing import List, Dict, Any, Optional
from uuid import UUID, uuid4
import json
from datetime import datetime

from sqlalchemy import select, update, delete
from sqlalchemy.ext.asyncio import AsyncSession
from loguru import logger

from common.utils.db_utils import get_one_or_none
from stockeasy.models.chat import StockChatSession, StockChatMessage
from common.utils.util import remove_null_chars


# JSON 직렬화를 위한 커스텀 인코더 (datetime 객체 처리)
class DateTimeEncoder(json.JSONEncoder):
    def default(self, obj):
        if isinstance(obj, datetime):
            return obj.isoformat()
        return super().default(obj)


class ChatService:
    """채팅 서비스 클래스.
    
    채팅 세션 및 메시지 관련 데이터베이스 작업을 처리합니다.
    """
    
    @staticmethod
    async def create_chat_session(
        db: AsyncSession, 
        user_id: UUID, 
        title: str = "새 채팅",
        stock_code: Optional[str] = None,
        stock_name: Optional[str] = None,
        stock_info: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """새 채팅 세션을 생성합니다.
        
        Args:
            db: 데이터베이스 세션
            user_id: 사용자 ID
            title: 채팅 세션 제목 (기본값: "새 채팅")
            stock_code: 종목 코드 (선택)
            stock_name: 종목명 (선택)
            stock_info: 종목 관련 추가 정보 (선택)
            
        Returns:
            Dict[str, Any]: 생성된 채팅 세션 정보
        """
        try:
            # 새 채팅 세션 생성
            chat_session = StockChatSession(
                user_id=user_id,
                title=title,
                is_active=True,
                stock_code=stock_code,
                stock_name=stock_name,
                stock_info=stock_info
            )
            
            db.add(chat_session)
            await db.flush()
            await db.refresh(chat_session)
          
            await db.commit()
            
            # 세션 정보를 딕셔너리로 변환
            return {
                "ok": True,
                "status_message": "정상 응답 완료",
                "id": str(chat_session.id),
                "user_id": str(chat_session.user_id),
                "title": chat_session.title,
                "is_active": chat_session.is_active,
                "stock_code": chat_session.stock_code,
                "stock_name": chat_session.stock_name,
                "stock_info": chat_session.stock_info,
                "created_at": chat_session.created_at.isoformat() if chat_session.created_at else None,
                "updated_at": chat_session.updated_at.isoformat() if chat_session.updated_at else None
            }
            
        except Exception as e:
            await db.rollback()
            logger.error(f"채팅 세션 생성 중 오류 발생: {str(e)}")
            return {
                "ok": False,
                "status_message": "세션 생성 실패",
                "id": None,
                "user_id": None,
                "title": None,
                "is_active": None,
                "stock_code": None,
                "stock_name": None,
                "stock_info": None,
                "created_at": chat_session.created_at.isoformat() if chat_session.created_at else None,
                "updated_at": chat_session.updated_at.isoformat() if chat_session.updated_at else None
            }
            
    
    @staticmethod
    async def get_chat_sessions(
        db: AsyncSession, 
        user_id: UUID,
        is_active: Optional[bool] = None
    ) -> List[Dict[str, Any]]:
        """사용자의 채팅 세션 목록을 조회합니다.
        
        Args:
            db: 데이터베이스 세션
            user_id: 사용자 ID
            is_active: 활성화 상태 필터 (선택)
            
        Returns:
            List[Dict[str, Any]]: 채팅 세션 목록
        """
        try:
            # 쿼리 기본 설정
            query = select(StockChatSession).where(StockChatSession.user_id == user_id)
            
            # 활성화 상태 필터 추가
            if is_active is not None:
                query = query.where(StockChatSession.is_active == is_active)
            
            # 최신순 정렬
            query = query.order_by(StockChatSession.updated_at.desc())
            
            # 쿼리 실행
            result = await db.execute(query)
            chat_sessions = result.scalars().all()
            
            # 결과를 딕셔너리 리스트로 변환
            return [
                {
                    "ok": True,
                    "status_message": "채팅 세션 목록 조회 완료",
                    "id": str(chat_session.id),
                    "user_id": str(chat_session.user_id),
                    "title": chat_session.title,
                    "is_active": chat_session.is_active,
                    "stock_code": chat_session.stock_code,
                    "stock_name": chat_session.stock_name,
                    "stock_info": chat_session.stock_info,
                    "created_at": chat_session.created_at.isoformat() if chat_session.created_at else None,
                    "updated_at": chat_session.updated_at.isoformat() if chat_session.updated_at else None
                }
                for chat_session in chat_sessions
            ]
            
        except Exception as e:
            logger.error(f"채팅 세션 조회 중 오류 발생: {str(e)}")
            return [
                {
                    "ok": False,
                    "status_message": "채팅 세션 조회에 실패하였습니다.",
                    "id": None,
                    "user_id": None,
                    "title": None,
                    "is_active": None,
                    "stock_code": None,
                    "stock_name": None,
                    "stock_info": None,
                    "created_at": None,
                    "updated_at": None
                }
            ]    
    @staticmethod
    async def get_chat_session(
        db: AsyncSession, 
        session_id: UUID, 
        user_id: Optional[UUID] = None
    ) -> Optional[Dict[str, Any]]:
        """특정 채팅 세션의 상세 정보를 조회합니다.
        
        Args:
            db: 데이터베이스 세션
            session_id: 채팅 세션 ID
            user_id: 사용자 ID (권한 검증용, 선택)
            
        Returns:
            Optional[Dict[str, Any]]: 채팅 세션 정보 (존재하지 않는 경우 None)
        """
        try:
            # 쿼리 기본 설정
            query = select(StockChatSession).where(StockChatSession.id == session_id)
            
            # 사용자 ID 필터 추가 (선택)
            if user_id:
                query = query.where(StockChatSession.user_id == user_id)
            
            # 쿼리 실행
            chat_session = await get_one_or_none(db, query)
            
            # 세션이 없는 경우 None 반환
            if not chat_session:
                return None
            
            # 결과를 딕셔너리로 변환
            return {
                "ok": True,
                "status_message": "채팅 세션 상세 조회 완료",
                "id": str(chat_session.id),
                "user_id": str(chat_session.user_id),
                "title": chat_session.title,
                "is_active": chat_session.is_active,
                "stock_code": chat_session.stock_code,
                "stock_name": chat_session.stock_name,
                "stock_info": chat_session.stock_info,
                "created_at": chat_session.created_at.isoformat() if chat_session.created_at else None,
                "updated_at": chat_session.updated_at.isoformat() if chat_session.updated_at else None
            }
            
        except Exception as e:
            logger.error(f"채팅 세션 상세 조회 중 오류 발생: {str(e)}")
            raise
    
    @staticmethod
    async def update_chat_session(
        db: AsyncSession, 
        session_id: UUID, 
        user_id: UUID,
        update_data: Dict[str, Any]
    ) -> Optional[Dict[str, Any]]:
        """채팅 세션 정보를 업데이트합니다.
        
        Args:
            db: 데이터베이스 세션
            session_id: 채팅 세션 ID
            user_id: 사용자 ID (권한 검증용)
            update_data: 업데이트할 데이터
            
        Returns:
            Optional[Dict[str, Any]]: 업데이트된 채팅 세션 정보 (존재하지 않는 경우 None)
        """
        try:
            # 먼저 해당 세션이 존재하는지 확인
            query = select(StockChatSession).where(
                StockChatSession.id == session_id,
                StockChatSession.user_id == user_id
            )
            session = await get_one_or_none(db, query)
            
            # 세션이 없는 경우 None 반환
            if not session:
                return None
            
            # 업데이트 가능한 필드 목록
            allowed_fields = {"title", "stock_code", "stock_name", "stock_info", "is_active", "agent_results"}
            
            # 허용된 필드만 업데이트
            update_values = {k: v for k, v in update_data.items() if k in allowed_fields}
            
            # NULL 문자(\u0000) 제거
            if "agent_results" in update_values and update_values["agent_results"] is not None:
                update_values["agent_results"] = remove_null_chars(update_values["agent_results"])
                
                # datetime 객체 처리
                update_values["agent_results"] = json.loads(
                    json.dumps(update_values["agent_results"], cls=DateTimeEncoder)
                )
            
            # 업데이트 실행
            update_stmt = (
                update(StockChatSession)
                .where(StockChatSession.id == session_id)
                .values(**update_values)
                .execution_options(synchronize_session="fetch")
            )
            await db.execute(update_stmt)
            
            # 업데이트된 세션 조회
            await db.refresh(session)
            await db.commit()
            
            # 결과를 딕셔너리로 변환
            return {
                "id": str(session.id),
                "user_id": str(session.user_id),
                "title": session.title,
                "stock_code": session.stock_code,
                "stock_name": session.stock_name,
                "stock_info": session.stock_info,
                "agent_results": session.agent_results,
                "is_active": session.is_active,
                "created_at": session.created_at.isoformat() if session.created_at else None,
                "updated_at": session.updated_at.isoformat() if session.updated_at else None
            }
            
        except Exception as e:
            await db.rollback()
            logger.error(f"채팅 세션 업데이트 중 오류 발생: {str(e)}")
            raise
    
    @staticmethod
    async def delete_chat_session(
        db: AsyncSession, 
        session_id: UUID, 
        user_id: UUID
    ) -> bool:
        """채팅 세션을 삭제합니다.
        
        Args:
            db: 데이터베이스 세션
            session_id: 채팅 세션 ID
            user_id: 사용자 ID (권한 검증용)
            
        Returns:
            bool: 삭제 성공 여부
        """
        try:
            # 삭제 실행 (CASCADE 옵션으로 연결된 메시지도 함께 삭제됨)
            delete_stmt = (
                delete(StockChatSession)
                .where(
                    StockChatSession.id == session_id,
                    StockChatSession.user_id == user_id
                )
                .execution_options(synchronize_session="fetch")
            )
            result = await db.execute(delete_stmt)
            await db.commit()
            
            # 영향을 받은 행이 1개라면 삭제 성공
            return result.rowcount == 1
            
        except Exception as e:
            await db.rollback()
            logger.error(f"채팅 세션 삭제 중 오류 발생: {str(e)}")
            raise
    
    @staticmethod
    async def create_chat_message(
        db: AsyncSession, 
        chat_session_id: UUID, 
        role: str, 
        content: str,
        message_id: Optional[UUID] = None,
        content_expert: Optional[str] = None,
        stock_code: Optional[str] = None,
        stock_name: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
        agent_results: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """새 채팅 메시지를 생성합니다.
        
        Args:
            db: 데이터베이스 세션
            session_id: 채팅 세션 ID
            role: 메시지 역할 (user, assistant, system)
            content: 메시지 내용
            message_id: 메시지 ID (선택, None이면 자동 생성)
            content_expert: 전문가 모드 메시지 내용 (선택)
            stock_code: 종목 코드 (선택)
            stock_name: 종목명 (선택)
            metadata: 메시지 메타데이터 (선택)
            agent_results: 에이전트 처리 결과 데이터 (선택)
            
        Returns:
            Dict[str, Any]: 생성된 채팅 메시지 정보
        """
        try:
            # datetime 객체가 포함된 JSON 데이터 처리
            if metadata is not None:
                metadata = json.loads(json.dumps(metadata, cls=DateTimeEncoder))
                
            # agent_results에 datetime 객체가 포함되어 있는 경우 처리
            if agent_results is not None:
                agent_results = json.loads(json.dumps(agent_results, cls=DateTimeEncoder))
            
            # 메시지 생성
            message_params = {
                "chat_session_id": chat_session_id,
                "role": role,
                "content": content,
                "content_expert": content_expert,
                "stock_code": stock_code,
                "stock_name": stock_name,
                "message_metadata": metadata,
                "agent_results": agent_results
            }

            # id가 있는 경우에만 추가
            if message_id is not None:
                message_params["id"] = message_id

            message = StockChatMessage(**message_params)
            
            db.add(message)
            await db.flush()
            await db.refresh(message)
            
            # 관련 세션의 updated_at 업데이트
            session_update = (
                update(StockChatSession)
                .where(StockChatSession.id == chat_session_id)
                .values(updated_at=datetime.now())
                .execution_options(synchronize_session="fetch")
            )
            await db.execute(session_update)
            
            await db.commit()
            
            # 메시지 정보를 딕셔너리로 변환
            return {
                "id": str(message.id),
                "chat_session_id": str(message.chat_session_id),
                "role": message.role,
                "content": message.content,
                "content_expert": message.content_expert,
                "stock_code": message.stock_code,
                "stock_name": message.stock_name,
                "metadata": message.message_metadata,
                "agent_results": message.agent_results,
                "created_at": message.created_at.isoformat() if message.created_at else None,
                "updated_at": message.updated_at.isoformat() if message.updated_at else None
            }
            
        except Exception as e:
            await db.rollback()
            logger.error(f"채팅 메시지 생성 중 오류 발생: {str(e)}")
            raise
    
    @staticmethod
    async def get_chat_messages(
        db: AsyncSession, 
        session_id: UUID,
        user_id: Optional[UUID] = None,
        limit: int = 100,
        offset: int = 0
    ) -> List[Dict[str, Any]]:
        """특정 채팅 세션의 메시지 목록을 조회합니다.
        
        Args:
            db: 데이터베이스 세션
            session_id: 채팅 세션 ID
            user_id: 사용자 ID (권한 검증용, 선택)
            limit: 조회할 최대 메시지 수 (기본값: 100)
            offset: 조회 시작 위치 (기본값: 0)
            
        Returns:
            List[Dict[str, Any]]: 채팅 메시지 목록
        """
        try:
            # 사용자 권한 확인 (선택)
            if user_id:
                session_query = select(StockChatSession).where(
                    StockChatSession.id == session_id,
                    StockChatSession.user_id == user_id
                )
                session = await get_one_or_none(db, session_query)
                
                # 세션이 없거나 권한이 없는 경우 빈 리스트 반환
                if not session:
                    return []
            
            # 메시지 쿼리 구성
            query = (
                select(StockChatMessage)
                .where(StockChatMessage.chat_session_id == session_id)
                .order_by(StockChatMessage.created_at)
                .limit(limit)
                .offset(offset)
            )
            
            # 쿼리 실행
            result = await db.execute(query)
            messages = result.scalars().all()
            
            # 결과를 딕셔너리 리스트로 변환
            return [
                {
                    "ok": True,
                    "status_message": "채팅 메시지 조회 완료",
                    "id": str(message.id),
                    "chat_session_id": str(message.chat_session_id),
                    "role": message.role,
                    "content": message.content,
                    "content_expert": message.content_expert,
                    "stock_code": message.stock_code,
                    "stock_name": message.stock_name,
                    "metadata": message.message_metadata,
                    "agent_results": message.agent_results,
                    "created_at": message.created_at.isoformat() if message.created_at else None,
                    "updated_at": message.updated_at.isoformat() if message.updated_at else None
                }
                for message in messages
            ]
            
        except Exception as e:
            logger.error(f"채팅 메시지 조회 중 오류 발생: {str(e)}")
            return [
                {
                    "ok": False,
                    "status_message": "채팅 메시지 조회에 실패하였습니다.",
                    "id": None,
                    "session_id": None,
                    "role": None,
                    "content": None,
                    "stock_code": None,
                    "stock_name": None,
                    "metadata": None,
                    "agent_results": None,
                    "created_at": None,
                    "updated_at": None
                }
            ]
    
    @staticmethod
    async def get_chat_session_agent_results(
        db: AsyncSession, 
        session_id: UUID, 
        user_id: Optional[UUID] = None
    ) -> Dict[str, Any]:
        """특정 채팅 세션의 agent_results만 조회합니다.
        
        Args:
            db: 데이터베이스 세션
            session_id: 채팅 세션 ID
            user_id: 사용자 ID (권한 검증용, 선택)
            
        Returns:
            Dict[str, Any]: 채팅 세션의 agent_results (세션이 없거나 결과가 없으면 빈 딕셔너리)
        """
        try:
            # 쿼리 기본 설정 - agent_results 필드만 조회
            query = select(StockChatSession.agent_results).where(StockChatSession.id == session_id)
            
            # 사용자 ID 필터 추가 (선택)
            if user_id:
                query = query.where(StockChatSession.user_id == user_id)
            
            # 쿼리 실행
            result = await db.execute(query)
            agent_results = result.scalar_one_or_none()
            
            if agent_results is None:
                logger.warning(f"채팅 세션을 찾을 수 없음: {session_id}")
                return {}
            
            logger.info(f"채팅 세션 {session_id}의 agent_results 조회 완료")
            return agent_results or {}
            
        except Exception as e:
            logger.error(f"채팅 세션 agent_results 조회 중 오류 발생: {str(e)}")
            return {}