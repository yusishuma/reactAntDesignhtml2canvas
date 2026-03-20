#!/bin/bash

# =============================================================================
# 健康检查脚本
# 用途：检查应用运行状态，支持定时监控和告警
# =============================================================================

set -euo pipefail

# 颜色定义
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

# 配置变量
APP_NAME="user-management-api"
APP_DIR="/opt/app"
LOG_DIR="/var/log/${APP_NAME}"
HEALTH_LOG="${LOG_DIR}/health.log"
ALERT_WEBHOOK="${ALERT_WEBHOOK_URL:-}"  # 告警 webhook URL

# 阈值配置
CPU_THRESHOLD=80
MEMORY_THRESHOLD=80
DISK_THRESHOLD=85
RESPONSE_TIME_THRESHOLD=2000  # 毫秒

# 日志函数
log_info() {
    local msg="[INFO] $(date '+%Y-%m-%d %H:%M:%S') - $1"
    echo -e "${BLUE}${msg}${NC}"
    echo "$msg" >> "$HEALTH_LOG"
}

log_success() {
    local msg="[SUCCESS] $(date '+%Y-%m-%d %H:%M:%S') - $1"
    echo -e "${GREEN}${msg}${NC}"
    echo "$msg" >> "$HEALTH_LOG"
}

log_warning() {
    local msg="[WARNING] $(date '+%Y-%m-%d %H:%M:%S') - $1"
    echo -e "${YELLOW}${msg}${NC}"
    echo "$msg" >> "$HEALTH_LOG"
}

log_error() {
    local msg="[ERROR] $(date '+%Y-%m-%d %H:%M:%S') - $1"
    echo -e "${RED}${msg}${NC}"
    echo "$msg" >> "$HEALTH_LOG"
}

# 发送告警
send_alert() {
    local title="$1"
    local message="$2"
    local severity="${3:-warning}"  # info, warning, error
    
    log_warning "发送告警: $title"
    
    # 记录到日志
    echo "$(date '+%Y-%m-%d %H:%M:%S') - [$severity] $title: $message" >> "${LOG_DIR}/alerts.log"
    
    # 如果配置了 webhook，发送告警
    if [ -n "$ALERT_WEBHOOK" ]; then
        curl -s -X POST "$ALERT_WEBHOOK" \
            -H "Content-Type: application/json" \
            -d "{
                \"title\": \"$title\",
                \"message\": \"$message\",
                \"severity\": \"$severity\",
                \"timestamp\": \"$(date -Iseconds)\",
                \"hostname\": \"$(hostname)\"
            }" || true
    fi
}

# 检查容器状态
check_containers() {
    log_info "检查容器状态..."
    
    cd "$APP_DIR"
    
    local all_healthy=true
    local containers=$(docker-compose ps -q)
    
    if [ -z "$containers" ]; then
        log_error "没有运行中的容器"
        send_alert "容器状态异常" "没有运行中的容器" "error"
        return 1
    fi
    
    while IFS= read -r container; do
        if [ -n "$container" ]; then
            local name=$(docker inspect --format='{{.Name}}' "$container" | sed 's/\///')
            local status=$(docker inspect --format='{{.State.Status}}' "$container")
            local health=$(docker inspect --format='{{.State.Health.Status}}' "$container" 2>/dev/null || echo "N/A")
            
            if [ "$status" != "running" ]; then
                log_error "容器 $name 状态异常: $status"
                send_alert "容器状态异常" "容器 $name 状态: $status" "error"
                all_healthy=false
            elif [ "$health" != "healthy" ] && [ "$health" != "N/A" ]; then
                log_warning "容器 $name 健康状态: $health"
                send_alert "容器健康检查警告" "容器 $name 健康状态: $health" "warning"
                all_healthy=false
            else
                log_success "容器 $name 运行正常 (状态: $status, 健康: $health)"
            fi
        fi
    done <<< "$containers"
    
    if [ "$all_healthy" = true ]; then
        return 0
    else
        return 1
    fi
}

