# 🎯 Mission 04: Progressive Skills 기반 금융 분석 & 인터랙티브 대시보드 시각화

본 미션은 `4.Skills_and_MCP.ipynb`에서 학습한 **Progressive Skill Execution (점진적 스킬 공개)** 원리를 바탕으로, 교육생 여러분이 에이전트 코드를 한 줄도 수정하지 않고도 `skills/` 라이브러리를 확장하여 **`main_agent`를 전문 금융 분석 에이전트로 즉각 진화**시키고, **실시간 금융 데이터 수집 및 인터랙티브 HTML 대시보드(Chart.js) 시각화**를 완성하는 실습 과제입니다.

---

## 💡 도구(Tool) vs 스킬(Skill)의 패러다임 전환

| 구분 | Mission 01: 도구 (Tool) 바인딩 | Mission 04: 점진적 스킬 (Progressive Skill) |
| :--- | :--- | :--- |
| **확장 방식** | 파이썬 코드 작성 + `@tool` 데코레이터 + 에이전트 재빌드 | **코드 수정 0줄!** `skills/` 폴더에 스크립트 패키지 복사 |
| **토큰 비용** | 모든 도구 스키마가 프롬프트에 상시 적재되어 토큰 낭비 발생 | **1단계(Frontmatter 이름/설명)만 가볍게 적재** ➔ 필요 시에만 본문 열람 |
| **실행 원리** | LLM이 ToolCall JSON 생성 ➔ 런타임이 함수 직접 호출 | LLM이 `file_read`로 `SKILL.md` 학습 ➔ `bash_command`로 실행 |
| **유연성** | 환경 변경 시 서버 재배포 필요 | 실시간으로 스킬을 다운로드(`npx skills add`)하거나 추가 가능 |

---

## 📂 실습 대상 디렉토리 및 파일

* **스킬 저장소 (스킬 풀)**: `artifacts/skills_pool/` (10종의 금융 전문 스킬 패키지 보관)
* **런타임 활성 스킬 폴더**: `skills/` (에이전트가 실제로 인식하고 실행하는 디렉토리)
* **5계층 프롬프트 조립기**: `app/middleware/prompt/prompt_assembler.py` (Layer 2.2에 스킬 자동 주입)
* **메인 오케스트레이터**: `app/agents/main_agent.py` (`file_read`와 `bash_command`로 스킬 자율 실행)
* **자동화 검증 스크립트**: `tests/test_mission04.py`

---

## 📚 탑재된 13종 스킬 라이브러리 목록

에이전트는 `skills/` 폴더에 설치된 아래 스킬들의 `SKILL.md`를 자율적으로 열람하여 파이썬 코드를 학습하고 `bash_command`로 실행합니다:

