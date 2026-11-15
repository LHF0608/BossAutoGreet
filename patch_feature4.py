import os

app_path = r"L:\小雨\找工作\boss_auto_greet\app.py"
with open(app_path, "r", encoding="utf-8") as f:
    content = f.read()

# 1. Update DEFAULT_CONFIG
old_cfg_line = '    "followup_message": "您好，看您比较忙还没来得及看消息，我对贵司该岗位非常感兴趣，有3个月Agent开发实战经验，期待您的回复！"'
new_cfg_line = '''    "followup_message": "您好，看您比较忙还没来得及看消息，我对贵司该岗位非常感兴趣，有3个月Agent开发实战经验，期待您的回复！",
    "enable_cross_account_collision": True,
    "enable_company_limit_once": False'''

assert old_cfg_line in content, "old_cfg_line not found!"
content = content.replace(old_cfg_line, new_cfg_line, 1)

# 2. Add normalize_company_name, load_history_companies, check_collision_and_company_limit
old_history_anchor = "def load_history_keys(account_id: str = None) -> set:"
new_history_functions = '''def normalize_company_name(name: str) -> str:
    """去除公司后缀，提取核心企业标识进行高精度比对"""
    if not name:
        return ""
    n = name.strip()
    for sfx in ["（有限合伙）", "(有限合伙)", "有限责任公司", "股份有限公司", "网络科技有限公司", "科技有限公司", "有限公司", "（中国）", "(中国)"]:
        n = n.replace(sfx, "")
    return n.strip().lower()

def load_history_companies(account_id: str = None) -> set:
    """从历史记录中读取已投递过的所有公司原名与特征词 (按账号数据隔离)"""
    if not account_id:
        account_id = get_current_account_id()
    h_path = get_history_path(account_id)
    companies = set()
    if not os.path.exists(h_path):
        return companies
    try:
        with open(h_path, "r", encoding="utf-8-sig") as f:
            reader = csv.reader(f)
            next(reader, None)
            for row in reader:
                if row and len(row) >= 2:
                    c = row[1].strip()
                    if c:
                        companies.add(c)
                        norm = normalize_company_name(c)
                        if norm:
                            companies.add(norm)
    except Exception as e:
        print(f"[Warn] 读取已投递公司失败 ({account_id}): {e}")
    return companies

def check_collision_and_company_limit(company_name: str, job_name: str, job_href: str, account_id: str = None) -> tuple:
    """
    检查双号跨账号协同防撞车与同公司仅投一次限制
    返回 (is_blocked: bool, reason: str)
    """
    if not company_name or not company_name.strip():
        return False, ""
    
    acc = account_id or get_current_account_id() or "account_1"
    st = account_states.get(acc)
    cfg = load_config()
    enable_cross = getattr(st, 'enable_cross_account_collision', cfg.get("enable_cross_account_collision", True))
    enable_comp_limit = getattr(st, 'enable_company_limit_once', cfg.get("enable_company_limit_once", False))

    raw_comp = company_name.strip()
    norm_comp = normalize_company_name(raw_comp)

    # 1. 同公司仅投一次限制 (检查本账号历史是否已联系过该企业)
    if enable_comp_limit:
        my_comps = load_history_companies(acc)
        if raw_comp in my_comps or (norm_comp and norm_comp in my_comps):
            return True, f"同公司防轰炸: 本账号已向【{raw_comp}】投递过职位，避免同公司重复骚扰"

    # 2. 双号跨账号协同防撞车 (检查另一账号历史是否已投递过该公司或同岗位)
    if enable_cross:
        other_accounts = [a for a in ACCOUNT_REGISTRY.keys() if a != acc]
        for other_acc in other_accounts:
            other_comps = load_history_companies(other_acc)
            other_keys = load_history_keys(other_acc)
            other_name = ACCOUNT_REGISTRY.get(other_acc, {}).get("name", other_acc)
            
            # 校验公司是否已被另一账号投过
            if raw_comp in other_comps or (norm_comp and norm_comp in other_comps):
                return True, f"跨号协同防撞车: 【{other_name}】已投递过企业【{raw_comp}】，自动避让防撞车"
            
            # 校验具体岗位链接/去重特征
            if job_href and any(k in job_href for k in other_keys if len(k) > 10):
                return True, f"跨号协同防撞车: 【{other_name}】已投递过该岗位链接，自动跳过"

    return False, ""

def load_history_keys(account_id: str = None) -> set:'''

