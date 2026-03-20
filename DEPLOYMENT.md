# 自动化部署指南

## 架构概述

本方案采用 GitHub Actions + Docker Compose 实现自动化部署，包含以下组件：

- **CI/CD 流水线**: GitHub Actions 自动构建、测试并部署应用
- **容器化**: Docker + Docker Compose 管理应用服务
- **反向代理**: Nginx 处理 HTTP 请求和 SSL
- **自动更新**: Watchtower 自动监控并更新容器镜像
- **健康监控**: 应用健康检查 + 系统资源监控

---

## 快速开始

### 1. 服务器初始化

登录到 Linux 服务器，执行初始化脚本：

```bash
# 克隆仓库或上传脚本到服务器
scp -r scripts/ root@your-server:/tmp/

# 在服务器上执行初始化
ssh root@your-server
chmod +x /tmp/deploy-init.sh
/tmp/deploy-init.sh
```

### 2. 配置 GitHub Secrets

在 GitHub 仓库的 Settings > Secrets and variables > Actions 中添加以下 secrets：

| Secret 名称 | 说明 | 示例值 |
|------------|------|--------|
| `SERVER_HOST` | 服务器 IP 或域名 | `192.168.1.100` |
| `SERVER_USERNAME` | SSH 用户名 | `root` |
| `SERVER_SSH_KEY` | SSH 私钥内容 | `-----BEGIN RSA PRIVATE KEY-----...` |
| `SERVER_PORT` | SSH 端口 | `22` |
| `JWT_SECRET_KEY` | JWT 加密密钥 | 随机字符串 |

### 3. 服务器配置

在服务器上配置应用：

```bash
cd /opt/flask-app

# 创建环境变量文件
cp .env.example .env
vim .env  # 修改配置

# 创建 logs 目录
mkdir -p logs instance
chmod 755 logs instance

# 启动服务
docker-compose up -d
```

### 4. 配置 SSL 证书

```bash
# 使用 Certbot 获取免费 SSL 证书
certbot --nginx -d your-domain.com
```

---

## 文件结构

```
├── .github/
│   └── workflows/
│       └── deploy.yml          # GitHub Actions 工作流
├── nginx/
│   └── conf.d/
│       └── app.conf            # Nginx 配置
├── scripts/
│   ├── deploy-init.sh          # 服务器初始化脚本
│   ├── monitor.sh              # 监控脚本
│   └── status-check.sh         # 状态检查脚本
├── .env.example                # 环境变量模板
├── docker-compose.yml          # Docker Compose 配置
├── Dockerfile                  # Docker 镜像配置
└── requirements.txt            # Python 依赖
```

---

## 监控配置

### 自动监控

配置 cron 定时任务执行监控脚本：

```bash
crontab -e

# 添加以下内容（每 5 分钟执行一次）
*/5 * * * * /opt/flask-app/scripts/monitor.sh >> /var/log/app-monitor.log 2>&1
```

### 手动状态检查

```bash
/opt/flask-app/scripts/status-check.sh
```

### Docker 健康检查

Docker 内置健康检查会自动检测应用状态：

```bash
# 查看健康状态
docker inspect --format '{{.State.Health.Status}}' flask-app

# 查看健康检查日志
docker inspect --format '{{json .State.Health.Log}}' flask-app | jq
```

---

## 告警通知

监控脚本支持多种告警方式：

### 邮件告警

安装邮件客户端：

```bash
apt-get install -y mailutils
# 或
apt-get install -y bsd-mailx
```

在 `.env` 中配置：

```env
ALERT_EMAIL=admin@example.com
```

### Discord 通知

在 Discord 中创建 Webhook，然后在 `.env` 中配置：

```env
DISCORD_WEBHOOK=https://discord.com/api/webhooks/...
```

---

## 日常维护

### 查看日志

```bash
# 应用日志
docker logs -f flask-app

# Nginx 日志
tail -f /var/log/nginx/app.access.log

# 监控日志
tail -f /opt/flask-app/logs/monitor.log
```

### 服务管理

```bash
# 启动服务
docker-compose up -d

# 停止服务
docker-compose down

# 重启服务
docker-compose restart app

# 查看服务状态
docker-compose ps
```

### 系统更新

```bash
# Watchtower 会自动更新容器镜像
# 手动更新
docker-compose pull
docker-compose up -d
```

---

## 故障排查

### 应用无法访问

1. 检查容器状态：
   ```bash
   docker ps
   docker logs flask-app
   ```

2. 检查 Nginx 配置：
   ```bash
   nginx -t
   systemctl status nginx
   ```

3. 检查防火墙：
   ```bash
   ufw status
   # 确保 80、443 端口开放
   ufw allow 80/tcp
   ufw allow 443/tcp
   ```

### 健康检查失败

1. 检查应用是否正常响应：
   ```bash
   curl http://localhost:5000/health
   ```

2. 检查数据库文件权限：
   ```bash
   ls -la /opt/flask-app/instance/
   chown -R 1000:1000 /opt/flask-app/instance/
   ```

### 资源使用率过高

1. 查看容器资源使用：
   ```bash
   docker stats
   ```

2. 调整 Gunicorn worker 数量（Dockerfile 中）：
   ```dockerfile
   CMD ["gunicorn", "--bind", "0.0.0.0:5000", "--workers", "2", "app:create_app()"]
   ```

---

## 安全建议

1. **定期更新系统和软件包**：
   ```bash
   apt-get update && apt-get upgrade -y
   ```

2. **配置防火墙**：
   ```bash
   ufw enable
   ufw allow ssh
   ufw allow 80/tcp
   ufw allow 443/tcp
   ```

3. **使用非 root 用户运行容器**：Dockerfile 中已配置使用 `appuser` 用户

4. **定期备份数据**：
   ```bash
   # 备份数据库
   cp /opt/flask-app/instance/user_management.db /backup/
   ```

5. **监控日志中的异常行为**：配置告警通知，及时发现问题

---

## 扩展功能

### 添加更多服务

修改 `docker-compose.yml` 添加 Redis、MySQL 等服务：

```yaml
services:
  redis:
    image: redis:alpine
    container_name: redis
    restart: always
    volumes:
      - redis_data:/data
    networks:
      - app-network

volumes:
  redis_data:
```

### 配置日志轮转

创建 `/etc/logrotate.d/flask-app`：

```
/opt/flask-app/logs/*.log {
    daily
    missingok
    rotate 14
    compress
    delaycompress
    notifempty
    create 0640 root adm
    sharedscripts
    postrotate
        docker kill -s USR1 flask-app > /dev/null 2>&1 || true
    endscript
}
```

---

## 技术支持

如遇问题，请：

1. 检查本指南的故障排查部分
2. 查看相关日志文件
3. 运行状态检查脚本获取详细信息
