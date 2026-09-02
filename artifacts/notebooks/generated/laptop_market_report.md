# 노트북 시장 분석 및 가치 평가 보고서 (Laptop Market Analysis Report)

## 1. 개요 및 분석 기준
본 보고서는 `backup_laptops_catalog.json` 카탈로그 데이터를 바탕으로 `specs_criteria.json`에 정의된 가치 평가 공식(Value Score Formula)을 적용하여 각 모델의 가격 대비 성능, 스펙 및 만족도를 정량적으로 분석하고 최적의 추천 모델을 도출합니다.

### 가치 점수 산출 공식 (Value Scoring Formula)
$$\text{Value\_Score} = \frac{\text{RAM\_GB} \times 10 + \frac{\text{SSD\_GB}}{10} + \text{Rating} \times 20}{\frac{\text{Price\_KRW}}{100,000}}$$

---

## 2. 노트북 제품 비교 및 점수표

| ID | Brand | Model | Price | Score | Category | CPU / GPU | RAM / SSD | Weight | Rating (Reviews) |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| **LP-001** | 레노버 | 아이디어패드 Slim 3 15IAH8 | ₩599,000 | **50.95** | 가성비/사무용 | Intel Core i5-12450H | 16GB / 512GB | 1.62kg | 4.7 (420건) |
| **LP-002** | LG전자 | 2026 그램 프로 16 | ₩1,890,000 | **27.53** | 초경량/프리미엄 | Intel Core Ultra 7 155H | 32GB / 1TB | 1.19kg | 4.9 (890건) |
| **LP-003** | ASUS | ROG 제피러스 G14 | ₩2,150,000 | **24.11** | 게이밍/크리에이터 | AMD Ryzen 9 8945HS (RTX 4060) | 32GB / 1TB | 1.50kg | 4.8 (310건) |

---

## 3. 부문별 세부 분석

### 3.1. 보급형/가성비 부문 (Budget Tier)
- **대표 모델**: 레노버 아이디어패드 Slim 3 15IAH8 (LP-001)
- **분석**: 599,000원의 합리적인 가격대에 Intel Core i5-12450H 고성능 H시리즈 프로세서와 16GB RAM, 512GB NVMe SSD를 탑재하여 사무 및 일반 작업 환경에서 압도적인 가성비(Score: 50.95)를 달성하였습니다. 4.7점의 높은 평점과 다수의 사용자 리뷰로 신뢰성이 입증되었습니다.

### 3.2. 프리미엄/초경량 부문 (Premium Ultralight Tier)
- **대표 모델**: LG전자 2026 그램 프로 16 (LP-002)
- **분석**: 최신 AI NPU가 탑재된 Intel Core Ultra 7 155H와 32GB 대용량 메모리, 1TB SSD를 갖추었음에도 1.19kg의 경량화를 실현했습니다. 4.9점이라는 최상위 평점(리뷰 890건)을 기록하여 휴대성과 작업 생산성을 동시에 요구하는 비즈니스 사용자에게 가장 최적화되어 있습니다.

### 3.3. 고성능 게이밍/크리에이터 부문 (High-End Gaming & Creator Tier)
- **대표 모델**: ASUS ROG 제피러스 G14 (LP-003)
- **분석**: 최신 AMD Ryzen 9 8945HS 플래그십 프로세서와 외장 GPU(GeForce RTX 4060)를 탑재하여 3D 그래픽 작업, 영상 렌더링, 고사양 게이밍에 특화되었습니다. 고성능 대비 1.5kg의 콤팩트한 무게로 이동성을 겸비했습니다.

---

## 4. 최종 Top 2 추천 모델

1. **1위 추천: 레노버 아이디어패드 Slim 3 15IAH8 (Value Score: 50.95)**
   - **선정 이유**: 50만원대 예산에서 16GB RAM과 512GB 스토리지를 제공하여 전 모델 중 가장 높은 가치 점수를 획득함. 학생 및 일반 직장인 사무용으로 최고의 선택지.
2. **2위 추천: LG전자 2026 그램 프로 16 (Value Score: 27.53)**
   - **선정 이유**: 32GB RAM / 1TB SSD 풀스펙과 1.19kg의 초경량 폼팩터, 평점 4.9점의 압도적 만족도를 기반으로 프리미엄 라인업 중 최고 점수 기록.
