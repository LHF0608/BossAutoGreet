#!/usr/bin/env bash
# ==============================================================================
# 脚本名称: 1_setup_debian.sh
# 适用环境: Redmi K50 Ultra (骁龙 8+ Gen 1) - Debian 12 (Bookworm) ARM64 Chroot 容器
# 功能说明: 自动化初始化 Debian 运行环境，安装 Chromium、Xvfb、中文字体、Supervisor 及 Python 虚拟环境
# ==============================================================================

set -euo pipefail

# 终端输出着色
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

echo -e "${BLUE}================================================================${NC}"
echo -e "${BLUE}  Redmi K50 Ultra - Debian 12 ARM64 Chroot 容器自动化部署脚本   ${NC}"
echo -e "${BLUE}  项目: BOSS直聘自动化打招呼系统 (DrissionPage + NiceGUI)       ${NC}"
echo -e "${BLUE}================================================================${NC}"

# 1. 检查 root 权限
if [ "$(id -u)" -ne 0 ]; then
    echo -e "${RED}[错误] 本脚本必须在容器内以 root 权限执行！${NC}"
    exit 1
fi

# 2. 定位项目路径 (deploy_k50u 的上一级即为项目根目录)
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(cd "${SCRIPT_DIR}/.." && pwd)"
echo -e "${GREEN}[*] 检测到项目根目录: ${PROJECT_DIR}${NC}"

# 3. 设置非交互环境与基础变量
export DEBIAN_FRONTEND=noninteractive
export LC_ALL=C.UTF-8
export LANG=C.UTF-8

# 4. 更新软件源
echo -e "${YELLOW}[1/6] 正在更新 Debian 软件源索引 (apt update)...${NC}"
apt-get update -y

# 5. 安装必要系统依赖
echo -e "${YELLOW}[2/6] 正在安装系统基础依赖与运行组件...${NC}"
echo -e "       - 浏览器引擎: chromium"
echo -e "       - 虚拟显示器: xvfb, xauth"
echo -e "       - 中文字体包: fonts-noto-cjk, fonts-wqy-microhei, fonts-wqy-zenhei"
echo -e "       - Python环境: python3, python3-pip, python3-venv, python3-dev"
echo -e "       - 进程守护器: supervisor"
echo -e "       - 辅助工具包: curl, wget, ca-certificates, locales, procps, psmisc, dbus-x11"

apt-get install -y --no-install-recommends \
    chromium \
    xvfb \
    xauth \
    fonts-noto-cjk \
    fonts-wqy-microhei \
    fonts-wqy-zenhei \
    python3 \
    python3-pip \
    python3-venv \
    python3-dev \
    supervisor \
    curl \
    wget \
    ca-certificates \
    locales \
    procps \
    psmisc \
    dbus-x11

# 6. 配置 UTF-8 中文语言环境，防止 Python 及终端输出中文字符乱码
echo -e "${YELLOW}[3/6] 配置系统本地化语言支持 (zh_CN.UTF-8 & en_US.UTF-8)...${NC}"
if [ -f /etc/locale.gen ]; then
    sed -i 's/# zh_CN.UTF-8 UTF-8/zh_CN.UTF-8 UTF-8/' /etc/locale.gen || true
    sed -i 's/# en_US.UTF-8 UTF-8/en_US.UTF-8 UTF-8/' /etc/locale.gen || true
    locale-gen || true
fi
export LANG=zh_CN.UTF-8
export LC_ALL=zh_CN.UTF-8

# 7. 配置 Chromium ARM64 / Root 运行垫片 (Wrapper)
# 核心作用:
# 1) Linux Chroot 环境下默认以 root 身份运行，原生 Chromium 会拒绝执行报错:
#    "Running as root without --no-sandbox is not supported."
# 2) 容器内 /dev/shm 共享内存可能受限，添加 --disable-dev-shm-usage 防止浏览器随机 SIGBUS 崩溃。
# 3) 垫片脚本置于 /usr/local/bin，优先级高于系统 /usr/bin，并软链接 google-chrome，让 DrissionPage 自动调用。
echo -e "${YELLOW}[4/6] 配置 Chromium 容器启动垫片 (自动注入 --no-sandbox 等参数)...${NC}"

cat << 'EOF' > /usr/local/bin/chromium-wrapped
#!/bin/sh
exec /usr/bin/chromium \
    --no-sandbox \
    --disable-setuid-sandbox \
    --disable-dev-shm-usage \
    --disable-gpu \
    --disable-software-rasterizer \
    --disable-extensions \
    --no-first-run \
    "$@"
