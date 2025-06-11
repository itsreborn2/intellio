#!/usr/bin/env python3
import asyncio
import sys
import os

# 현재 디렉토리를 Python path에 추가
sys.path.insert(0, '/app')

from stockeasy.collector.services.kiwoom_client import KiwoomAPIClient

async def test_kiwoom_connection():
    """키움 API 연결 테스트"""
    print("키움 API 연결 테스트 시작...")
    
    try:
        client = KiwoomAPIClient()
        result = await client.test_api_connection()
        print(f"테스트 결과: {result}")
        
        if result.get("status") == "success":
            print("✅ 키움 API 연결 성공!")
        else:
            print(f"❌ 키움 API 연결 실패: {result.get('message')}")
            
    except Exception as e:
        print(f"❌ 테스트 중 오류 발생: {e}")

if __name__ == "__main__":
    asyncio.run(test_kiwoom_connection()) 