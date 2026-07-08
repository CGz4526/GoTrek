# GT_agent - 面试题智能学习平台

> 一个帮助开发者准备后端/Agent开发面试的智能学习平台，集成题目提取、智能出题、模拟面试、复习模式等完整学习链路。

## 📸 系统截图

<!-- 建议在本地运行后截图替换以下占位符 -->

### 题目提取页面 - 批量识题
![题目提取-批量识题](docs/screenshots/extract-batch.png)

### 题目提取页面 - 解题问答
![题目提取-解题问答](docs/screenshots/extract-solve.png)

### 题库管理页面
![题库管理](docs/screenshots/library.png)

### 智能出题页面
![智能出题](docs/screenshots/exam.png)

### 模拟面试页面
![模拟面试](docs/screenshots/interview.png)

### 复习模式页面
![复习模式](docs/screenshots/review.png)

---

## 🎯 项目背景与目标

本项目是一个**面试备考智能助手**，旨在解决以下问题：

1. **面经整理效率低**：传统方式需要人工从面经文本中手动提取题目、整理答案
2. **题目质量参差不齐**：网上找到的面经答案往往不准确或不完整
3. **复习缺乏针对性**：不知道哪些题是自己的薄弱点，复习盲目
4. **缺乏实战演练**：只能"看题背答案"，无法模拟真实面试的对话场景

**GT_agent 通过 AI Agent 技术提供完整解决方案：**
- 自动从面经文本/图片中提取题目并补全答案
- 智能出题，根据项目背景生成针对性问题
- 模拟面试官进行多轮对话式面试
- 权重系统追踪掌握度，优先复习薄弱题目

---

## 🏗 系统架构

### 技术栈

| 层级 | 技术 |
|------|------|
| **后端框架** | FastAPI + SQLAlchemy ORM + SQLite |
| **LLM集成** | DeepSeek API (deepseek-chat 模型) |
| **OCR识别** | PaddleOCR (中文识别，支持截图粘贴) |
| **前端** | 纯 HTML/CSS/JS 单文件应用，白底简洁设计 |
| **认证** | OAuth2 + JWT（可选，默认免登录模式） |

### 项目结构

```
Interview_agent/
├── main.py                 # FastAPI 入口，路由注册
├── requirements.txt        # Python 依赖
├── .env                    # 环境变量配置（API Key 等）
├── frontend/
│   └── index.html          # 前端单文件应用（所有页面）
├── api/                    # REST API 路由层
│   ├── auth.py             # 用户认证（登录/注册）
│   ├── questions.py        # 题库 CRUD、OCR、解题接口
│   ├── projects.py         # 项目管理
│   ├── exams.py            # 智能出题
│   ├── review.py           # 复习模式
│   └ interview.py          # 模拟面试
│   ├── llm.py              # LLM 直接调用入口
│   └ review.py             # 复习评估
├── core/                   # 核心业务逻辑层
│   ├── agents/             # 专用 Agent 模块
│   │   ├── base_agent.py   # Agent 基类（封装 LLM 调用）
│   │   ├── extract_agent.py # 识题 Agent：提取题目+补全答案
│   │   ├── answer_agent.py  # 答案 Agent：生成标准答案
│   │   ├── exam_agent.py    # 出题 Agent：生成针对性试卷
│   │   ├── interview_agent.py # 面试 Agent：模拟面试官对话
│   │   ├── review_agent.py   # 复习 Agent：评估回答质量
│   │   ├── project_agent.py  # 项目 Agent：识别项目信息
│   │   └ solve_agent.py      # 解题 Agent：问答+改写题面
│   ├── parser.py           # 文本解析器（正则+LLM）
│   ├── dedup.py            # 题目去重（精确+相似度）
│   ├── weight_manager.py   # 权重管理（追踪掌握度）
│   ├── matcher.py          # 题目-项目匹配器
│   ├── ocr.py              # OCR 封装（PaddleOCR）
│   ├── llm_client.py       # DeepSeek API 客户端
│   └ project_analyzer.py   # 项目分析器
├── db/                     # 数据层
│   ├── models.py           # ORM 模型定义
│   ├── schemas.py          # Pydantic Schema
│   ├── database.py         # 数据库连接
├── utils/                  # 工具模块
│   ├── classifier.py       # 题目分类器
│   ├── text_utils.py       # 文本处理工具
│   ├── pdf_parser.py       # PDF 解析器
│   └ custom_dict.txt       # 自定义分类词典
```

### 核心模块交互图

