import requests
import json
from datetime import datetime, timedelta

BASE_URL = "http://localhost:8000/api/v1"

def test_project_cleanup():
    try:
        # 1. 서버 상태 확인
        try:
            requests.get(f"{BASE_URL}/projects/")
        except requests.exceptions.ConnectionError:
            print("서버가 실행되고 있지 않습니다. 먼저 서버를 실행해주세요.")
            return

        # 2. 프로젝트 생성
        project_data = {
            "name": "Test Project 1",
            "description": "Test project for cleanup"
        }
        
        response = requests.post(
            f"{BASE_URL}/projects/",
            headers={"Content-Type": "application/json"},
            json=project_data
        )
        response.raise_for_status()  # 에러 체크
        print("프로젝트 생성 응답:", response.json())

        # 3. 프로젝트 목록 조회
        response = requests.get(f"{BASE_URL}/projects/")
        response.raise_for_status()
        print("\n현재 프로젝트 목록:", response.json())

        # 4. 정리 작업 실행
        response = requests.post(f"{BASE_URL}/projects/test/cleanup")
        response.raise_for_status()
        print("\n정리 작업 실행 결과:", response.json())

        # 5. 업데이트된 프로젝트 목록 조회
        response = requests.get(f"{BASE_URL}/projects/")
        response.raise_for_status()
        print("\n정리 후 프로젝트 목록:", response.json())

    except requests.exceptions.RequestException as e:
        print(f"\n에러 발생: {str(e)}")
        if hasattr(e.response, 'text'):
            print(f"응답 내용: {e.response.text}")

if __name__ == "__main__":
    test_project_cleanup()
