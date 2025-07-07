#!/usr/bin/env python3
"""
TimescaleDB 연결 테스트 스크립트
"""
import asyncio
import os
import sys
from pathlib import Path

# 현재 디렉토리를 Python 경로에 추가
current_dir = Path(__file__).parent
sys.path.insert(0, str(current_dir))

# 환경변수 설정 (테스트용)
os.environ.setdefault("TIMESCALE_PASSWORD", "StockCollector2024")
os.environ.setdefault("TIMESCALE_HOST", "localhost")  # localhost로 직접 연결
os.environ.setdefault("TIMESCALE_PORT", "6433")        # 외부 포트로 연결

from core.timescale_database import (
    test_timescale_connection,
    TimescaleConnectionMonitor,
    close_timescale_connections
)
from core.config import get_settings


async def main():
    """메인 테스트 함수"""
    print("=== TimescaleDB 연결 테스트 시작 ===")
    
    # 설정 확인
    settings = get_settings()
    print(f"TimescaleDB 호스트: {settings.TIMESCALE_HOST}")
    print(f"TimescaleDB 포트: {settings.TIMESCALE_PORT}")
    print(f"TimescaleDB 데이터베이스: {settings.TIMESCALE_DB}")
    print(f"TimescaleDB 사용자: {settings.TIMESCALE_USER}")
    
    try:
        # 연결 테스트
        print("\n1. 연결 테스트 실행 중...")
        is_connected = await test_timescale_connection()
        
        if is_connected:
            print("✅ TimescaleDB 연결 성공!")
            
            # 연결 정보 조회
            print("\n2. 연결 정보 조회 중...")
            monitor = TimescaleConnectionMonitor()
            conn_info = await monitor.get_connection_info()
            
            print("📊 연결 상태 정보:")
            for key, value in conn_info.items():
                print(f"   - {key}: {value}")
                
        else:
            print("❌ TimescaleDB 연결 실패!")
            
    except Exception as e:
        print(f"❌ 테스트 중 오류 발생: {e}")
        import traceback
        traceback.print_exc()
        
    finally:
        # 연결 정리
        print("\n3. 연결 정리 중...")
        await close_timescale_connections()
        print("✅ 연결 정리 완료")
    
    print("\n=== TimescaleDB 연결 테스트 완료 ===")


if __name__ == "__main__":
    asyncio.run(main()) 