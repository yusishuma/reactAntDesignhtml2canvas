#!/bin/bash
# 状态检查脚本 - 用于快速查看应用运行状态

APP_NAME="flask-app"
APP_DIR="/opt/flask-app"

echo "=== 应用运行状态检查 ==="
echo ""

# 检查 Docker 服务状态
echo "1. Docker 服务状态:"
systemctl is-active --quiet docker && echo "   ✅ Docker 服务正在运行" || echo "   ❌ Docker 服务未运行"

# 检查容器状态
echo ""
echo "2. 容器状态:"
if docker ps --format '{{.Names}} {{.Status}}' | grep -q $APP_NAME; then
    container_info=$(docker ps --format '{{.Names}} {{.Status}}' | grep $APP_NAME)
    echo "   ✅ 容器正在运行: $container_info"
else
    echo "   ❌ 容器未运行"
fi

# 检查健康状态
echo ""
echo "3. 应用健康状态:"
health_status=$(docker inspect --format '{{.State.Health.Status}}' $APP_NAME 2>/dev/null || echo "unknown")
if [ "$health_status" = "healthy" ]; then
    echo "   ✅ 应用健康状态: $health_status"
else
    echo "   ⚠️  应用健康状态: $health_status"
fi

# 检查端口监听
echo ""
echo "4. 端口监听:"
if netstat -tulpn 2>/dev/null | grep -q ':5000'; then
    echo "   ✅ 端口 5000 正在监听"
else
    echo "   ❌ 端口 5000 未监听"
fi

# 资源使用情况
echo ""
echo "5. 资源使用:"
docker stats --no-stream $APP_NAME 2>/dev/null | tail -n 1 | awk '{print "   CPU: " $3 ", 内存: " $4 ", 内存使用率: " $7}'

# 最近的日志
echo ""
echo "6. 最近 10 条日志:"
docker logs --tail 10 $APP_NAME 2>&1 | sed 's/^/   /'

echo ""
echo "=== 检查完成 ==="
