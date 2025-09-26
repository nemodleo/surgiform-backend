#!/bin/bash

# 로컬에서 docker buildx를 사용한 GCP 배포 스크립트 (Apple Silicon 대응)
# 사용법: ./deploy.sh [PROJECT_ID] [REGION]

set -e

# 기본값 설정
PROJECT_ID=${1:-"surgiform-471510"}
REGION=${2:-"asia-northeast1"}  # 도쿄 리전 (도메인 매핑 지원)
SERVICE_NAME="surgiform-backend"
IMAGE_NAME="gcr.io/${PROJECT_ID}/${SERVICE_NAME}"

echo "🚀 Surgiform Backend GCP 배포 시작 (Docker Buildx)"
echo "Project ID: ${PROJECT_ID}"
echo "Region: ${REGION}"

# 1. GCP 프로젝트 설정
echo "📌 GCP 프로젝트 설정..."
gcloud config set project ${PROJECT_ID}

# 2. Docker 인증 설정
echo "🔐 Docker 인증 설정..."
gcloud auth configure-docker

# 3. Docker buildx 빌더 생성/사용
echo "🛠️ Docker buildx 설정..."
docker buildx create --use --name multiarch-builder 2>/dev/null || docker buildx use multiarch-builder

# 4. linux/amd64 플랫폼용 이미지 빌드 및 푸시
echo "🔨 linux/amd64 이미지 빌드 및 푸시..."
docker buildx build \
    --platform linux/amd64 \
    -t ${IMAGE_NAME}:latest \
    --push \
    .

# 5. Cloud Run 배포
echo "☁️ Cloud Run에 배포..."

# .env 파일에서 환경변수 로드 (옵션)
if [ -f ".env" ] && [ "$3" == "--with-env" ]; then
    echo "📄 .env 파일에서 환경변수 로드 중..."
    ENV_VARS=""
    while IFS='=' read -r key value; do
        if [[ ! "$key" =~ ^#.*$ ]] && [[ ! -z "$key" ]]; then
            value="${value%\"}"
            value="${value#\"}"
            if [ -z "$ENV_VARS" ]; then
                ENV_VARS="${key}=${value}"
            else
                ENV_VARS="${ENV_VARS},${key}=${value}"
            fi
        fi
    done < .env
    
    gcloud run deploy ${SERVICE_NAME} \
        --image ${IMAGE_NAME}:latest \
        --platform managed \
        --region ${REGION} \
        --allow-unauthenticated \
        --memory 2Gi \
        --cpu 2 \
        --max-instances 10 \
        --min-instances 1 \
        --set-env-vars="${ENV_VARS}"
else
    # 환경변수 없이 배포
    gcloud run deploy ${SERVICE_NAME} \
        --image ${IMAGE_NAME}:latest \
        --platform managed \
        --region ${REGION} \
        --allow-unauthenticated \
        --memory 2Gi \
        --cpu 2 \
        --max-instances 10 \
        --min-instances 1
    
    echo ""
    echo "💡 팁: 환경변수를 설정하려면 다음 명령을 사용하세요:"
    echo "  ./sync-env.sh  # .env 파일의 모든 환경변수 동기화"
    echo "  ./deploy.sh ${PROJECT_ID} ${REGION} --with-env  # 배포 시 .env 파일 포함"
fi

# 6. 서비스 URL 가져오기
SERVICE_URL=$(gcloud run services describe ${SERVICE_NAME} \
    --platform managed \
    --region ${REGION} \
    --format 'value(status.url)')

echo "✅ 배포 완료!"
echo "🌐 서비스 URL: ${SERVICE_URL}"
echo "📊 헬스체크: ${SERVICE_URL}/health"

# 7. 커스텀 도메인 매핑 (옵션)
CUSTOM_DOMAIN=${4:-""}
if [ ! -z "${CUSTOM_DOMAIN}" ]; then
    echo ""
    echo "🔗 커스텀 도메인 매핑 중: ${CUSTOM_DOMAIN}"
    
    # 기존 도메인 매핑 확인
    EXISTING_MAPPING=$(gcloud beta run domain-mappings list \
        --region ${REGION} \
        --filter "metadata.name=${CUSTOM_DOMAIN}" \
        --format "value(metadata.name)" 2>/dev/null || echo "")
    
    if [ ! -z "${EXISTING_MAPPING}" ]; then
        echo "ℹ️  도메인 매핑이 이미 존재합니다: ${CUSTOM_DOMAIN}"
    else
        # 도메인 매핑 생성
        if gcloud beta run domain-mappings create \
            --service ${SERVICE_NAME} \
            --domain ${CUSTOM_DOMAIN} \
            --region ${REGION}; then
            
            echo "✅ 도메인 매핑 완료!"
            echo ""
            echo "📌 DNS 설정 안내:"
            echo "다음 DNS 레코드를 도메인 제공업체에 추가하세요:"
            
            # DNS 레코드 정보 가져오기
            gcloud beta run domain-mappings describe ${CUSTOM_DOMAIN} \
                --region ${REGION} \
                --format "table(status.resourceRecords[].type,status.resourceRecords[].rrdata)"
            
            echo ""
            echo "🌐 커스텀 도메인: https://${CUSTOM_DOMAIN}"
            echo "📊 헬스체크: https://${CUSTOM_DOMAIN}/health"
        else
            echo "⚠️  도메인 매핑 실패. 도메인 소유권을 먼저 확인하세요:"
            echo "   https://console.cloud.google.com/run/domains"
        fi
    fi
fi

# 사용법 안내
if [ -z "${CUSTOM_DOMAIN}" ]; then
    echo ""
    echo "💡 커스텀 도메인을 설정하려면:"
    echo "   ./deploy.sh ${PROJECT_ID} ${REGION} --with-env api.surgi-form.com"
fi