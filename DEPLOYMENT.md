# 项目部署与更新指南

本文档说明如何将 GT_agent 面试题学习平台的代码更新同步到 GitHub 和云服务器上。

## 目录

- [一、本地代码推送到 GitHub](#一本地代码推送到-github)
- [二、云服务器更新代码](#二云服务器更新代码)
- [三、一键更新脚本（推荐）](#三一键更新脚本推荐)
- [四、常见问题](#四常见问题)

---

## 一、本地代码推送到 GitHub

### 前置条件

- 本地已安装 Git
- 已配置 GitHub 仓库地址
- 项目目录：`d:\CCDevelop\Interview_agent`

### 步骤

```bash
# 1. 进入项目目录
cd d:\CCDevelop\Interview_agent

# 2. 查看当前变更
git status

# 3. 添加所有修改的文件
git add .

# 4. 提交变更（描述本次修改内容）
git commit -m "描述本次更新内容"

# 5. 推送到 GitHub
git push
```

### 示例

```bash
git add .
git commit -m "feat: 添加模糊标记功能"
git push
```

---

## 二、云服务器更新代码

### 前置条件

- 能通过腾讯云控制台登录服务器（云终端或 SSH）
- 服务器上已配置好项目环境

### 登录服务器

1. 打开腾讯云控制台
2. 进入轻量应用服务器 → 你的服务器
3. 点击「登录」→「免密登录 (TAT)」

### 手动更新步骤

```bash
# 1. 停止服务
sudo systemctl stop gt-agent

# 2. 进入项目目录
cd ~/Interview_agent

# 3. 拉取最新代码
git pull

# 4. 激活虚拟环境，更新依赖（如有新增依赖）
source venv/bin/activate
pip install -r requirements.txt

# 5. 重启服务
sudo systemctl start gt-agent

# 6. 查看服务状态
sudo systemctl status gt-agent
```

---

## 三、一键更新脚本（推荐）

服务器上已配置一键更新脚本，以后更新只需一条命令：

```bash
update-gt-agent
```

脚本会自动完成：
1. 停止服务
2. 拉取最新代码
3. 更新依赖
4. 重启服务
5. 显示运行状态

### 如果脚本不存在，创建方法

在服务器终端执行：

```bash
sudo bash -c 'cat > /usr/local/bin/update-gt-agent << "EOF"
#!/bin/bash
echo "=== 停止服务 ==="
sudo systemctl stop gt-agent

echo "=== 拉取最新代码 ==="
cd ~/Interview_agent && git pull

echo "=== 更新依赖（如有必要） ==="
source ~/Interview_agent/venv/bin/activate && pip install -r requirements.txt

echo "=== 重启服务 ==="
sudo systemctl start gt-agent

echo "=== 查看状态 ==="
sleep 2 && sudo systemctl status gt-agent --no-pager -l
EOF'

sudo chmod +x /usr/local/bin/update-gt-agent
```

---

## 四、常见问题

### 1. git pull 失败怎么办？

**问题：** `fatal: unable to access 'https://github.com/...': SSL connection timeout`

**原因：** 服务器在国内，访问 GitHub 不稳定

**解决方法：**

```bash
# 方法一：使用代理镜像站
cd ~/Interview_agent
git remote set-url origin https://ghproxy.com/https://github.com/CGz4526/Interview_agent.git
git pull

# 方法二：直接下载 ZIP 包替换
cd ~
sudo systemctl stop gt-agent
rm -rf Interview_agent
curl -sL https://ghproxy.com/https://github.com/CGz4526/Interview_agent/archive/refs/heads/main.zip -o main.zip
unzip main.zip
mv Interview_agent-main Interview_agent
rm main.zip
# 恢复 .env 和数据库
# 注意：如果是全新部署，需要重新配置 .env 和复制数据库文件
sudo systemctl start gt-agent
```

### 2. 服务启动失败怎么排查？

```bash
# 查看服务状态
sudo systemctl status gt-agent

# 查看实时日志
sudo journalctl -u gt-agent -f

# 查看最近 50 行日志
sudo journalctl -u gt-agent -n 50 --no-pager
```

### 3. 数据库迁移失败？

项目使用 SQLite，新增字段时会自动迁移（在 `main.py` 的 `_migrate_db` 函数中）。

如果迁移失败，可以手动执行：

```bash
cd ~/Interview_agent
source venv/bin/activate
python -c "
from db.database import engine
from sqlalchemy import text, inspect
insp = inspect(engine)
cols = [c['name'] for c in insp.get_columns('question_weights')]
if 'vague_count' not in cols:
    with engine.connect() as conn:
        conn.execute(text('ALTER TABLE question_weights ADD COLUMN vague_count INTEGER DEFAULT 0 NOT NULL'))
        conn.commit()
    print('迁移完成')
else:
    print('字段已存在')
"
```

### 4. 想备份数据库？

```bash
# 创建备份
cd ~/Interview_agent
cp db/gt_agent.db db/gt_agent_backup_$(date +%Y%m%d).db

# 查看备份文件
ls -la db/

# 恢复备份
sudo systemctl stop gt-agent
cp db/gt_agent_backup_YYYYMMDD.db db/gt_agent.db
sudo systemctl start gt-agent
```

### 5. 修改了 .env 配置怎么办？

```bash
# 编辑配置文件
nano ~/Interview_agent/.env

# 修改完后重启服务
sudo systemctl restart gt-agent
```

### 6. API Key 用完了怎么换？

```bash
# 编辑 .env 文件
nano ~/Interview_agent/.env

# 修改 DEEPSEEK_API_KEY=你的新密钥
# Ctrl+O 保存，Ctrl+X 退出

# 重启服务
sudo systemctl restart gt-agent
```

---

## 五、服务器常用命令速查

| 操作 | 命令 |
|------|------|
| 查看服务状态 | `sudo systemctl status gt-agent` |
| 启动服务 | `sudo systemctl start gt-agent` |
| 停止服务 | `sudo systemctl stop gt-agent` |
| 重启服务 | `sudo systemctl restart gt-agent` |
| 查看实时日志 | `sudo journalctl -u gt-agent -f` |
| 查看最近日志 | `sudo journalctl -u gt-agent -n 100 --no-pager` |
| 查看端口占用 | `netstat -tlnp \| grep 8000` |
| 查看磁盘空间 | `df -h` |
| 查看内存使用 | `free -h` |

---

## 六、完整更新工作流

```
本地开发                       GitHub                        云服务器
   │                             │                             │
   │  1. 修改代码                │                             │
   │                             │                             │
   │  2. git add .               │                             │
   │  3. git commit -m "..."     │                             │
   │  4. git push ──────────────▶│                             │
   │                             │                             │
   │                             │  5. 登录云终端              │
   │                             │  6. update-gt-agent ───────▶│
   │                             │                             │  7. 自动拉取+重启
   │                             │                             │
   │                             │  8. 访问网站验证             │
   │◀────────────────────────────│─────────────────────────────│
```

**总结：本地改完 push 到 GitHub，服务器执行 `update-gt-agent` 即可。**
