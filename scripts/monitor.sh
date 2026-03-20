#!/bin/bash

APP_NAME="fastapi_app"
HEALTH_URL="http://localhost:8000/health"
LOG_FILE="/var/log/app_monitor.log"
ALERT_WEBHOOK="${WEBHOOK_URL:-}"
MAX_RESTARTS=3
RESTART_WINDOW=3600

restart_count_file="/tmp/${APP_NAME}_restarts"
restart_timestamps_file="/tmp/${APP_NAME}_timestamps"

log() {
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] $1" | tee -a "$LOG_FILE"
}

send_alert() {
    local message="$1"
    log "ALERT: $message"
    
    if [ -n "$ALERT_WEBHOOK" ]; then
        curl -s -X POST "$ALERT_WEBHOOK" \
            -H 'Content-Type: application/json' \
            -d "{\"text\": \"$message\"}" > /dev/null
    fi
}

check_container_running() {
    if ! docker ps --format '{{.Names}}' | grep -q "^${APP_NAME}$"; then
        return 1
    fi
    return 0
}

check_health_endpoint() {
    local response
    response=$(curl -s -o /dev/null -w "%{http_code}" --max-time 10 "$HEALTH_URL" 2>/dev/null)
    
    if [ "$response" = "200" ]; then
        return 0
    fi
    return 1
}

check_container_health() {
    local health_status
    health_status=$(docker inspect --format='{{.State.Health.Status}}' "$APP_NAME" 2>/dev/null)
    
    if [ "$health_status" = "healthy" ]; then
        return 0
    fi
    return 1
}

record_restart() {
    local current_time=$(date +%s)
    
    echo "$current_time" >> "$restart_timestamps_file"
    
    local cutoff_time=$((current_time - RESTART_WINDOW))
    local count=0
    
    while IFS= read -r timestamp; do
        if [ "$timestamp" -ge "$cutoff_time" ]; then
            ((count++))
        fi
    done < "$restart_timestamps_file"
    
    echo "$count" > "$restart_count_file"
    
    return $count
}

restart_container() {
    local restarts
    restarts=$(record_restart)
    
    if [ "$restarts" -ge "$MAX_RESTARTS" ]; then
        send_alert "容器重启次数过多 ($restarts 次)，已停止自动重启。请手动检查！"
        return 1
    fi
    
    log "尝试重启容器... (第 $restarts 次)"
    
    cd /opt/app || return 1
    docker compose restart "$APP_NAME"
    
    sleep 10
    
    if check_container_running && check_health_endpoint; then
        log "容器重启成功"
        return 0
    else
        send_alert "容器重启失败"
        return 1
    fi
}

get_container_stats() {
    docker stats --no-stream --format \
        "CPU: {{.CPUPerc}}, Memory: {{.MemUsage}}, Network: {{.NetIO}}" \
        "$APP_NAME" 2>/dev/null || echo "无法获取统计信息"
}

main() {
    log "========== 健康检查开始 =========="
    
    if ! check_container_running; then
        log "错误: 容器未运行"
        send_alert "容器 $APP_NAME 未运行！"
        restart_container
        exit 1
    fi
    
    if ! check_container_health; then
        log "警告: 容器健康状态异常"
    fi
    
    if ! check_health_endpoint; then
        log "错误: 健康检查端点无响应"
        send_alert "健康检查端点无响应！"
        restart_container
        exit 1
    fi
    
    log "容器状态: 正常"
    log "资源使用: $(get_container_stats)"
    log "========== 健康检查完成 =========="
}

main "$@"