EOF
chmod +x /usr/local/bin/chromium-wrapped

# 软链接拦截，使得调用 chromium 或 google-chrome 均走封装后的垫片
ln -sf /usr/local/bin/chromium-wrapped /usr/local/bin/chromium
ln -sf /usr/local/bin/chromium-wrapped /usr/local/bin/google-chrome
echo -e "${GREEN}[+] Chromium 垫片已成功就绪: /usr/local/bin/chromium & /usr/local/bin/google-chrome${NC}"

# 8. 配置 Python 虚拟环境并安装 Python 依赖
echo -e "${YELLOW}[5/6] 配置 Python 虚拟环境与项目依赖...${NC}"
cd "${PROJECT_DIR}"

if [ ! -d "${PROJECT_DIR}/venv" ]; then
    echo -e "${BLUE}[*] 创建 Python 虚拟环境: ${PROJECT_DIR}/venv${NC}"
    python3 -m venv "${PROJECT_DIR}/venv"
else
    echo -e "${GREEN}[*] 虚拟环境已存在，跳过新建。${NC}"
fi

# 确保 pip 为最新版，并配置国内清华 PyPI 源加速下载
echo -e "${BLUE}[*] 配置 PyPI 国内清华源加速...${NC}"
"${PROJECT_DIR}/venv/bin/pip" config set global.index-url https://pypi.tuna.tsinghua.edu.cn/simple || true
"${PROJECT_DIR}/venv/bin/pip" install --upgrade pip

# 安装依赖文件
if [ -f "${PROJECT_DIR}/requirements.txt" ]; then
    echo -e "${BLUE}[*] 正在安装 requirements.txt 依赖...${NC}"
    "${PROJECT_DIR}/venv/bin/pip" install -r "${PROJECT_DIR}/requirements.txt"
else
    echo -e "${YELLOW}[!] 未检测到 requirements.txt，安装默认核心依赖...${NC}"
    "${PROJECT_DIR}/venv/bin/pip" install "nicegui>=3.18.0" "DrissionPage>=4.1.1.4"
fi
echo -e "${GREEN}[+] Python 依赖安装完成！${NC}"

# 9. 部署 Supervisor 配置
echo -e "${YELLOW}[6/6] 部署并初始化 Supervisor 守护进程...${NC}"
mkdir -p /etc/supervisor/conf.d
mkdir -p /var/log/supervisor

CONF_SOURCE="${SCRIPT_DIR}/boss_bot.conf"
CONF_TARGET="/etc/supervisor/conf.d/boss_bot.conf"

if [ -f "${CONF_SOURCE}" ]; then
    echo -e "${BLUE}[*] 安装 Supervisor 配置文件至: ${CONF_TARGET}${NC}"
    # 动态将模板中的默认路径替换为当前检测到的实际项目路径
    sed "s|/root/boss_auto_greet_k50u|${PROJECT_DIR}|g" "${CONF_SOURCE}" > "${CONF_TARGET}"
    echo -e "${GREEN}[+] Supervisor 配置文件已动态适配并安装。${NC}"
else
    echo -e "${RED}[警告] 未在 ${SCRIPT_DIR} 找到 boss_bot.conf，请手动确认配置！${NC}"
fi

# 启动或重载 Supervisor 服务
echo -e "${BLUE}[*] 启动 Supervisor 服务...${NC}"
service supervisor start >/dev/null 2>&1 || service supervisor restart >/dev/null 2>&1 || true

echo -e "\n${GREEN}================================================================${NC}"
echo -e "${GREEN}🎉 Debian ARM64 容器运行环境初始化全部完成！${NC}"
echo -e "${GREEN}项目根目录: ${PROJECT_DIR}${NC}"
echo -e "${GREEN}虚拟环境路径: ${PROJECT_DIR}/venv${NC}"
echo -e "${GREEN}================================================================${NC}"
echo -e "后续快捷运维命令:"
echo -e "  - 重新加载配置: supervisorctl reread && supervisorctl update"
echo -e "  - 查看服务状态: supervisorctl status boss_bot"
echo -e "  - 实时查看日志: supervisorctl tail -f boss_bot stdout"
echo -e "  - 重启任务服务: supervisorctl restart boss_bot"
echo -e "  - 停止任务服务: supervisorctl stop boss_bot"
echo -e "  - 本地网页访问: http://<手机WLAN_IP>:8080\n"
