import time
from DrissionPage import ChromiumPage, ChromiumOptions

co = ChromiumOptions()
co.headless(True)
p = ChromiumPage(co)
try:
    p.get("http://127.0.0.1:8080")
    time.sleep(2)
    btns = p.eles('tag:button')
    acc2_btn = [b for b in btns if '扫码' in b.text][2]
    acc2_btn.click(by_js=True)
    time.sleep(3)
    
    # Click 微信扫码
    wx_btn = p.ele('text:微信扫码')
    if wx_btn:
        print("Clicking 微信扫码...")
        wx_btn.click(by_js=True)
        time.sleep(3)
        p.get_screenshot(path=r'C:\Users\下雨\.gemini\antigravity\brain\bcf5e808-14e0-4f36-93d6-5a39dac684e1\test_click_wx_mode.png')
        print("Wx mode screenshot saved!")
        
    # Click back to BOSS APP 扫码
    boss_btn = p.ele('text:BOSS APP扫码')
    if boss_btn:
        print("Clicking back to BOSS APP扫码...")
        boss_btn.click(by_js=True)
        time.sleep(3)
        p.get_screenshot(path=r'C:\Users\下雨\.gemini\antigravity\brain\bcf5e808-14e0-4f36-93d6-5a39dac684e1\test_click_boss_back.png')
        print("Boss back screenshot saved!")
finally:
    p.quit()
