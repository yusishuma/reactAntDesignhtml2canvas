#!/bin/bash

DEPLOY_PATH="${DEPLOY_PATH:-/opt/app}"
BACKUP_PATH="${BACKUP_PATH:-/opt/backups}"
MAX_BACKUPS=5

log() {
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] $1"
}

create_backup() {
    log "创建备份..."
    mkdir -p "$BACKUP_PATH"
    
    local backup_name="backup_$(date +%Y%m%d_%H%M%S)"
    local backup_file="$BACKUP_PATH/${backup_name}.tar.gz"
    
    tar -czf "$backup_file" -C "$DEPLOY_PATH" . 2>/dev/null
    
    log "备份已创建: $backup_file"
    
    ls -t "$BACKUP_PATH"/backup_*.tar.gz 2>/dev/null | tail -n +$((MAX_BACKUPS + 1)) | xargs rm -f 2>/dev/null
}

rollback() {
    local backup_file="$1"
    
    if [ ! -f "$backup_file" ]; then
        log "错误: 备份文件不存在: $backup_file"
        return 1
    fi
    
    log "开始回滚..."
    
    cd "$DEPLOY_PATH" || return 1
    
    docker compose down
    
    tar -xzf "$backup_file" -C "$DEPLOY_PATH"
    
    docker compose up -d
    
    log "回滚完成"
}

check_deployment() {
    log "检查部署状态..."
    
    local max_retries=30
    local retry=0
    
    while [ $retry -lt $max_retries ]; do
        if curl -sf http://localhost:8000/health > /dev/null; then
            log "部署成功！应用运行正常。"
            return 0
        fi
        
        retry=$((retry + 1))
        log "等待应用启动... ($retry/$max_retries)"
        sleep 2
    done
    
    log "错误: 应用启动失败"
    return 1
}

case "$1" in
    backup)
        create_backup
        ;;
    rollback)
        if [ -z "$2" ]; then
            echo "用法: $0 rollback <backup_file>"
            exit 1
        fi
        rollback "$2"
        ;;
    check)
        check_deployment
        ;;
    *)
        echo "用法: $0 {backup|rollback|check}"
        exit 1
        ;;
esac
