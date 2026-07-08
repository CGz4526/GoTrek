from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
import os
from dotenv import load_dotenv

from db.database import engine, Base, SessionLocal
from db import models
from api.auth import router as auth_router, get_password_hash
from api.questions import router as questions_router
from api.projects import router as projects_router
from api.exams import router as exams_router
from api.review import router as review_router
from api.llm import router as llm_router
from api.interview import router as interview_router

load_dotenv()
Base.metadata.create_all(bind=engine)

# 是否为公开部署模式（公网/内网穿透暴露时建议设为 true）
PUBLIC_MODE = os.getenv("PUBLIC_MODE", "false").lower() == "true"


def _migrate_db():
    """对已有 SQLite 数据库做轻量迁移：添加 questions.starred 列。
    新增的表（interview_sessions / interview_messages）由 create_all 自动创建。"""
    from sqlalchemy import text, inspect
    insp = inspect(engine)
    if 'questions' in insp.get_table_names():
        cols = [c['name'] for c in insp.get_columns('questions')]
        if 'starred' not in cols:
            with engine.connect() as conn:
                conn.execute(text("ALTER TABLE questions ADD COLUMN starred BOOLEAN DEFAULT 0 NOT NULL"))
                conn.commit()


_migrate_db()


def init_preset_account():
    """启动时创建/修正预设账号。
    预设用户名/密码由环境变量控制（PRESET_USER / PRESET_PASSWORD），
    默认 111/111 仅在非公开模式使用；公开模式下若未设置环境变量则不创建弱密码账号。
    """
    preset_user = os.getenv("PRESET_USER") or "111"
    preset_pwd = os.getenv("PRESET_PASSWORD") or ("" if PUBLIC_MODE else "111")
    if not preset_pwd:
        # 公开模式且未配置密码 -> 跳过创建，避免弱密码暴露
        return
    db = SessionLocal()
    try:
        existing = db.query(models.User).filter(models.User.username == preset_user).first()
        if not existing:
            db.add(models.User(
                username=preset_user,
                email=f"{preset_user}@gtagent.com",
                password_hash=get_password_hash(preset_pwd)
            ))
            db.commit()
            print(f"预设账号 {preset_user} 创建成功")
        else:
            # 公开模式下，把默认弱密码 111 升级为环境变量配置的密码
            if PUBLIC_MODE and preset_pwd != "111":
                from api.auth import verify_password
                if not verify_password(preset_pwd, existing.password_hash):
                    existing.password_hash = get_password_hash(preset_pwd)
                    db.commit()
                    print(f"已更新预设账号 {preset_user} 的密码（公开模式安全升级）")
    finally:
        db.close()


init_preset_account()

# 公开模式下关闭 API 文档公开访问
app = FastAPI(
    title="GT_agent - 面试题学习平台",
    description="一个帮助开发者准备后端/agent开发面试的智能学习平台",
    version="1.0.0",
    docs_url=None if PUBLIC_MODE else "/docs",
    redoc_url=None if PUBLIC_MODE else "/redoc",
    openapi_url=None if PUBLIC_MODE else "/openapi.json"
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth_router)
app.include_router(questions_router)
app.include_router(projects_router)
app.include_router(exams_router)
app.include_router(review_router)
app.include_router(llm_router)
app.include_router(interview_router)

app.mount("/static", StaticFiles(directory="frontend"), name="static")


@app.get("/")
def root():
    return FileResponse("frontend/index.html")


@app.get("/index.html")
def index():
    return FileResponse("frontend/index.html")


@app.get("/health")
def health_check():
    return {"status": "healthy"}