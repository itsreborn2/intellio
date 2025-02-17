#!/usr/bin/env python3
import os
import asyncio
from telethon import TelegramClient
from loguru import logger

# 텔레그램 API 인증 정보
API_ID = "22508254"
API_HASH = "cdd455d868a2405d47eb3d98733a28ee"

# 세션 파일 저장 경로
SESSION_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "telegram_sessions")
SESSION_PATH = os.path.join(SESSION_DIR, "telegram_collector")

async def create_session():
    """텔레그램 세션 생성
    1. 전화번호 입력
    2. Telegram으로 받은 인증 코드 입력
    3. 세션 파일 생성
    """
    try:
        # 세션 디렉토리 생성
        os.makedirs(SESSION_DIR, exist_ok=True)
        logger.info(f"세션 파일 저장 경로: {SESSION_DIR}")
        
        # 텔레그램 클라이언트 초기화
        client = TelegramClient(SESSION_PATH, API_ID, API_HASH)
        
        logger.info("텔레그램 클라이언트 시작...")
        await client.start()
        
        # 클라이언트가 연결되었는지 확인
        if await client.is_user_authorized():
            me = await client.get_me()
            logger.success(f"성공적으로 인증되었습니다! 사용자: {me.first_name} (@{me.username})")
            logger.info(f"세션 파일이 생성되었습니다: {SESSION_PATH}.session")
        
    except Exception as e:
        logger.error(f"세션 생성 중 오류 발생: {str(e)}")
        raise
    finally:
        await client.disconnect()

def main():
    """메인 함수"""
    try:
        # 이벤트 루프 생성 및 실행
        loop = asyncio.get_event_loop()
        loop.run_until_complete(create_session())
    except KeyboardInterrupt:
        logger.warning("사용자가 프로그램을 중단했습니다.")
    except Exception as e:
        logger.error(f"예상치 못한 오류 발생: {str(e)}")
    finally:
        loop.close()

if __name__ == "__main__":
    logger.info("텔레그램 세션 생성 스크립트 시작")
    main()
    logger.info("스크립트 종료")
    