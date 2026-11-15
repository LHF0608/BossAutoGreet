# -*- coding: utf-8 -*-
with open(r'L:\小雨\找工作\boss_auto_greet\app.py', 'r', encoding='utf-8') as f:
    text = f.read()

# 1. 恢复纯净 trigger_page_scroll (移除所有下一页逻辑)
old_scroll_chunk = """# ============================
# 左侧列表瀑布流滚轮下拉加载
# ============================
def trigger_page_scroll(page, target_card=None):
    \"\"\"
    触发 BOSS 直聘左侧职位列表的向下滚轮加载与底部分页翻页：
    1. 优先检测底部分页器的【下一页】按钮 (解决BOSS瀑布流转分页后无法向下滚动的致命问题)
    2. 穿透滚动左侧职位列表真实容器与窗口，模拟滚轮触底
    3. 返回 True 表示已触发翻页或正在滚动，返回 False 表示无滚动
    \"\"\"
    try:
        # ====== 1. 优先检查并点击底部分页条的“下一页” ======
        next_btn = (
            page.ele('css:.options-pages a.next:not(.disabled)', timeout=0.1) or
            page.ele('css:.pagination a.next:not(.disabled)', timeout=0.1) or
            page.ele('css:a.page-next:not(.disabled)', timeout=0.1) or
            page.ele('css:.ui-icon-arrow-right', timeout=0.1)
        )
        if next_btn and next_btn.is_displayed:
            try:
                next_btn.scroll.to_see()
                time.sleep(0.3)
                next_btn.click()
                push_log("[分页跳转] 成功点击底部分页【下一页】按钮，等待新页面岗位载入...")
                time.sleep(2.5)
                return True
            except Exception:
                pass

        # ====== 2. 若有当前卡片，先将视口对齐到卡片 ======
        if target_card:
            try:
                target_card.scroll.to_see()
            except Exception:
                pass

        # ====== 3. 穿透左侧独立滚动容器 + 全局 Window 滚动 ======
        scroll_js = \"\"\"
        (() => {
            const listWrap = document.querySelector(
                '.job-card-wrapper, .job-list-container, .job-list-wrapper, .job-list-box, ul.job-list-box, .sub-feed-list'
            );
            if (listWrap) {
                listWrap.scrollTop += 1200;
                listWrap.dispatchEvent(new WheelEvent('wheel', { deltaY: 1200, bubbles: true }));
            }
            window.scrollBy(0, 1000);
            window.scrollTo(0, document.body.scrollHeight || document.documentElement.scrollHeight);
        })()
        \"\"\"
        page.run_js(scroll_js)
        return True
    except Exception:
        try:
            page.scroll.down(1000)
            return True
        except Exception:
            return False"""

new_scroll_chunk = """# ============================
# 左侧列表瀑布流滚轮下拉加载 (纯瀑布流架构，无下一页)
# ============================
def trigger_page_scroll(page, target_card=None):
    \"\"\"
    触发 BOSS 直聘左侧职位列表的向下滚轮加载：
    纯瀑布流架构：穿透左侧独立滚动容器并注入滚轮事件，拉取新一批岗位
    \"\"\"
    try:
        # 若有当前卡片，先将视口对齐到卡片
        if target_card:
            try:
                target_card.scroll.to_see()
            except Exception:
                pass

        # 穿透左侧独立滚动容器 + 全局 Window 滚动
        scroll_js = \"\"\"
        (() => {
            const listWrap = document.querySelector(
                '.job-card-wrapper, .job-list-container, .job-list-wrapper, .job-list-box, ul.job-list-box, .sub-feed-list'
            );
            if (listWrap) {
                listWrap.scrollTop += 1200;
                listWrap.dispatchEvent(new WheelEvent('wheel', { deltaY: 1200, bubbles: true }));
            }
            window.scrollBy(0, 1000);
            window.scrollTo(0, document.body.scrollHeight || document.documentElement.scrollHeight);
        })()
        \"\"\"
        page.run_js(scroll_js)
        return True
    except Exception:
        try:
            page.scroll.down(1000)
            return True
        except Exception:
            return False"""

# 2. 去除历史去重池初筛拦截，只要页面显示【立即沟通】就投
old_seen_init = """    # 1. 历史去重与全局去重池初始化 (Global Seen Set)
    history_keys = load_history_keys()
    global_seen_hrefs = set(history_keys)
    push_log(f"[历史去重] 成功加载 {len(history_keys)} 条历史投递记录，跨关键词全局去重池已就绪")"""

new_seen_init = """    # 1. 全局去重池初始化 (按用户要求：不根据历史 records 强行跳过，只要页面是立即沟通就投)
    history_keys = set()
    global_seen_hrefs = set()
    push_log("[去重策略] 已开启【所见即所投】：只要卡片右侧为【立即沟通】均可发起投递，不因历史记录跳过")"""

