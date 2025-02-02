import requests
import json

def test_create_project():
    # 프로젝트 생성
    project_data = {
        "name": "테스트 프로젝트",
        "description": "문서 처리 테스트를 위한 프로젝트"
    }
    
    response = requests.post(
        "http://localhost:8000/api/v1/projects/",
        json=project_data
    )
    
    print("프로젝트 생성 응답:", response.status_code)
    print("응답 내용:", response.text)
    
    try:
        response_json = response.json()
        print(json.dumps(response_json, indent=2, ensure_ascii=False))
        
        if response.status_code == 200:
            project_id = response_json["id"]
            return project_id
    except Exception as e:
        print(f"에러 발생: {str(e)}")
    
    return None

def test_upload_document(project_id):
    if not project_id:
        print("프로젝트 ID가 없어서 문서 업로드를 건너뜁니다.")
        return
        
    # 문서 업로드
    files = [
        ('files', ('test.txt', 'This is a test document.', 'text/plain')),
        # 여기에 더 많은 테스트 파일 추가 가능
    ]
    
    response = requests.post(
        f"http://localhost:8000/api/v1/documents/upload/{project_id}",
        files=files
    )
    
    print("\n문서 업로드 응답:", response.status_code)
    print("응답 내용:", response.text)
    
    try:
        print(json.dumps(response.json(), indent=2, ensure_ascii=False))
    except Exception as e:
        print(f"에러 발생: {str(e)}")

if __name__ == "__main__":
    project_id = test_create_project()
    if project_id:
        test_upload_document(project_id)
