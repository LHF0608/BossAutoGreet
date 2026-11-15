#!/system/bin/sh
# ==============================================================================
# 脚本名称: 2_ksu_boot_service.sh
# 适用机型: Redmi K50 Ultra (骁龙 8+ Gen 1, Android 12/13/14 / HyperOS)
# 部署路径: /data/adb/service.d/2_ksu_boot_service.sh
# 功能说明: KernelSU 开机自启保活服务
#           1. 等待安卓完全开机与网络就绪
#           2. 锁定 CPU WakeLock，防止息屏后 CPU 休眠与 Wi-Fi 断连
#           3. 解除 Android 12+ 幽灵进程上限 (Phantom Process Killer) 限制
#           4. 挂载 Debian 容器虚拟文件系统并启动 Supervisor / SSH 守护服务
# ==============================================================================

LOG_FILE="/data/adb/service.d/ksu_boot_service.log"

log() {
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] $1" >> "$LOG_FILE"
}

log "========================================================"
log "Redmi K50 Ultra - KernelSU 开机保活自启服务启动..."

# ------------------------------------------------------------------------------
# 1. 等待安卓系统完全开机完成
# ------------------------------------------------------------------------------
log "[1/4] 等待 Android 启动标记 sys.boot_completed..."
while [ "$(getprop sys.boot_completed)" != "1" ]; do
    sleep 2
done
log "[+] 检测到系统开机已就绪，缓冲 5 秒等待网络与存储就绪..."
sleep 5

# ------------------------------------------------------------------------------
# 2. 锁定 CPU 唤醒锁 (Wake Lock) 保持全天候高频响应
# ------------------------------------------------------------------------------
log "[2/4] 配置 CPU 唤醒锁与防止后台休眠..."
if [ -e /sys/power/wake_lock ]; then
    echo "boss_bot_keepalive" > /sys/power/wake_lock
    log "[+] 成功向 /sys/power/wake_lock 写入 boss_bot_keepalive 唤醒锁"
else
    log "[!] /sys/power/wake_lock 不存在，跳过原生写入"
fi

# ------------------------------------------------------------------------------
# 3. 解除 Android 12+ 幽灵进程杀手 (Phantom Process Killer)
#    解决多进程 Chromium/Python 在后台被 Android 强行 SIGKILL 闪退的关键
# ------------------------------------------------------------------------------
log "[3/4] 解除 Android 12+ 幽灵进程 (Phantom Process) 限制..."
/system/bin/device_config put activity_manager max_phantom_processes 2147483647 2>/dev/null || true
/system/bin/setprop persist.sys.fflag.override.settings_enable_monitor_phantom_procs false 2>/dev/null || true
log "[+] 已将 max_phantom_processes 设置为最大整数限制 (2147483647)"

# ------------------------------------------------------------------------------
# 4. Debian 12 ARM64 Chroot 容器挂载与服务拉起
# ------------------------------------------------------------------------------
# Debian 容器在手机内部存储的根路径 (根据你的实际部署路径配置，常见为 /data/debian)
DEBIAN_ROOT="/data/debian"

log "[4/4] 检查并挂载 Debian 容器环境: ${DEBIAN_ROOT}..."

if [ ! -d "${DEBIAN_ROOT}" ]; then
    log "[错误] 容器根目录 ${DEBIAN_ROOT} 不存在！请检查路径配置。"
    exit 1
fi

# 挂载必要的虚拟文件系统 (若未挂载则挂载)
mount_if_needed() {
    local target="$1"
    local type="$2"
    local source="$3"
    local options="$4"

    if ! grep -q " ${target} " /proc/mounts; then
        mkdir -p "${target}"
        if [ -n "${options}" ]; then
            mount -t "${type}" -o "${options}" "${source}" "${target}"
        else
            mount -t "${type}" "${source}" "${target}"
        fi
        log "  [挂载] ${target} (${type})"
    fi
}

# 挂载 /proc, /sys, /dev, /dev/pts, /dev/shm
mount_if_needed "${DEBIAN_ROOT}/proc" "proc" "proc" ""
mount_if_needed "${DEBIAN_ROOT}/sys" "sysfs" "sysfs" ""

if ! grep -q " ${DEBIAN_ROOT}/dev " /proc/mounts; then
    mount -o bind /dev "${DEBIAN_ROOT}/dev"
    log "  [挂载] ${DEBIAN_ROOT}/dev (bind)"
fi

mount_if_needed "${DEBIAN_ROOT}/dev/pts" "devpts" "devpts" ""
# /dev/shm 必须为足够的 tmpfs，否则 Chromium 多标签通信容易发生崩溃
mount_if_needed "${DEBIAN_ROOT}/dev/shm" "tmpfs" "tmpfs" "size=1G"

# 同步 DNS 配置文件，保证容器内网络解析通畅
if [ -f /system/etc/resolv.conf ]; then
    cp -f /system/etc/resolv.conf "${DEBIAN_ROOT}/etc/resolv.conf" 2>/dev/null || true
fi
if [ ! -s "${DEBIAN_ROOT}/etc/resolv.conf" ]; then
    echo "nameserver 223.5.5.5" > "${DEBIAN_ROOT}/etc/resolv.conf"
    echo "nameserver 119.29.29.29" >> "${DEBIAN_ROOT}/etc/resolv.conf"
    echo "nameserver 8.8.8.8" >> "${DEBIAN_ROOT}/etc/resolv.conf"
fi

# 启动容器内部服务: SSH (方便远程调试) + Supervisor (自启 boss_bot)
log "[+] 正在容器内拉起 SSH 与 Supervisor 守护服务..."
/system/bin/chroot "${DEBIAN_ROOT}" /bin/bash -c "
    export PATH=/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin
    # 启动 SSH 服务 (若已安装 openssh-server)
    if [ -x /etc/init.d/ssh ]; then
        /etc/init.d/ssh start >/dev/null 2>&1 || true
    fi
    # 重启或拉起 Supervisor 守护进程
    if [ -x /etc/init.d/supervisor ]; then
        /etc/init.d/supervisor restart >/dev/null 2>&1 || /etc/init.d/supervisor start >/dev/null 2>&1 || true
    fi
"

log "🎉 KernelSU 开机保活与容器拉起流程全部完成！"
log "========================================================"
