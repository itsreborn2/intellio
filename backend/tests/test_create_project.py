import requests
import json

url = 'http://localhost:8000/api/v1/projects/'
headers = {'Content-Type': 'application/json'}
data = {
    'name': '테스트 프로젝트',
    'description': '문서 분석 테스트를 위한 프로젝트입니다.'
}

response = requests.post(url, headers=headers, json=data)
print(response.status_code)
print(response.json())
