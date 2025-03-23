# LLM 설정 관리 시스템

이 시스템은 에이전트별로 LLM(Large Language Model) 설정을 구성하고 관리하는 기능을 제공합니다.

## 주요 기능

- 각 에이전트별로 고유한, JSON 기반 LLM 설정 관리
- 동적 설정 불러오기 및 갱신
- 다양한 LLM 제공자(OpenAI, Google, Anthropic 등) 지원
- 폴백 메커니즘 및 오류 처리

## 구성 요소

### 1. LLM 설정 관리자 (`llm_config_manager.py`)

- JSON 설정 파일 로드 및 캐싱
- 파일 변경 감지 및 자동 리로드
- 에이전트별 설정 검색 기능

### 2. LLM 팩토리 (`llm_factory.py`)

- 다양한 LLM 제공자에 대한 인스턴스 생성
- 설정 기반 LLM 객체 생성
- 스트리밍 지원

### 3. 에이전트별 LLM 관리 (`agent_llm.py`)

- 에이전트별 LLM 인스턴스 생성 및 캐싱
- 스트리밍 지원
- 설정 검증 및 갱신

## 설정 파일 구조

LLM 설정은 `agent_llm_config.json` 파일에 정의되며, 다음과 같은 구조를 가집니다:

```json
{
  "default": {
    "provider": "openai",
    "model_name": "gpt-4o-mini",
    "temperature": 0,
    "max_tokens": 2048,
    "top_p": 0.7,
    "api_key_env": "OPENAI_API_KEY"
  },
  "agents": {
    "agent_name": {
      "provider": "openai",
      "model_name": "gpt-4o",
      "temperature": 0.1,
      "max_tokens": 4096,
      "api_key_env": "OPENAI_API_KEY"
    },
    // 다른 에이전트 설정...
  },
  "fallback_settings": {
    "enabled": true,
    "max_retries": 3,
    "providers": [
      {
        "provider": "openai",
        "model_name": "gpt-3.5-turbo",
        "temperature": 0,
        "api_key_env": "OPENAI_API_KEY"
      },
      // 다른 폴백 옵션...
    ]
  }
}
```

## 사용 방법

### 1. 에이전트 코드에서 LLM 가져오기

```python
from common.services.agent_llm import get_llm_for_agent

class MyAgent:
    def __init__(self):
        # 설정 파일에서 에이전트 이름 기반으로 LLM 생성
        self.llm, self.model_name, self.provider = get_llm_for_agent("my_agent")
        
    def process(self, input_text):
        # LLM 사용
        response = self.llm.invoke(input_text)
        return response
```

### 2. 스트리밍 LLM 사용

```python
from common.services.agent_llm import get_agent_llm

def on_token(token):
    # 토큰 처리 로직
    print(token, end="", flush=True)

# 에이전트 LLM 관리자 가져오기
agent_llm = get_agent_llm("my_streaming_agent")

# 스트리밍 LLM 가져오기
streaming_llm = agent_llm.get_streaming_llm(callback=on_token)

# 스트리밍 LLM 사용
streaming_llm.invoke(input_text)
```

### 3. 설정 업데이트

```python
from common.services.agent_llm import get_agent_llm

# 에이전트 LLM 관리자 가져오기
agent_llm = get_agent_llm("my_agent")

# 새 설정
new_config = {
    "provider": "anthropic",
    "model_name": "claude-3-5-sonnet",
    "temperature": 0.2,
    "api_key_env": "ANTHROPIC_API_KEY"
}

# 설정 업데이트
agent_llm.update_config(new_config)

# 새 설정으로 LLM 사용
updated_llm = agent_llm.get_llm(refresh=True)
```

## API 키 관리

각 LLM 제공자의 API 키는 다음 3단계의 우선순위에 따라 가져옵니다:

1. **설정의 `api_key_env` 필드로 지정된 환경 변수**
   - 설정 파일의 `api_key_env` 필드에 지정된 환경 변수 이름(예: "CUSTOM_OPENAI_KEY")에서 API 키를 가져옵니다.
   - 이 방법을 사용하면 특정 에이전트만 다른 API 키를 사용하도록 구성할 수 있습니다.
   - 예: `"api_key_env": "PRODUCTION_OPENAI_KEY"` 또는 `"api_key_env": "PREMIUM_ANTHROPIC_KEY"`

2. **기본 환경 변수**
   - 1번에서 API 키를 찾을 수 없으면, 기본 환경 변수 이름(예: "OPENAI_API_KEY", "GEMINI_API_KEY" 등)에서 API 키를 가져옵니다.
   - 예: `os.getenv("OPENAI_API_KEY")` 또는 `os.getenv("ANTHROPIC_API_KEY")`

3. **설정 객체(`settings`)**
   - 1번과 2번 모두에서 API 키를 찾을 수 없으면, `settings` 객체(CommonSettings)에서 API 키를 가져옵니다.
   - `settings` 객체는 `.env` 파일에서 로드한 환경 변수를 담고 있습니다.
   - 예: `settings.OPENAI_API_KEY` 또는 `settings.ANTHROPIC_API_KEY`

이 단계적 접근 방식은 다양한 사용 사례에 맞게 API 키를 유연하게 구성할 수 있도록 합니다. 개발 환경, 테스트 환경, 프로덕션 환경에서 서로 다른 API 키를 사용하거나, 특정 에이전트에 대해 높은 등급의 API 계정을 사용하는 등의 시나리오를 지원합니다.

## 오류 처리 및 폴백

폴백 설정이 활성화된 경우:

1. 첫 번째 제공자로 LLM 생성 또는 호출 시 실패하면 자동으로 다음 폴백 제공자로 전환합니다.
2. 폴백은 최대 재시도 횟수(`max_retries`) 내에서 시도됩니다.
3. 모든 폴백이 실패하면 마지막 예외가 발생합니다.

폴백을 통해 다음과 같은 상황을 처리할 수 있습니다:
- API 키 만료나 할당량 한도 도달
- 서비스 중단이나 네트워크 오류
- 특정 모델의 일시적 사용 불가

이를 통해 고가용성을 유지하고 LLM 서비스의 장애 허용성을 높일 수 있습니다. 