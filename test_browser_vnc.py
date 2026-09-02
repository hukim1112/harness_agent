"""
test_browser_vnc.py
VNC 가상 디스플레이(:1) 및 Playwright Chromium 브라우저 정상 작동 여부 검증 스크립트

[실행 순서]
1. 터미널 1: ./start_vnc.sh (6080 포트 가동)
2. Codespaces 포트 탭: 6080 포트 브라우저 열기 (noVNC 데스크톱 접속)
3. 터미널 2: python test_browser_vnc.py (VNC 화면에 실제 브라우저가 뜨는지 확인)
"""
import os
import time
from playwright.sync_api import sync_playwright

def main():
    display = os.getenv("DISPLAY", "None")
    print(f"🖥️ [1/4] DISPLAY 환경 변수: {display}")
    
    if display == "None":
        print("⚠️ DISPLAY 환경 변수가 설정되지 않았습니다. 기본값 :1 을 사용합니다.")
        os.environ["DISPLAY"] = ":1"

    print("🌐 [2/4] Chromium 브라우저(Headed 모드)를 가상 디스플레이에 띄웁니다...")
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=False)
        page = browser.new_page()
        
        print("🔍 [3/4] 테스트 웹페이지(https://example.com)에 접속합니다...")
        page.goto("https://example.com")
        title = page.title()
        print(f"   - 확인된 페이지 타이틀: '{title}'")
        
        print("⏳ [4/4] VNC 화면 확인을 위해 3초간 브라우저 창을 유지합니다...")
        time.sleep(3)
        
        browser.close()
        print("🎉 [성공] Playwright Chromium과 noVNC 가상 화면이 완벽하게 연동되었습니다!")

if __name__ == "__main__":
    main()
