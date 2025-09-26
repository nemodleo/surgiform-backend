#!/bin/bash

# Cloud Run 환경변수 설정 스크립트
# 사용법: ./set-env-vars.sh [OPENAI_API_KEY]

set -e

OPENAI_API_KEY=${1:-"your-openai-api-key"}
SERVICE_NAME="surgiform-backend"
REGION="asia-northeast3"

echo "🔧 Cloud Run 환경변수 설정 중..."

gcloud run services update ${SERVICE_NAME} \
    --region ${REGION} \
    --set-env-vars OPENAI_API_KEY=${OPENAI_API_KEY}

echo "✅ 환경변수 설정 완료!"
echo "📊 서비스 확인: https://surgiform-backend-wxk3fcve3q-du.a.run.app/health"