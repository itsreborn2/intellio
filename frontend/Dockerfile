# Node.js 18 이미지 사용
FROM node:18-alpine

# 작업 디렉토리 설정
WORKDIR /app

# 의존성 파일 복사 및 설치
COPY package*.json ./
RUN npm install

# 소스 코드 복사
COPY . .

# 빌드
RUN npm run build

# 포트 설정
EXPOSE 3000

# 실행 명령
CMD ["npm", "run", "dev"]
