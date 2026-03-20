#!/bin/bash

# =============================================================================
# 实时监控脚本
# 用途：实时显示容器状态、资源使用和日志
# =============================================================================

set -euo pipefail

# 颜色定义
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
CYAN='\033[0;36m'
NC='\033[0m'

APP_DIR="/opt/app"
REFRESH_INTERVAL=2

# 清屏并移动光标到顶部
clear_screen() {
    printf "\033[2J\033[H"
}

# 显示头部信息
show_header() {
    echo -e "${CYAN}========================================${NC}"
    echo -e "${CYAN}      User Management API 监控面板${NC}"
    echo -e "${CYAN}========================================${NC}"
    echo -e "更新时间: $(date '+%Y-%m-%d %H:%M:%S')"
    echo ""
}

# 显示容器状态
show_container_status() {
    echo -e "${YELLOW}【容器状态】${NC}"
    echo "----------------------------------------"
    
    cd "$APP_DIR" 2>/dev/null || return
    
    local containers=$(docker-compose ps -q 2>/dev/null)
    
    if [ -z "$containers" ]; then
        echo -e "${RED}没有运行中的容器${NC}"
        return
    fi
    
    printf "%-20s %-15s %-15s %-20s\n" "名称" "状态" "健康" "运行时间"
    echo "----------------------------------------"
    
    while IFS= read -r container; do
        if [ -n "$container" ]; then
            local name=$(docker inspect --format='{{.Name}}' "$container" | sed 's/\///' | cut -c1-20)
            local status=$(docker inspect --format='{{.State.Status}}' "$container")
            local health=$(docker inspect --format='{{.State.Health.Status}}' "$container" 2>/dev/null || echo "N/A")
            local uptime=$(docker inspect --format='{{.State.StartedAt}}' "$container" | xargs -I {} date -d {} +%H:%M:%S 2>/dev/null || echo "N/A")
            
            local status_color=$NC
            if [ "$status" == "running" ]; then
                status_color=$GREEN
            else
                status_color=$RED
            fi
            
            local health_color=$NC
            if [ "$health" == "healthy" ]; then
                health_color=$GREEN
            elif [ "$health" == "unhealthy" ]; then
                health_color=$RED
            else
                health_color=$YELLOW
            fi
            
            printf "%-20s ${status_color}%-15s${NC} ${health_color}%-15s${NC} %-20s\n" "$name" "$status" "$health" "$uptime"
        fi
    done <<< "$containers"
    
    echo ""
}

# 显示资源使用
show_resource_usage() {
    echo -e "${YELLOW}【资源使用】${NC}"
    echo "----------------------------------------"
    
    cd "$APP_DIR" 2>/dev/null || return
    
    local containers=$(docker-compose ps -q 2>/dev/null)
    
    if [ -z "$containers" ]; then
        echo "没有运行中的容器"
        return
    fi
    
    printf "%-20s %-10s %-15s %-15s\n" "名称" "CPU" "内存" "网络 I/O"
    echo "----------------------------------------"
    
    while IFS= read -r container; do
        if [ -n "$container" ]; then
            local name=$(docker inspect --format='{{.Name}}' "$container" | sed 's/\///' | cut -c1-20)
            local stats=$(docker stats --no-stream --format "table {{.CPUPerc}}\t{{.MemUsage}}\t{{.NetIO}}" "$container" | tail -n +2)
            local cpu=$(echo "$stats" | awk '{print $1}')
            local mem=$(echo "$stats" | awk '{print $2,$3}')
            local net=$(echo "$stats" | awk '{print $4,$5}')
            
            printf "%-20s %-10s %-15s %-15s\n" "$name" "$cpu" "$mem" "$net"
        fi
    done <<< "$containers"
    
    echo ""
}

