#!/bin/bash
# 应用监控脚本

APP_NAME="flask-app"
APP_DIR="/opt/flask-app"
LOG_FILE="$APP_DIR/logs/monitor.log"
ALERT_EMAIL="admin@example.com"
DISCORD_WEBHOOK=""

# 日志函数
log() {
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] $1" | tee -a $LOG_FILE
}

# 发送告警通知
send_alert() {
    local message="$1"
    log "ALERT: $message"
    
    # 邮件告警（需要配置 mailx 或 sendmail）
    if [ -n "$ALERT_EMAIL" ]; then
        echo "$message" | mail -s "[$APP_NAME] 告警通知" $ALERT_EMAIL
    fi
    
    # Discord Webhook 通知
    if [ -n "$DISCORD_WEBHOOK" ]; then
        curl -H "Content-Type: application/json" -X POST -d "{\"content\":\"**[$APP_NAME] 告警**\n$message\"}" $DISCORD_WEBHOOK
    fi
}

# 检查 Docker 容器状态
check_container() {
    local container_status=$(docker inspect --format '{{.State.Status}}' $APP_NAME 2>/dev/null || echo "not_found")
    
    if [ "$container_status" != "running" ]; then
        send_alert "容器 $APP_NAME 状态异常: $container_status，尝试重启..."
        cd $APP_DIR && docker-compose up -d app
        
        # 等待重启后再次检查
        sleep 10
        local new_status=$(docker inspect --format '{{.State.Status}}' $APP_NAME 2>/dev/null || echo "failed")
        if [ "$new_status" != "running" ]; then
            send_alert "容器 $APP_NAME 重启失败，当前状态: $new_status"
            return 1
        else
            log "容器 $APP_NAME 已成功重启"
        fi
    fi
    return 0
}

# 检查应用健康状态
check_health() {
    local health_status=$(docker inspect --format '{{.State.Health.Status}}' $APP_NAME 2>/dev/null || echo "unknown")
    
    if [ "$health_status" != "healthy" ]; then
        send_alert "应用健康检查失败: $health_status"
        return 1
    fi
    return 0
}

# 检查系统资源
check_resources() {
    # CPU 使用率
    local cpu_usage=$(top -bn1 | grep "Cpu(s)" | sed "s/.*, *\([0-9.]*\)%* id.*/\1/" | awk '{print 100 - $1}')
    if (( $(echo "$cpu_usage > 80" | bc -l) )); then
        send_alert "CPU 使用率过高: ${cpu_usage}%"
    fi
    
    # 内存使用率
    local mem_usage=$(free | grep Mem | awk '{print $3/$2 * 100.0}')
    if (( $(echo "$mem_usage > 85" | bc -l) )); then
        send_alert "内存使用率过高: ${mem_usage}%"
    fi
    
    # 磁盘使用率
    local disk_usage=$(df -h / | grep / | awk '{print $5}' | sed 's/%//g')
    if [ "$disk_usage" -gt 85 ]; then
        send_alert "磁盘使用率过高: ${disk_usage}%"
    fi
    
    # 容器资源使用
    local container_stats=$(docker stats --no-stream $APP_NAME 2>/dev/null | tail -n 1)
    if [ -n "$container_stats" ]; then
        local container_cpu=$(echo $container_stats | awk '{print $3}' | sed 's/%//')
        local container_mem=$(echo $container_stats | awk '{print $7}' | sed 's/%//')
        
        if (( $(echo "$container_cpu > 70" | bc -l) )); then
            send_alert "容器 CPU 使用率过高: ${container_cpu}%"
        fi
        
        if (( $(echo "$container_mem > 75" | bc -l) )); then
            send_alert "容器内存使用率过高: ${container_mem}%"
        fi
    fi
}

# 检查日志错误
check_logs() {
    local error_count=$(docker logs --since 5m $APP_NAME 2>&1 | grep -i "error\|exception\|traceback" | wc -l)
    if [ "$error_count" -gt 5 ]; then
        send_alert "最近 5 分钟内检测到 $error_count 个错误日志"
    fi
}

# 主函数
main() {
    log "开始监控检查..."
    
    check_container
    if [ $? -eq 0 ]; then
        check_health
        check_resources
        check_logs
    fi
    
    log "监控检查完成"
}

# 创建日志目录
mkdir -p $(dirname $LOG_FILE)

# 运行主函数
main
