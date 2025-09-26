# DNS 설정 가이드

## Cloud Run 도메인 매핑 후 DNS 구성 (도쿄 리전)

`./setup-domain.sh` 실행 후 표시되는 CNAME 레코드를 DNS에 설정합니다.

## DNS 제공업체별 설정 방법

### 1. Cloudflare

1. [Cloudflare Dashboard](https://dash.cloudflare.com) 로그인
2. 도메인 선택 → DNS 관리
3. **Add record** 클릭
4. 설정값:
   - Type: `CNAME`
   - Name: `api` (또는 `@` for root)
   - Target: `ghs.googlehosted.com`
   - Proxy status: **DNS only** (회색 구름 - 중요!)
   - TTL: `Auto`
5. **Save** 클릭

⚠️ **중요**: Proxy status를 반드시 "DNS only"로 설정하세요.

### 2. Gabia

1. [마이가비아](https://my.gabia.com) 로그인
2. My 서비스 관리 → 도메인 → DNS 설정
3. **레코드 추가** 클릭
4. 설정값:
   - 타입: `CNAME`
   - 호스트: `api`
   - 값/위치: `ghs.googlehosted.com`
   - TTL: `300`
5. **확인** 클릭

### 3. AWS Route 53

1. [Route 53 Console](https://console.aws.amazon.com/route53) 접속
2. Hosted zones → 도메인 선택
3. **Create record** 클릭
4. 설정값:
   - Record name: `api`
   - Record type: `CNAME`
   - Value: `ghs.googlehosted.com`
   - TTL: `300`
   - Routing policy: `Simple routing`
5. **Create records** 클릭

### 4. Google Domains

1. [Google Domains](https://domains.google.com) 로그인
2. 도메인 선택 → DNS
3. **Manage custom records** → **Create new record**
4. 설정값:
   - Host name: `api`
   - Type: `CNAME`
   - TTL: `300`
   - Data: `ghs.googlehosted.com`
5. **Save** 클릭

### 5. Namecheap

1. [Namecheap Dashboard](https://ap.www.namecheap.com) 로그인
2. Domain List → Manage → Advanced DNS
3. **Add New Record** 클릭
4. 설정값:
   - Type: `CNAME Record`
   - Host: `api`
   - Value: `ghs.googlehosted.com`
   - TTL: `Automatic`
5. **Save** 클릭

## DNS 설정 확인

### 1. DNS 전파 확인 (5-30분 소요)

```bash
# DNS 조회
nslookup api.surgi-form.com

# 또는
dig api.surgi-form.com

# 또는 온라인 도구
# https://www.whatsmydns.net/#A/api.surgi-form.com
```

### 2. SSL 인증서 상태 확인

```bash
# GCP에서 인증서 상태 확인
gcloud compute ssl-certificates describe cert-surgiform-api

# ACTIVE 상태가 되어야 정상
```

### 3. 서비스 접속 테스트

```bash
# HTTPS 접속 테스트
curl -v https://api.surgi-form.com/health

# 브라우저에서 확인
# https://api.surgi-form.com/health
# https://api.surgi-form.com/docs
```

## 문제 해결

### DNS가 반영되지 않는 경우

1. **캐시 문제**
   ```bash
   # Mac/Linux
   sudo dscacheutil -flushcache
   
   # Windows
   ipconfig /flushdns
   ```

2. **TTL 대기**
   - 기존 DNS 레코드가 있었다면 TTL 시간만큼 대기 필요
   - 보통 5-30분, 최대 48시간

### SSL 인증서가 발급되지 않는 경우

1. **DNS 설정 확인**
   - A 레코드가 올바른 IP를 가리키는지 확인
   - CNAME과 A 레코드가 충돌하지 않는지 확인

2. **인증서 상태 확인**
   ```bash
   gcloud compute ssl-certificates describe cert-surgiform-api
   ```
   - `PROVISIONING`: 발급 중 (최대 30분)
   - `PROVISIONING_FAILED`: 발급 실패 (DNS 설정 재확인)
   - `ACTIVE`: 정상 발급됨

3. **도메인 소유권**
   - 도메인이 실제로 본인 소유인지 확인
   - CAA 레코드가 있다면 Google을 허용하는지 확인

### 502/503 에러가 발생하는 경우

1. **Cloud Run 서비스 상태 확인**
   ```bash
   gcloud run services describe surgiform-backend --region asia-northeast1
   ```

2. **서비스 URL 테스트**
   ```bash
   curl https://surgiform-backend-[hash]-an.a.run.app/health
   ```

3. **로그 확인**
   ```bash
   gcloud logging read "resource.type=cloud_run_revision" --limit 50
   ```

## 비용 관련 정보

### 예상 비용 (월 기준)

- **로드밸런서 기본 요금**: ~$18
- **포워딩 룰**: 룰당 ~$0.025/시간
- **SSL 인증서**: 무료 (관리형)
- **데이터 처리**: GB당 ~$0.008-0.012
- **Cloud Run**: 요청 수와 컴퓨팅 시간에 따라 과금

### 비용 절감 팁

1. 개발/테스트 환경은 로드밸런서 없이 Cloud Run URL 직접 사용
2. 트래픽이 적은 서비스는 도쿄 리전 + 도메인 매핑 고려
3. Cloud CDN 활성화로 대역폭 비용 절감 가능

## 추가 자료

- [Cloud Run 공식 문서](https://cloud.google.com/run/docs)
- [HTTPS 로드밸런서 문서](https://cloud.google.com/load-balancing/docs/https)
- [SSL 인증서 문서](https://cloud.google.com/load-balancing/docs/ssl-certificates)
- [가격 계산기](https://cloud.google.com/products/calculator)