import os
import zipfile
import shutil

def pack_release():
    src_dir = os.path.dirname(os.path.abspath(__file__))
    parent_dir = os.path.dirname(src_dir)
    out_zip = os.path.join(parent_dir, "boss_auto_greet_免弹窗绿色解压即用版.zip")

    include_files = [
        "app.py",
        "city_data.py",
        "rag_engine.py",
        "config.json",
        "history.csv",
        "requirements.txt",
        "run.bat",
        "一键运行.bat",
        "一键运行(后台静默免黑框版).vbs",
        "README.md",
        "使用说明(必读).txt"
    ]

    include_dirs = [
        "h5",
        "data"
    ]

    print(f"[*] 开始打包 BOSS直聘免弹窗解压即用版...")
    print(f"[*] 源目录: {src_dir}")
    print(f"[*] 输出压缩包: {out_zip}")

    total_files = 0
    with zipfile.ZipFile(out_zip, "w", zipfile.ZIP_DEFLATED) as zf:
        # 1. 写入关键单文件
        for fn in include_files:
            fp = os.path.join(src_dir, fn)
            if os.path.isfile(fp):
                arcname = os.path.join("boss_auto_greet", fn)
                zf.write(fp, arcname)
                print(f"  + 文件: {fn}")
                total_files += 1

        # 2. 写入附带目录 (如有)
        for d in include_dirs:
            dp = os.path.join(src_dir, d)
            if os.path.isdir(dp):
                for root, dirs, files in os.walk(dp):
                    if "__pycache__" in root or "boss_browser_data" in root:
                        continue
                    for f in files:
                        if f.endswith((".pyc", ".log", ".tmp", "lockfile")) or "lock" in f.lower() or "singleton" in f.lower():
                            continue
                        f_path = os.path.join(root, f)
                        try:
                            rel_path = os.path.relpath(f_path, src_dir)
                            arcname = os.path.join("boss_auto_greet", rel_path)
                            zf.write(f_path, arcname)
                            total_files += 1
                        except Exception:
                            pass

        # 3. 写入空的 boss_browser_data 目录标识
        zf.writestr("boss_auto_greet/boss_browser_data/.keep", "")
        total_files += 1

    file_size_mb = round(os.path.getsize(out_zip) / (1024 * 1024), 2)
    print(f"\n✅ 打包完成！共计打包 {total_files} 个文件。")
    print(f"📦 压缩包已生成: {out_zip} ({file_size_mb} MB)")
    print("👉 您可以直接将此 zip 压缩包发送给他人，对方在任意 Windows 电脑解压并双击 run.bat 即可直接使用！")

if __name__ == "__main__":
    pack_release()
