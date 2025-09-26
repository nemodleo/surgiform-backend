#!/bin/bash

# .env 파일의 모든 환경변수를 Cloud Run에 동기화하는 스크립트
# 사용법: ./sync-env.sh [.env 파일 경로]

set -e

# 기본값 설정
ENV_FILE=${1:-.env}
SERVICE_NAME="surgiform-backend"
REGION="asia-northeast1"  # 도쿄 리전

# 색상 코드
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

echo -e "${GREEN}🔄 .env 파일을 Cloud Run과 동기화합니다${NC}"
echo "📄 환경변수 파일: ${ENV_FILE}"
echo "🎯 대상 서비스: ${SERVICE_NAME}"
echo "📍 리전: ${REGION}"
echo ""

# .env 파일 존재 확인
if [ ! -f "$ENV_FILE" ]; then
    echo -e "${RED}❌ 오류: ${ENV_FILE} 파일을 찾을 수 없습니다${NC}"
    exit 1
fi

# 환경변수 문자열 생성
ENV_VARS=""
MASKED_VARS=""
VAR_COUNT=0

while IFS='=' read -r key value; do
    # 주석과 빈 줄 무시
    if [[ ! "$key" =~ ^#.*$ ]] && [[ ! -z "$key" ]]; then
        # 따옴표 제거
        value="${value%\"}"
        value="${value#\"}"
        
        # 환경변수 문자열에 추가
        if [ -z "$ENV_VARS" ]; then
            ENV_VARS="${key}=${value}"
        else
            ENV_VARS="${ENV_VARS},${key}=${value}"
        fi
        
        # 마스킹된 출력용 (민감한 정보 숨김)
        if [[ "$key" == *"KEY"* ]] || [[ "$key" == *"PASSWORD"* ]] || [[ "$key" == *"SECRET"* ]]; then
            masked_value="***"
        else
            masked_value="${value}"
        fi
        
        echo -e "  ${YELLOW}→${NC} ${key}=${masked_value}"
        VAR_COUNT=$((VAR_COUNT + 1))
    fi
done < "$ENV_FILE"

echo ""
echo -e "${GREEN}📊 총 ${VAR_COUNT}개의 환경변수를 설정합니다${NC}"
echo ""

# 사용자 확인
read -p "계속하시겠습니까? (y/N): " -n 1 -r
echo
if [[ ! $REPLY =~ ^[Yy]$ ]]; then
    echo -e "${YELLOW}⚠️  작업이 취소되었습니다${NC}"
    exit 0
fi

# Cloud Run 서비스 업데이트
echo ""
echo -e "${GREEN}🚀 Cloud Run 서비스 업데이트 중...${NC}"

if gcloud run services update ${SERVICE_NAME} \
    --region ${REGION} \
    --set-env-vars="${ENV_VARS}" \
    --quiet; then
    
    echo ""
    echo -e "${GREEN}✅ 환경변수가 성공적으로 업데이트되었습니다!${NC}"
    
    # 서비스 URL 가져오기
    SERVICE_URL=$(gcloud run services describe ${SERVICE_NAME} \
        --region ${REGION} \
        --format 'value(status.url)')
    
    echo ""
    echo -e "${GREEN}🌐 서비스 URL: ${SERVICE_URL}${NC}"
    echo -e "${GREEN}📊 헬스체크: ${SERVICE_URL}/health${NC}"
else
    echo ""
    echo -e "${RED}❌ 환경변수 업데이트 실패${NC}"
    echo -e "${YELLOW}팁: gcloud 로그인 상태와 프로젝트 설정을 확인하세요${NC}"
    echo -e "${YELLOW}    gcloud auth login${NC}"
    echo -e "${YELLOW}    gcloud config set project surgiform-471510${NC}"
    exit 1
fi