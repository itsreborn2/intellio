"""
채팅 서비스 모듈.

이 모듈은 채팅 세션 및 메시지 관리를 위한 기능을 제공합니다.
"""

import json
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional
from uuid import UUID, uuid4

import pytz
from fastapi import HTTPException
from loguru import logger
from sqlalchemy import delete, func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from common.core.config import settings
from common.utils.db_utils import get_one_or_none
from common.utils.util import remove_null_chars
from stockeasy.models.chat import ShareStockChatMessage, ShareStockChatSession, StockChatMessage, StockChatSession
from stockeasy.schemas.chat import ShareLinkResponse


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
        db: AsyncSession, user_id: UUID, title: str = "새 채팅", stock_code: Optional[str] = None, stock_name: Optional[str] = None, stock_info: Optional[Dict[str, Any]] = None
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
            chat_session = StockChatSession(user_id=user_id, title=title, is_active=True, stock_code=stock_code, stock_name=stock_name, stock_info=stock_info)

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
                "updated_at": chat_session.updated_at.isoformat() if chat_session.updated_at else None,
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
                "updated_at": chat_session.updated_at.isoformat() if chat_session.updated_at else None,
            }

    @staticmethod
    async def get_chat_sessions(
        db: AsyncSession,
        user_id: UUID,
        is_active: Optional[bool] = None,
        limit: int = 50,  # 기본값 50개로 제한
        offset: int = 0,  # 페이징을 위한 offset
    ) -> Dict[str, Any]:
        """사용자의 채팅 세션 목록을 조회합니다.

        Args:
            db: 데이터베이스 세션
            user_id: 사용자 ID
            is_active: 활성화 상태 필터 (선택)
            limit: 조회할 최대 세션 수 (기본값: 50)
            offset: 조회 시작 위치 (기본값: 0)

        Returns:
            Dict[str, Any]: 채팅 세션 목록과 총 개수
        """
        try:
            # 총 개수 조회를 위한 쿼리
            count_query = select(func.count(StockChatSession.id)).where(StockChatSession.user_id == user_id)
            if is_active is not None:
                count_query = count_query.where(StockChatSession.is_active == is_active)

            count_result = await db.execute(count_query)
            total_count = count_result.scalar() or 0

            # 필요한 필드만 선택하여 쿼리 최적화 (agent_results 제외)
            query = select(
                StockChatSession.id,
                StockChatSession.user_id,
                StockChatSession.title,
                StockChatSession.is_active,
                StockChatSession.stock_code,
                StockChatSession.stock_name,
                StockChatSession.stock_info,
                StockChatSession.created_at,
                StockChatSession.updated_at,
            ).where(StockChatSession.user_id == user_id)

            # 활성화 상태 필터 추가
            if is_active is not None:
                query = query.where(StockChatSession.is_active == is_active)

            # 최신순 정렬, 페이징 적용
            query = query.order_by(StockChatSession.updated_at.desc()).limit(limit).offset(offset)

            # 쿼리 실행
            result = await db.execute(query)
            rows = result.fetchall()

            # 딕셔너리 변환 최적화
            sessions = [
                {
                    "ok": True,
                    "status_message": "채팅 세션 목록 조회 완료",
                    "id": str(row.id),
                    "user_id": str(row.user_id),
                    "title": row.title,
                    "is_active": row.is_active,
                    "stock_code": row.stock_code,
                    "stock_name": row.stock_name,
                    "stock_info": row.stock_info,
                    "created_at": row.created_at.isoformat() if row.created_at else None,
                    "updated_at": row.updated_at.isoformat() if row.updated_at else None,
                }
                for row in rows
            ]

            return {"sessions": sessions, "total": total_count, "limit": limit, "offset": offset, "has_more": offset + len(sessions) < total_count}

        except Exception as e:
            logger.error(f"채팅 세션 조회 중 오류 발생: {str(e)}")
            return {
                "sessions": [
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
                        "updated_at": None,
                    }
                ],
                "total": 0,
                "limit": limit,
                "offset": offset,
                "has_more": False,
            }

    @staticmethod
    async def get_chat_session(db: AsyncSession, session_id: UUID, user_id: Optional[UUID] = None) -> Optional[Dict[str, Any]]:
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
                "updated_at": chat_session.updated_at.isoformat() if chat_session.updated_at else None,
            }

        except Exception as e:
            logger.error(f"채팅 세션 상세 조회 중 오류 발생: {str(e)}")
            raise

    @staticmethod
    async def update_chat_session(db: AsyncSession, session_id: UUID, user_id: UUID, update_data: Dict[str, Any]) -> Optional[Dict[str, Any]]:
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
            query = select(StockChatSession).where(StockChatSession.id == session_id, StockChatSession.user_id == user_id)
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
                update_values["agent_results"] = json.loads(json.dumps(update_values["agent_results"], cls=DateTimeEncoder))

            # 업데이트 실행
            update_stmt = update(StockChatSession).where(StockChatSession.id == session_id).values(**update_values).execution_options(synchronize_session="fetch")
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
                "updated_at": session.updated_at.isoformat() if session.updated_at else None,
            }

        except Exception as e:
            await db.rollback()
            logger.error(f"채팅 세션 업데이트 중 오류 발생: {str(e)}")
            raise

    @staticmethod
    async def delete_chat_session(db: AsyncSession, session_id: UUID, user_id: UUID) -> bool:
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
            delete_stmt = delete(StockChatSession).where(StockChatSession.id == session_id, StockChatSession.user_id == user_id).execution_options(synchronize_session="fetch")
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
        agent_results: Optional[Dict[str, Any]] = None,
        components: Optional[List[Dict[str, Any]]] = None,
    ) -> Dict[str, Any]:
        """새 채팅 메시지를 생성합니다.

        Args:
            db: 데이터베이스 세션
            chat_session_id: 채팅 세션 ID
            role: 메시지 역할 (user, assistant, system)
            content: 메시지 내용
            message_id: 메시지 ID (선택, None이면 자동 생성)
            content_expert: 전문가 모드 메시지 내용 (선택)
            stock_code: 종목 코드 (선택)
            stock_name: 종목명 (선택)
            metadata: 메시지 메타데이터 (선택)
            agent_results: 에이전트 처리 결과 데이터 (선택)
            components: 구조화된 메시지 컴포넌트 배열 (선택)

        Returns:
            Dict[str, Any]: 생성된 채팅 메시지 정보
        """
        try:
            # datetime 객체가 포함된 JSON 데이터 처리
            if metadata is not None:
                metadata = json.loads(json.dumps(metadata, cls=DateTimeEncoder))

            # agent_results에 datetime 객체가 포함되어 있는 경우 처리
            if agent_results is not None:
                agent_results = remove_null_chars(json.loads(json.dumps(agent_results, cls=DateTimeEncoder)))

            # components에 datetime 객체가 포함되어 있는 경우 처리
            if components is not None:
                components = remove_null_chars(json.loads(json.dumps(components, cls=DateTimeEncoder)))

            # 메시지 생성
            message_params = {
                "chat_session_id": chat_session_id,
                "role": role,
                "content": content,
                "content_expert": content_expert,
                "stock_code": stock_code,
                "stock_name": stock_name,
                "message_metadata": metadata,
                "agent_results": agent_results,
                "components": components,
            }

            # id가 있는 경우에만 추가
            if message_id is not None:
                message_params["id"] = message_id

            message = StockChatMessage(**message_params)

            db.add(message)
            await db.flush()
            await db.refresh(message)

            # 관련 세션의 updated_at 업데이트
            session_update = update(StockChatSession).where(StockChatSession.id == chat_session_id).values(updated_at=datetime.now()).execution_options(synchronize_session="fetch")
            await db.execute(session_update)

            await db.commit()

            # 메시지 정보를 딕셔너리로 변환
            return {
                "id": str(message.id),
                "chat_session_id": str(message.chat_session_id),
                "role": message.role,
                "content": message.content,
                "content_expert": message.content_expert,
                "components": message.components,
                "stock_code": message.stock_code,
                "stock_name": message.stock_name,
                "metadata": message.message_metadata,
                "agent_results": message.agent_results,
                "created_at": message.created_at.isoformat() if message.created_at else None,
                "updated_at": message.updated_at.isoformat() if message.updated_at else None,
            }

        except Exception as e:
            await db.rollback()
            logger.error(f"채팅 메시지 생성 중 오류 발생: {str(e)}")
            raise

    @staticmethod
    async def get_chat_messages(db: AsyncSession, session_id: UUID, user_id: Optional[UUID] = None, limit: int = 100, offset: int = 0) -> List[Dict[str, Any]]:
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
                session_query = select(StockChatSession).where(StockChatSession.id == session_id, StockChatSession.user_id == user_id)
                session = await get_one_or_none(db, session_query)

                # 세션이 없거나 권한이 없는 경우 빈 리스트 반환
                if not session:
                    return []

            # 메시지 쿼리 구성
            query = select(StockChatMessage).where(StockChatMessage.chat_session_id == session_id).order_by(StockChatMessage.created_at).limit(limit).offset(offset)

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
                    "components": message.components,
                    "stock_code": message.stock_code,
                    "stock_name": message.stock_name,
                    "metadata": message.message_metadata,
                    "agent_results": message.agent_results,
                    "created_at": message.created_at.isoformat() if message.created_at else None,
                    "updated_at": message.updated_at.isoformat() if message.updated_at else None,
                }
                for message in messages
            ]

        except Exception as e:
            logger.error(f"채팅 메시지 조회 중 오류 발생: {str(e)}")
            return []

    @staticmethod
    async def get_chat_session_agent_results(db: AsyncSession, session_id: UUID, user_id: Optional[UUID] = None) -> Dict[str, Any]:
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

    @staticmethod
    async def create_share_link(db: AsyncSession, chat_session_id: UUID) -> ShareLinkResponse:
        """채팅 세션 공유 링크 생성

        원본 채팅 세션을 복제하여 공유용 세션 생성

        Args:
            db: 데이터베이스 세션
            session_id: 채팅 세션 ID

        Returns:
            ShareLinkResponse: 공유 링크 정보

        Raises:
            HTTPException: 세션을 찾을 수 없는 경우
        """
        try:
            # 채팅 세션 조회
            query = select(StockChatSession).where(StockChatSession.id == chat_session_id)
            result = await db.execute(query)
            original_session = result.scalar_one_or_none()

            if not original_session:
                raise HTTPException(status_code=404, detail="채팅 세션을 찾을 수 없습니다.")

            # 먼저 기존 공유 세션 확인
            existing_query = select(ShareStockChatSession).where(ShareStockChatSession.original_session_id == original_session.id)
            existing_result = await db.execute(existing_query)
            existing_share_session = existing_result.scalar_one_or_none()

            # 기존 공유 세션이 있으면 해당 UUID만 가져와서 바로 반환
            if existing_share_session:
                share_uuid = existing_share_session.share_uuid

                # # 공유 URL 생성하여 바로 반환
                # base_url = settings.STOCKEASY_URL
                # share_url = f"{base_url}/share_chat/{share_uuid}"

                # return ShareLinkResponse(
                #     share_uuid=share_uuid,
                #     share_url=share_url
                # )
            else:
                # 새 공유 세션 생성 로직 (기존 코드)
                share_uuid = str(uuid4())
                share_session = ShareStockChatSession(
                    original_session_id=original_session.id,
                    share_uuid=share_uuid,
                    title=original_session.title,
                    stock_code=original_session.stock_code,
                    stock_name=original_session.stock_name,
                    stock_info=original_session.stock_info,
                    agent_results=original_session.agent_results,
                )
                db.add(share_session)
                await db.flush()

                # 원본 메시지 복사
                for msg in original_session.messages:
                    share_message = ShareStockChatMessage(
                        chat_session_id=share_session.id,
                        original_message_id=msg.id,
                        role=msg.role,
                        stock_code=msg.stock_code,
                        stock_name=msg.stock_name,
                        content_type=msg.content_type,
                        content=msg.content,
                        content_expert=msg.content_expert,
                        components=msg.components,
                        message_data=msg.message_data,
                        data_url=msg.data_url,
                        message_metadata=msg.message_metadata,
                        # agent_results 필드 제외
                    )
                    db.add(share_message)

                await db.commit()

            # 공유 URL 생성
            base_url = settings.STOCKEASY_URL
            share_url = f"{base_url}/share_chat/{share_uuid}"

            return ShareLinkResponse(share_uuid=share_uuid, share_url=share_url)

        except HTTPException:
            await db.rollback()
            raise
        except Exception as e:
            await db.rollback()
            logger.error(f"공유 링크 생성 중 오류 발생: {str(e)}")
            raise HTTPException(status_code=500, detail=f"공유 링크 생성 중 오류가 발생했습니다: {str(e)}")

    @staticmethod
    async def get_shared_chat_session(db: AsyncSession, share_uuid: str) -> Dict[str, Any]:
        """공유된 채팅 세션 조회

        공유 UUID로 세션과 메시지 조회

        Args:
            db: 데이터베이스 세션
            share_uuid: 공유 링크용 UUID

        Returns:
            Dict[str, Any]: 공유된 채팅 세션 정보와 메시지 목록

        Raises:
            HTTPException: 공유된 채팅을 찾을 수 없는 경우
            HTTPException: 공유 링크가 만료된 경우 (15일 이상 경과)
        """
        try:
            # 공유 세션 조회
            query = select(ShareStockChatSession).where(ShareStockChatSession.share_uuid == share_uuid)
            result = await db.execute(query)
            session = result.scalar_one_or_none()

            if not session:
                raise HTTPException(status_code=404, detail="공유된 채팅을 찾을 수 없습니다.")

            # 만료 여부 확인 (15일 이상 경과) => 60일 변경(2개월)
            seoul_tz = pytz.timezone("Asia/Seoul")
            expiry_date = datetime.now(seoul_tz) - timedelta(days=60)

            # 항상 timezone-aware 상태로 비교 (created_at은 항상 timezone with time zone이므로)
            if session.created_at < expiry_date:
                raise HTTPException(status_code=410, detail="공유 링크가 만료되었습니다.")

            # 조회수 증가
            session.view_count += 1
            await db.commit()

            # 메시지를 별도 쿼리로 명시적으로 로드
            messages_query = select(ShareStockChatMessage).where(ShareStockChatMessage.chat_session_id == session.id).order_by(ShareStockChatMessage.created_at)

            messages_result = await db.execute(messages_query)
            session_messages = messages_result.scalars().all()

            # 구조화된 응답 생성
            return {"session": session.to_dict, "messages": [msg.to_dict for msg in session_messages]}

        except HTTPException:
            raise
        except Exception as e:
            await db.rollback()
            logger.error(f"공유된 채팅 조회 중 오류 발생: {str(e)}")
            raise HTTPException(status_code=500, detail=f"공유된 채팅 조회 중 오류가 발생했습니다: {str(e)}")