assert old_history_anchor in content, "old_history_anchor not found!"
content = content.replace(old_history_anchor, new_history_functions, 1)

# 3. Add state fields to AccountState
old_st_anchor = '    active_hr_filters: set = field(default_factory=set)'
new_st_anchor = '''    active_hr_filters: set = field(default_factory=set)
    enable_cross_account_collision: bool = True
    enable_company_limit_once: bool = False'''

assert old_st_anchor in content, "old_st_anchor not found!"
content = content.replace(old_st_anchor, new_st_anchor, 1)

# 4. In init_today_log:
old_init_log_anchor = "    st.active_city_mode = _init_cfg.get('city_filter_mode', 'blacklist')"
new_init_log_anchor = '''    st.active_city_mode = _init_cfg.get('city_filter_mode', 'blacklist')
    st.enable_cross_account_collision = bool(_init_cfg.get('enable_cross_account_collision', True))
    st.enable_company_limit_once = bool(_init_cfg.get('enable_company_limit_once', False))'''

assert old_init_log_anchor in content, "old_init_log_anchor not found!"
content = content.replace(old_init_log_anchor, new_init_log_anchor, 1)

# 5. In process_single_job_card:
old_card_dedup = '''            # 将本卡片写入本轮已扫描池，防止同一次搜索重复点击同一元素
            if job_href:
                global_seen_hrefs.add(job_href)
            if job_id:
                global_seen_hrefs.add(job_id)'''

new_card_dedup = '''            # 将本卡片写入本轮已扫描池，防止同一次搜索重复点击同一元素
            if job_href:
                global_seen_hrefs.add(job_href)
            if job_id:
                global_seen_hrefs.add(job_id)

            # 1.5 双号跨账号协同防撞车 与 同公司防轰炸机制 (执行层立即拦截)
            is_col, col_reason = check_collision_and_company_limit(company_name, job_name, job_href, account_id)
            if is_col:
                rec_skip(company_name, job_name, col_reason, job_href)
                log(f"[跳过-防撞车] {company_name} | {job_name} -> {col_reason}")
                return False'''

assert old_card_dedup in content, "old_card_dedup not found!"
content = content.replace(old_card_dedup, new_card_dedup, 1)

# 6. Replace UI Feature 4 card (lines 5621 to 5642)
old_ui_feature4 = '''                # 功能 4：双号协同防撞车与公司防轰炸机制
                with ui.card().classes('w-1/2 p-5 rounded-2xl border border-slate-200 dark:border-slate-800 bg-white dark:bg-slate-900 shadow-sm'):
                    with ui.row().classes('items-center justify-between w-full pb-2 border-b border-slate-100 dark:border-slate-800'):
                        with ui.row().classes('items-center gap-2'):
                            ui.icon('security', color='rose', size='1.4rem')
                            ui.label('功能 4：双号防撞车与公司防轰炸机制').classes('font-black text-sm text-slate-800 dark:text-slate-100')
                        ui.badge('协同防撞车', color='rose').props('dense rounded')

                    with ui.column().classes('w-full gap-3 mt-3'):
                        collision_switch = ui.switch('开启双号跨账号协同过滤 (账号一投过，账号二自动跳过)', value=True).props('color=rose')
                        company_limit_switch = ui.switch('同公司仅投一次限制 (同一家企业只联系一位最高契合度HR)', value=True).props('color=rose')

                        with ui.card().classes('w-full p-2.5 rounded-xl bg-rose-50/60 dark:bg-rose-950/40 border border-rose-200 dark:border-rose-800'):
                            ui.label('🛡️ 防撞车保障体系: 当账号一与腾讯科技某HR发起沟通后，账号二在全国检索中将自动将腾讯科技列为保护企业直接跳过，杜绝两个账号同时轰炸同一企业，捍卫专业求职形象！').classes('text-xs text-rose-800 dark:text-rose-200 leading-relaxed')

                        def save_collision_config():
                            ui.notify('✅ 双号防撞车与公司防轰炸机制已激活！', color='positive', position='top')

                        with ui.row().classes('items-center justify-between w-full mt-1'):
                            ui.label('✅ 跨号企业库已自动对齐同步').classes('text-xs text-slate-500')
                            ui.button('保存防撞车配置', icon='save', on_click=save_collision_config).props('unelevated dense size=sm color=rose')'''

