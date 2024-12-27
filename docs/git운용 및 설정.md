# Intellio 프로젝트 Git 가이드

## 목차
1. [Git 기본 이해하기](#git-기본-이해하기)
2. [시작하기](#시작하기)
3. [일상적인 개발 과정](#일상적인-개발-과정)
4. [협업하기](#협업하기)
5. [문제 해결하기](#문제-해결하기)
6. [실전 예제](#실전-예제)

## Git 기본 이해하기

### Git이란?
Git은 여러 개발자가 하나의 프로젝트를 함께 작업할 수 있게 해주는 도구입니다. 
- 마치 구글 독스처럼 여러 사람이 동시에 작업 가능
- 누가 어떤 부분을 수정했는지 모두 기록
- 실수했을 때 이전 상태로 되돌리기 가능

### 주요 개념
1. **브랜치**: 독립적인 작업 공간
   - `main`: 실제 서비스에 반영된 안정적인 코드
   - `develop`: 개발자들이 새로운 기능을 합치는 곳
   - `feature/기능이름`: 각자 맡은 기능을 개발하는 공간

2. **커밋**: 작업 내용 저장
   - 언제, 무엇을, 왜 변경했는지 기록
   - 예: "로그인 화면 디자인 완성", "비밀번호 찾기 기능 추가"

## 시작하기

### 1. 프로젝트 시작
```bash
# 프로젝트 복사
git clone https://github.com/회사명/프로젝트명.git
cd 프로젝트명

# 기본 브랜치 설정
git checkout -b main
git checkout -b develop
```

### 2. 브랜치 만들기
```bash
# develop 브랜치에서 시작
git checkout develop
git pull origin develop

# 새 기능 브랜치 생성
git checkout -b feature/내가-만들-기능
```

## 일상적인 개발 과정

### 1. 작업 전 준비
```bash
# 최신 코드 받기
git checkout develop
git pull origin develop

# 작업 브랜치로 이동
git checkout feature/내가-만들-기능
```

### 2. 코드 작성과 저장
```bash
# 변경사항 확인
git status

# 변경사항 저장
git add .
git commit -m "feat: 새로운 기능 추가
- 상세 설명 1
- 상세 설명 2"
```

### 3. 팀과 공유
```bash
git push origin feature/내가-만들-기능
```

## 협업하기

### 커밋 메시지 규칙
```
[타입]: [제목]

[상세 설명]
- 변경사항 1
- 변경사항 2
```

타입 종류:
- `feat`: 새로운 기능
- `fix`: 버그 수정
- `docs`: 문서 수정
- `style`: 코드 정리
- `refactor`: 코드 개선
- `test`: 테스트 코드
- `chore`: 기타 작업

### 코드 리뷰 과정
1. GitHub/GitLab에서 Pull Request 생성
2. 팀원들의 리뷰 요청
3. 피드백 받고 수정
4. 승인 후 develop 브랜치에 병합

## 문제 해결하기

### 1. 충돌 해결하기
```bash
# 1. 최신 코드 받기
git checkout develop
git pull origin develop

# 2. 내 브랜치에 적용
git checkout feature/내가-만들-기능
git rebase develop

# 3. 충돌 발생 시
# - 파일 열어서 충돌 부분 수정
# - git add .
# - git rebase --continue
```

### 2. 실수 취소하기
```bash
# 파일 하나 되돌리기
git checkout -- 파일이름.확장자

# 모든 변경사항 되돌리기
git reset --hard HEAD
```

## 실전 예제

### 예제 1: 로그인 기능 개발
```bash
# 1. 작업 시작
git checkout develop
git pull origin develop
git checkout -b feature/login

# 2. 개발 작업
# - auth.py 작성
# - login.html 작성
# - 테스트 코드 작성

# 3. 변경사항 저장
git add .
git commit -m "feat: 로그인 기능 구현
- 로그인 화면 추가
- 비밀번호 암호화
- 실패 처리 추가"

# 4. 공유
git push origin feature/login
```

### 예제 2: 회원가입 기능 개발
```bash
# 1. 작업 시작
git checkout develop
git pull origin develop
git checkout -b feature/signup

# 2. 개발 작업
# - signup.py 작성
# - signup.html 작성

# 3. 변경사항 저장
git add .
git commit -m "feat: 회원가입 기능 구현
- 이메일 인증 추가
- 비밀번호 검사
- 중복 확인"

# 4. 공유
git push origin feature/signup
```

## 자주 쓰는 명령어
- `git status`: 현재 상태 확인
- `git log`: 변경 기록 확인
- `git checkout 브랜치`: 브랜치 이동
- `git pull`: 최신 코드 받기
- `git add .`: 변경사항 준비
- `git commit`: 변경사항 저장
- `git push`: 변경사항 공유

## 주의사항
1. 항상 작업 전 `git pull`로 최신화
2. 커밋 메시지는 상세하게 작성
3. 모르는 건 바로 물어보기
4. 큰 작업은 작게 나누어 커밋
5. 실수해도 괜찮아요!

## 도움받기
- [Git 공식 문서](https://git-scm.com/doc)
- [GitHub 가이드](https://guides.github.com/)
- 팀 채팅방에 질문하기