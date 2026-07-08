from fastapi import APIRouter, Depends, HTTPException, status, Request
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from jose import JWTError, jwt
from passlib.context import CryptContext
from datetime import datetime, timedelta
from sqlalchemy.orm import Session
from dotenv import load_dotenv
import os
import time
from collections import defaultdict

from db.models import User
from db.schemas import UserCreate, UserResponse, Token, TokenData
from db.database import get_db

load_dotenv()

SECRET_KEY = os.getenv("SECRET_KEY", "gt_agent_secret_key")
ALGORITHM = os.getenv("ALGORITHM", "HS256")
ACCESS_TOKEN_EXPIRE_MINUTES = int(os.getenv("ACCESS_TOKEN_EXPIRE_MINUTES", "30"))

# 注册开关：公开服务时建议设为 false
ALLOW_REGISTER = os.getenv("ALLOW_REGISTER", "true").lower() == "true"

pwd_context = CryptContext(schemes=["pbkdf2_sha256"], deprecated="auto")
# auto_error=False：无 token 时不报错，由 get_current_user 决定如何处理
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="api/auth/login", auto_error=False)

router = APIRouter(prefix="/api/auth", tags=["auth"])


# ========== 登录限流（内存版，单机够用） ==========
_LOGIN_LIMIT = int(os.getenv("LOGIN_LIMIT", "5"))      # 次数
_LOGIN_WINDOW = int(os.getenv("LOGIN_WINDOW", "300"))  # 秒（默认 5 分钟）
_login_attempts: dict[str, list[float]] = defaultdict(list)


def _client_ip(request: Request) -> str:
    """获取真实客户端 IP（兼容反向代理）"""
    fwd = request.headers.get("x-forwarded-for")
    if fwd:
        return fwd.split(",")[0].strip()
    return request.client.host if request.client else "unknown"


def _check_login_limit(ip: str):
    """超出限制则抛 429"""
    now = time.time()
    attempts = _login_attempts[ip]
    # 清掉窗口外的
    _login_attempts[ip] = [t for t in attempts if now - t < _LOGIN_WINDOW]
    if len(_login_attempts[ip]) >= _LOGIN_LIMIT:
        retry = int(_LOGIN_WINDOW - (now - _login_attempts[ip][0]))
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail=f"登录失败次数过多，请 {max(retry, 1)} 秒后再试",
        )
    _login_attempts[ip].append(now)


def _clear_login_limit(ip: str):
    """登录成功后清空该 IP 的失败记录"""
    _login_attempts.pop(ip, None)


def verify_password(plain_password: str, hashed_password: str) -> bool:
    return pwd_context.verify(plain_password, hashed_password)


def get_password_hash(password: str) -> str:
    return pwd_context.hash(password)


def create_access_token(data: dict, expires_delta: timedelta | None = None) -> str:
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.utcnow() + expires_delta
    else:
        expire = datetime.utcnow() + timedelta(minutes=15)
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    return encoded_jwt


def get_user(db: Session, username: str) -> User | None:
    return db.query(User).filter(User.username == username).first()


def authenticate_user(db: Session, username: str, password: str) -> User | bool:
    user = get_user(db, username)
    if not user:
        return False
    if not verify_password(password, user.password_hash):
        return False
    return user


async def get_current_user(
    token: str = Depends(oauth2_scheme),
    db: Session = Depends(get_db)
) -> User:
    """获取当前用户。无 token 时返回预设用户（取消登录模式）。

    保留 token 合法性校验：若传了 token 但无效，仍按未登录处理（返回预设用户），
    而不是抛 401，这样前端无需登录即可访问所有接口。
    """
    if token:
        # 传了 token 就校验，合法则返回对应用户
        try:
            payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
            username: str = payload.get("sub")
            if username:
                user = get_user(db, username=username)
                if user:
                    return user
        except JWTError:
            pass  # token 无效，走下面的预设用户兜底

    # 无 token 或 token 无效：返回预设用户（默认 111）
    preset_user = os.getenv("PRESET_USER", "111")
    user = get_user(db, preset_user)
    if user is None:
        # 极端情况：预设用户不存在，取第一个用户
        user = db.query(User).first()
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="系统未初始化，无可用用户",
        )
    return user


@router.post("/register", response_model=UserResponse)
def register(user: UserCreate, db: Session = Depends(get_db)):
    if not ALLOW_REGISTER:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="管理员已关闭注册功能"
        )
    db_user = get_user(db, user.username)
    if db_user:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Username already registered"
        )

    email_exists = db.query(User).filter(User.email == user.email).first()
    if email_exists:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Email already registered"
        )

    hashed_password = get_password_hash(user.password)
    new_user = User(
        username=user.username,
        email=user.email,
        password_hash=hashed_password
    )
    db.add(new_user)
    db.commit()
    db.refresh(new_user)

    return new_user


@router.post("/login", response_model=Token)
def login(request: Request, form_data: OAuth2PasswordRequestForm = Depends(),
          db: Session = Depends(get_db)):
    ip = _client_ip(request)
    _check_login_limit(ip)
    user = authenticate_user(db, form_data.username, form_data.password)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username or password",
            headers={"WWW-Authenticate": "Bearer"},
        )
    _clear_login_limit(ip)

    access_token_expires = timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    access_token = create_access_token(
        data={"sub": user.username}, expires_delta=access_token_expires
    )

    return {"access_token": access_token, "token_type": "bearer"}


@router.get("/me", response_model=UserResponse)
def read_users_me(current_user: User = Depends(get_current_user)):
    return current_user


@router.get("/register-enabled")
def register_enabled():
    """前端用来判断是否显示注册 tab"""
    return {"allow_register": ALLOW_REGISTER}