# 检查应用 API 健康
check_api_health() {
    log_info "检查 API 健康状态..."
    
    local api_url="http://localhost:8000/health"
    local start_time=$(date +%s%N)
    
    local response
    local http_code
    
    response=$(curl -s -w "\n%{http_code}" --max-time 10 "$api_url" 2>/dev/null) || true
    http_code=$(echo "$response" | tail -n1)
    response_body=$(echo "$response" | sed '$d')
    
    local end_time=$(date +%s%N)
    local response_time=$(( (end_time - start_time) / 1000000 ))  # 转换为毫秒
    
    if [ "$http_code" == "200" ]; then
        log_success "API 健康检查通过 (响应时间: ${response_time}ms)"
        
        if [ "$response_time" -gt "$RESPONSE_TIME_THRESHOLD" ]; then
            log_warning "API 响应时间较慢: ${response_time}ms"
            send_alert "API 响应缓慢" "响应时间: ${response_time}ms" "warning"
        fi
        
        return 0
    else
        log_error "API 健康检查失败 (HTTP: $http_code)"
        send_alert "API 健康检查失败" "HTTP 状态码: $http_code" "error"
        return 1
    fi
}

# 检查系统资源
check_system_resources() {
    log_info "检查系统资源..."
    
    local has_issue=false
    
    # 检查 CPU 使用率
    local cpu_usage=$(top -bn1 | grep "Cpu(s)" | awk '{print $2}' | cut -d'%' -f1)
    cpu_usage=${cpu_usage%.*}  # 取整
    
    if [ "$cpu_usage" -gt "$CPU_THRESHOLD" ]; then
        log_warning "CPU 使用率过高: ${cpu_usage}%"
        send_alert "CPU 使用率警告" "当前使用率: ${cpu_usage}%" "warning"
        has_issue=true
    else
        log_success "CPU 使用率正常: ${cpu_usage}%"
    fi
    
    # 检查内存使用率
    local memory_info=$(free | grep Mem)
    local memory_total=$(echo "$memory_info" | awk '{print $2}')
    local memory_used=$(echo "$memory_info" | awk '{print $3}')
    local memory_usage=$(( memory_used * 100 / memory_total ))
    
    if [ "$memory_usage" -gt "$MEMORY_THRESHOLD" ]; then
        log_warning "内存使用率过高: ${memory_usage}%"
        send_alert "内存使用率警告" "当前使用率: ${memory_usage}%" "warning"
        has_issue=true
    else
        log_success "内存使用率正常: ${memory_usage}%"
    fi
    
    # 检查磁盘使用率
    local disk_usage=$(df -h / | tail -1 | awk '{print $5}' | sed 's/%//')
    
    if [ "$disk_usage" -gt "$DISK_THRESHOLD" ]; then
        log_warning "磁盘使用率过高: ${disk_usage}%"
        send_alert "磁盘使用率警告" "当前使用率: ${disk_usage}%" "warning"
        has_issue=true
    else
        log_success "磁盘使用率正常: ${disk_usage}%"
    fi
    
    if [ "$has_issue" = true ]; then
        return 1
    fi
    
    return 0
}

# 检查 Docker 资源使用
check_docker_resources() {
    log_info "检查 Docker 资源使用..."
    
    cd "$APP_DIR"
    
    local containers=$(docker-compose ps -q)
    
    if [ -z "$containers" ]; then
        log_warning "没有运行中的容器"
        return 1
    fi
    
    while IFS= read -r container; do
        if [ -n "$container" ]; then
            local name=$(docker inspect --format='{{.Name}}' "$container" | sed 's/\///')
            
            # 获取容器资源使用
            local stats=$(docker stats --no-stream --format "table {{.CPUPerc}}\t{{.MemPerc}}\t{{.MemUsage}}" "$container" | tail -n +2)
            local cpu=$(echo "$stats" | awk '{print $1}' | sed 's/%//')
            local mem=$(echo "$stats" | awk '{print $2}' | sed 's/%//')
            local mem_usage=$(echo "$stats" | awk '{print $3,$4,$5}')
            
            log_info "容器 $name - CPU: ${cpu}%, 内存: ${mem}% (${mem_usage})"
            
            # 检查资源使用是否异常
            local cpu_int=${cpu%.*}
            if [ "$cpu_int" -gt "$CPU_THRESHOLD" ]; then
                log_warning "容器 $name CPU 使用率过高: ${cpu}%"
                send_alert "容器资源警告" "容器 $name CPU 使用率: ${cpu}%" "warning"
            fi
        fi
    done <<< "$containers"
}

