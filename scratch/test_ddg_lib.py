from duckduckgo_search import DDGS

query = "NVIDIA GTC 2026 news"
try:
    with DDGS() as ddgs:
        results = list(ddgs.text(query, max_results=5))
        print("✅ [Live Search Succeed]")
        print("Results Count:", len(results))
        for idx, r in enumerate(results):
            print(f"{idx+1}. [{r.get('title')}]: {r.get('body')}")
except Exception as e:
    print("❌ [Live Search Failed]:", e)
