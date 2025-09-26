#!/bin/bash

# Cloud Run 커스텀 도메인 설정 스크립트
# 사용법: ./setup-domain.sh [DOMAIN_NAME]

set -e

# 기본값 설정
DOMAIN=${1:-"api.surgi-form.com"}
SERVICE_NAME="surgiform-backend"
REGION="asia-northeast1"  # 도쿄 리전 (도메인 매핑 지원)
PROJECT_ID="surgiform-471510"

# 색상 코드
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

echo -e "${GREEN}🔗 Cloud Run 커스텀 도메인 설정${NC}"
echo "도메인: ${DOMAIN}"
echo "서비스: ${SERVICE_NAME}"
echo "리전: ${REGION}"
echo ""

# 1. 도메인 소유권 확인
echo -e "${BLUE}📋 1단계: 도메인 소유권 확인${NC}"
echo "다음 URL에서 도메인 소유권을 먼저 확인해야 합니다:"
echo -e "${YELLOW}https://console.cloud.google.com/run/domains?project=${PROJECT_ID}${NC}"
echo ""
read -p "도메인 소유권 확인을 완료하셨습니까? (y/N): " -n 1 -r
echo
if [[ ! $REPLY =~ ^[Yy]$ ]]; then
    echo -e "${YELLOW}⚠️  도메인 소유권을 먼저 확인하세요${NC}"
    echo ""
    echo "확인 방법:"
    echo "1. 위 URL 접속"
    echo "2. 'Add mapping' 클릭"
    echo "3. 도메인 입력 후 'Verify domain' 클릭"
    echo "4. DNS TXT 레코드 추가 안내 따르기"
    exit 0
fi

# 2. 기존 도메인 매핑 확인
echo ""
echo -e "${BLUE}📋 2단계: 기존 도메인 매핑 확인${NC}"
EXISTING_MAPPING=$(gcloud beta run domain-mappings list \
    --region ${REGION} \
    --filter "metadata.name=${DOMAIN}" \
    --format "value(metadata.name)" 2>/dev/null || echo "")

if [ ! -z "${EXISTING_MAPPING}" ]; then
    echo -e "${YELLOW}ℹ️  도메인 매핑이 이미 존재합니다: ${DOMAIN}${NC}"
    
    # 기존 매핑 정보 표시
    echo ""
    echo "현재 매핑 정보:"
    gcloud beta run domain-mappings describe ${DOMAIN} \
        --region ${REGION} \
        --format "table(metadata.name,status.mappedRouteName,status.url)"
    
    read -p "기존 매핑을 삭제하고 다시 생성하시겠습니까? (y/N): " -n 1 -r
    echo
    if [[ $REPLY =~ ^[Yy]$ ]]; then
        echo -e "${YELLOW}기존 매핑 삭제 중...${NC}"
        gcloud beta run domain-mappings delete ${DOMAIN} --region ${REGION} --quiet
        sleep 2
    else
        echo -e "${GREEN}기존 매핑을 유지합니다${NC}"
        SKIP_CREATE=true
    fi
fi

# 3. 도메인 매핑 생성
if [ -z "${SKIP_CREATE}" ]; then
    echo ""
    echo -e "${BLUE}📋 3단계: 도메인 매핑 생성${NC}"
    
    if gcloud beta run domain-mappings create \
        --service ${SERVICE_NAME} \
        --domain ${DOMAIN} \
        --region ${REGION}; then
        
        echo -e "${GREEN}✅ 도메인 매핑 생성 완료!${NC}"
    else
        echo -e "${RED}❌ 도메인 매핑 실패${NC}"
        echo "가능한 원인:"
        echo "1. 도메인 소유권이 확인되지 않음"
        echo "2. 서비스가 배포되지 않음"
        echo "3. 권한 부족"
        exit 1
    fi
fi

# 4. DNS 레코드 정보 표시
echo ""
echo -e "${BLUE}📋 4단계: DNS 설정${NC}"
echo -e "${YELLOW}다음 DNS 레코드를 도메인 제공업체에 추가하세요:${NC}"
echo ""

# DNS 레코드 가져오기
DNS_RECORDS=$(gcloud beta run domain-mappings describe ${DOMAIN} \
    --region ${REGION} \
    --format "json" | jq -r '.status.resourceRecords[]')

# A 레코드와 AAAA 레코드 분리 표시
echo -e "${GREEN}A 레코드 (IPv4):${NC}"
echo "${DNS_RECORDS}" | jq -r 'select(.type=="A") | "  \(.type) @ \(.rrdata)"'

echo ""
echo -e "${GREEN}AAAA 레코드 (IPv6):${NC}"
echo "${DNS_RECORDS}" | jq -r 'select(.type=="AAAA") | "  \(.type) @ \(.rrdata)"'

echo ""
echo -e "${GREEN}CNAME 레코드 (있는 경우):${NC}"
echo "${DNS_RECORDS}" | jq -r 'select(.type=="CNAME") | "  \(.type) \(.name) \(.rrdata)"'

# 5. 도메인 제공업체별 가이드
echo ""
echo -e "${BLUE}📋 5단계: 도메인 제공업체별 설정 가이드${NC}"
echo ""
echo -e "${YELLOW}Cloudflare:${NC}"
echo "1. DNS 관리 페이지로 이동"
echo "2. 프록시 상태를 'DNS only'로 설정 (주황색 구름 → 회색 구름)"
echo "3. 위의 A/AAAA 레코드 추가"
echo ""
echo -e "${YELLOW}Google Domains:${NC}"
echo "1. DNS 관리 페이지로 이동"
echo "2. 'Custom records' 섹션"
echo "3. 위의 A/AAAA 레코드 추가"
echo ""
echo -e "${YELLOW}Route 53 (AWS):${NC}"
echo "1. Hosted Zone으로 이동"
echo "2. 'Create Record' 클릭"
echo "3. 위의 A/AAAA 레코드 추가"

# 6. 확인 방법
echo ""
echo -e "${BLUE}📋 6단계: 설정 확인${NC}"
echo ""
echo "DNS 전파 확인 (5-30분 소요):"
echo -e "${GREEN}nslookup ${DOMAIN}${NC}"
echo -e "${GREEN}dig ${DOMAIN}${NC}"
echo ""
echo "서비스 접속 테스트:"
echo -e "${GREEN}curl https://${DOMAIN}/health${NC}"
echo ""
echo -e "${GREEN}✅ 설정 완료!${NC}"
echo ""
echo "🌐 커스텀 도메인: https://${DOMAIN}"
echo "📊 헬스체크: https://${DOMAIN}/health"
echo "📖 API 문서: https://${DOMAIN}/docs"