import os

app_path = r"L:\小雨\找工作\boss_auto_greet\app.py"
with open(app_path, "r", encoding="utf-8") as f:
    content = f.read()

old_row = """                        with ui.row().classes('items-center justify-between w-full mt-2 pt-2 border-t border-slate-100 dark:border-slate-800'):
                            ui.label('✅ 跨号企业库已自动对齐同步').classes('text-xs text-slate-400')
                            ui.button('⚡ 保存立即执行设置', icon='bolt', on_click=lambda: save_collision_config(notify=True)).props('unelevated color=rose text-color=white font-bold').classes('px-3 py-1 shadow-sm')"""

new_row = """                        with ui.row().classes('items-center justify-between w-full mt-2 pt-2 border-t border-slate-100 dark:border-slate-800'):
                            ui.label('✅ 跨号企业库已自动对齐同步').classes('text-xs text-slate-500 font-medium')
                            ui.button('⚡ 保存立即执行设置', icon='bolt', on_click=lambda: save_collision_config(notify=True)).props('unelevated dense size=sm color=rose text-color=white font-bold').classes('px-3 shadow-sm')"""

assert old_row in content, "old_row not found"
content = content.replace(old_row, new_row, 1)

with open(app_path, "w", encoding="utf-8") as f:
    f.write(content)

print("Feature 4 button style adjusted!")
