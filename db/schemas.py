from pydantic import BaseModel, EmailStr
from datetime import datetime
from typing import Optional, List, Dict


class UserCreate(BaseModel):
    username: str
    email: EmailStr
    password: str


class UserResponse(BaseModel):
    id: int
    username: str
    email: str
    created_at: datetime

    class Config:
        from_attributes = True


class Token(BaseModel):
    access_token: str
    token_type: str


class TokenData(BaseModel):
    username: Optional[str] = None


class ProjectCreate(BaseModel):
    name: str
    description: str
    tech_stack: Optional[List[str]] = None
    project_type: Optional[str] = None
    domain_tags: Optional[List[str]] = None


class ProjectResponse(BaseModel):
    id: int
    name: str
    description: str
    tech_stack: List[str]
    project_type: str
    domain_tags: List[str]
    created_at: datetime

    class Config:
        from_attributes = True


class QuestionCreate(BaseModel):
    content: str
    question_type: str
    category: Optional[str] = None
    source: Optional[str] = None
    original_project_id: Optional[int] = None
    answer: Optional[str] = None
    difficulty: Optional[int] = 1


class QuestionResponse(BaseModel):
    id: int
    content: str
    question_type: str
    category: str
    source: str
    answer: str
    difficulty: int
    starred: Optional[bool] = False
    created_at: datetime
    weight: Optional[int] = 0
    vague_count: Optional[int] = 0

    class Config:
        from_attributes = True


class InterviewStartRequest(BaseModel):
    project_id: Optional[int] = None
    position: Optional[str] = "后端开发"


class InterviewChatRequest(BaseModel):
    message: str


class InterviewMessageOut(BaseModel):
    id: int
    role: str
    content: str
    created_at: datetime

    class Config:
        from_attributes = True


class InterviewSessionOut(BaseModel):
    id: int
    project_id: Optional[int] = None
    project_name: Optional[str] = None
    position: str
    status: str
    created_at: datetime
    updated_at: Optional[datetime] = None
    message_count: int = 0
    last_message: Optional[str] = None

    class Config:
        from_attributes = True


class InterviewChatResponse(BaseModel):
    session_id: int
    role: str
    content: str
    should_end: bool = False


class QuestionUpload(BaseModel):
    text: str


class QuestionMarkConfused(BaseModel):
    question_id: int


class ExamGenerate(BaseModel):
    mode: str
    project_id: Optional[int] = None
    category: Optional[str] = None
    count: Optional[int] = 10


class ExamResponse(BaseModel):
    id: int
    questions: List[QuestionResponse]
    generated_at: datetime


class ReviewStart(BaseModel):
    count: Optional[int] = 10


class ReviewQuestion(BaseModel):
    question: QuestionResponse
    is_weighted: bool


class ReviewSubmit(BaseModel):
    question_id: int
    user_answer: str
    is_confused: Optional[bool] = False


class ReviewProgress(BaseModel):
    total_reviewed: int
    correct_count: int
    confused_count: int
    current_weight_distribution: Dict[str, int]