```
┌─────────────────────────────────────────────────────────────────────┐
│                         前端 (index.html)                           │
│  ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌──────────┐  │
│  │题目提取   │ │题库管理   │ │智能出题   │ │模拟面试   │ │复习模式   │  │
│  └────┬─────┘ └────┬─────┘ └────┬─────┘ └────┬─────┘ └────┬─────┘  │
└───────┼────────────┼────────────┼────────────┼────────────┼─────────┘
        │            │            │            │            │
        ▼            ▼            ▼            ▼            ▼
┌─────────────────────────────────────────────────────────────────────┐
│                        REST API Layer                                │
│  /api/questions  /api/projects  /api/exams  /api/interview  /api/review │
└───────┬────────────┬────────────┬────────────┬────────────┬─────────┘
        │            │            │            │            │
        ▼            ▼            ▼            ▼            ▼
┌─────────────────────────────────────────────────────────────────────┐
│                        Agent Layer (core/agents/)                    │
│                                                                      │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐ │
│  │ExtractAgent │  │ ExamAgent   │  │InterviewAgent│  │ReviewAgent  │ │
│  │识题+补全答案 │  │生成试卷     │  │对话式面试   │  │评估回答     │ │
│  └──────┬──────┘  └──────┬──────┘  └──────┬──────┘  └──────┬──────┘ │
│         │                │                │                │        │
│         └────────────────┴────────────────┴────────────────┘        │
│                                    │                                 │
│                                    ▼                                 │
│                          ┌──────────────────┐                       │
│                          │   BaseAgent      │                       │
│                          │  (LLM Client)    │                       │
│                          │  DeepSeek API    │                       │
│                          └──────────────────┘                       │
└─────────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
┌─────────────────────────────────────────────────────────────────────┐
│                        Data Layer (SQLite)                           │
│                                                                      │
│  ┌──────────────┐ ┌──────────────┐ ┌──────────────┐ ┌────────────┐ │
│  │  questions   │ │  projects    │ │ question_    │ │ interview_ │ │
│  │  题库表      │ │  项目表      │ │ weights      │ │ sessions   │ │
│  │              │ │              │ │ 权重追踪     │ │ 面试记录   │ │
│  └──────────────┘ └──────────────┘ └──────────────┘ └────────────┘ │
└─────────────────────────────────────────────────────────────────────┘
```

---

## 🧠 核心功能详解

### 1️⃣ 题目提取模块

**两种模式：**

| 模式 | 功能 | 适用场景 |
|------|------|----------|
| **批量识题** | 从面经文本/图片中批量提取题目，自动补全答案 | 整理网上找到的面经 |
| **解题问答** | 对话式提问，AI 解答并自动改写为标准题存入题库 | 学习时遇到不懂的问题直接问 |

**批量识题流程：**
```
用户粘贴面经文本/截图 OCR
    ↓
ExtractAgent（LLM）识别题目结构
    ↓
AnswerAgent（LLM）补全缺失答案
    ↓
去重检查（精确匹配 + 相似度匹配）
    ↓
存入题库
```

**解题问答流程：**
```
用户提问（如"Redis缓存穿透是什么？"）
    ↓
SolveAgent 解答 + 改写为标准题面
    ↓
自动存入题库（高权重，标记为薄弱点）
    ↓
优先在复习模式出现
```

### 2️⃣ 智能出题模块

根据用户选择的项目和模式生成针对性试卷：

| 模式 | 说明 |
|------|------|
| **八股题模式** | 纯技术原理题，适合刷基础 |
| **项目题模式** | 结合项目背景的实战题 |
| **混合模式** | 60% 项目题 + 40% 八股题 |

**生成策略：**
1. 从题库匹配相关题目（根据项目技术栈、分类）
2. LLM 生成新题（结合项目背景改写）
3. 自动去重，避免重复
4. 生成的题目可一键加入题库

### 3️⃣ 模拟面试模块

**对话式面试体验：**
- 选择项目后，面试官（InterviewAgent）进行多轮对话
- 递进式提问：架构 → 技术选型 → 难点攻坚 → 八股原理
- 每轮给出简短评价后追问
- 面试结束后可提取题目到题库

**Agent 行为设计：**
```
开场：简短寒暄 + 第一个问题
过程：评价回答 → 追问/延伸/切换话题
结束：总结评价（优点+改进点）
```

### 4️⃣ 复习模式

**权重系统追踪掌握度：**

| 场景 | 权重变化 |
|------|----------|
| 标记"困惑" | +20 权重 |
| 回答错误 | +15 权重 |
| 回答正确 | -10 权重 |
| 解题问答新题 | +30 权重（初始高权重） |
| 超过 7 天未复习 | -5 权重（时间衰减） |

**复习流程：**
```
按权重排序，优先出高权重题目
    ↓
用户口述回答
    ↓
ReviewAgent 评估回答质量（分数+反馈）
    ↓
更新权重，继续下一题
```

### 5️⃣ 项目管理模块

- 上传简历 PDF 或手动输入项目描述
- ProjectAgent 自动识别项目名称、类型、技术栈
- 自动匹配题库中相关题目
- 作为智能出题和模拟面试的背景

---

## 🔧 快速启动

### 1. 环境准备

```bash
# 克隆项目
git clone https://github.com/你的用户名/Interview_agent.git
cd Interview_agent

# 创建虚拟环境（推荐）
python -m venv venv
source venv/bin/activate  # Linux/Mac
# 或 venv\Scripts\activate  # Windows

# 安装依赖
pip install -r requirements.txt
```

### 2. 配置 API Key

创建 `.env` 文件：

