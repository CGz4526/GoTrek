# GT_agent 启动指南

> 面试题学习平台 · FastAPI + SQLite · 单机部署

---

## 一、环境准备（首次使用 / 换电脑时执行一次）

### 1. 安装 Python 3.10+

到 https://www.python.org/downloads/ 下载安装，安装时勾选 **Add Python to PATH**。

验证：
```powershell
python --version
```

### 2. 安装依赖

进入项目目录：
```powershell
cd d:\CCDevelop\Interview_agent
pip install -r requirements.txt
```

---

## 二、配置文件 `.env`

项目根目录下的 `.env` 控制所有运行参数。**关键字段说明**：

```env
DATABASE_URL=sqlite:///./gt_agent.db      # 数据库文件（不要改）
SECRET_KEY=eb7ae4ad...                    # JWT 密钥（勿泄露）
DEEPSEEK_API_KEY=sk-xxx                   # DeepSeek API Key

PUBLIC_MODE=true                          # true=公开模式（内网穿透/公网）；false=本地模式
ALLOW_REGISTER=false                      # 是否允许注册（公开模式建议 false）
LOGIN_LIMIT=5                             # 登录失败次数上限
LOGIN_WINDOW=300                          # 限流窗口（秒）

PRESET_USER=111                           # 预设账号
PRESET_PASSWORD=Gt@2026#Interview         # 预设账号密码
```

### 两种使用模式

| 模式 | `PUBLIC_MODE` | 用途 | 注册 | `/docs` | 密码强度 |
|------|--------------|------|------|---------|---------|
| 本地 | `false` | 自己电脑上用 | 开放 | 可访问 | 默认 111/111 可用 |
| 公开 | `true` | 内网穿透/公网部署 | 关闭 | 关闭 | 必须用强密码 |

**切换模式**：改 `.env` 后重启服务即可。

---

## 三、启动命令

### 启动后端（同时提供前端页面）

```powershell
cd d:\CCDevelop\Interview_agent
python -m uvicorn main:app --host 0.0.0.0 --port 8000
```

看到以下输出即成功：
```
INFO:     Uvicorn running on http://0.0.0.0:8000 (Press CTRL+C to quit)
INFO:     Application startup complete.
```

### 访问地址

| 地址 | 说明 |
|------|------|
| http://localhost:8000 | 前端页面 |
| http://localhost:8000/docs | API 文档（仅本地模式） |
| http://localhost:8000/health | 健康检查 |

### 登录账号

- **本地模式**：`111` / `111`
- **公开模式**：`111` / `Gt@2026#Interview`

### 停止服务

在终端按 `Ctrl + C`。

---

## 四、常用操作

### 后台运行（关闭终端不退出）

```powershell
Start-Process python -ArgumentList "-m","uvicorn","main:app","--host","0.0.0.0","--port","8000" -WorkingDirectory "d:\CCDevelop\Interview_agent" -WindowStyle Hidden
```

### 查看是否在运行

```powershell
netstat -ano | findstr :8000
```
有输出说明在跑，最后一列是 PID。

### 强制停止（按 PID）

```powershell
taskkill /F /PID <上一条命令显示的PID>
```

### 查看实时日志

前台启动时日志直接输出在终端。后台启动如需日志，加日志重定向：

```powershell
python -m uvicorn main:app --host 0.0.0.0 --port 8000 >> server.log 2>&1
```

然后用 `Get-Content server.log -Wait` 实时查看。

---

## 五、数据备份与迁移

### 数据在哪里

所有数据都在 **`gt_agent.db`** 这一个 SQLite 文件里（项目根目录）。题库、项目、面试记录、用户全部在这里。

### 备份

```powershell
Copy-Item gt_agent.db "gt_agent_backup_$(Get-Date -Format yyyyMMdd).db"
```

### 换电脑迁移

1. 整个 `d:\CCDevelop\Interview_agent` 文件夹拷到新电脑
2. 新电脑装 Python + `pip install -r requirements.txt`
3. 改 `.env`（如果路径或 API Key 有变）
4. `python -m uvicorn main:app --host 0.0.0.0 --port 8000` 启动

数据库会自动迁移（新增列、新表），不会丢数据。

---

## 六、手机访问（内网穿透）

### 1. 安装 cpolar

到 https://www.cpolar.com/download 下载 Windows 客户端，注册账号，拿到 authtoken。

```powershell
cpolar authtoken 你的token
```

### 2. 启动隧道

确保后端服务已在 8000 端口运行，然后另开一个终端：

```powershell
cpolar http 8000
```

输出会显示一个公网地址，形如：
```
Forwarding   https://xxx.r6.cpolar.top -> http://localhost:8000
```

### 3. 手机访问

用手机浏览器打开那个 **https** 地址，登录即可。

**注意**：
- 电脑必须保持开机 + 后端运行 + cpolar 隧道开着
- 免费版 URL 每次重启 cpolar 会变
- 建议用公开模式（`PUBLIC_MODE=true`）+ 强密码

---

## 七、故障排查

### 启动报错 `Address already in use`

8000 端口被占用，先停掉旧进程：
```powershell
netstat -ano | findstr :8000
taskkill /F /PID <显示的PID>
```

### 启动报错 `ModuleNotFoundError`

依赖没装全：
```powershell
pip install -r requirements.txt
```

### 前端能打开但登录失败

- 检查 `.env` 里的 `PRESET_PASSWORD` 是否是你用的密码
- 公开模式下默认密码已从 `111` 升级为 `Gt@2026#Interview`
- 5 次失败会被锁定 5 分钟

### LLM 功能（出题/面试/答案）不工作

- 检查 `.env` 里 `DEEPSEEK_API_KEY` 是否有效
- 看后端日志有没有 `ExamAgent failed` 或 `InterviewAgent error`

### 数据库锁死 / 报错

```powershell
# 停掉服务
# 备份后删除
Move-Item gt_agent.db gt_agent.db.bak
# 重启服务会自动创建空库，预设账号会自动创建
python -m uvicorn main:app --host 0.0.0.0 --port 8000
```

---

## 八、项目结构速查

```
d:\CCDevelop\Interview_agent\
├── main.py                 # 入口，启动文件
├── .env                    # 配置文件（改这里）
├── requirements.txt        # 依赖清单
├── gt_agent.db             # 数据库（所有数据在这）
├── api/                    # 后端 API 路由
│   ├── auth.py             # 登录/注册
│   ├── questions.py        # 题库管理
│   ├── projects.py         # 项目管理
│   ├── exams.py            # 智能出题
│   ├── review.py           # 复习模式
│   └── interview.py        # 模拟面试
├── core/agents/            # 5 个独立 Agent
├── db/                     # 数据库模型
└── frontend/index.html     # 前端单文件
```

---

## 快速启动 Cheat Sheet

```powershell
# 一次性命令：进目录 + 装依赖
cd d:\CCDevelop\Interview_agent
pip install -r requirements.txt

# 每次启动：
python -m uvicorn main:app --host 0.0.0.0 --port 8000

# 浏览器打开：
# http://localhost:8000
# 账号 111 / Gt@2026#Interview（公开模式）
# 账号 111 / 111（本地模式）

# 停止：Ctrl+C
```
