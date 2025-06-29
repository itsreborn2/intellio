# GitHub Actions 워크플로우 가이드

## 📁 파일 구조
```
.github/
└── workflows/
    ├── auto-close-issues.yml       # 기본 이슈 자동 닫기 (추천)
    ├── advanced-auto-close.yml     # 고급 기능 포함 (선택사항)
    └── README.md                   # 이 파일
```

## 🔧 워크플로우 선택

### 1. 기본 버전 (auto-close-issues.yml) - 추천
- 간단하고 안정적
- 기본적인 이슈 닫기 기능
- 빠른 실행 속도

### 2. 고급 버전 (advanced-auto-close.yml) - 선택사항  
- 더 많은 패턴 매칭
- 자동 라벨 추가
- 상세한 코멘트와 통계
- 에러 처리 강화

> ⚠️ **주의**: 두 워크플로우를 동시에 활성화하면 중복 실행될 수 있습니다.
> 
> **사용 방법**: 
> - 기본 버전만 사용: `advanced-auto-close.yml` 파일명을 `advanced-auto-close.yml.disabled`로 변경
> - 고급 버전만 사용: `auto-close-issues.yml` 파일명을 `auto-close-issues.yml.disabled`로 변경

## 🤖 Auto Close Issues on Develop

### 기능
- develop 브랜치에 push할 때 커밋 메시지에서 이슈 번호를 찾아 자동으로 닫습니다
- 한국어와 영어 키워드를 모두 지원합니다
- 닫은 이슈에 자동으로 코멘트를 추가합니다

### 지원하는 키워드

#### 영어
- `fixes #123`
- `closes #456` 
- `resolves #789`
- `fixed #101`
- `closed #102`
- `resolved #103`

#### 한국어
- `해결 #123`
- `수정 #456`
- `완료 #789`
- `닫기 #101`

### 사용 예시

```bash
# 영어
git commit -m "fix: 로그인 버그 수정 fixes #123"
git commit -m "feat: 새 기능 구현 closes #456"

# 한국어  
git commit -m "수정: 데이터베이스 연결 오류 해결 #789"
git commit -m "기능: 회원가입 페이지 완료 #101"
```

### 실행 확인
1. GitHub Repository → **Actions** 탭
2. **Auto Close Issues on Develop** 클릭
3. 실행 로그에서 상세 정보 확인

### 문제해결

#### 권한 오류가 발생하는 경우
워크플로우 파일에 다음 추가:
```yaml
permissions:
  issues: write
  contents: read
```

#### 이슈가 닫히지 않는 경우
1. 커밋 메시지 형식 확인
2. 이슈 번호가 정확한지 확인
3. Actions 탭에서 오류 로그 확인

## 🚀 Advanced Auto Close Issues (고급 버전)

### 추가 기능
- **다양한 패턴 매칭**: 더 유연한 키워드 인식
- **자동 라벨**: `auto-closed`, `develop-branch` 라벨 자동 추가
- **상세 코멘트**: 이슈 통계, 마일스톤 정보 포함
- **에러 처리**: 상세한 오류 로깅 및 처리
- **워크플로우 요약**: GitHub Actions Summary 생성

### 지원하는 추가 패턴
```bash
# 기본 패턴 외에 추가로 지원
git commit -m "bug fix: 메모리 누수 해결 #123"
git commit -m "버그 수정: 로그인 오류 #456"
git commit -m "#789 해결"
git commit -m "성능 개선 #101 완료"
```

### 비활성화 방법
```bash
# 고급 버전을 사용하지 않으려면
mv .github/workflows/advanced-auto-close.yml .github/workflows/advanced-auto-close.yml.disabled

# 기본 버전을 사용하지 않으려면  
mv .github/workflows/auto-close-issues.yml .github/workflows/auto-close-issues.yml.disabled
``` 