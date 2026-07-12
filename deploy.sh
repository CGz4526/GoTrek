#!/bin/bash
set -e

echo "============================================"
echo "  GT_agent 部署脚本"
echo "============================================"
echo ""

DEEPSEEK_KEY="$1"

echo "[1/7] 更新系统包..."
sudo apt-get update -y
sudo apt-get upgrade -y

echo ""
echo "[2/7] 安装 Python、pip、git..."
sudo apt-get install -y python3 python3-pip python3-venv git curl

python3 --version
pip3 --version

echo ""
echo "[3/7] 克隆项目..."
cd ~
if [ -d "Interview_agent" ]; then
    echo "项目已存在，更新中..."
    cd Interview_agent
    git pull
else
    git clone https://github.com/CGz4526/Interview_agent.git
    cd Interview_agent
fi

echo ""
echo "[4/7] 创建虚拟环境并安装依赖..."
python3 -m venv venv
source venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt
pip install uvicorn

echo ""
echo "[5/7] 配置 .env 文件..."
if [ ! -f ".env" ]; then
    cat > .env << EOF
DEEPSEEK_API_KEY=${DEEPSEEK_KEY}
SECRET_KEY=$(python3 -c "import secrets; print(secrets.token_hex(32))")
PUBLIC_MODE=false
EOF
    echo ".env 文件已创建"
else
    echo ".env 文件已存在，跳过"
fi

echo ""
echo "[6/7] 创建 systemd 服务..."
SERVICE_FILE="/etc/systemd/system/gt-agent.service"
sudo bash -c "cat > $SERVICE_FILE << 'SVCEOF'
[Unit]
Description=GT_agent 面试题智能学习平台
After=network.target

[Service]
Type=simple
User=ubuntu
WorkingDirectory=/home/ubuntu/Interview_agent
Environment=PATH=/home/ubuntu/Interview_agent/venv/bin
ExecStart=/home/ubuntu/Interview_agent/venv/bin/uvicorn main:app --host 0.0.0.0 --port 8000
Restart=always
RestartSec=5
StandardOutput=journal
StandardError=journal

[Install]
WantedBy=multi-user.target
SVCEOF"

sudo systemctl daemon-reload
sudo systemctl enable gt-agent
sudo systemctl restart gt-agent

echo ""
echo "[7/7] 等待服务启动..."
sleep 3

echo ""
echo "============================================"
echo "  部署完成！"
echo "============================================"
echo ""
echo "访问地址: http://$(curl -s ifconfig.me):8000"
echo ""
echo "常用命令："
echo "  查看状态: sudo systemctl status gt-agent"
echo "  查看日志: sudo journalctl -u gt-agent -f"
echo "  重启服务: sudo systemctl restart gt-agent"
echo "  停止服务: sudo systemctl stop gt-agent"
echo "  更新代码: cd ~/Interview_agent && git pull && sudo systemctl restart gt-agent"
echo ""

sudo systemctl status gt-agent --no-pager -l