| # | 스킬명 (폴더명) | 주요 기능 및 역할 | 대표 라이브러리 / 소스 |
| :-: | :--- | :--- | :--- |
| **1** | `pykrx-korean-market` | **국내 주식 & 시장 시세**: KOSPI/KOSDAQ 종목 시세, 시가총액 순위, 외국인/기관/개인 수급 동향, 밸류에이션(PER, PBR) | `FinanceDataReader`, `pykrx` |
| **2** | `yfinance-market-data` | **글로벌/미국 주식 & 재무 지표**: 미국 빅테크 및 전 세계 주식 시세, 52주 신고/신저가, 손익계산서 요약 | `yfinance` |
| **3** | `opendart-disclosure` | **대한민국 기업 전자공시(DART)**: 금감원 DART 공시 검색, 사업보고서/분기보고서 주요 사항 조회 | `OpenDART API`, `dart-fss` |
| **4** | `sec-edgar-financials` | **미국 SEC 기업 공시(EDGAR)**: 미국 상장사 연차보고서(`10-K`), 분기보고서(`10-Q`) 전문 파싱 | `edgartools` |
| **5** | `fred-macro-economics` | **미국 연준(FRED) 거시경제 지표**: 기준금리(Fed Funds Rate), 10년-2년 장단기 금리차(T10Y2Y), CPI, 실업률 | `fredapi`, `pandas_datareader` |
| **6** | `portfolio-risk-quant` | **퀀트 자산배분 & 포트폴리오 리스크**: 샤프 지수(Sharpe Ratio), 최대 낙폭(MDD), VaR, 변동성 계산 | `numpy`, `scipy.optimize` |
| **7** | `technical-analysis-indicators` | **기술적 분석 & 차트 지표**: RSI, MACD, 볼린저 밴드, 이동평균선(SMA/EMA), 골든크로스 감지 | `ta`, `pandas-ta` |
| **8** | `financial-news-sentiment` | **금융 뉴스 & 시장 감성 분석**: 금융 언론사 헤드라인 RSS 수집, 긍정/부정 센티먼트 점수화 | `feedparser`, `beautifulsoup4` |
| **9** | `crypto-market-coingecko` | **디지털 자산 & 가상화폐 시황**: 비트코인(BTC), 이더리움(ETH) 실시간 시세, 시가총액 점유율 | `CoinGecko API`, `requests` |
| **10** | `alpha-vantage-finance` | **외환(FX) & 글로벌 거시 데이터**: 주요 통화쌍(USD/KRW 등) 실시간 환율 및 글로벌 지표 | `Alpha Vantage API` |
| **11** | `analyst` | **인터랙티브 HTML 대시보드 시각화**: Chart.js 차트와 KPI 카드가 포함된 미려한 standalone 대시보드 템플릿 | `Chart.js`, `CSS Grid` |
| **12** | `mcp` | **FastMCP 도구 서버 연계**: Model Context Protocol 표준 기반의 외부 도구 연계 가이드 | `fastmcp` |
| **13** | `pdf_processing` | **금융 리포트 & PDF 처리**: 증권사 리서치 리포트의 텍스트 및 테이블 구조화 추출 | `pdfplumber`, `pypdf` |

---

## 🛠️ 단계별 수행 가이드

### 1단계: 스킬 저장소(`artifacts/skills_pool/`)에서 금융 스킬 복사하기

Codespaces 터미널(또는 bash 쉘)에서 아래 명령어를 실행하여 보관된 10종의 금융 스킬을 `skills/` 폴더로 복사합니다:

```bash
cp -r artifacts/skills_pool/* skills/
```

복사 후 `skills/` 폴더의 내용을 확인합니다:
```bash
ls skills/
```
*(출력에 `pykrx-korean-market`, `yfinance-market-data`, `fred-macro-economics` 등 총 13종 폴더가 보이면 성공입니다.)*

---

### 2단계: 프롬프트 조립기의 자동 스캔 원리 이해하기