```env
DEEPSEEK_API_KEY=你的DeepSeek API Key
SECRET_KEY=随机字符串用于JWT签名
PUBLIC_MODE=false
```

**获取 DeepSeek API Key：**
1. 访问 https://platform.deepseek.com/
2. 注册并创建 API Key
3. 填入 `.env` 文件

### 3. 启动服务

```bash
# 方式1：直接运行
python main.py

# 方式2：使用 uvicorn（推荐）
uvicorn main:app --host 0.0.0.0 --port 8000
```

访问 http://localhost:8000 即可使用。

---

## 📝 API 接口说明

### 题库相关

| 接口 | 方法 | 说明 |
|------|------|------|
| `/api/questions/` | GET | 获取题库列表（支持筛选） |
| `/api/questions/` | POST | 手动添加题目 |
| `/api/questions/upload` | POST | 批量识题（文本解析） |
| `/api/questions/ocr` | POST | OCR 图片识别 |
| `/api/questions/solve` | POST | 解题问答（自动入库） |
| `/api/questions/{id}` | PUT | 编辑题目 |
| `/api/questions/{id}` | DELETE | 删除题目 |
| `/api/questions/{id}/mark-confused` | POST | 标记困惑 |
| `/api/questions/{id}/star` | POST | 星标收藏 |

### 模拟面试

| 接口 | 方法 | 说明 |
|------|------|------|
| `/api/interview/` | POST | 创建面试会话 |
| `/api/interview/{id}/chat` | POST | 发送候选人回答 |
| `/api/interview/{id}/end` | POST | 结束面试 |
| `/api/interview/{id}/extract` | POST | 提取题目到题库 |

### 复习模式

| 接口 | 方法 | 说明 |
|------|------|------|
| `/api/review/start` | POST | 开始复习会话 |
| `/api/review/next` | GET | 获取下一题 |
| `/api/review/submit` | POST | 提交回答并评估 |

---

## 🎨 界面设计理念

- **白底简洁风格**：专注内容，减少视觉干扰
- **行列表布局**：题库管理一屏可见多道题，点击展开答案
- **对话式交互**：模拟面试和复习模式采用聊天气泡风格
- **即时反馈**：AI 回答实时显示，无需等待全加载

---

## 🔐 安全与部署

### 本地开发模式（默认）

- 无需登录，自动以预设用户身份使用
- 适合个人学习使用

### 公开部署模式

修改 `.env`：
```env
PUBLIC_MODE=true
PRESET_USER=你的用户名
PRESET_PASSWORD=强密码
ALLOW_REGISTER=false
```

效果：
- 关闭 API 文档公开访问（/docs、/redoc）
- 必须登录才能使用
- 关闭注册功能

---

## 📊 数据模型

### 主要表结构

```sql
-- 用户表
users (id, username, email, password_hash, created_at)

-- 题库表
questions (id, user_id, content, question_type, category, 
           source, answer, difficulty, starred, created_at)

-- 项目表
projects (id, user_id, name, description, tech_stack, 
          project_type, domain_tags, created_at)

-- 权重表（追踪掌握度）
question_weights (id, user_id, question_id, weight, 
                  review_count, confused_count, last_review_time)

-- 面试会话表
interview_sessions (id, user_id, project_id, position, 
                    question_count, status, created_at)

-- 面试消息表
interview_messages (id, session_id, role, content, created_at)
```

---

## 🚀 技术亮点

1. **Agent 架构设计**
   - 统一 BaseAgent 封装 LLM 调用、JSON 解析
   - 7 个专用 Agent 各司其职，职责清晰
   - LLM Prompt 精心设计，输出格式规范

2. **题目去重算法**
   - 精确匹配：规范化后字符串相同
   - 相似度匹配：bigram Jaccard ≥ 0.8 或包含关系
   - 短题保护：<6 字只走精确匹配

3. **权重追踪系统**
   - 多维度权重变化（困惑、回答、时间衰减）
   - 优先复习薄弱题目
   - 新题高权重初始化

4. **OCR 集成**
   - PaddleOCR 中文识别
   - 支持 Ctrl+V 粘贴截图
   - 懒加载优化启动速度

---

## 📸 截图指南

建议在本地运行后截取以下界面，放入 `docs/screenshots/` 目录：

1. **题目提取-批量识题**：粘贴一段面经文本，点击"开始解析"后的结果
2. **题目提取-解题问答**：切换到"解题问答" tab，提问后的对话界面
3. **题库管理**：题库有多道题时的列表界面，展开一道题看答案
4. **智能出题**：选择项目和模式后生成的试卷界面
5. **模拟面试**：面试对话界面，包含面试官和候选人的消息
6. **复习模式**：复习时的对话框，包含题目、回答、评估反馈

---

## 📄 License

MIT License

---

## 🙏 致谢

- [DeepSeek](https://www.deepseek.com/) - 提供强大的 LLM API
- [PaddleOCR](https://github.com/PaddlePaddle/PaddleOCR) - 中文 OCR 支持
- [FastAPI](https://fastapi.tiangolo.com/) - 现代化 Python Web 框架