new_ui_feature4 = '''                # 功能 4：双号协同防撞车与公司防轰炸机制
                with ui.card().classes('w-1/2 p-5 rounded-2xl border border-slate-200 dark:border-slate-800 bg-white dark:bg-slate-900 shadow-sm'):
                    with ui.row().classes('items-center justify-between w-full pb-2 border-b border-slate-100 dark:border-slate-800'):
                        with ui.row().classes('items-center gap-2'):
                            ui.icon('security', color='rose', size='1.4rem')
                            ui.label('功能 4：双号防撞车与公司防轰炸机制').classes('font-black text-sm text-slate-800 dark:text-slate-100')
                        ui.badge('协同防撞车', color='rose').props('dense rounded')

                    with ui.column().classes('w-full gap-3 mt-3'):
                        init_cross = current_cfg.get('enable_cross_account_collision', True)
                        init_comp = current_cfg.get('enable_company_limit_once', False)

                        collision_switch = ui.switch('开启双号跨账号协同过滤 (账号一投过，账号二自动跳过)', value=init_cross).props('color=rose')
                        company_limit_switch = ui.switch('同公司仅投一次限制 (同一家企业只联系一位最高契合度HR)', value=init_comp).props('color=rose')

                        with ui.card().classes('w-full p-2.5 rounded-xl bg-rose-50/60 dark:bg-rose-950/40 border border-rose-200 dark:border-rose-800'):
                            ui.label('🛡️ 防撞车保障体系: 当账号一与某企业HR发起沟通后，账号二在全国检索中将自动将该企业列为保护避让直接跳过，杜绝双号同时轰炸同一企业，捍卫专业求职形象！').classes('text-xs text-rose-800 dark:text-rose-200 leading-relaxed')

                        collision_status_label = ui.label('正在计算跨号保护企业库...').classes('text-xs text-slate-500 font-medium')

                        def update_collision_stats():
                            acc1_comps = load_history_companies("account_1")
                            acc2_comps = load_history_companies("account_2")
                            all_comps = acc1_comps | acc2_comps
                            collision_status_label.text = f"📊 跨号受保护企业库: {len(all_comps)} 家 (账号一: {len(acc1_comps)} 家 | 账号二: {len(acc2_comps)} 家)"

                        def save_collision_config(notify=True):
                            cfg = load_config()
                            cfg['enable_cross_account_collision'] = bool(collision_switch.value)
                            cfg['enable_company_limit_once'] = bool(company_limit_switch.value)
                            save_config(cfg)
                            for s in account_states.values():
                                s.enable_cross_account_collision = bool(collision_switch.value)
                                s.enable_company_limit_once = bool(company_limit_switch.value)
                            update_collision_stats()
                            push_log(f"🛡️ [防撞策略生效] 跨号协同防撞: {'【开启】' if collision_switch.value else '【关闭】'} | 同公司仅投一次: {'【开启】' if company_limit_switch.value else '【关闭】'} (设置已立即执行生效)")
                            if notify:
                                ui.notify('✅ 防撞车设置已保存并立即执行！双核引擎后续投递已实时生效。', color='positive', position='top')

                        # 开关变动立即自动保存并执行
                        collision_switch.on_change(lambda: save_collision_config(notify=True))
                        company_limit_switch.on_change(lambda: save_collision_config(notify=True))

                        update_collision_stats()

                        with ui.row().classes('items-center justify-between w-full mt-2 pt-2 border-t border-slate-100 dark:border-slate-800'):
                            ui.label('✅ 跨号企业库已自动对齐同步').classes('text-xs text-slate-400')
                            ui.button('⚡ 保存立即执行设置', icon='bolt', on_click=lambda: save_collision_config(notify=True)).props('unelevated color=rose text-color=white font-bold').classes('px-3 py-1 shadow-sm')'''

assert old_ui_feature4 in content, "old_ui_feature4 not found!"
content = content.replace(old_ui_feature4, new_ui_feature4, 1)

with open(app_path, "w", encoding="utf-8") as f:
    f.write(content)

print("Feature 4 full implementation applied successfully!")
