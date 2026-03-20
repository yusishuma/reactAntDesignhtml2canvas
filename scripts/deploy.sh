#!/bin/bash

# =============================================================================
# 自动化部署脚本
# 用途：部署 Docker Compose 应用到生产环境
# =============================================================================

set -euo pipefail

# 颜色定义
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# 配置变量
APP_NAME="user-management-api"
APP_DIR="/opt/app"
BACKUP_DIR="/opt/backups"
LOG_DIR="/var/log/${APP_NAME}"
MAX_BACKUPS=5
HEALTH_CHECK_TIMEOUT=60
HEALTH_CHECK_INTERVAL=5

# 日志函数
log_info() {
    echo -e "${BLUE}[INFO]${NC} $(date '+%Y-%m-%d %H:%M:%S') - $1"
}

log_success() {
    echo -e "${GREEN}[SUCCESS]${NC} $(date '+%Y-%m-%d %H:%M:%S') - $1"
}

log_warning() {
    echo -e "${YELLOW}[WARNING]${NC} $(date '+%Y-%m-%d %H:%M:%S') - $1"
}

log_error() {
    echo -e "${RED}[ERROR]${NC} $(date '+%Y-%m-%d %H:%M:%S') - $1"
}

# 错误处理
error_exit() {
    log_error "$1"
    exit 1
}

# 检查命令是否存在
check_command() {
    if ! command -v "$1" &> /dev/null; then
        error_exit "$1 命令未找到，请先安装"
    fi
}

# 检查 Docker 和 Docker Compose
check_prerequisites() {
    log_info "检查前置条件..."
    
    check_command docker
    check_command docker-compose
    
    # 检查 Docker 守护进程
    if ! docker info &> /dev/null; then
        error_exit "Docker 守护进程未运行"
    fi
    
    log_success "前置条件检查通过"
}

# 创建必要的目录
setup_directories() {
    log_info "设置目录结构..."
    
    mkdir -p "${APP_DIR}"/{data,logs,scripts,nginx/ssl}
    mkdir -p "${BACKUP_DIR}"
    mkdir -p "${LOG_DIR}"
    
    # 设置权限
    chmod 755 "${APP_DIR}"
    chmod 700 "${BACKUP_DIR}"
    
    log_success "目录结构创建完成"
}

# 备份当前版本
backup_current() {
    log_info "备份当前版本..."
    
    if [ -f "${APP_DIR}/docker-compose.yml" ]; then
        local backup_name="backup_$(date +%Y%m%d_%H%M%S)"
        local backup_path="${BACKUP_DIR}/${backup_name}"
        
        mkdir -p "${backup_path}"
        
        # 备份配置文件
        cp "${APP_DIR}/docker-compose.yml" "${backup_path}/"
        cp "${APP_DIR}/.env" "${backup_path}/" 2>/dev/null || true
        
        # 备份数据（如果存在）
        if [ -d "${APP_DIR}/data" ]; then
            tar -czf "${backup_path}/data.tar.gz" -C "${APP_DIR}" data/ 2>/dev/null || true
        fi
        
        # 备份镜像标签
        docker-compose -f "${APP_DIR}/docker-compose.yml" config --images > "${backup_path}/images.txt" 2>/dev/null || true
        
        log_success "备份完成: ${backup_path}"
        
        # 清理旧备份
        cleanup_old_backups
    else
        log_warning "没有找到现有的部署，跳过备份"
    fi
}

# 清理旧备份
cleanup_old_backups() {
    log_info "清理旧备份..."
    
    local backup_count=$(ls -1d "${BACKUP_DIR}"/backup_* 2>/dev/null | wc -l)
    
    if [ "$backup_count" -gt "$MAX_BACKUPS" ]; then
        ls -1td "${BACKUP_DIR}"/backup_* | tail -n +$((MAX_BACKUPS + 1)) | xargs rm -rf
        log_success "已清理旧备份，保留最近 ${MAX_BACKUPS} 个"
    fi
}

# 拉取最新镜像
pull_images() {
    log_info "拉取最新镜像..."
    
    cd "${APP_DIR}"
    
    # 登录到 GitHub Container Registry
    if [ -f "${APP_DIR}/.env" ]; then
        export $(grep -v '^#' "${APP_DIR}/.env" | xargs)
    fi
    
    docker-compose pull
    
    log_success "镜像拉取完成"
}

