#!/bin/bash

# =============================================================================
# 服务器初始化脚本
# 用途：在新服务器上快速配置部署环境
# =============================================================================

set -euo pipefail

# 颜色定义
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

log_info() { echo -e "${BLUE}[INFO]${NC} $1"; }
log_success() { echo -e "${GREEN}[SUCCESS]${NC} $1"; }
log_warning() { echo -e "${YELLOW}[WARNING]${NC} $1"; }
log_error() { echo -e "${RED}[ERROR]${NC} $1"; }

# 配置变量
APP_NAME="user-management-api"
APP_DIR="/opt/app"
APP_USER="appuser"
DOCKER_COMPOSE_VERSION="v2.23.0"

# 检查 root 权限
check_root() {
    if [ "$EUID" -ne 0 ]; then
        log_error "请使用 root 权限运行此脚本"
        exit 1
    fi
}

# 更新系统
update_system() {
    log_info "更新系统包..."
    apt-get update && apt-get upgrade -y
    log_success "系统更新完成"
}

# 安装基础工具
install_base_tools() {
    log_info "安装基础工具..."
    
    apt-get install -y \
        curl \
        wget \
        git \
        vim \
        htop \
        net-tools \
        unzip \
        ca-certificates \
        gnupg \
        lsb-release \
        fail2ban \
        ufw
    
    log_success "基础工具安装完成"
}

# 安装 Docker
install_docker() {
    log_info "安装 Docker..."
    
    if command -v docker &> /dev/null; then
        log_warning "Docker 已安装，跳过"
        return
    fi
    
    # 添加 Docker 官方 GPG 密钥
    install -m 0755 -d /etc/apt/keyrings
    curl -fsSL https://download.docker.com/linux/ubuntu/gpg | gpg --dearmor -o /etc/apt/keyrings/docker.gpg
    chmod a+r /etc/apt/keyrings/docker.gpg
    
    # 添加 Docker 软件源
    echo \
        "deb [arch="$(dpkg --print-architecture)" signed-by=/etc/apt/keyrings/docker.gpg] https://download.docker.com/linux/ubuntu \
        "$(. /etc/os-release && echo "$VERSION_CODENAME")" stable" | \
        tee /etc/apt/sources.list.d/docker.list > /dev/null
    
    apt-get update
    apt-get install -y docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin
    
    # 启动 Docker
    systemctl enable docker
    systemctl start docker
    
    log_success "Docker 安装完成"
}

# 安装 Docker Compose
install_docker_compose() {
    log_info "安装 Docker Compose..."
    
    if command -v docker-compose &> /dev/null; then
        log_warning "Docker Compose 已安装，跳过"
        return
    fi
    
    curl -L "https://github.com/docker/compose/releases/download/${DOCKER_COMPOSE_VERSION}/docker-compose-$(uname -s)-$(uname -m)" -o /usr/local/bin/docker-compose
    chmod +x /usr/local/bin/docker-compose
    
    # 创建软链接
    ln -sf /usr/local/bin/docker-compose /usr/bin/docker-compose
    
    log_success "Docker Compose 安装完成"
}

# 配置防火墙
setup_firewall() {
    log_info "配置防火墙..."
    
    ufw default deny incoming
    ufw default allow outgoing
    
    # 允许 SSH
    ufw allow 22/tcp
    
    # 允许 HTTP/HTTPS
    ufw allow 80/tcp
    ufw allow 443/tcp
    
    # 允许应用端口
    ufw allow 8000/tcp
    
    # 启用防火墙
    echo "y" | ufw enable
    
    log_success "防火墙配置完成"
}

# 配置 Fail2ban
setup_fail2ban() {
    log_info "配置 Fail2ban..."
    
    cat > /etc/fail2ban/jail.local << 'EOF'
[DEFAULT]
bantime = 3600
findtime = 600
maxretry = 3

[sshd]
enabled = true
port = ssh
filter = sshd
logpath = /var/log/auth.log
maxretry = 3
EOF
    
    systemctl enable fail2ban
    systemctl restart fail2ban
    
    log_success "Fail2ban 配置完成"
}

# 创建应用用户和目录
setup_app_user() {
    log_info "创建应用用户和目录..."
    
    # 创建用户
    if ! id "$APP_USER" &>/dev/null; then
        useradd -m -s /bin/bash "$APP_USER"
        usermod -aG docker "$APP_USER"
        log_success "用户 $APP_USER 创建完成"
    else
        log_warning "用户 $APP_USER 已存在"
    fi
    
    # 创建应用目录
    mkdir -p "$APP_DIR"/{data,logs,scripts,nginx/ssl}
    chown -R "$APP_USER:$APP_USER" "$APP_DIR"
    chmod 755 "$APP_DIR"
    
    # 创建备份目录
    mkdir -p /opt/backups
    chmod 700 /opt/backups
    
    log_success "应用目录创建完成"
}