# 显示系统资源
show_system_resources() {
    echo -e "${YELLOW}【系统资源】${NC}"
    echo "----------------------------------------"
    
    # CPU 使用率
    local cpu_usage=$(top -bn1 | grep "Cpu(s)" | awk '{print $2}' | cut -d'%' -f1)
    printf "CPU 使用率: %.1f%%\n" "$cpu_usage"
    
    # 内存使用率
    local mem_info=$(free | grep Mem)
    local mem_total=$(echo "$mem_info" | awk '{print $2}')
    local mem_used=$(echo "$mem_info" | awk '{print $3}')
    local mem_usage=$(( mem_used * 100 / mem_total ))
    local mem_total_gb=$(( mem_total / 1024 / 1024 ))
    local mem_used_gb=$(( mem_used / 1024 / 1024 ))
    printf "内存使用: %d%% (%dGB / %dGB)\n" "$mem_usage" "$mem_used_gb" "$mem_total_gb"
    
    # 磁盘使用率
    local disk_usage=$(df -h / | tail -1 | awk '{print $5}' | sed 's/%//')
    local disk_used=$(df -h / | tail -1 | awk '{print $3}')
    local disk_total=$(df -h / | tail -1 | awk '{print $2}')
    printf "磁盘使用: %d%% (%s / %s)\n" "$disk_usage" "$disk_used" "$disk_total"
    
    # 负载
    local load=$(uptime | awk -F'load average:' '{print $2}')
    printf "系统负载:%s\n" "$load"
    
    echo ""
}

# 显示最近日志
show_recent_logs() {
    echo -e "${YELLOW}【最近日志】${NC}"
    echo "----------------------------------------"
    
    cd "$APP_DIR" 2>/dev/null || return
    
    # 显示最后 10 行日志
    docker-compose logs --tail=10 --no-color 2>/dev/null | tail -n 15 || echo "无法获取日志"
    
    echo ""
}

# 显示 API 状态
show_api_status() {
    echo -e "${YELLOW}【API 状态】${NC}"
    echo "----------------------------------------"
    
    local start_time=$(date +%s%N)
    local response=$(curl -s -o /dev/null -w "%{http_code}|%{time_total}" --max-time 5 http://localhost:8000/health 2>/dev/null || echo "000|0")
    local end_time=$(date +%s%N)
    
    local http_code=$(echo "$response" | cut -d'|' -f1)
    local response_time=$(echo "$response" | cut -d'|' -f2)
    local response_ms=$(echo "$response_time * 1000" | bc 2>/dev/null || echo "0")
    
    if [ "$http_code" == "200" ]; then
        echo -e "状态: ${GREEN}✓ 正常${NC} (HTTP $http_code)"
    else
        echo -e "状态: ${RED}✗ 异常${NC} (HTTP $http_code)"
    fi
    
    printf "响应时间: %.0f ms\n" "$response_ms"
    
    echo ""
}

# 显示帮助信息
show_help() {
    echo -e "${CYAN}使用说明:${NC}"
    echo "  q - 退出监控"
    echo "  r - 立即刷新"
    echo "  l - 查看完整日志"
    echo "  h - 显示帮助"
    echo ""
}

# 主监控循环
monitor_loop() {
    while true; do
        clear_screen
        show_header
        show_api_status
        show_container_status
        show_resource_usage
        show_system_resources
        show_recent_logs
        show_help
        
        # 等待用户输入或超时刷新
        read -t "$REFRESH_INTERVAL" -n 1 key || true
        
        case "$key" in
            q|Q)
                echo "退出监控..."
                exit 0
                ;;
            r|R)
                continue
                ;;
            l|L)
                clear_screen
                cd "$APP_DIR" 2>/dev/null && docker-compose logs -f --tail=100
                echo "按任意键继续..."
                read -n 1
                ;;
            h|H)
                clear_screen
                show_help
                echo "按任意键继续..."
                read -n 1
                ;;
        esac
    done
}

# 单次监控模式
single_monitor() {
    show_header
    show_api_status
    show_container_status
    show_resource_usage
    show_system_resources
}

# 主函数
main() {
    case "${1:-}" in
        once)
            single_monitor
            ;;
        *)
            monitor_loop
            ;;
    esac
}

main "$@"
