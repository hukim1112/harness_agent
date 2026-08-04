#!/bin/bash

# 스크립트가 위치한 디렉토리로 이동하여 경로 문제를 방지합니다.
cd "$(dirname "$0")"

echo "🚀 Github Codespaces / WSL 환경 자동 설치를 시작합니다..."

# 1. Python 의존성 설치 (requirements.txt가 있을 경우)
if [ -f "requirements.txt" ]; then
    echo "🐍 Python 패키지 의존성 설치 중..."
    pip install -r requirements.txt
else
    echo "⚠️ requirements.txt 파일을 찾을 수 없어 Python 패키지 설치를 건너뜁니다."
fi

# 4. .env 파일 생성 (.env.example 복사)
if [ ! -f "../.env" ]; then
    cp ../.env.example ../.env
    echo "📄 .env 파일이 성공적으로 생성되었습니다. API 키를 설정해 주세요."
else
    echo "📄 .env 파일이 이미 존재합니다. 덮어쓰지 않습니다."
fi

# 5. 완료 메시지
echo "---------------------------------------------------------"
echo "✅ 전체 설치 및 환경 세팅이 성공적으로 완료되었습니다!"
echo "---------------------------------------------------------"