# 配置日志轮转
setup_logrotate() {
    log_info "配置日志轮转..."
    
    cat > /etc/logrotate.d/${APP_NAME} << EOF
${APP_DIR}/logs/*.log {
    daily
    rotate 30
    compress
    delaycompress
    missingok
    notifempty
    create 644 ${APP_USER} ${APP_USER}
    sharedscripts
    postrotate
        /usr/bin/docker-compose -f ${APP_DIR}/docker-compose.yml kill -s USR1 app 2>/dev/null || true
    endscript
}
EOF
    
    log_success "日志轮转配置完成"
}

# 配置时区
setup_timezone() {
    log_info "配置时区..."
    timedatectl set-timezone Asia/Shanghai
    log_success "时区配置完成"
}

# 配置 SSH 安全
setup_ssh_security() {
    log_info "配置 SSH 安全..."
    
    # 备份原配置
    cp /etc/ssh/sshd_config /etc/ssh/sshd_config.bak
    
    # 修改 SSH 配置
    sed -i 's/#PermitRootLogin yes/PermitRootLogin no/' /etc/ssh/sshd_config
    sed -i 's/#PasswordAuthentication yes/PasswordAuthentication no/' /etc/ssh/sshd_config
    sed -i 's/X11Forwarding yes/X11Forwarding no/' /etc/ssh/sshd_config
    
    # 重启 SSH
    systemctl restart sshd
    
    log_success "SSH 安全配置完成"
    log_warning "请确保已配置 SSH 密钥登录，否则可能无法连接"
}

# 创建 systemd 服务
setup_systemd_service() {
    log_info "创建 Systemd 服务..."
    
    cat > /etc/systemd/system/${APP_NAME}.service << EOF
[Unit]
Description=${APP_NAME} Application
Requires=docker.service
After=docker.service

[Service]
Type=oneshot
RemainAfterExit=yes
WorkingDirectory=${APP_DIR}
ExecStart=/usr/local/bin/docker-compose up -d
ExecStop=/usr/local/bin/docker-compose down
ExecReload=/usr/local/bin/docker-compose restart
User=${APP_USER}
Group=${APP_USER}

[Install]
WantedBy=multi-user.target
EOF
    
    systemctl daemon-reload
    systemctl enable ${APP_NAME}.service
    
    log_success "Systemd 服务创建完成"
}

# 配置定时任务
setup_cron() {
    log_info "配置定时任务..."
    
    # 创建健康检查定时任务
    cat > /etc/cron.d/${APP_NAME} << EOF
# ${APP_NAME} 定时任务
SHELL=/bin/bash
PATH=/usr/local/sbin:/usr/local/bin:/sbin:/bin:/usr/sbin:/usr/bin

# 每 5 分钟执行健康检查
*/5 * * * * root ${APP_DIR}/scripts/health-check.sh quick >> /var/log/${APP_NAME}/cron.log 2>&1

# 每天凌晨 3 点执行完整健康检查
0 3 * * * root ${APP_DIR}/scripts/health-check.sh >> /var/log/${APP_NAME}/cron.log 2>&1

# 每周日凌晨 4 点清理旧备份
0 4 * * 0 root ${APP_DIR}/scripts/deploy.sh cleanup >> /var/log/${APP_NAME}/cron.log 2>&1
EOF
    
    chmod 644 /etc/cron.d/${APP_NAME}
    
    log_success "定时任务配置完成"
}

# 显示配置信息
show_summary() {
    echo ""
    echo "========================================"
    echo "服务器初始化完成！"
    echo "========================================"
    echo ""
    echo "应用信息:"
    echo "  - 应用名称: $APP_NAME"
    echo "  - 应用目录: $APP_DIR"
    echo "  - 应用用户: $APP_USER"
    echo ""
    echo "服务状态:"
    echo "  - Docker: $(systemctl is-active docker)"
    echo "  - Fail2ban: $(systemctl is-active fail2ban)"
    echo ""
    echo "防火墙状态:"
    ufw status | grep -E "(Status|To|ALLOW)"
    echo ""
    echo "下一步操作:"
    echo "  1. 将应用代码复制到 ${APP_DIR}"
    echo "  2. 配置 .env 文件"
    echo "  3. 运行 ${APP_DIR}/scripts/deploy.sh 进行部署"
    echo ""
    echo "常用命令:"
    echo "  - 查看服务状态: systemctl status ${APP_NAME}"
    echo "  - 查看日志: journalctl -u ${APP_NAME} -f"
    echo "  - 健康检查: ${APP_DIR}/scripts/health-check.sh"
    echo "========================================"
}

# 主函数
main() {
    log_info "开始初始化服务器..."
    
    check_root
    update_system
    install_base_tools
    install_docker
    install_docker_compose
    setup_timezone
    setup_firewall
    setup_fail2ban
    setup_app_user
    setup_logrotate
    setup_systemd_service
    setup_cron
    
    # SSH 安全配置（可选）
    read -p "是否配置 SSH 安全（禁用 root 登录和密码认证）？[y/N] " -n 1 -r
    echo
    if [[ $REPLY =~ ^[Yy]$ ]]; then
        setup_ssh_security
    fi
    
    show_summary
}

# 执行主函数
main
