# Python 3.11 slim image 사용
FROM python:3.11-slim

# 작업 디렉토리 설정
WORKDIR /app

# 시스템 패키지 업데이트 및 필수 도구 설치
RUN apt-get update && apt-get install -y \
    gcc \
    g++ \
    curl \
    libnss3 \
    libnspr4 \
    libatk1.0-0 \
    libatk-bridge2.0-0 \
    libcups2 \
    libdrm2 \
    libxkbcommon0 \
    libxcomposite1 \
    libxdamage1 \
    libxrandr2 \
    libgbm1 \
    libasound2 \
    fonts-noto-color-emoji \
    fonts-unifont \
    && rm -rf /var/lib/apt/lists/*

# Poetry 설치
RUN pip install --no-cache-dir poetry==1.8.3

# 프로젝트 파일 복사
COPY pyproject.toml poetry.lock ./

# Poetry 설정 - 가상환경 생성 비활성화
RUN poetry config virtualenvs.create false

# 의존성 설치
RUN poetry install --no-dev --no-interaction --no-ansi

# Playwright 브라우저 설치 (필요한 경우)
RUN playwright install chromium

# 애플리케이션 코드 복사
COPY . .

# 포트 노출
EXPOSE 8000

# 애플리케이션 실행
# Cloud Run은 PORT 환경변수를 자동으로 설정
CMD exec uvicorn surgiform.deploy.server:app --host 0.0.0.0 --port ${PORT:-8000}