# OpenAI Model Performance Benchmark Report

**Test Date**: 2025-10-03
**Number of iterations**: 3
**Tasks**: 100자 한영번역, 100자 10자 요약

## Executive Summary

이 보고서는 OpenAI의 다양한 모델(GPT-5, GPT-4.1, GPT-4o, o-시리즈, GPT-3.5-turbo)의 성능을 2가지 작업을 통해 비교 분석합니다:
- **100자 한영번역**: 한글 100자를 영어로 번역
- **100자 10자 요약**: 텍스트를 10자 이내로 요약

## Performance Comparison Table

### 100자 한영번역 (Korean to English Translation)

| Model | Avg Time (s) | Min Time (s) | Max Time (s) | Avg Tokens | Status |
|-------|--------------|--------------|--------------|------------|--------|
| gpt-3.5-turbo | 0.70 | 0.62 | 0.76 | 192 | ✅ |
| gpt-4.1-nano | 0.99 | 0.85 | 1.22 | 122 | ✅ |
| gpt-4.1 | 1.11 | 0.94 | 1.24 | 130 | ✅ |
| gpt-4.1-mini | 1.26 | 0.98 | 1.70 | 128 | ✅ |
| gpt-4o | 1.41 | 1.22 | 1.62 | 129 | ✅ |
| gpt-4o-mini | 1.44 | 1.19 | 1.92 | 126 | ✅ |
| o1-mini | 2.22 | 1.99 | 2.38 | 441 | ✅ |
| o3-mini | 3.10 | 2.75 | 3.29 | 269 | ✅ |
| o4-mini | 3.78 | 3.71 | 3.90 | 337 | ✅ |
| **gpt-5-mini** | **4.95** | **4.33** | **5.39** | **346** | ✅ |
| **gpt-5** | **5.27** | **4.70** | **5.72** | **520** | ✅ |
| **gpt-5-nano** | **20.49** | **6.79** | **39.86** | **586** | ✅ |

### 100자를 10자로 요약 (Text Summarization)

| Model | Avg Time (s) | Min Time (s) | Max Time (s) | Avg Tokens | Status |
|-------|--------------|--------------|--------------|------------|--------|
| gpt-3.5-turbo | 0.66 | 0.54 | 0.88 | 137 | ✅ |
| gpt-4.1-mini | 0.67 | 0.63 | 0.74 | 75 | ✅ |
| gpt-4o-mini | 0.73 | 0.67 | 0.81 | 74 | ✅ |
| gpt-4.1-nano | 0.73 | 0.56 | 1.00 | 73 | ✅ |
| gpt-4.1 | 0.79 | 0.73 | 0.83 | 73 | ✅ |
| gpt-4o | 1.28 | 0.87 | 1.60 | 73 | ✅ |
| o1-mini | 3.23 | 2.54 | 3.85 | 533 | ✅ |
| o4-mini | 5.99 | 5.11 | 7.55 | 668 | ✅ |
| **gpt-5** | **6.89** | **5.88** | **8.50** | **567** | ✅ |
| **gpt-5-mini** | **8.14** | **7.51** | **8.53** | **567** | ✅ |
| o3-mini | 10.20 | 9.52 | 11.02 | 833 | ✅ |
| **gpt-5-nano** | - | - | - | - | ❌ Error |

## Key Findings

### 속도 순위 (Speed Ranking)

#### 100자 한영번역 - 최고 속도 Top 5
1. 🥇 **gpt-3.5-turbo**: 0.70초 (레거시 모델, 가장 빠름)
2. 🥈 **gpt-4.1-nano**: 0.99초 (최신 nano 모델)
3. 🥉 **gpt-4.1**: 1.11초
4. **gpt-4.1-mini**: 1.26초
5. **gpt-4o**: 1.41초

#### 100자 10자 요약 - 최고 속도 Top 5
1. 🥇 **gpt-3.5-turbo**: 0.66초
2. 🥈 **gpt-4.1-mini**: 0.67초
3. 🥉 **gpt-4o-mini**: 0.73초
4. **gpt-4.1-nano**: 0.73초
5. **gpt-4.1**: 0.79초

### GPT-5 시리즈 성능 분석