# 3. process_single_job_card 中去掉历史已投递判断
old_card_dedup = """            # 1. 历史去重与全局并发去重校验 (Global Seen Set)
            if (job_href and job_href in global_seen_hrefs) or (job_id and job_id in global_seen_hrefs) or (signature in global_seen_hrefs):
                is_history = (job_href in history_keys) or (signature in history_keys)
                reason = "历史已投递 (history.csv去重)" if is_history else "重复扫描卡片"
                record_skip(company_name, job_name, reason, job_href)
                if is_history:
                    push_log(f"[跳过-历史已投] {company_name} | {job_name} (已记录在 history.csv 中)")
                return False

            # 将本卡片写入全局已扫描池，防止跨词重复处理
            if job_href:
                global_seen_hrefs.add(job_href)
            if job_id:
                global_seen_hrefs.add(job_id)
            global_seen_hrefs.add(signature)"""

new_card_dedup = """            # 1. 仅防止同一次遍历内针对同一卡片无限死循环
            card_key = job_href or f"{company_name}_{job_name}"
            if card_key in processed_in_kw:
                return False
            processed_in_kw.add(card_key)"""

# 4. JD 正文过滤：把通用性销售/培训等多义词从 JD 正文黑名单中剔除，避免误杀 Agent/研发/技术方案类好岗位！
old_jd_check = """                # 深度黑名单复筛 (严查漫剧/短剧/小说/分镜等)
                matched_jd_black = [b for b in state.active_blacklist if b.lower() in jd_text.lower()]
                if matched_jd_black:
                    record_skip(company_name, job_name, f"JD正文命中屏蔽词: 【{','.join(matched_jd_black)}】", detail_url)
                    push_log(f"[跳过-JD正文含黑名单] {company_name} | {job_name} -> 命中屏蔽词: 【{','.join(matched_jd_black)}】")
                    if tab:
                        tab.close()
                    return False"""

new_jd_check = """                # 深度黑名单复筛 (避免技术岗位因包含'销售培训'、'内部培训'、'客户方案'而被误杀)
                # 排除纯灰产词汇 (小说推文、短剧、漫剧、兼职打字、学徒收费等)
                STRICT_DIRTY_WORDS = ['漫剧', '短剧', '真人短剧', '小说推文', '推文', '剪辑分镜', '影视剪辑分发', '学徒收费', '交押金', '打字兼职']
                matched_jd_black = [b for b in STRICT_DIRTY_WORDS if b in jd_text]
                
                # 只有标题明确叫销售才过滤；如果正文含销售，只有当出现强销售特征(电话销售/陌拜/提成)时才过滤
                if ('销售' in state.active_blacklist or '课程顾问' in state.active_blacklist):
                    if any(sp in jd_text for sp in ['电话销售', '电话陌拜', '拨打电话量', '销售提成', '陌拜客户']):
                        matched_jd_black.append('纯销售特征(电销/陌拜)')

                if matched_jd_black:
                    record_skip(company_name, job_name, f"JD正文命中屏蔽词: 【{','.join(matched_jd_black)}】", detail_url)
                    push_log(f"[跳过-JD正文含黑名单] {company_name} | {job_name} -> 命中屏蔽词: 【{','.join(matched_jd_black)}】")
                    if tab:
                        tab.close()
                    return False"""

# 5. 瀑布流探底提示语修改
old_bottom_log = """                    else:
                        push_log(f"[深度加载/翻页] 未出现新卡片，触发滚动或下一页 (重试 {no_new_cards_count}/7)...")
                        trigger_page_scroll(page)
                        # 留足 2.0-3.0 秒等待网络回包渲染
                        sleep_interruptible(random.uniform(2.0, 3.0))"""

new_bottom_log = """                    else:
                        push_log(f"[瀑布流下拉] 未出现新卡片，触发向下触底滚动 (重试 {no_new_cards_count}/7)...")
                        trigger_page_scroll(page)
                        # 留足 2.0-2.8 秒等待网络回包渲染
                        sleep_interruptible(random.uniform(2.0, 2.8))"""

# 替换
assert old_scroll_chunk in text, "old_scroll_chunk mismatch"
assert old_seen_init in text, "old_seen_init mismatch"
assert old_card_dedup in text, "old_card_dedup mismatch"
assert old_jd_check in text, "old_jd_check mismatch"
assert old_bottom_log in text, "old_bottom_log mismatch"

text = text.replace(old_scroll_chunk, new_scroll_chunk)
text = text.replace(old_seen_init, new_seen_init)
text = text.replace(old_card_dedup, new_card_dedup)
text = text.replace(old_jd_check, new_jd_check)
text = text.replace(old_bottom_log, new_bottom_log)

with open(r'L:\小雨\找工作\boss_auto_greet\app.py', 'w', encoding='utf-8') as f:
    f.write(text)

print("UPDATE_COMPLETE_SUCCESS")
