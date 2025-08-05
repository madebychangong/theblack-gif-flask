# ================================================
# 🔧 Leapcell용 Dockerfile
# ================================================
# 주의: Leapcell에서 자동으로 처리해줄 수도 있어서 
#       이 파일이 실제로 사용되지 않을 수도 있습니다!

# 🐍 Python 3.10 베이스 이미지 (Ubuntu 기반)
FROM python:3.10-slim

# 🔧 작업 디렉토리 설정
WORKDIR /app

# 📦 시스템 패키지 업데이트 및 필수 dependencies 설치
RUN apt-get update && apt-get install -y \
    # 🌐 네트워크 도구들
    wget \
    curl \
    # 🎭 Playwright 브라우저를 위한 시스템 dependencies
    libnss3 \
    libnspr4 \
    libdbus-1-3 \
    libatk1.0-0 \
    libatk-bridge2.0-0 \
    libdrm2 \
    libxkbcommon0 \
    libgtk-3-0 \
    libgbm1 \
    libasound2 \
    # 🖼️ 이미지 처리를 위한 라이브러리들 (Pillow용)
    libjpeg-dev \
    libpng-dev \
    libfreetype6-dev \
    # 🔧 빌드 도구들
    gcc \
    g++ \
    # 정리
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

# 📋 requirements.txt 복사 및 Python 패키지 설치
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# 🎭 Playwright 브라우저 설치
RUN playwright install chromium && \
    playwright install-deps chromium

# 📁 애플리케이션 코드 복사
COPY . .

# 📂 필요한 디렉토리 생성
RUN mkdir -p temp static templates

# 🌍 환경변수 설정
ENV PYTHONUNBUFFERED=1
ENV PLAYWRIGHT_BROWSERS_PATH=/tmp/ms-playwright

# 🚀 포트 설정 (Leapcell에서 동적으로 할당됨)
EXPOSE 5000

# 🏃‍♂️ 애플리케이션 실행 명령어
CMD ["gunicorn", "--bind", "0.0.0.0:5000", "--workers", "1", "--timeout", "120", "app:app"]