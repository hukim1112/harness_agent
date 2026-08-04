#!/bin/bash

# 1. 기존에 찌꺼기로 남은 잠금 파일 및 프로세스 정리
pkill -f Xvfb
pkill -f x11vnc
pkill -f fluxbox
pkill -f novnc
sudo rm -f /tmp/.X1-lock
sudo rm -f /tmp/.X11-unix/X1

# 2. 가상 디스플레이 시작
Xvfb :1 -screen 0 1280x800x24 &
sleep 2
export DISPLAY=:1

# 3. 창 관리자 실행
fluxbox &

# 4. VNC 서버 실행 (포트를 5900으로 고정)
x11vnc -display :1 -nopw -forever -shared -rfbport 5900 &
sleep 2

# 5. noVNC 실행 (경로를 범용적으로 수정)
if [ -f /usr/bin/novnc_proxy ]; then
    /usr/bin/novnc_proxy --vnc localhost:5900 --listen 6080
elif [ -f /usr/share/novnc/utils/novnc_proxy ]; then
    /usr/share/novnc/utils/novnc_proxy --vnc localhost:5900 --listen 6080
else
    # 둘 다 없을 경우 직접 경로 지정 실행
    websockify --web /usr/share/novnc/ 6080 localhost:5900
fi
