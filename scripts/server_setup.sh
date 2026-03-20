#!/bin/bash

set -e

APP_NAME="fastapi_app"
DEPLOY_PATH="${DEPLOY_PATH:-/opt/app}"
MONITOR_INTERVAL=60

log() {
    echo "[Setup] $1"
}

check_root() {
    if [ "$EUID" -ne 0 ]; then
        log "请使用 root 权限运行此脚本"
        exit 1
    fi
}

install_docker() {
    if command -v docker &> /dev/null; then
        log "Docker 已安装"
    else
        log "安装 Docker..."
        curl -fsSL https://get.docker.com | sh
        systemctl enable docker
        systemctl start docker
        log "Docker 安装完成"
    fi
}

install_docker_compose() {
    if command -v docker compose &> /dev/null; then
        log "Docker Compose 已安装"
    else
        log "安装 Docker Compose..."
        apt-get update
        apt-get install -y docker-compose-plugin
        log "Docker Compose 安装完成"
    fi
}

setup_deploy_user() {
    local username="deploy"
    
    if id "$username" &>/dev/null; then
        log "用户 $username 已存在"
    else
        log "创建部署用户 $username..."
        useradd -m -s /bin/bash "$username"
        usermod -aG docker "$username"
        log "用户创建完成"
    fi
    
    log "设置 SSH 目录..."
    mkdir -p "/home/$username/.ssh"
    touch "/home/$username/.ssh/authorized_keys"
    chmod 700 "/home/$username/.ssh"
    chmod 600 "/home/$username/.ssh/authorized_keys"
    chown -R "$username:$username" "/home/$username/.ssh"
}

setup_app_directory() {
    log "创建应用目录..."
    mkdir -p "$DEPLOY_PATH"
    mkdir -p "$DEPLOY_PATH/logs"
    mkdir -p "$DEPLOY_PATH/nginx/ssl"
    mkdir -p "/opt/backups"
    
    if [ -d "$DEPLOY_PATH" ]; then
        chown -R deploy:deploy "$DEPLOY_PATH"
        chown -R deploy:deploy "/opt/backups"
    fi
}

setup_cron() {
    log "设置定时任务..."
    
    local cron_job="*/$MONITOR_INTERVAL * * * * $DEPLOY_PATH/scripts/monitor.sh >> /var/log/app_monitor.log 2>&1"
    
    (crontab -u deploy -l 2>/dev/null | grep -v "monitor.sh"; echo "$cron_job") | crontab -u deploy -
    
    log "定时任务设置完成"
}

setup_logrotate() {
    log "设置日志轮转..."
    
    cat > /etc/logrotate.d/app_monitor << EOF
/var/log/app_monitor.log {
    daily
    rotate 7
    compress
    missingok
    notifempty
    create 0644 deploy deploy
}
EOF
    
    log "日志轮转设置完成"
}

setup_firewall() {
    log "配置防火墙..."
    
    if command -v ufw &> /dev/null; then
        ufw allow 22/tcp
        ufw allow 80/tcp
        ufw allow 443/tcp
        ufw --force enable
        log "防火墙配置完成"
    else
        log "ufw 未安装，跳过防火墙配置"
    fi
}

main() {
    log "=========================================="
    log "开始服务器初始化"
    log "=========================================="
    
    check_root
    install_docker
    install_docker_compose
    setup_deploy_user
    setup_app_directory
    setup_cron
    setup_logrotate
    setup_firewall
    
    log "=========================================="
    log "初始化完成！"
    log "=========================================="
    log ""
    log "下一步操作："
    log "1. 将 SSH 公钥添加到 /home/deploy/.ssh/authorized_keys"
    log "2. 在 GitHub 仓库设置 Secrets:"
    log "   - SERVER_HOST: 服务器 IP"
    log "   - SERVER_USER: deploy"
    log "   - SSH_PRIVATE_KEY: SSH 私钥"
    log "   - DEPLOY_PATH: $DEPLOY_PATH"
    log "3. 推送代码到 main 分支触发部署"
}

main "$@"