# 停止旧版本
stop_old_version() {
    log_info "停止旧版本..."
    
    cd "${APP_DIR}"
    
    if docker-compose ps -q &> /dev/null; then
        docker-compose down --remove-orphans
        log_success "旧版本已停止"
    else
        log_warning "没有运行中的容器"
    fi
}

# 启动新版本
start_new_version() {
    log_info "启动新版本..."
    
    cd "${APP_DIR}"
    
    # 启动服务
    docker-compose up -d
    
    log_success "新版本已启动"
}

# 健康检查
health_check() {
    log_info "执行健康检查..."
    
    local elapsed=0
    local healthy=false
    
    while [ $elapsed -lt $HEALTH_CHECK_TIMEOUT ]; do
        if docker-compose ps | grep -q "healthy"; then
            healthy=true
            break
        fi
        
        # 检查容器是否运行
        if ! docker-compose ps | grep -q "Up"; then
            log_error "容器未正常运行"
            return 1
        fi
        
        log_info "等待服务就绪... (${elapsed}s/${HEALTH_CHECK_TIMEOUT}s)"
        sleep $HEALTH_CHECK_INTERVAL
        elapsed=$((elapsed + HEALTH_CHECK_INTERVAL))
    done
    
    if [ "$healthy" = true ]; then
        log_success "健康检查通过"
        return 0
    else
        log_error "健康检查超时"
        return 1
    fi
}

# 回滚操作
rollback() {
    log_warning "执行回滚操作..."
    
    cd "${APP_DIR}"
    
    # 停止当前失败的部署
    docker-compose down --remove-orphans 2>/dev/null || true
    
    # 找到最新的备份
    local latest_backup=$(ls -1td "${BACKUP_DIR}"/backup_* 2>/dev/null | head -1)
    
    if [ -n "$latest_backup" ] && [ -f "${latest_backup}/docker-compose.yml" ]; then
        log_info "恢复到备份: ${latest_backup}"
        
        # 恢复配置文件
        cp "${latest_backup}/docker-compose.yml" "${APP_DIR}/"
        cp "${latest_backup}/.env" "${APP_DIR}/" 2>/dev/null || true
        
        # 恢复数据
        if [ -f "${latest_backup}/data.tar.gz" ]; then
            rm -rf "${APP_DIR}/data"
            tar -xzf "${latest_backup}/data.tar.gz" -C "${APP_DIR}"
        fi
        
        # 重新启动
        docker-compose up -d
        
        log_success "回滚完成"
    else
        log_error "没有找到可用的备份"
    fi
}

# 清理旧镜像
cleanup_images() {
    log_info "清理未使用的镜像..."
    
    docker image prune -af --filter "until=168h" || true
    docker volume prune -f || true
    
    log_success "镜像清理完成"
}

# 显示部署信息
show_deployment_info() {
    log_info "部署信息:"
    echo "========================================"
    cd "${APP_DIR}"
    docker-compose ps
    echo "========================================"
    docker-compose images
    echo "========================================"
}

# 主函数
main() {
    log_info "开始部署 ${APP_NAME}..."
    
    # 检查是否在正确的目录
    if [ ! -f "${APP_DIR}/docker-compose.yml" ]; then
        error_exit "未找到 docker-compose.yml 文件，请确保在正确的目录"
    fi
    
    # 执行部署步骤
    check_prerequisites
    setup_directories
    backup_current
    pull_images
    stop_old_version
    start_new_version
    
    # 健康检查
    if health_check; then
        log_success "部署成功！"
        cleanup_images
        show_deployment_info
        
        # 记录部署日志
        echo "$(date '+%Y-%m-%d %H:%M:%S') - 部署成功" >> "${LOG_DIR}/deploy.log"
    else
        log_error "部署失败，执行回滚..."
        rollback
        
        # 记录部署日志
        echo "$(date '+%Y-%m-%d %H:%M:%S') - 部署失败，已回滚" >> "${LOG_DIR}/deploy.log"
        exit 1
    fi
}

# 处理命令行参数
case "${1:-}" in
    backup)
        backup_current
        ;;
    rollback)
        rollback
        ;;
    cleanup)
        cleanup_images
        ;;
    health)
        health_check
        ;;
    *)
        main
        ;;
esac
