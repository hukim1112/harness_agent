import json

with open('artifacts/data/naver_life_culture_news.json', 'r', encoding='utf-8') as f:
    raw_articles = json.load(f)

# Structured article metadata
articles_data = [
    {
        "id": 1,
        "title": raw_articles[0]["title"],
        "press": raw_articles[0]["press"],
        "category": "생활",
        "topic": "기상/기후",
        "topic_color": "bg-sky-100 text-sky-800 border-sky-200",
        "published_at": raw_articles[0]["published_at"],
        "char_count": len(raw_articles[0]["content"]),
        "word_count": len(raw_articles[0]["content"].split()),
        "summary": "낮 기온이 30도를 웃도는 찜통더위가 이어지는 가운데 전국 곳곳에 5~60mm의 비와 돌풍·천둥번개를 동반한 국지성 소나기가 예보되었습니다.",
        "takeaways": [
            "전국적 30도 이상 찜통더위 및 높은 습도 유지",
            "전남·경남 10~60mm, 수도권·강원 5~30mm 소나기 예상",
            "대기 불안정으로 인한 돌풍 및 천둥번개 주의"
        ],
        "keywords": ["무더위", "소나기", "기온", "강수량", "돌풍"],
        "content": raw_articles[0]["content"],
        "url": raw_articles[0]["url"]
    },
    {
        "id": 2,
        "title": raw_articles[1]["title"],
        "press": raw_articles[1]["press"],
        "category": "생활",
        "topic": "공연/무용",
        "topic_color": "bg-purple-100 text-purple-800 border-purple-200",
        "published_at": raw_articles[1]["published_at"],
        "char_count": len(raw_articles[1]["content"]),
        "word_count": len(raw_articles[1]["content"].split()),
        "summary": "케이글로벌발레원이 서울 용산에서 기자회견을 열고 세계 정상급 발레단 예술감독 및 무용수들과 함께 '2026 서울 글로벌 발레 포럼'의 비전을 공개했습니다.",
        "takeaways": [
            "마린스키·ABT·보스턴 등 글로벌 최고 명문 발레단 대거 참가",
            "글로벌 무용수(전민철, 김석주, 박선미 등) 및 예술감독 회동",
            "한국 발레의 글로벌 네트워크 강화 및 교류의 장 마련"
        ],
        "keywords": ["발레", "글로벌포럼", "예술감독", "마린스키", "솔리스트"],
        "content": raw_articles[1]["content"],
        "url": raw_articles[1]["url"]
    },
    {
        "id": 3,
        "title": raw_articles[2]["title"],
        "press": raw_articles[2]["press"],
        "category": "생활",
        "topic": "관광/여행",
        "topic_color": "bg-emerald-100 text-emerald-800 border-emerald-200",
        "published_at": raw_articles[2]["published_at"],
        "char_count": len(raw_articles[2]["content"]),
        "word_count": len(raw_articles[2]["content"].split()),
        "summary": "문체부와 한국관광공사가 인구감소 지역 9곳을 신규 선정하여 가을철 여행경비의 최대 50%(10~14만원)를 지역상품권으로 환급하는 반값 여행 사업을 확대합니다.",
        "takeaways": [
            "강원 화천, 충남 태안 등 하반기 신규 9개 지자체 참여",
            "상반기 예산 52억 투입 대비 162억 소비 창출 (3.1배 경제효과)",
            "이용자의 81.2%가 사업을 계기로 신규 또는 행선지 변경 여행 진행"
        ],
        "keywords": ["반값여행", "휴가지원", "환급", "한국관광공사", "소비창출"],
        "content": raw_articles[2]["content"],
        "url": raw_articles[2]["url"]
    },
    {
        "id": 4,
        "title": raw_articles[3]["title"],
        "press": raw_articles[3]["press"],
        "category": "경제",
        "topic": "자동차/라이프",
        "topic_color": "bg-blue-100 text-blue-800 border-blue-200",
        "published_at": raw_articles[3]["published_at"],
        "char_count": len(raw_articles[3]["content"]),
        "word_count": len(raw_articles[3]["content"].split()),
        "summary": "기아가 대표 레저용 차량(RV) 3종인 스포티지·쏘렌토·카니발에 전용 다크 디자인을 가미한 '블랙 에디션'과 핵심 편의사양을 기본 탑재한 연식변경 모델을 선보였습니다.",
        "takeaways": [
            "최상위 시그니처 트림 기반 블랙 인테리어 및 다크 메탈 외장 적용",
            "스포티지 12.3인치 내비 및 고속도로 주행 보조 기본 탑재",
            "카니발 전 트림 LED 리어램프 및 전좌석 100W C타입 USB 기본화"
        ],
        "keywords": ["기아", "블랙에디션", "스포티지", "쏘렌토", "카니발"],
        "content": raw_articles[3]["content"],
        "url": raw_articles[3]["url"]
    },
    {
        "id": 5,
        "title": raw_articles[4]["title"],
        "press": raw_articles[4]["press"],
        "category": "생활",
        "topic": "미술/문화계",
        "topic_color": "bg-amber-100 text-amber-800 border-amber-200",
        "published_at": raw_articles[4]["published_at"],
        "char_count": len(raw_articles[4]["content"]),
        "word_count": len(raw_articles[4]["content"].split()),
        "summary": "노란 호박과 물방울(Polka Dot) 무늬로 전 세계 미술계에 거대한 발자취를 남긴 일본 아방가르드 현대미술의 거장 쿠사마 야요이가 향년 97세로 별세했습니다.",
        "takeaways": [
            "도쿄 병원에서 97세 일기로 영면, 마지막 순간까지 창작 몰두",
            "1929년생으로 물방울 무늬·호박 연작 등 독보적 예술세계 구축",
            "베니스 비엔날레 대표 참가 및 프랑스 예술문화훈장 등 수훈"
        ],
        "keywords": ["쿠사마야요이", "호박", "현대미술", "아방가르드", "별세"],
        "content": raw_articles[4]["content"],
        "url": raw_articles[4]["url"]
    }
]

