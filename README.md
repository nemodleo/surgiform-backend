# Surgiform Backend

수술동의서 생성·변환 API 백엔드 서비스

## 🚀 Quick Start

### 로컬 개발

```bash
# 환경변수 설정
cp .env.example .env

# 의존성 설치 (Poetry)
poetry install

# 개발 서버 실행
uvicorn surgiform.deploy.server:app --reload --port 8000
```

### GCP 배포 (도쿄 리전)

```bash
# 배포 + 환경변수 + 도메인 설정
./deploy.sh surgiform-471510 asia-northeast1 --with-env api.surgi-form.com

# 환경변수만 업데이트
./sync-env.sh
```

## 📁 프로젝트 구조

```
surgiform-backend/
├── surgiform/
│   ├── api/           # API 엔드포인트
│   ├── core/          # 핵심 비즈니스 로직
│   ├── deploy/        # 배포 설정
│   └── external/      # 외부 서비스 연동
├── tests/             # 테스트 코드
├── .env               # 환경변수
├── pyproject.toml     # Poetry 설정
└── deploy.sh          # 배포 스크립트
```

## 🔧 기술 스택

- **Framework**: FastAPI
- **Language**: Python 3.11+
- **Package Manager**: Poetry
- **LLM**: OpenAI GPT-4
- **Database**: Elasticsearch, Neo4j
- **Deployment**: Google Cloud Run (도쿄 리전)

## 🌐 API 엔드포인트

- **Health Check**: `GET /health`
- **API Docs**: `GET /docs`
- **Consent Generation**: `POST /consent`
- **Chat**: `POST /chat`
- **Transform**: `POST /transform`

## 🚢 배포

### 1. Cloud Run 배포 (권장)

```bash
# 도쿄 리전으로 배포
./deploy.sh surgiform-471510 asia-northeast1 --with-env

# 커스텀 도메인 설정
./setup-domain.sh api.surgi-form.com
```

### 2. 환경변수 설정

`.env` 파일 생성 후 필요한 환경변수 설정:

```env
OPENAI_API_KEY=sk-...
ES_HOST=http://localhost:9200
NEO4J_URL=bolt://localhost:7687
NEO4J_USERNAME=neo4j
NEO4J_PASSWORD=password
```

### 3. DNS 설정

도메인 매핑 후 CNAME 레코드 추가:
- `api.surgi-form.com` → `ghs.googlehosted.com`

## 📊 모니터링

```bash
# 로그 확인
gcloud logging read "resource.type=cloud_run_revision" --limit 50

# 서비스 상태
gcloud run services describe surgiform-backend --region asia-northeast1
```

## 💰 비용

- **Cloud Run**: 요청당 과금 (프리티어 포함)
- **도메인 매핑**: 무료
- **SSL 인증서**: 무료 (자동 관리)
- **예상 월 비용**: ~$10-50 (트래픽에 따라)

## 📝 문서

- [배포 가이드](./README_DEPLOYMENT.md)
- [DNS 설정 가이드](./DNS_SETUP_GUIDE.md)
- [API 문서](https://api.surgi-form.com/docs)

## 🔐 보안

- HTTPS 자동 적용
- 환경변수로 민감정보 관리
- Cloud Run 자동 스케일링 및 보안

## 🤝 기여

1. Fork the repository
2. Create your feature branch
3. Commit your changes
4. Push to the branch
5. Create a Pull Request

## 📄 라이선스

Private repository - All rights reserved

## 👥 팀

- Hyun Park - nemod.leo@snu.ac.kr
- Shin Seowon - sswilove1@kaist.ac.kr
- Kim Minjun - kimminjun67@snu.ac.kr