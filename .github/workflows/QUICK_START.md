# 🚀 빠른 시작 가이드

## ✅ 설정 완료!

GitHub Actions가 성공적으로 설정되었습니다!

## 🎯 사용법

### 1. develop 브랜치에서 커밋하기
```bash
git checkout develop
git add .
git commit -m "fix: 로그인 버그 수정 fixes #123"
git push origin develop
```

### 2. 이슈 자동 닫기 확인
1. GitHub Repository → **Actions** 탭
2. **Auto Close Issues on Develop** 워크플로우 클릭
3. 실행 로그 확인

### 3. 지원하는 키워드
```bash
# 영어
fixes #123, closes #456, resolves #789

# 한국어  
해결 #123, 수정 #456, 완료 #789, 닫기 #101
```

## 🔧 고급 기능 사용하기

고급 기능을 원한다면:
```bash
# 기본 버전 비활성화
mv .github/workflows/auto-close-issues.yml .github/workflows/auto-close-issues.yml.disabled

# 고급 버전 활성화
mv .github/workflows/advanced-auto-close.yml.disabled .github/workflows/advanced-auto-close.yml
```

## 🆘 문제 해결

### 권한 오류 시
`.github/workflows/auto-close-issues.yml` 파일에 추가:
```yaml
permissions:
  issues: write
  contents: read
```

### 문의사항
- GitHub Actions 탭에서 로그 확인
- 커밋 메시지 형식 재확인
- 이슈 번호가 존재하는지 확인

---
🎉 **준비 완료!** 이제 develop 브랜치에 push할 때마다 이슈가 자동으로 닫힙니다! 