articles_json = json.dumps(articles_data, ensure_ascii=False)

html_content = f"""<!DOCTYPE html>
<html lang="ko">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>네이버 생활/문화 뉴스 심층 분석 대시보드</title>
    <!-- Tailwind CSS CDN -->
    <script src="https://cdn.tailwindcss.com"></script>
    <!-- Pretendard Font -->
    <link rel="stylesheet" as="style" crossorigin href="https://cdn.jsdelivr.net/gh/orioncactus/pretendard@v1.3.9/dist/web/static/pretendard.min.css" />
    <!-- Chart.js 4.4.1 -->
    <script src="https://cdn.jsdelivr.net/npm/chart.js"></script>
    <!-- Font Awesome -->
    <link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.4.0/css/all.min.css">

    <style>
        body {{
            font-family: "Pretendard Variable", Pretendard, -apple-system, BlinkMacSystemFont, system-ui, Roboto, sans-serif;
            background-color: #0F172A;
            color: #E2E8F0;
        }}
        .glass-card {{
            background: rgba(30, 41, 59, 0.7);
            backdrop-filter: blur(12px);
            border: 1px solid rgba(255, 255, 255, 0.08);
        }}
        .glass-card-hover {{
            transition: all 0.25s ease-in-out;
        }}
        .glass-card-hover:hover {{
            transform: translateY(-4px);
            border-color: rgba(99, 102, 241, 0.4);
            box-shadow: 0 12px 24px -10px rgba(99, 102, 241, 0.2);
        }}
        .gradient-text {{
            background: linear-gradient(135deg, #38BDF8 0%, #818CF8 50%, #C084FC 100%);
            -webkit-background-clip: text;
            -webkit-text-fill-color: transparent;
        }}
        .custom-scrollbar::-webkit-scrollbar {{
            width: 6px;
            height: 6px;
        }}
        .custom-scrollbar::-webkit-scrollbar-track {{
            background: rgba(15, 23, 42, 0.6);
        }}
        .custom-scrollbar::-webkit-scrollbar-thumb {{
            background: rgba(100, 116, 139, 0.5);
            border-radius: 3px;
        }}
        .custom-scrollbar::-webkit-scrollbar-thumb:hover {{
            background: rgba(148, 163, 184, 0.8);
        }}
    </style>
</head>
<body class="min-h-screen pb-16">

    <!-- Top Navigation Header -->
    <header class="sticky top-0 z-50 glass-card border-b border-slate-700/60 shadow-lg">
        <div class="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-4 flex flex-col md:flex-row items-center justify-between gap-4">
            <div class="flex items-center space-x-3">
                <div class="w-10 h-10 rounded-xl bg-gradient-to-tr from-indigo-500 to-cyan-400 flex items-center justify-center shadow-md">
                    <i class="fa-solid fa-newspaper text-white text-lg"></i>
                </div>
                <div>
                    <div class="flex items-center space-x-2">
                        <h1 class="text-xl font-bold text-white tracking-tight">생활/문화 뉴스 분석 대시보드</h1>
                        <span class="px-2.5 py-0.5 rounded-full text-xs font-semibold bg-indigo-500/20 text-indigo-300 border border-indigo-500/30">
                            LIVE
                        </span>
                    </div>
                    <p class="text-xs text-slate-400">Naver Life & Culture News Comprehensive Intelligence Report</p>
                </div>
            </div>

            <div class="flex items-center space-x-3">
                <div class="flex items-center text-xs text-slate-300 bg-slate-800/80 px-3 py-1.5 rounded-lg border border-slate-700">
                    <i class="fa-regular fa-clock mr-2 text-indigo-400"></i>
                    기준 시점: <span class="font-semibold text-white ml-1">2026-08-27</span>
                </div>
                <a href="culture_news_analysis.xlsx" download class="inline-flex items-center text-xs font-medium bg-emerald-600 hover:bg-emerald-500 text-white px-3.5 py-2 rounded-lg transition shadow-sm">
                    <i class="fa-solid fa-file-excel mr-1.5"></i> Excel 보고서 다운로드
                </a>
            </div>
        </div>
    </header>

    <!-- Main Container -->
    <main class="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 pt-8 space-y-8">

        <!-- Executive Summary Banner -->
        <div class="glass-card rounded-2xl p-6 relative overflow-hidden border border-indigo-500/20">
            <div class="absolute -right-10 -bottom-10 w-60 h-60 bg-indigo-500/10 rounded-full blur-3xl pointer-events-none"></div>
            <div class="flex flex-col lg:flex-row lg:items-center justify-between gap-6 relative z-10">
                <div class="space-y-2 max-w-3xl">
                    <div class="inline-flex items-center space-x-2 px-2.5 py-1 rounded-md bg-indigo-500/20 text-indigo-300 text-xs font-medium">
                        <i class="fa-solid fa-sparkles text-cyan-400 mr-1"></i> 데이터 분석 인사이트 요약
                    </div>
                    <h2 class="text-2xl font-extrabold text-white">
                        문화예술계 거장 타계와 정책·레저 모빌리티 중심의 라이프 트렌드
                    </h2>
                    <p class="text-sm text-slate-300 leading-relaxed">
                        본 보고서는 2026년 8월 27일 수집된 네이버 생활/문화 섹션 주요 5개 기사를 심층 분석한 결과입니다. 
                        세계적 미술 거장 <span class="text-amber-300 font-medium">쿠사마 야요이 별세</span>와 <span class="text-purple-300 font-medium">서울 글로벌 발레 포럼</span> 등 문화예술계 굵직한 이슈와 더불어, 
                        국민 체감형 <span class="text-emerald-300 font-medium">가을 반값 여행 휴가지원 확대</span>, <span class="text-blue-300 font-medium">기아 RV 3종 블랙 에디션</span> 출시 등 생활·소비 트렌드가 고르게 분포되어 있습니다.
                    </p>
                </div>
                <div class="flex sm:flex-col gap-2 shrink-0">
                    <div class="px-4 py-3 bg-slate-800/90 rounded-xl border border-slate-700/80 text-center">
                        <div class="text-xs text-slate-400">데이터 수집률</div>
                        <div class="text-xl font-bold text-emerald-400 mt-0.5">100.0%</div>
                    </div>
                    <div class="px-4 py-3 bg-slate-800/90 rounded-xl border border-slate-700/80 text-center">
                        <div class="text-xs text-slate-400">총 텍스트 분량</div>
                        <div class="text-xl font-bold text-cyan-400 mt-0.5">3,738자</div>
                    </div>
                </div>
            </div>
        </div>

        <!-- 5 KPI Cards -->
        <section class="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-5 gap-4">
            <!-- Card 1 -->
            <div class="glass-card rounded-xl p-5 border-l-4 border-l-indigo-500 flex flex-col justify-between">
                <div class="flex items-center justify-between">
                    <span class="text-xs font-medium text-slate-400">총 수집 기사 수</span>
                    <div class="w-8 h-8 rounded-lg bg-indigo-500/20 text-indigo-400 flex items-center justify-center">
                        <i class="fa-solid fa-newspaper text-sm"></i>
                    </div>
                </div>
                <div class="mt-4">
                    <div class="text-3xl font-extrabold text-white">5 <span class="text-base font-medium text-slate-400">건</span></div>
                    <p class="text-xs text-slate-400 mt-1">주요 언론사 실시간 헤드라인</p>
                </div>
            </div>

            <!-- Card 2 -->
            <div class="glass-card rounded-xl p-5 border-l-4 border-l-cyan-500 flex flex-col justify-between">
                <div class="flex items-center justify-between">
                    <span class="text-xs font-medium text-slate-400">평균 글자 수</span>
                    <div class="w-8 h-8 rounded-lg bg-cyan-500/20 text-cyan-400 flex items-center justify-center">
                        <i class="fa-solid fa-text-height text-sm"></i>
                    </div>
                </div>
                <div class="mt-4">
                    <div class="text-3xl font-extrabold text-white">747.6 <span class="text-base font-medium text-slate-400">자</span></div>
                    <p class="text-xs text-slate-400 mt-1">범위: 326자 ~ 1,240자</p>
                </div>
            </div>

            <!-- Card 3 -->
            <div class="glass-card rounded-xl p-5 border-l-4 border-l-emerald-500 flex flex-col justify-between">
                <div class="flex items-center justify-between">
                    <span class="text-xs font-medium text-slate-400">평균 단어(어절) 수</span>
                    <div class="w-8 h-8 rounded-lg bg-emerald-500/20 text-emerald-400 flex items-center justify-center">
                        <i class="fa-solid fa-align-left text-sm"></i>
                    </div>
                </div>
                <div class="mt-4">
                    <div class="text-3xl font-extrabold text-white">156.6 <span class="text-base font-medium text-slate-400">단어</span></div>
                    <p class="text-xs text-slate-400 mt-1">기사당 평균 심층도 양호</p>
                </div>
            </div>

            <!-- Card 4 -->
            <div class="glass-card rounded-xl p-5 border-l-4 border-l-amber-500 flex flex-col justify-between">
                <div class="flex items-center justify-between">
                    <span class="text-xs font-medium text-slate-400">주요 섹션 비중</span>
                    <div class="w-8 h-8 rounded-lg bg-amber-500/20 text-amber-400 flex items-center justify-center">
                        <i class="fa-solid fa-layer-group text-sm"></i>
                    </div>
                </div>
                <div class="mt-4">
                    <div class="text-3xl font-extrabold text-white">생활 80%</div>
                    <p class="text-xs text-slate-400 mt-1">생활(4건) / 경제(1건)</p>
                </div>
            </div>

            <!-- Card 5 -->
            <div class="glass-card rounded-xl p-5 border-l-4 border-l-pink-500 flex flex-col justify-between">
                <div class="flex items-center justify-between">
                    <span class="text-xs font-medium text-slate-400">분석 언론사 수</span>
                    <div class="w-8 h-8 rounded-lg bg-pink-500/20 text-pink-400 flex items-center justify-center">
                        <i class="fa-solid fa-building-columns text-sm"></i>
                    </div>
                </div>
                <div class="mt-4">
                    <div class="text-3xl font-extrabold text-white">3 <span class="text-base font-medium text-slate-400">개 언론사</span></div>
                    <p class="text-xs text-slate-400 mt-1">뉴시스, 헤럴드경제, MBC</p>
                </div>
            </div>
        </section>

        <!-- Charts Grid (2x2) -->
        <section class="grid grid-cols-1 lg:grid-cols-2 gap-6">
            
            <!-- Chart 1: Top 10 Keywords -->
            <div class="glass-card rounded-2xl p-6">
                <div class="flex items-center justify-between mb-4">
                    <div>
                        <h3 class="text-base font-bold text-white flex items-center">
                            <i class="fa-solid fa-fire text-amber-400 mr-2"></i> 핵심 키워드 빈도 TOP 10
                        </h3>
                        <p class="text-xs text-slate-400">기사 본문 및 제목 내 주요 단어 등장 횟수</p>
                    </div>
                    <span class="text-xs px-2.5 py-1 rounded bg-slate-800 text-slate-300 border border-slate-700">빈도수 기준</span>
                </div>
                <div class="h-64 relative">
                    <canvas id="keywordChart"></canvas>
                </div>
            </div>

            <!-- Chart 2: Article Length Comparison -->
            <div class="glass-card rounded-2xl p-6">
                <div class="flex items-center justify-between mb-4">
                    <div>
                        <h3 class="text-base font-bold text-white flex items-center">
                            <i class="fa-solid fa-chart-column text-indigo-400 mr-2"></i> 기사별 분량 비교 (글자수 / 단어수)
                        </h3>
                        <p class="text-xs text-slate-400">기사별 텍스트 심층도 및 길이 비교</p>
                    </div>
                    <span class="text-xs px-2.5 py-1 rounded bg-slate-800 text-slate-300 border border-slate-700">단위: 자 / 개</span>
                </div>
                <div class="h-64 relative">
                    <canvas id="articleLengthChart"></canvas>
                </div>
            </div>

            <!-- Chart 3: Press Distribution Doughnut -->
            <div class="glass-card rounded-2xl p-6">
                <div class="flex items-center justify-between mb-4">
                    <div>
                        <h3 class="text-base font-bold text-white flex items-center">
                            <i class="fa-solid fa-chart-pie text-cyan-400 mr-2"></i> 언론사별 기사 점유율
                        </h3>
                        <p class="text-xs text-slate-400">수집된 기사의 발행 언론사 비중</p>
                    </div>
                    <span class="text-xs px-2.5 py-1 rounded bg-slate-800 text-slate-300 border border-slate-700">점유율 (%)</span>
                </div>
                <div class="h-64 relative flex items-center justify-center">
                    <canvas id="pressChart"></canvas>
                </div>
            </div>

            <!-- Chart 4: Topic & Category Breakdown -->
            <div class="glass-card rounded-2xl p-6">
                <div class="flex items-center justify-between mb-4">
                    <div>
                        <h3 class="text-base font-bold text-white flex items-center">
                            <i class="fa-solid fa-tags text-purple-400 mr-2"></i> 세부 주제(토픽) 분포
                        </h3>
                        <p class="text-xs text-slate-400">기사 내용 기반 5대 세부 주제 분류</p>
                    </div>
                    <span class="text-xs px-2.5 py-1 rounded bg-slate-800 text-slate-300 border border-slate-700">주제별 1건</span>
                </div>
                <div class="h-64 relative flex items-center justify-center">
                    <canvas id="topicChart"></canvas>
                </div>
            </div>

        </section>

        <!-- Topic Insights & In-depth Analysis Section -->
        <section class="glass-card rounded-2xl p-6">
            <h3 class="text-lg font-bold text-white flex items-center mb-4">
                <i class="fa-solid fa-lightbulb text-amber-300 mr-2.5"></i> 생활/문화 주요 테마별 심층 분석
            </h3>
            <div class="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
                
                <div class="bg-slate-800/60 rounded-xl p-4 border border-slate-700/60 flex flex-col justify-between">
                    <div>
                        <div class="flex items-center justify-between mb-2">
                            <span class="text-xs font-bold px-2 py-0.5 rounded bg-amber-500/20 text-amber-300 border border-amber-500/30">미술 / 문화계</span>
                            <span class="text-xs text-slate-400">헤럴드경제</span>
                        </div>
                        <h4 class="font-bold text-white text-sm">쿠사마 야요이 작가 별세 (향년 97세)</h4>
                        <p class="text-xs text-slate-300 mt-2 leading-relaxed">
                            물방울(Dot) 패턴과 '호박' 작품으로 세계적 사랑을 받은 일본 아방가르드 대표 작가의 타계로 글로벌 미술계의 추모 분위기 확산.
                        </p>
                    </div>
                    <div class="mt-3 pt-3 border-t border-slate-700 text-xs text-slate-400">
                        영향: 현대미술 시장 내 아카이브 및 특별전 주목
                    </div>
                </div>

                <div class="bg-slate-800/60 rounded-xl p-4 border border-slate-700/60 flex flex-col justify-between">
                    <div>
                        <div class="flex items-center justify-between mb-2">
                            <span class="text-xs font-bold px-2 py-0.5 rounded bg-emerald-500/20 text-emerald-300 border border-emerald-500/30">여행 / 정책</span>
                            <span class="text-xs text-slate-400">헤럴드경제</span>
                        </div>
                        <h4 class="font-bold text-white text-sm">가을 반값 여행 지원지 9곳 신규 확대</h4>
                        <p class="text-xs text-slate-300 mt-2 leading-relaxed">
                            문체부·관광공사 지원으로 최대 14만원 환급. 상반기 투입 예산 대비 3.1배(162억원) 소비 창출로 인구감소 지역 경제 활성화 견인.
                        </p>
                    </div>
                    <div class="mt-3 pt-3 border-t border-slate-700 text-xs text-slate-400">
                        효과: 응답자 81.2%가 지원 통해 여행 계획 확정
                    </div>
                </div>

                <div class="bg-slate-800/60 rounded-xl p-4 border border-slate-700/60 flex flex-col justify-between">
                    <div>
                        <div class="flex items-center justify-between mb-2">
                            <span class="text-xs font-bold px-2 py-0.5 rounded bg-purple-500/20 text-purple-300 border border-purple-500/30">공연 / 예술</span>
                            <span class="text-xs text-slate-400">뉴시스</span>
                        </div>
                        <h4 class="font-bold text-white text-sm">2026 서울 글로벌 발레 포럼 개최</h4>
                        <p class="text-xs text-slate-300 mt-2 leading-relaxed">
                            마린스키, 아메리칸 발레시어터, 보스턴발레단 등 최정상 예술감독진 및 한국인 주역 무용수들이 서울에 집결해 글로벌 미래 논의.
                        </p>
                    </div>
                    <div class="mt-3 pt-3 border-t border-slate-700 text-xs text-slate-400">
                        전망: K-발레의 세계적 위상 제고 및 교육 교류 강화
                    </div>
                </div>

                <div class="bg-slate-800/60 rounded-xl p-4 border border-slate-700/60 flex flex-col justify-between">
                    <div>
                        <div class="flex items-center justify-between mb-2">
                            <span class="text-xs font-bold px-2 py-0.5 rounded bg-blue-500/20 text-blue-300 border border-blue-500/30">자동차 / 라이프</span>
                            <span class="text-xs text-slate-400">뉴시스</span>
                        </div>
                        <h4 class="font-bold text-white text-sm">기아 RV 3종 블랙 에디션 동시 출시</h4>
                        <p class="text-xs text-slate-300 mt-2 leading-relaxed">
                            스포티지·쏘렌토·카니발 등 대표 패밀리/레저 차량의 내외관 다크 테마 적용 및 첨단 주행 보조·100W 고속충전 단자 기본화.
                        </p>
                    </div>
                    <div class="mt-3 pt-3 border-t border-slate-700 text-xs text-slate-400">
                        전략: 패밀리 레저 시장 내 상품 경쟁력 강화
                    </div>
                </div>

            </div>
        </section>

        <!-- Interactive Article List Section -->
        <section class="space-y-4">
            <div class="flex flex-col md:flex-row md:items-center justify-between gap-4">
                <div>
                    <h3 class="text-xl font-bold text-white flex items-center">
                        <i class="fa-solid fa-list-check text-indigo-400 mr-2.5"></i> 수집 기사 상세 목록 및 핵심 요약
                    </h3>
                    <p class="text-xs text-slate-400">기사별 2줄 AI 핵심 요약 및 본문 전문 열람 인터페이스</p>
                </div>

                <!-- Search & Filters -->
                <div class="flex flex-wrap items-center gap-2">
                    <div class="relative">
                        <i class="fa-solid fa-magnifying-glass absolute left-3 top-1/2 -translate-y-1/2 text-slate-400 text-xs"></i>
                        <input id="searchInput" type="text" placeholder="키워드/제목 검색..." 
                               class="bg-slate-800 text-xs text-white pl-8 pr-3 py-2 rounded-lg border border-slate-700 focus:outline-none focus:border-indigo-500 w-44">
                    </div>
                    <select id="pressFilter" class="bg-slate-800 text-xs text-white px-3 py-2 rounded-lg border border-slate-700 focus:outline-none focus:border-indigo-500">
                        <option value="ALL">언론사 전체</option>
                        <option value="뉴시스">뉴시스 (2)</option>
                        <option value="헤럴드경제">헤럴드경제 (2)</option>
                        <option value="MBC">MBC (1)</option>
                    </select>
                    <select id="categoryFilter" class="bg-slate-800 text-xs text-white px-3 py-2 rounded-lg border border-slate-700 focus:outline-none focus:border-indigo-500">
                        <option value="ALL">카테고리 전체</option>
                        <option value="생활">생활 (4)</option>
                        <option value="경제">경제 (1)</option>
                    </select>
                </div>
            </div>

            <!-- Cards Container -->
            <div id="articlesContainer" class="grid grid-cols-1 gap-4">
                <!-- Articles dynamically inserted by JS -->
            </div>
        </section>

    </main>

    <!-- Modal for Full Content View -->
    <div id="articleModal" class="fixed inset-0 z-50 hidden bg-black/75 backdrop-blur-sm flex items-center justify-center p-4">
        <div class="glass-card max-w-3xl w-full max-h-[85vh] rounded-2xl p-6 flex flex-col shadow-2xl border border-slate-700 overflow-hidden">
            <div class="flex items-start justify-between pb-4 border-b border-slate-700">
                <div class="pr-6">
                    <div class="flex items-center space-x-2 mb-2">
                        <span id="modalPress" class="text-xs font-bold px-2 py-0.5 rounded bg-indigo-500/20 text-indigo-300"></span>
                        <span id="modalCategory" class="text-xs font-bold px-2 py-0.5 rounded bg-slate-700 text-slate-300"></span>
                        <span id="modalDate" class="text-xs text-slate-400"></span>
                    </div>
                    <h3 id="modalTitle" class="text-lg font-bold text-white"></h3>
                </div>
                <button onclick="closeModal()" class="text-slate-400 hover:text-white p-2 rounded-lg hover:bg-slate-800">
                    <i class="fa-solid fa-xmark text-lg"></i>
                </button>
            </div>
            <div id="modalContent" class="py-4 text-sm text-slate-300 leading-relaxed overflow-y-auto custom-scrollbar whitespace-pre-line">
            </div>
            <div class="pt-4 border-t border-slate-700 flex items-center justify-between">
                <div class="text-xs text-slate-400" id="modalMeta"></div>
                <div class="flex items-center space-x-2">
                    <a id="modalUrl" href="#" target="_blank" class="inline-flex items-center text-xs bg-indigo-600 hover:bg-indigo-500 text-white px-4 py-2 rounded-lg font-medium">
                        <i class="fa-solid fa-arrow-up-right-from-square mr-1.5"></i> 네이버 뉴스 원문 보기
                    </a>
                    <button onclick="closeModal()" class="text-xs bg-slate-800 hover:bg-slate-700 text-slate-300 px-4 py-2 rounded-lg">
                        닫기
                    </button>
                </div>
            </div>
        </div>
    </div>

    <!-- Footer -->
    <footer class="mt-16 border-t border-slate-800 py-6 text-center text-xs text-slate-500">
        <p>© 2026 The Analyst Intelligence Platform. Data source: Naver News Scraped Data.</p>
    </footer>

    <!-- JavaScript Application Logic -->
    <script>
        const articles = {articles_json};

        // Render Article Cards
        function renderArticles(list) {{
            const container = document.getElementById('articlesContainer');
            if (list.length === 0) {{
                container.innerHTML = `
                    <div class="glass-card rounded-xl p-12 text-center text-slate-400">
                        <i class="fa-solid fa-circle-exclamation text-3xl mb-3 text-slate-500"></i>
                        <p class="text-sm">조건에 맞는 기사가 없습니다.</p>
                    </div>
                `;
                return;
            }}

            container.innerHTML = list.map(item => `
                <div class="glass-card glass-card-hover rounded-xl p-5 border border-slate-700/80">
                    <div class="flex flex-col lg:flex-row lg:items-start justify-between gap-4">
                        <div class="space-y-2.5 flex-1">
                            <div class="flex flex-wrap items-center gap-2">
                                <span class="px-2.5 py-0.5 rounded-full text-xs font-semibold ${{item.topic_color}} border">
                                    ${{item.topic}}
                                </span>
                                <span class="px-2.5 py-0.5 rounded-full text-xs font-medium bg-slate-800 text-slate-300 border border-slate-700">
                                    <i class="fa-regular fa-building text-[10px] mr-1"></i>${{item.press}}
                                </span>
                                <span class="px-2.5 py-0.5 rounded-full text-xs font-medium bg-slate-800/60 text-slate-400 border border-slate-700/60">
                                    ${{item.category}}
                                </span>
                                <span class="text-xs text-slate-400 ml-auto sm:ml-0">
                                    <i class="fa-regular fa-clock text-[10px] mr-1"></i>${{item.published_at}}
                                </span>
                            </div>

                            <h4 class="text-lg font-bold text-white hover:text-indigo-300 transition cursor-pointer" onclick="openModal(${{item.id}})">
                                ${{item.title}}
                            </h4>

                            <div class="bg-slate-800/70 rounded-lg p-3 border border-slate-700/50">
                                <div class="text-xs font-bold text-indigo-300 mb-1 flex items-center">
                                    <i class="fa-solid fa-wand-magic-sparkles mr-1.5 text-xs text-indigo-400"></i> AI 핵심 요약
                                </div>
                                <p class="text-xs text-slate-200 leading-relaxed">${{item.summary}}</p>
                            </div>

                            <div class="space-y-1 pt-1">
                                ${{item.takeaways.map(t => `
                                    <div class="flex items-start text-xs text-slate-300">
                                        <i class="fa-solid fa-check text-emerald-400 mt-1 mr-2 text-[10px]"></i>
                                        <span>${{t}}</span>
                                    </div>
                                `).join('')}}
                            </div>

                            <div class="flex flex-wrap items-center gap-1.5 pt-2">
                                <span class="text-[11px] text-slate-400 mr-1"><i class="fa-solid fa-hashtag text-[10px]"></i> 키워드:</span>
                                ${{item.keywords.map(kw => `
                                    <span class="px-2 py-0.5 bg-slate-800 text-slate-300 text-[11px] rounded border border-slate-700">${{kw}}</span>
                                `).join('')}}
                            </div>
                        </div>

                        <div class="flex lg:flex-col items-center lg:items-end justify-between lg:justify-start gap-3 shrink-0 pt-3 lg:pt-0 border-t lg:border-t-0 border-slate-700">
                            <div class="text-right">
                                <div class="text-xs text-slate-400">분량: <span class="font-bold text-white">${{item.char_count.toLocaleString()}}자</span></div>
                                <div class="text-[11px] text-slate-400">${{item.word_count}}개 단어</div>
                            </div>
                            <div class="flex items-center space-x-2">
                                <button onclick="openModal(${{item.id}})" class="text-xs bg-slate-800 hover:bg-slate-700 text-indigo-300 px-3 py-1.5 rounded-lg border border-slate-700 transition">
                                    <i class="fa-solid fa-book-open mr-1"></i> 본문 열람
                                </button>
                                <a href="${{item.url}}" target="_blank" class="text-xs bg-indigo-600 hover:bg-indigo-500 text-white px-3 py-1.5 rounded-lg transition inline-flex items-center">
                                    <i class="fa-solid fa-arrow-up-right-from-square mr-1"></i> 네이버 원문
                                </a>
                            </div>
                        </div>
                    </div>
                </div>
            `).join('');
        }}

        // Filter Handlers
        function filterArticles() {{
            const query = document.getElementById('searchInput').value.toLowerCase();
            const press = document.getElementById('pressFilter').value;
            const category = document.getElementById('categoryFilter').value;

            const filtered = articles.filter(item => {{
                const matchQuery = item.title.toLowerCase().includes(query) || 
                                   item.content.toLowerCase().includes(query) ||
                                   item.summary.toLowerCase().includes(query);
                const matchPress = press === 'ALL' || item.press === press;
                const matchCategory = category === 'ALL' || item.category === category;
                return matchQuery && matchPress && matchCategory;
            }});

            renderArticles(filtered);
        }}

        document.getElementById('searchInput').addEventListener('input', filterArticles);
        document.getElementById('pressFilter').addEventListener('change', filterArticles);
        document.getElementById('categoryFilter').addEventListener('change', filterArticles);

        // Modal Functions
        function openModal(id) {{
            const item = articles.find(a => a.id === id);
            if (!item) return;

            document.getElementById('modalTitle').textContent = item.title;
            document.getElementById('modalPress').textContent = item.press;
            document.getElementById('modalCategory').textContent = item.category + ' | ' + item.topic;
            document.getElementById('modalDate').textContent = item.published_at;
            document.getElementById('modalContent').textContent = item.content;
            document.getElementById('modalMeta').textContent = `글자 수: ${{item.char_count.toLocaleString()}}자 | 단어 수: ${{item.word_count}}개`;
            document.getElementById('modalUrl').href = item.url;

            document.getElementById('articleModal').classList.remove('hidden');
        }}

        function closeModal() {{
            document.getElementById('articleModal').classList.add('hidden');
        }}

        // Initialize Charts
        function initCharts() {{
            // 1. Keyword Bar Chart
            const kwCtx = document.getElementById('keywordChart').getContext('2d');
            new Chart(kwCtx, {{
                type: 'bar',
                data: {{
                    labels: ['쿠사마/예술', '블랙 에디션', '반값 여행', '예술감독/솔리스트', '스포티지/쏘렌토', '연식변경', '소비창출/환급', '무더위/소나기', '글로벌발레포럼', '인구감소지역'],
                    datasets: [{{
                        label: '출현 빈도',
                        data: [8, 6, 6, 6, 5, 5, 4, 3, 3, 3],
                        backgroundColor: [
                            'rgba(245, 158, 11, 0.85)',
                            'rgba(59, 130, 246, 0.85)',
                            'rgba(16, 185, 129, 0.85)',
                            'rgba(168, 85, 247, 0.85)',
                            'rgba(59, 130, 246, 0.7)',
                            'rgba(59, 130, 246, 0.6)',
                            'rgba(16, 185, 129, 0.7)',
                            'rgba(14, 165, 233, 0.85)',
                            'rgba(168, 85, 247, 0.7)',
                            'rgba(16, 185, 129, 0.6)'
                        ],
                        borderRadius: 6,
                    }}]
                }},
                options: {{
                    indexAxis: 'y',
                    responsive: true,
                    maintainAspectRatio: false,
                    plugins: {{
                        legend: {{ display: false }},
                        tooltip: {{
                            backgroundColor: '#1E293B',
                            titleColor: '#F8FAFC',
                            bodyColor: '#CBD5E1',
                            borderColor: '#475569',
                            borderWidth: 1
                        }}
                    }},
                    scales: {{
                        x: {{
                            grid: {{ color: 'rgba(255, 255, 255, 0.05)' }},
                            ticks: {{ color: '#94A3B8', stepSize: 2 }}
                        }},
                        y: {{
                            grid: {{ display: false }},
                            ticks: {{ color: '#E2E8F0', font: {{ size: 11 }} }}
                        }}
                    }}
                }}
            }});

            // 2. Article Length Comparison Chart
            const lenCtx = document.getElementById('articleLengthChart').getContext('2d');
            new Chart(lenCtx, {{
                type: 'bar',
                data: {{
                    labels: ['날씨 속보', '발레 포럼', '반값 여행', '기아 RV', '쿠사마 별세'],
                    datasets: [
                        {{
                            label: '글자 수',
                            data: [326, 444, 1240, 889, 839],
                            backgroundColor: 'rgba(99, 102, 241, 0.85)',
                            borderRadius: 6
                        }},
                        {{
                            label: '단어 수 (x5 스케일)',
                            data: [58 * 5, 85 * 5, 267 * 5, 192 * 5, 181 * 5],
                            backgroundColor: 'rgba(14, 165, 233, 0.85)',
                            borderRadius: 6
                        }}
                    ]
                }},
                options: {{
                    responsive: true,
                    maintainAspectRatio: false,
                    plugins: {{
                        legend: {{
                            position: 'top',
                            labels: {{ color: '#CBD5E1', font: {{ size: 11 }} }}
                        }},
                        tooltip: {{
                            callbacks: {{
                                label: function(context) {{
                                    if (context.datasetIndex === 1) {{
                                        return '단어 수: ' + (context.raw / 5) + '개';
                                    }}
                                    return context.dataset.label + ': ' + context.raw + '자';
                                }}
                            }}
                        }}
                    }},
                    scales: {{
                        x: {{
                            grid: {{ display: false }},
                            ticks: {{ color: '#E2E8F0' }}
                        }},
                        y: {{
                            grid: {{ color: 'rgba(255, 255, 255, 0.05)' }},
                            ticks: {{ color: '#94A3B8' }}
                        }}
                    }}
                }}
            }});

            // 3. Press Distribution Doughnut
            const pressCtx = document.getElementById('pressChart').getContext('2d');
            new Chart(pressCtx, {{
                type: 'doughnut',
                data: {{
                    labels: ['뉴시스 (2건)', '헤럴드경제 (2건)', 'MBC (1건)'],
                    datasets: [{{
                        data: [40, 40, 20],
                        backgroundColor: ['#6366F1', '#06B6D4', '#EC4899'],
                        borderColor: '#1E293B',
                        borderWidth: 3
                    }}]
                }},
                options: {{
                    responsive: true,
                    maintainAspectRatio: false,
                    plugins: {{
                        legend: {{
                            position: 'bottom',
                            labels: {{ color: '#CBD5E1', padding: 16 }}
                        }}
                    }}
                }}
            }});

            // 4. Topic Distribution Doughnut
            const topicCtx = document.getElementById('topicChart').getContext('2d');
            new Chart(topicCtx, {{
                type: 'doughnut',
                data: {{
                    labels: ['미술/문화계', '관광/여행', '공연/예술', '자동차/라이프', '기상/날씨'],
                    datasets: [{{
                        data: [20, 20, 20, 20, 20],
                        backgroundColor: ['#F59E0B', '#10B981', '#A855F7', '#3B82F6', '#0EA5E9'],
                        borderColor: '#1E293B',
                        borderWidth: 3
                    }}]
                }},
                options: {{
                    responsive: true,
                    maintainAspectRatio: false,
                    plugins: {{
                        legend: {{
                            position: 'bottom',
                            labels: {{ color: '#CBD5E1', padding: 12, boxWidth: 12 }}
                        }}
                    }}
                }}
            }});
        }}

        // Initial Execution
        document.addEventListener('DOMContentLoaded', () => {{
            renderArticles(articles);
            initCharts();
        }});
    </script>
</body>
</html>
"""

with open('artifacts/reports/culture_news_dashboard.html', 'w', encoding='utf-8') as f:
    f.write(html_content)

print("Successfully generated HTML dashboard: artifacts/reports/culture_news_dashboard.html")