# 检查日志错误
check_logs() {
    log_info "检查应用日志..."
    
    local error_count=0
    local warning_count=0
    
    # 检查最近 5 分钟的错误日志
    if [ -d "${APP_DIR}/logs" ]; then
        error_count=$(find "${APP_DIR}/logs" -name "*.log" -type f -mmin -5 -exec grep -i "error" {} + 2>/dev/null | wc -l)
        warning_count=$(find "${APP_DIR}/logs" -name "*.log" -type f -mmin -5 -exec grep -i "warning" {} + 2>/dev/null | wc -l)
    fi
    
    # 检查 Docker 日志
    cd "$APP_DIR"
    local docker_errors=$(docker-compose logs --tail=100 2>&1 | grep -i "error" | wc -l)
    local docker_warnings=$(docker-compose logs --tail=100 2>&1 | grep -i "warning" | wc -l)
    
    error_count=$((error_count + docker_errors))
    warning_count=$((warning_count + docker_warnings))
    
    if [ "$error_count" -gt 0 ]; then
        log_warning "发现 ${error_count} 个错误日志"
        if [ "$error_count" -gt 10 ]; then
            send_alert "错误日志过多" "最近发现 ${error_count} 个错误" "error"
        fi
    else
        log_success "没有发现错误日志"
    fi
    
    if [ "$warning_count" -gt 0 ]; then
        log_info "发现 ${warning_count} 个警告日志"
    fi
}

# 生成健康报告
generate_report() {
    log_info "生成健康报告..."
    
    local report_file="${LOG_DIR}/health-report-$(date +%Y%m%d-%H%M%S).txt"
    
    {
        echo "========================================"
        echo "健康检查报告"
        echo "生成时间: $(date '+%Y-%m-%d %H:%M:%S')"
        echo "主机: $(hostname)"
        echo "========================================"
        echo ""
        echo "系统信息:"
        echo "  - 操作系统: $(uname -a)"
        echo "  - 运行时间: $(uptime -p 2>/dev/null || uptime)"
        echo ""
        echo "容器状态:"
        cd "$APP_DIR"
        docker-compose ps
        echo ""
        echo "资源使用:"
        echo "  - CPU: $(top -bn1 | grep "Cpu(s)" | awk '{print $2}')"
        echo "  - 内存: $(free -h | grep Mem | awk '{print $3"/"$2}')"
        echo "  - 磁盘: $(df -h / | tail -1 | awk '{print $3"/"$2 " (" $5 ")"}')"
        echo ""
        echo "========================================"
    } > "$report_file"
    
    log_success "健康报告已生成: $report_file"
}

# 主函数
main() {
    log_info "开始健康检查..."
    
    mkdir -p "$LOG_DIR"
    
    local all_checks_passed=true
    
    # 执行各项检查
    check_containers || all_checks_passed=false
    check_api_health || all_checks_passed=false
    check_system_resources || all_checks_passed=false
    check_docker_resources
    check_logs
    
    # 生成报告
    generate_report
    
    if [ "$all_checks_passed" = true ]; then
        log_success "所有健康检查通过！"
        exit 0
    else
        log_error "部分健康检查未通过"
        exit 1
    fi
}

# 处理命令行参数
case "${1:-}" in
    quick)
        # 快速检查
        check_containers && check_api_health
        ;;
    api)
        # 仅检查 API
        check_api_health
        ;;
    resources)
        # 仅检查资源
        check_system_resources && check_docker_resources
        ;;
    logs)
        # 仅检查日志
        check_logs
        ;;
    report)
        # 生成报告
        generate_report
        ;;
    *)
        main
        ;;
esac