우리가 Mission 03에서 구축한 5계층 프롬프트 조립기([`app/middleware/prompt/prompt_assembler.py`](file:///c:/Users/hyoun/Desktop/working_project/harness_lecture/instructor/agent_lab/app/middleware/prompt/prompt_assembler.py))는 에이전트 초기화 시 `SkillPromptBuilder`를 호출합니다.

`SkillPromptBuilder`는 `skills/` 폴더 내 모든 하위 폴더의 `SKILL.md`를 스캔하여 **상단의 YAML Frontmatter(`name`, `description`)만 추출**한 뒤 다음과 같이 **Layer 2.2**에 동적으로 카탈로그를 조립합니다:

```markdown
=== Layer 2: Capabilities (Tools & Skills) ===

## 🛠️ Layer 2.1: Registered Tool Capabilities (Alphabetical)
[1] `bash_command`: Execute shell commands
[2] `file_read`: Read files
...

## 📦 Layer 2.2: Available Skills Catalog & Execution Policy
### 📦 Available Skills Catalog (Indexed from Frontmatter)
<skills>
- **pykrx-korean-market** (`skills/pykrx-korean-market/SKILL.md`):
    국내 주식 및 시장 시세: KOSPI/KOSDAQ 종목 시세, 시가총액 순위, 외국인/기관 수급 동향...
- **yfinance-market-data** (`skills/yfinance-market-data/SKILL.md`):
    Comprehensive Yahoo Finance toolset for global stock quotes...
- **analyst** (`skills/analyst/SKILL.md`):
    Comprehensive data analysis, statistical profiling, interactive HTML dashboard...
...
</skills>

__SYSTEM_PROMPT_DYNAMIC_BOUNDARY__
```

> 💡 **핵심 포인트**:  
> 수천 줄에 달하는 스킬 코드 전체를 프롬프트에 넣지 않고, **이름과 1줄 설명만 카탈로그로 유지(1단계)**하므로 GPU KV-Cache를 완벽히 보존하고 토큰 비용을 90% 이상 절감합니다!

---

### 3단계: 자동화 검증 스크립트 실행

스킬 복사와 프롬프트 조립기 연동이 정상인지 터미널에서 검증합니다:

```bash
python tests/test_mission04.py
```

#### ✅ 기대 성공 출력:
```text
======================================================================
🧪 [Mission 04] Progressive Skills 동적 확장 & 카탈로그 검증 시작
======================================================================
  ✅ Test 1 통과: skills/ 내 금융 전문 스킬 및 SKILL.md 확인 (현재 탑재: 총 13종)
  ✅ Test 2 통과: SkillPromptBuilder Frontmatter 스캔 및 카탈로그 생성 완료
  ✅ Test 3 통과: Progressive Skill 실행 필수 도구 바인딩 확인 (file_read, bash_command)

======================================================================
🎨 [실물 시각화] main_agent 시스템 프롬프트(Layer 2.2)에 자동 주입된 스킬 카탈로그
======================================================================
... (13종 스킬 카탈로그 목록 출력) ...
======================================================================

🎉 [Mission 04] Progressive Skills 동적 확장 & 카탈로그 검증 100% 통과!
```

---

### 4단계: FastAPI 서버 & Chainlit 웹 UI 실행

터미널 2개를 열어 각각 백엔드와 프론트엔드를 실행합니다:

#### 🖥️ 터미널 1 (FastAPI 백엔드 서버 가동):
```bash
python app/server.py --port 8000
```

#### 🌐 터미널 2 (Chainlit 웹 UI 가동):
```bash
chainlit run app/chainlit_ui.py --port 8080
```

웹 브라우저에서 `http://localhost:8080`에 접속하고 좌측 상단 에이전트 선택창에서 **`main_agent`**를 선택합니다.

---

## 🧪 5단계: 실무 금융 시나리오 5종 테스트

Chainlit 웹 UI에서 `main_agent`에게 아래 질문들을 던지며, 에이전트가 어떻게 자율적으로 스킬을 발견하고 실행하는지 관찰합니다!

---

### 📊 시나리오 1. 국내 주식 시세 및 시가총액 비교 (`pykrx-korean-market`)

* **입력 프롬프트**:
  ```text
  삼성전자(005930)와 SK하이닉스(000660)의 최근 1개월 종가 추이와 시가총액을 비교 분석해줘.
  ```
* **동작 관찰 포인트**:
  1. 에이전트가 Layer 2.2에서 `pykrx-korean-market` 스킬을 스스로 탐색합니다.
  2. `file_read`로 `skills/pykrx-korean-market/SKILL.md`를 열람하여 실행 코드를 파악합니다.
  3. `bash_command`로 Python 스크립트를 실행하여 실시간 종가 추이 및 시가총액 데이터를 획득합니다.
  4. 양사의 시가총액과 최근 등락률을 한국어로 깔끔하게 정리해 브리핑합니다.

---

### 🎨 시나리오 2. 인터랙티브 HTML 대시보드 시각화 생성 (`analyst` 스킬 연계)

* **입력 프롬프트** (시나리오 1 분석 직후 입력):
  ```text
  방금 분석한 삼성전자와 SK하이닉스 데이터를 바탕으로 멋진 인터랙티브 HTML 대시보드를 생성해줘.
  ```
* **동작 관찰 포인트 (✨ 킬러 기능)**:
  1. 에이전트가 `skills/analyst/` 스킬 가이드를 참조하여 Chart.js 라인 차트와 KPI 요약 카드가 포함된 standalone HTML 대시보드 파일(`artifacts/dashboard.html`)을 생성합니다.
  2. 최종 답변에 `<Render_HTML>artifacts/dashboard.html</Render_HTML>` 태그를 출력합니다.
  3. **Chainlit 채팅창 내에 미려한 인라인 대시보드 카드**가 렌더링되며, 헤더 클릭(접기/펼치기) 및 **`↗ 새 탭 전체화면` 열기**가 정상 작동하는지 확인합니다!

---

### 🌐 시나리오 3. 글로벌 빅테크 밸류에이션 지표 분석 (`yfinance-market-data`)

* **입력 프롬프트**:
  ```text
  엔비디아(NVDA)와 애플(AAPL)의 현재 주가, PER, PBR, 52주 최고가 대비 하락률을 표로 비교 정리해줘.
  ```
* **동작 관찰 포인트**:
  - `skills/yfinance-market-data/SKILL.md`를 열람하고 `yfinance` 명령어를 실행하여 최신 미국 빅테크 재무 지표를 표(Markdown Table)로 도출합니다.

---

### 🏛️ 시나리오 4. 거시경제 지표 및 금리 역전 현상 분석 (`fred-macro-economics`)

* **입력 프롬프트**:
  ```text
  미국 FRED 최신 기준금리(Fed Funds Rate)와 10년물-2년물 국채 장단기 금리차(T10Y2Y) 추이를 확인하고, 현재 경기 국면에 대해 간단히 해설해줘.
  ```
* **동작 관찰 포인트**:
  - 연준(FRED) 데이터 스킬을 활용하여 수익률 곡선(Yield Curve) 역전 여부를 확인하고 전문적인 거시경제 해설을 제공합니다.

---

### 📈 시나리오 5. 퀀트 포트폴리오 리스크 & 샤프 지수 계산 (`portfolio-risk-quant`)

* **입력 프롬프트**:
  ```text
  AAPL, MSFT, GOOGL로 구성된 동일 가중(1/3씩) 포트폴리오의 최근 1년 연환산 변동성(Volatility), 샤프 지수(Sharpe Ratio), 최대 낙폭(MDD)을 계산해줘.
  ```
* **동작 관찰 포인트**:
  - `skills/portfolio-risk-quant/SKILL.md`의 현대 포트폴리오 이론(MPT) 코드를 실행하여 정확한 수치 계산 결과를 도출합니다.

---

## 🏆 Mission 04 완료 체크리스트

- [ ] 도구(Tool)와 스킬(Skill)의 차이점 및 Progressive Disclosure 원리를 이해했다.
- [ ] `artifacts/skills_pool/`의 금융 스킬들을 `skills/` 디렉토리로 성공적으로 복사했다.
- [ ] `PromptAssembler`가 코드 수정 없이 `skills/`의 Frontmatter를 스캔하여 Layer 2.2에 카탈로그를 자동 주입함을 확인했다.
- [ ] `main_agent`가 `file_read`와 `bash_command`를 통해 스킬 코드를 자율적으로 읽고 실행함을 확인했다.
- [ ] `python tests/test_mission04.py`를 실행하여 3개 검증 테스트를 100% 통과했다.
- [ ] Chainlit UI에서 국내/해외 주식, 거시경제 분석 및 Chart.js 인터랙티브 대시보드 인라인 렌더링을 확인했다.