**주요 발견사항**:
- GPT-5 시리즈는 **이전 세대보다 현저히 느림**
- GPT-5는 한영번역에서 gpt-3.5-turbo보다 **7.5배 느림** (5.27초 vs 0.70초)
- GPT-5-nano는 가장 느리고 불안정 (6.79초 ~ 39.86초)
- GPT-5-nano는 요약 작업 중 Connection Error 발생

**속도 비교**:
| Model | 한영번역 속도 | 요약 속도 | 평균 |
|-------|------------|---------|------|
| gpt-5 | 5.27초 | 6.89초 | 6.08초 |
| gpt-5-mini | 4.95초 | 8.14초 | 6.55초 |
| gpt-5-nano | 20.49초 | Error | - |
| **gpt-4.1** | **1.11초** | **0.79초** | **0.95초** |
| **gpt-3.5-turbo** | **0.70초** | **0.66초** | **0.68초** |

### 모델별 특성

**추론 모델 (o-시리즈)**: 느리지만 고품질
- o1-mini: 2~3초 (중간 추론)
- o3-mini: 3~10초 (고급 추론)
- o4-mini: 4~6초 (최신 추론)

**GPT-4.1 시리즈**: 최고의 균형
- 빠른 응답 속도 (0.7~1.3초)
- 적절한 토큰 사용량
- 안정적인 성능

**GPT-4o 시리즈**: 중간 성능
- 1~1.5초 응답
- 균형잡힌 품질

**GPT-3.5-turbo**: 레거시 최고속
- 가장 빠른 응답 (0.66~0.70초)
- 높은 토큰 사용량 (192~253)

## Sample Responses

### 100자 한영번역
**Prompt**: 다음 100자 한글 텍스트를 영어로 번역해주세요: "인공지능 기술의 발전은 우리 삶의 많은 부분을 변화시키고 있습니다. 특히 자연어 처리 기술은 언어의 장벽을 넘어 전 세계 사람들이 소통할 수 있도록 돕고 있으며, 이는 글로벌 협력과 이해를 증진시키는 데 크게 기여하고 있습니다."

**gpt-5-mini** (4.95초):
```
The development of artificial intelligence technologies is transforming many aspects of our lives. In particular, natural language processing helps people worldwide communicate across language barriers, greatly contributing to enhanced global cooperation and understanding.
```

**gpt-4.1** (1.11초):
```
The advancement of artificial intelligence technology is changing many aspects of our lives. In particular, natural language processing technology helps people around the world communicate beyond language barriers, and this greatly contributes to promoting global cooperation and understanding.
```

**gpt-3.5-turbo** (0.70초):
```
The advancement of artificial intelligence technology is transforming many aspects of our lives. In particular, natural language processing technology is helping people around the world communicate beyond language barriers, greatly contributing to enhancing global cooperation and understanding.
```

## Recommendations

### 사용 용도별 추천 모델

1. **최고 속도 필요시**:
   - gpt-3.5-turbo (0.66~0.70초)
   - gpt-4.1-nano (0.73~0.99초)

2. **균형잡힌 성능**:
   - gpt-4.1 (0.79~1.11초)
   - gpt-4.1-mini (0.67~1.26초)

3. **고품질 추론 필요시**:
   - o1-mini (2~3초)
   - o4-mini (4~6초)

4. **GPT-5 시리즈**:
   - ⚠️ **현재 권장하지 않음** (느린 속도, 불안정성)
   - 추가 최적화 필요

## Technical Notes

- GPT-5 시리즈는 `temperature=1` 고정 (0.7 미지원)
- GPT-5 시리즈는 `max_completion_tokens` 파라미터 사용 (`max_tokens` 미지원)
- o-시리즈는 추론 모델로 temperature 설정 불가
- gpt-5-nano는 연결 안정성 문제 존재

## Conclusion

**GPT-4.1 시리즈**가 현재 가장 **빠르고 안정적인 성능**을 제공합니다.

**GPT-5 시리즈**는 예상과 달리 이전 세대보다 **5~8배 느린 성능**을 보이며, 특히 gpt-5-nano는 연결 오류가 발생하여 프로덕션 환경에서 사용을 권장하지 않습니다.

**가성비 최고**: gpt-3.5-turbo (레거시지만 여전히 가장 빠름)
**최신 기술 + 속도**: gpt-4.1 시리즈
**고품질 추론**: o-시리즈 (시간 여유 있을 때)
