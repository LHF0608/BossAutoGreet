# Redmi K50 Ultra (Debian 12 ARM64 Chroot) 自动化部署与全天候保活指南

本指南详细介绍如何将 **BOSS直聘全自动打招呼系统** 完整迁移并部署至 **Redmi K50 Ultra**（骁龙 8+ Gen 1 旗舰芯片，Root + KernelSU + Debian 12 ARM64 Chroot 容器），实现 **24小时无桌面后台全自动投递、开机自愈保活、电池硬件级防鼓包保护**。

---

## 目录
- [一、 方案架构与技术特性](#一-方案架构与技术特性)
- [二、 部署文件清单](#二-部署文件清单)
- [三、 第一步：PC 端登录与项目完整打包](#三-第一步pc-端登录与项目完整打包)
- [四、 第二步：配置 ACC 硬件级锁电 50%（防电池鼓包）](#四-第二步配置-acc-硬件级锁电-50防电池鼓包)
- [五、 第三步：配置 KernelSU 开机自启服务 (`2_ksu_boot_service.sh`)](#五-第三步配置-kernelsu-开机自启服务-2_ksu_boot_servicesh)
- [六、 第四步：Debian 容器内一键初始化 (`1_setup_debian.sh`)](#六-第四步debian-容器内一键初始化-1_setup_debiansh)
- [七、 第五步：Supervisor 守护进程配置与管理 (`boss_bot.conf`)](#七-第五步supervisor-守护进程配置与管理-boss_botconf)
- [八、 第六步：局域网 Web 控制台访问与测试](#八-第六步局域网-web-控制台访问与测试)
- [九、 常见问题与排错指南 (FAQ)](#九-常见问题与排错指南-faq)

---

## 一、 方案架构与技术特性

```
+--------------------------------------------------------------------------+
|                       Redmi K50 Ultra 硬件层                             |
|          高通骁龙 8+ Gen 1 旗舰芯片 (4nm) / 8GB-12GB LPDDR5 运存          |
|          ACC (Advanced Charging Controller) 锁电 50% (规避电池鼓包)       |
+--------------------------------------------------------------------------+
                                     │
+--------------------------------------------------------------------------+
|                   Android 宿主层 (KernelSU / Android 12-14)              |
|  - CPU WakeLock (/sys/power/wake_lock): 阻止 CPU 息屏睡眠与 Wi-Fi 休眠   |
|  - Phantom Process Killer 解除: 突破 Android 32 进程上限与 SIGKILL 限制  |
|  - 开机自启挂载 (/data/adb/service.d/2_ksu_boot_service.sh)             |
+--------------------------------------------------------------------------+
                                     │ (chroot bind 挂载)
+--------------------------------------------------------------------------+
|                  Debian 12 (Bookworm) ARM64 Chroot 容器                  |
|  - 进程守护: Supervisor (监控退出并秒级自启)                              |
|  - 虚拟屏幕: Xvfb (1920x1080x24 虚拟显示器，规避平台 Headless 浏览器指纹) |
|  - 浏览器引擎: Chromium ARM64 (专用 Wrapper: 自动注入 --no-sandbox)      |
|  - 自动化引擎: DrissionPage + 独立端口 9333                             |
|  - 交互界面: NiceGUI Web 控制台 (局域网直接访问 http://<手机IP>:8080)    |
+--------------------------------------------------------------------------+
```

---

## 二、 部署文件清单

部署包内所有文件均已生成在项目目录下的 `deploy_k50u/` 文件夹中：

| 文件名称 | 适用环境 | 核心作用 |
| :--- | :--- | :--- |
| `1_setup_debian.sh` | Debian 容器内部 (root) | 自动安装 Chromium、Xvfb、中文字体、Supervisor、创建 Python 虚拟环境并配置运行垫片 |
| `boss_bot.conf` | Supervisor 配置目录 | 使用 `xvfb-run` 包裹真实有头模式启动，配置自动重启、日志轮转与进程组回收 |
| `2_ksu_boot_service.sh` | 安卓 `/data/adb/service.d/` | KernelSU 开机自动获取 CPU 唤醒锁、关闭幽灵进程限制、自动挂载容器并启动守护服务 |
| `DEPLOY_GUIDE.md` | 本操作文档 | 全流程保姆级操作指导与故障自愈说明 |

---

## 三、 第一步：PC 端登录与项目完整打包

### 1. 为什么必须在 PC 端生成 `boss_browser_data`？
BOSS直聘拥有高强度的设备指纹与风控验证体系。在无桌面的手机 Linux 容器中直接执行首次登录，需要处理极验验证码与微信扫码，非常麻烦。
**推荐方案**：先在 PC 上运行一次，通过图形界面扫码登录成功，系统会自动将登录凭证与会话持久化保存在 `boss_browser_data/` 目录中。直接将该目录随代码打包迁移至手机，即可实现**免登直接运行**！

### 2. PC 端操作步骤
1. 在 Windows PC 打开项目主目录 `L:\小雨\找工作\boss_auto_greet_k50u`。
2. 双击运行 `run.bat`，浏览器将自动弹出控制台。
3. 点击前端界面的【开始任务】或等待 Chrome 弹出，使用手机微信或 BOSS直聘 APP 完成扫码登录。
4. 看到控制台输出 `[登录检查] 登录状态有效` 后，关闭脚本。
5. 检查项目根目录下已生成 `boss_browser_data/` 文件夹。

### 3. 打包项目文件
在 Windows PowerShell 或终端中执行以下命令（排除无用的旧虚拟环境与缓存文件）：

```powershell
# 进入项目所在上级目录
cd L:\小雨\找工作\boss_auto_greet_k50u

# 使用 tar 将所需源码与已登录数据打包为单个压缩包
tar -czvf boss_k50u.tar.gz `
    --exclude="venv" `
    --exclude="__pycache__" `
    --exclude="*.pyc" `
    app.py `
    city_data.py `
    config.json `
    history.csv `
    requirements.txt `
    boss_browser_data `
    deploy_k50u
```

### 4. 将打包文件推送至手机
通过 USB 连接手机并开启 ADB 调试，执行：

```powershell
# 将压缩包推送到手机内部存储
adb push boss_k50u.tar.gz /sdcard/

# 进入手机 root 环境并解压到 Debian 容器根目录 (假定容器目录为 /data/debian)
adb shell
su
mkdir -p /data/debian/root/boss_auto_greet_k50u
tar -xzvf /sdcard/boss_k50u.tar.gz -C /data/debian/root/boss_auto_greet_k50u/
```

> [!NOTE]
> 如果你是通过 Termux 或其他 SSH 工具连接手机，也可使用 `scp` 或通过手机本地文件管理器（如 MT管理器、Solid Explorer）直接解压到 `/data/debian/root/boss_auto_greet_k50u/`。

---

## 四、 第二步：配置 ACC 硬件级锁电 50%（防电池鼓包）

> [!CAUTION]
> **全天候挂机核心安全红线**：
> 手机若长期 24 小时插着充电线处于 100% 满电状态，电池长期处于 4.35V~4.45V 的高电压饱和区，极易在 1~2 个月内发生锂离子析出、鼓包胀气，甚至撑爆手机后盖产生安全隐患！
> 必须使用 **ACC (Advanced Charging Controller)** 将电池电量上限严格限制在 **45% ~ 50%**，使锂电处于最稳定的标称电压（~3.85V）区间。

### 1. 安装 ACC
1. 打开 **KernelSU** APP，在模块管理中刷入 `acc.zip` 模块（可在 GitHub 搜索 `VR25/acc` 或在模块市场下载）。
2. 重启手机使模块生效。

### 2. 配置锁电阈值
在手机 Termux 或 `adb shell` 中进入 root：

```bash
su

# 设置停充阈值为 50%，复充阈值为 45%
acc 50 45

# 启用自动守护模式
acc -D
```

### 3. 检查 ACC 运行状态
执行以下命令：

```bash
acc -i
```

你将看到类似输出：
```text
NAME: battery
STATUS: Discharging / Idle (电量达到50%时自动停止充电，处于空闲或微电流供电状态)
CAPACITY: 48%
VOLTAGE: 3.86 V (处于极其安全的稳定电压区)
TEMP: 31.0°C
```

> [!TIP]
> 也可以编辑 ACC 配置文件 `/data/adb/vr25/acc-data/config.txt`，设置：
> ```ini
> capacity=(45 50 48)
> cooldown=(10/60 38)
> ```
> 这样即使手机重启，锁电规则也会永久自动生效。

---

## 五、 第三步：配置 KernelSU 开机自启服务 (`2_ksu_boot_service.sh`)

KernelSU 拥有官方标准的开机脚本目录 `/data/adb/service.d/`。放置在该目录下的可执行脚本会在 Android 系统启动完成后以最高 root 权限自动后台运行。

### 1. 部署脚本
在手机 root 终端中执行：

```bash
su

# 拷贝开机脚本到 service.d 目录
cp /data/debian/root/boss_auto_greet_k50u/deploy_k50u/2_ksu_boot_service.sh /data/adb/service.d/2_ksu_boot_service.sh

# 赋予可执行权限
chmod 755 /data/adb/service.d/2_ksu_boot_service.sh
```

### 2. 核心功能说明
`2_ksu_boot_service.sh` 针对 Redmi K50 Ultra 的深度定制项：
1. **等待开机完全就绪**：检测 `sys.boot_completed == 1`，避免开机早期网络设备未加载完成导致脚本失败。
2. **锁定 CPU 唤醒锁 (WakeLock)**：向 `/sys/power/wake_lock` 写入锁，防止屏幕熄灭后安卓进入 Deep Sleep 休眠，导致 Wi-Fi 断开或任务暂停。
3. **解除幽灵进程杀手限制**：
   ```bash
   /system/bin/device_config put activity_manager max_phantom_processes 2147483647
   ```
   Android 12/13/14 默认会限制多进程数量（默认上限仅 32 个），DrissionPage + Chromium 多标签页很容易超过此上限，导致安卓系统直接发送 `SIGKILL` 强杀后台。此命令彻底解除该限制。
4. **虚拟文件系统挂载**：自动挂载 `/proc`, `/sys`, `/dev`, `/dev/pts` 以及最重要的 `/dev/shm`（分配 1GB tmpfs，确保 Chromium 渲染通信顺畅）。
5. **拉起守护**：自动在 chroot 容器内拉起 Supervisor 和 SSH。

---

## 六、 第四步：Debian 容器内一键初始化 (`1_setup_debian.sh`)

进入 Debian ARM64 容器，执行自动化初始化脚本完成全部运行依赖与 Chromium 垫片的配置。

### 1. 进入 Debian 容器
```bash
su
chroot /data/debian /bin/bash
```

### 2. 运行初始化脚本
```bash
cd /root/boss_auto_greet_k50u/deploy_k50u
chmod +x 1_setup_debian.sh
./1_setup_debian.sh
```

### 3. 脚本自动化处理事项
脚本运行时将全自动完成以下核心动作：
- 更新 Debian 12 软件源。
- 一键安装 `chromium`, `xvfb`, `xauth`, `fonts-noto-cjk`, `fonts-wqy-microhei`, `fonts-wqy-zenhei`, `python3`, `python3-venv`, `supervisor`, `curl` 等。
- 自动生成并配置 `zh_CN.UTF-8` 语言环境，防止控制台中文乱码。
- **自动安装 Chromium Wrapper**：在 `/usr/local/bin/chromium` 注入专用启动垫片，自动添加 `--no-sandbox`、`--disable-dev-shm-usage`、`--disable-gpu` 等关键参数。DrissionPage 默认以 root 执行 Chromium 时不会再报错。
- 自动创建并激活 Python 虚拟环境 `/root/boss_auto_greet_k50u/venv`。
- 配置清华 PyPI 镜像源并安装 `requirements.txt`（包含 `nicegui` 与 `DrissionPage`）。
- 自动将 `boss_bot.conf` 复制到 `/etc/supervisor/conf.d/boss_bot.conf` 并载入服务。

---

## 七、 第五步：Supervisor 守护进程配置与管理 (`boss_bot.conf`)

`boss_bot.conf` 已经通过初始化脚本自动部署至 `/etc/supervisor/conf.d/boss_bot.conf`。

### 1. 核心启动机制解析
```ini
command=/usr/bin/xvfb-run -a --server-args="-screen 0 1920x1080x24" /root/boss_auto_greet_k50u/venv/bin/python /root/boss_auto_greet_k50u/app.py
```
- **为什么使用 xvfb-run**：常规无头浏览器（Headless Chrome）会被各大反爬系统（包括 Cloudflare、极验、BOSS直聘防爬组件）通过 Canvas 指纹、WebGL 渲染特征瞬间识破并加重风控。`xvfb-run` 在 Linux 内存中开辟了一块真正的 1920x1080 虚拟显存屏幕，让 Chromium 完全工作在标准的**有头桌面模式**下，彻底消除反爬指纹异常。
- **进程组安全回收**：设置了 `stopasgroup=true` 与 `killasgroup=true`，当重启或停止服务时，会连同虚拟屏幕与 Chromium 及其衍生进程干净回收，防止后台堆积僵尸进程。

### 2. 常用管理指令
在容器内可随时使用以下指令管理应用：

```bash
# 查看运行状态 (应显示 RUNNING 状态与 pid)
supervisorctl status boss_bot

# 实时查看输出日志 (NiceGUI 与任务打招呼运行输出)
supervisorctl tail -f boss_bot stdout

# 实时查看错误日志
supervisorctl tail -f boss_bot stderr

# 重启任务程序 (热更新配置或重新拉起)
supervisorctl restart boss_bot

# 停止任务程序
supervisorctl stop boss_bot

# 启动任务程序
supervisorctl start boss_bot
```

---

## 八、 第六步：局域网 Web 控制台访问与测试

Debian Chroot 容器与 Android 宿主共享网络命名空间（Host Network Mode）。这意味着在容器内启动的端口，直接绑定在手机的 Wi-Fi 局域网 IP 上！

### 1. 获取手机局域网 IP
在手机上查看已连接 Wi-Fi 的 IP 地址（例如 `192.168.1.168`），或者在安卓终端执行：
```bash
ip addr show wlan0 | grep "inet "
```

### 2. 跨设备访问控制台
在同一局域网内的 **电脑、平板、甚至 iPhone** 的浏览器地址栏输入：
```text
http://192.168.1.168:8080
```
（注：默认端口为 `8080`，若被占用系统会自动递增至 `8081`、`8082` 等，可在终端日志中查看）。

你将看到精美的 **NiceGUI 现代化控制台**：
- **左侧面板**：岗位黑名单、必含词、薪资过滤、目标城市、投递打招呼语等参数随时在线调整保存。
- **右侧面板**：实时打招呼计数器、HR 活跃度过滤日志、当前进度条以及执行终端。
- 点击【开始打招呼】，手机上的骁龙 8+ Gen 1 芯片即开始在后台静默高效处理投递！

---

## 九、 常见问题与排错指南 (FAQ)

### Q1: 手机重启后，脚本真的会自动运行吗？
**答**：是的！
开机执行链路如下：
1. Android 开机完成 -> 触发 KernelSU 的 `/data/adb/service.d/2_ksu_boot_service.sh`；
2. 脚本写入 CPU 唤醒锁 + 解除幽灵进程杀手限制；
3. 挂载 Debian 容器虚拟文件系统；
4. 容器内调用 `/etc/init.d/supervisor start`；
5. Supervisor 读取 `/etc/supervisor/conf.d/boss_bot.conf` 中设置的 `autostart=true`，自动执行 `xvfb-run` 拉起 Python 虚拟环境中的 `app.py`。
可查看日志文件确认：
- 安卓宿主开机日志：`/data/adb/service.d/ksu_boot_service.log`
- 容器内服务运行日志：`/root/boss_auto_greet_k50u/supervisor_stdout.log`

### Q2: 提示 `Running as root without --no-sandbox is not supported` 怎么处理？
**答**：`1_setup_debian.sh` 已经在 `/usr/local/bin/chromium` 与 `/usr/local/bin/google-chrome` 配置了垫片（Wrapper）。
如果手动运行仍出现该提示，请检查 `$PATH` 变量中 `/usr/local/bin` 是否位于 `/usr/bin` 前面，或者确认软链接是否存在：
```bash
ls -l /usr/local/bin/chromium
# 正常应指向 /usr/local/bin/chromium-wrapped
```

### Q3: 运行中突然提示“检测到安全验证弹窗/滑块验证码”怎么办？
**答**：系统内置了安全拦截保护逻辑：
- 当页面触发滑块时，脚本会自动暂停打招呼，前端界面会显示橙色警告：“等待手动完成滑块验证”。
- 遇到此情况时，可以在 PC 端重新运行一次 `run.bat` 并完成手动滑块，然后将 PC 最新的 `boss_browser_data` 再次同步到手机即可；或者也可以在容器内安装 `x11vnc` 远程桌面查看并滑动。
- 绝大多数情况下，只要使用 PC 登录良好的 `boss_browser_data`，并且每次打招呼保持内置的模拟随机休眠（`2.5 ~ 5.0 秒`），极少触发二次验证。

### Q4: 提示中文字符显示为方框或乱码（豆腐块）？
**答**：初始化脚本已经安装了 `fonts-noto-cjk`、`fonts-wqy-microhei`、`fonts-wqy-zenhei`。
如仍有个别生僻字乱码，可在容器内执行刷新字体缓存：
```bash
fc-cache -fv
```

### Q5: 息屏一段时间后，局域网网页无法打开？
**答**：这是小米 MIUI/HyperOS 的神隐模式（电池深度省电）将 Wi-Fi 休眠了。
请按以下步骤优化手机系统设置：
1. 进入手机【设置】->【WLAN】->【高级设置】-> 开启【休眠状态下保持 WLAN 连接】。
2. 进入【设置】->【电池】-> 开启【性能模式】。
3. 确认 `2_ksu_boot_service.sh` 中成功写入了 `/sys/power/wake_lock`（锁定了 CPU 状态）。
