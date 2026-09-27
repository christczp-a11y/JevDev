@echo off
REM 打开抓取 Google 评价专用的 Chrome 配置（和日常 Chrome 完全分开）。
REM 首次使用：在弹出的窗口里手动登录 Google 小号，登录后关掉窗口即可。
REM 登录态失效时再运行一次这个脚本重新登录。
start "" "C:\Program Files\Google\Chrome\Application\chrome.exe" --user-data-dir="C:\Users\Chris\jevdev-browser\google-profile" --no-first-run "https://accounts.google.com/"
