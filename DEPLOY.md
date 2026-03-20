# 自动化部署指南

本文档介绍如何使用 GitHub Actions + Docker Compose 实现自动化部署和监控。

## 架构概览

```
GitHub (代码推送)
    ↓
GitHub Actions (构建镜像)
    ↓
GitHub Container Registry (镜像存储)
    ↓
SSH 部署到服务器
    ↓
Docker Compose (运行应用)
    ↓
健康检查 & 监控
```

## 文件说明

| 文件 | 说明 |
|------|------|
| `.github/workflows/deploy.yml` | GitHub Actions 工作流配置 |
| `Dockerfile` | 应用容器镜像构建配置 |
| `docker-compose.yml` | 多容器编排配置 |
| `scripts/deploy.sh` | 服务器端部署脚本 |
| `scripts/health-check.sh` | 健康检查脚本 |
| `scripts/monitor.sh` | 实时监控脚本 |
| `scripts/setup-server.sh` | 服务器初始化脚本 |
| `.env.example` | 环境变量模板 |

## 快速开始

### 1. 配置 GitHub Secrets

在 GitHub 仓库 Settings → Secrets and variables → Actions 中添加：

| Secret 名称 | 说明 | 示例 |
|------------|------|------|
| `SERVER_HOST` | 服务器 IP 或域名 | `192.168.1.100` |
| `SERVER_USER` | SSH 用户名 | `root` 或 `appuser` |
| `SSH_PRIVATE_KEY` | SSH 私钥 | `-----BEGIN OPENSSH PRIVATE KEY-----...` |
| `SSH_PORT` | SSH 端口（可选） | `22` |

可选配置：
- `SLACK_WEBHOOK_URL` - Slack 通知 webhook

### 2. 服务器初始化

在新服务器上执行：

```bash
# 1. 复制 setup-server.sh 到服务器
scp scripts/setup-server.sh root@your-server:/tmp/

# 2. SSH 登录并执行
ssh root@your-server
chmod +x /tmp/setup-server.sh
/tmp/setup-server.sh
```

这个脚本会自动安装：
- Docker & Docker Compose
- 防火墙 (UFW)
- Fail2ban (防暴力破解)
- 日志轮转
- Systemd 服务
- 定时任务

### 3. 配置应用

```bash
# 1. 进入应用目录
cd /opt/app

# 2. 复制环境变量文件
cp .env.example .env

# 3. 编辑配置
vim .env

# 4. 登录 GitHub Container Registry
echo $GHCR_TOKEN | docker login ghcr.io -u $GHCR_USERNAME --password-stdin
```

### 4. 首次部署

```bash
cd /opt/app
./scripts/deploy.sh
```

### 5. 启用自动部署

推送代码到 main 分支，GitHub Actions 会自动：
1. 构建 Docker 镜像
2. 推送到 GitHub Container Registry
3. SSH 到服务器执行部署
4. 运行健康检查

## 使用指南

### 部署脚本

```bash
# 完整部署
./scripts/deploy.sh

# 仅备份
./scripts/deploy.sh backup

# 回滚到上一个版本
./scripts/deploy.sh rollback

# 清理旧镜像
./scripts/deploy.sh cleanup

# 健康检查
./scripts/deploy.sh health
```

### 健康检查脚本

```bash
# 完整健康检查
./scripts/health-check.sh

# 快速检查（容器 + API）
./scripts/health-check.sh quick

# 仅检查 API
./scripts/health-check.sh api

# 仅检查资源
./scripts/health-check.sh resources

# 仅检查日志
./scripts/health-check.sh logs

# 生成报告
./scripts/health-check.sh report
```

### 实时监控

```bash
# 启动实时监控面板
./scripts/monitor.sh

# 单次监控
./scripts/monitor.sh once
```

监控面板快捷键：
- `q` - 退出
- `r` - 立即刷新
- `l` - 查看完整日志
- `h` - 显示帮助

## Docker Compose 配置

### 基础部署

```bash
# 使用 SQLite（默认）
docker-compose up -d
```

### 使用 PostgreSQL

```bash
# 启动应用 + PostgreSQL
docker-compose --profile postgres up -d
```

### 使用 Nginx 反向代理

```bash
# 启动应用 + Nginx
docker-compose --profile nginx up -d
```

### 启用监控（Prometheus + Grafana）

```bash
# 启动应用 + 监控
docker-compose --profile monitoring up -d
```

### 完整部署

```bash
# 启动所有服务
docker-compose --profile postgres --profile nginx --profile monitoring up -d
```

## Systemd 服务管理

```bash
# 启动服务
systemctl start user-management-api

# 停止服务
systemctl stop user-management-api

# 重启服务
systemctl restart user-management-api

# 查看状态
systemctl status user-management-api

# 查看日志
journalctl -u user-management-api -f
```

## 定时任务

系统已配置以下定时任务：

| 任务 | 频率 | 说明 |
|------|------|------|
| 快速健康检查 | 每 5 分钟 | 检查容器和 API 状态 |
| 完整健康检查 | 每天 3:00 | 包含资源、日志检查 |
| 清理旧备份 | 每周日 4:00 | 保留最近 5 个备份 |

查看定时任务日志：
```bash
tail -f /var/log/user-management-api/cron.log
```

## 备份与恢复

### 自动备份

每次部署会自动创建备份，保存在 `/opt/backups/`。

### 手动备份

```bash
./scripts/deploy.sh backup
```

### 恢复备份

```bash
./scripts/deploy.sh rollback
```

### 查看备份列表

```bash
ls -lah /opt/backups/
```

## 监控告警

### 告警触发条件

- 容器状态异常
- API 健康检查失败
- CPU 使用率 > 80%
- 内存使用率 > 80%
- 磁盘使用率 > 85%
- API 响应时间 > 2000ms
- 错误日志过多

### 配置 Slack 告警

1. 创建 Slack Incoming Webhook
2. 添加到 GitHub Secrets: `SLACK_WEBHOOK_URL`
3. 或在服务器 `.env` 中配置 `ALERT_WEBHOOK_URL`

## 故障排查

### 查看容器日志

```bash
cd /opt/app
docker-compose logs -f app
```

### 查看健康检查日志

```bash
tail -f /var/log/user-management-api/health.log
```

### 检查服务状态

```bash
systemctl status user-management-api
docker-compose ps
```

### 手动重启

```bash
cd /opt/app
docker-compose restart
```

## 安全建议

1. **修改默认密钥**：生产环境务必修改 `SECRET_KEY`
2. **使用 SSH 密钥**：禁用密码登录，使用 SSH 密钥认证
3. **配置防火墙**：仅开放必要的端口
4. **定期更新**：保持系统和 Docker 更新
5. **使用 HTTPS**：生产环境配置 SSL 证书
6. **限制访问**：使用 VPN 或 IP 白名单限制管理接口访问

## 更新日志

- 2024-XX-XX: 初始版本
