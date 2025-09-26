# Surgiform Backend GCP 배포 가이드

## 준비사항

1. GCP 계정 및 프로젝트 생성
2. Google Cloud SDK 설치
3. Docker 설치
4. 환경변수 설정 (.env 파일)

## 배포 방법

### 1. Cloud Run 배포 (권장)

```bash
# 기본 배포 (도쿄 리전)
./deploy.sh surgiform-471510 asia-northeast1

# .env 파일 포함 배포
./deploy.sh surgiform-471510 asia-northeast1 --with-env

# 커스텀 도메인 포함 배포
./deploy.sh surgiform-471510 asia-northeast1 --with-env api.surgi-form.com
```

### 2. App Engine 배포

```bash
# App Engine으로 배포
./deploy.sh surgiform-471510 asia-northeast3 --app-engine
```

### 3. GitHub Actions를 통한 자동 배포

GitHub Secrets에 다음 값 설정:
- `GCP_PROJECT_ID`: GCP 프로젝트 ID
- `GCP_SA_KEY`: 서비스 계정 키 (JSON)

main 브랜치에 푸시하면 자동 배포됨

## 필요한 GCP API

- Cloud Build API
- Cloud Run API
- Container Registry API
- Artifact Registry API

## 환경변수 설정

### 방법 1: .env 파일 전체 동기화 (권장)

```bash
# .env 파일의 모든 환경변수를 Cloud Run에 동기화
./sync-env.sh

# 특정 .env 파일 사용
./sync-env.sh .env.production
```

### 방법 2: 배포 시 .env 파일 포함

```bash
# 배포와 동시에 .env 파일의 환경변수 설정
./deploy.sh surgiform-471510 asia-northeast3 --with-env
```

### 방법 3: 개별 환경변수 설정

```bash
gcloud run services update surgiform-backend \
    --region asia-northeast3 \
    --set-env-vars OPENAI_API_KEY="your-key"
```

### 필요한 환경변수

- `OPENAI_API_KEY`: OpenAI API 키 (필수)
- `ES_HOST`: Elasticsearch URL
- `ES_USER`: Elasticsearch 사용자명
- `ES_PASSWORD`: Elasticsearch 비밀번호
- `NEO4J_URL`: Neo4j 데이터베이스 URI
- `NEO4J_USERNAME`: Neo4j 사용자명
- `NEO4J_PASSWORD`: Neo4j 비밀번호
- `UPTODATE_ID`, `UPTODATE_PW`, `UPTODATE_EMAIL`: UpToDate 서비스 인증

## 커스텀 도메인 설정 (도쿄 리전)

### 1. 자동 도메인 설정 스크립트

```bash
# 도메인 소유권 확인 및 매핑 설정
./setup-domain.sh api.surgi-form.com
```

### 2. 배포와 함께 도메인 설정

```bash
# 배포 + .env + 도메인 매핑
./deploy.sh surgiform-471510 asia-northeast1 --with-env api.surgi-form.com
```

### 3. 수동 도메인 매핑

```bash
# 도메인 매핑 생성
gcloud beta run domain-mappings create \
    --service surgiform-backend \
    --domain api.surgi-form.com \
    --region asia-northeast1
```

### DNS 설정

도메인 매핑 후 표시되는 DNS 레코드를 추가:
- **CNAME**: `api.surgi-form.com` → `ghs.googlehosted.com`
- SSL 인증서는 자동으로 발급/관리됩니다

## 서비스 확인

배포 후 다음 엔드포인트로 확인:
- 헬스체크: `https://[SERVICE_URL]/health`
- API 문서: `https://[SERVICE_URL]/docs`
- 커스텀 도메인: `https://api.surgi-form.com/health` (도메인 설정 후)

## 로그 확인

```bash
# Cloud Run 로그 확인 (도쿄 리전)
gcloud logging read "resource.type=cloud_run_revision AND resource.labels.service_name=surgiform-backend" --limit 50

# App Engine 로그 확인
gcloud app logs tail -s default
```
