#!/bin/bash
# 服务器初始化部署脚本

set -e

echo "=== 开始服务器初始化部署 ==="

# 检查是否为 root 用户
if [ "$EUID" -ne 0 ]; then
    echo "请以 root 用户运行此脚本"
    exit 1
fi

# 安装必要的系统依赖
echo "安装系统依赖..."
apt-get update
apt-get install -y \
    apt-transport-https \
    ca-certificates \
    curl \
    gnupg-agent \
    software-properties-common \
    nginx \
    certbot \
    python3-certbot-nginx

# 安装 Docker
echo "安装 Docker..."
curl -fsSL https://download.docker.com/linux/ubuntu/gpg | apt-key add -
add-apt-repository \
    "deb [arch=amd64] https://download.docker.com/linux/ubuntu \
    $(lsb_release -cs) \
    stable"
apt-get update
apt-get install -y docker-ce docker-ce-cli containerd.io

# 安装 Docker Compose
echo "安装 Docker Compose..."
curl -L "https://github.com/docker/compose/releases/latest/download/docker-compose-$(uname -s)-$(uname -m)" -o /usr/local/bin/docker-compose
chmod +x /usr/local/bin/docker-compose

# 启动并启用 Docker
systemctl start docker
systemctl enable docker

# 创建应用目录
APP_DIR="/opt/flask-app"
echo "创建应用目录: $APP_DIR"
mkdir -p $APP_DIR
mkdir -p $APP_DIR/nginx/conf.d
mkdir -p $APP_DIR/nginx/ssl
mkdir -p $APP_DIR/nginx/logs
mkdir -p $APP_DIR/scripts
mkdir -p $APP_DIR/logs

# 设置目录权限
chown -R $SUDO_USER:$SUDO_USER $APP_DIR

echo "=== 服务器初始化完成 ==="
echo ""
echo "接下来的步骤:"
echo "1. 将 docker-compose.yml 和 .env 文件上传到 $APP_DIR"
echo "2. 配置 Nginx: 在 $APP_DIR/nginx/conf.d/ 中添加配置文件"
echo "3. 运行: cd $APP_DIR && docker-compose up -d"
echo "4. 配置 SSL 证书: certbot --nginx -d your-domain.com"
