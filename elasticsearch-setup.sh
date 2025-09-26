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
