#!/bin/bash

# GCP에서 Elasticsearch VM 생성 및 설정 스크립트
# 사용법: ./setup-elasticsearch.sh [PROJECT_ID] [ZONE]

set -e

# 기본값 설정
PROJECT_ID=${1:-"surgiform-471510"}
ZONE=${2:-"asia-northeast1-a"}
VM_NAME="elasticsearch-vm"
MACHINE_TYPE="e2-standard-2"  # 2 vCPU, 8GB RAM
DISK_SIZE="50GB"
DISK_TYPE="pd-ssd"

echo "🔍 GCP Elasticsearch VM 설정 시작"
echo "Project ID: ${PROJECT_ID}"
echo "Zone: ${ZONE}"
echo "VM Name: ${VM_NAME}"

# 1. GCP 프로젝트 설정
echo "📌 GCP 프로젝트 설정..."
gcloud config set project ${PROJECT_ID}

# 2. VM 인스턴스 생성
echo "💻 Elasticsearch VM 생성 중..."
gcloud compute instances create ${VM_NAME} \
    --zone=${ZONE} \
    --machine-type=${MACHINE_TYPE} \
    --network-interface=network-tier=PREMIUM,subnet=default \
    --maintenance-policy=MIGRATE \
    --provisioning-model=STANDARD \
    --service-account=default \
    --scopes=https://www.googleapis.com/auth/cloud-platform \
    --tags=elasticsearch-server \
    --create-disk=auto-delete=yes,boot=yes,device-name=${VM_NAME},image=projects/cos-cloud/global/images/family/cos-stable,mode=rw,size=${DISK_SIZE},type=projects/${PROJECT_ID}/zones/${ZONE}/diskTypes/${DISK_TYPE} \
    --no-shielded-secure-boot \
    --shielded-vtpm \
    --shielded-integrity-monitoring \
    --labels=environment=production,service=elasticsearch \
    --reservation-affinity=any

# 3. 방화벽 규칙 생성 (Elasticsearch 포트 9200)
echo "🔥 방화벽 규칙 생성 중..."
gcloud compute firewall-rules create allow-elasticsearch \
    --allow tcp:9200 \
    --source-ranges 0.0.0.0/0 \
    --target-tags elasticsearch-server \
    --description "Allow Elasticsearch access" || echo "방화벽 규칙이 이미 존재합니다."

# 4. VM에 Elasticsearch Docker 설치 스크립트 전송
echo "📦 Elasticsearch 설치 스크립트 생성 중..."
cat > elasticsearch-setup.sh << 'EOF'
#!/bin/bash

# Container OS에서 Docker 명령 실행
echo "🐳 Elasticsearch Docker 컨테이너 시작..."

# Elasticsearch 8.x Docker 실행
docker run -d \
    --name elasticsearch \
    --restart unless-stopped \
    -p 9200:9200 \
    -p 9300:9300 \
    -e "discovery.type=single-node" \
    -e "xpack.security.enabled=false" \
    -e "ES_JAVA_OPTS=-Xms2g -Xmx2g" \
    -v elasticsearch-data:/usr/share/elasticsearch/data \
    docker.elastic.co/elasticsearch/elasticsearch:8.11.0

echo "⏳ Elasticsearch 시작 대기 중..."
sleep 30

# 헬스 체크
echo "🔍 Elasticsearch 상태 확인..."
curl -X GET "localhost:9200/_cluster/health?pretty" || echo "아직 시작 중입니다..."

echo "✅ Elasticsearch 설정 완료!"
echo "🌐 외부 접속: http://$(curl -s http://metadata.google.internal/computeMetadata/v1/instance/network-interfaces/0/access-configs/0/external-ip -H "Metadata-Flavor: Google"):9200"
EOF

# 5. VM에 스크립트 전송 및 실행
echo "📤 VM에 설치 스크립트 전송 중..."
gcloud compute scp elasticsearch-setup.sh ${VM_NAME}:~/elasticsearch-setup.sh --zone=${ZONE}

echo "🚀 VM에서 Elasticsearch 설치 실행 중..."
gcloud compute ssh ${VM_NAME} --zone=${ZONE} --command="chmod +x ~/elasticsearch-setup.sh && ~/elasticsearch-setup.sh"

# 6. VM 외부 IP 가져오기
VM_EXTERNAL_IP=$(gcloud compute instances describe ${VM_NAME} \
    --zone=${ZONE} \
    --format='get(networkInterfaces[0].accessConfigs[0].natIP)')

echo ""
echo "✅ Elasticsearch VM 설정 완료!"
echo "🌐 외부 IP: ${VM_EXTERNAL_IP}"
echo "📊 Elasticsearch URL: http://${VM_EXTERNAL_IP}:9200"
echo "🔍 상태 확인: curl http://${VM_EXTERNAL_IP}:9200/_cluster/health"
echo ""
echo "💡 다음 단계:"
echo "  1. .env 파일의 ES_HOST를 업데이트하세요:"
echo "     ES_HOST=http://${VM_EXTERNAL_IP}:9200"
echo "  2. Cloud Run 환경변수를 동기화하세요:"
echo "     ./sync-env.sh"
echo ""

# 정리
rm -f elasticsearch-setup.sh

echo "🎉 설정 완료!"
