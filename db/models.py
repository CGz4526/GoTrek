from sqlalchemy import Column, Integer, String, Text, DateTime, ForeignKey, Float, Boolean, JSON
from sqlalchemy.orm import relationship
from datetime import datetime
from db.database import Base


class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    username = Column(String, unique=True, index=True, nullable=False)
    email = Column(String, unique=True, index=True, nullable=False)
    password_hash = Column(String, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)

    projects = relationship("Project", back_populates="owner")
    questions = relationship("Question", back_populates="uploader")
    weights = relationship("QuestionWeight", back_populates="user")
    answer_records = relationship("AnswerRecord", back_populates="user")


class Project(Base):
    __tablename__ = "projects"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    name = Column(String, nullable=False)
    description = Column(Text)
    tech_stack = Column(JSON)
    project_type = Column(String)
    domain_tags = Column(JSON)
    created_at = Column(DateTime, default=datetime.utcnow)

    owner = relationship("User", back_populates="projects")
    question_adaptations = relationship("QuestionProject", back_populates="project")


class Question(Base):
    __tablename__ = "questions"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    content = Column(Text, nullable=False)
    question_type = Column(String, nullable=False)
    category = Column(String)
    source = Column(String)
    original_project_id = Column(Integer, ForeignKey("projects.id"))
    answer = Column(Text)
    difficulty = Column(Integer, default=1)
    starred = Column(Boolean, default=False, server_default="0")
    created_at = Column(DateTime, default=datetime.utcnow)

    uploader = relationship("User", back_populates="questions")
    original_project = relationship("Project")
    adaptations = relationship("QuestionProject", back_populates="question", cascade="all, delete-orphan")
    weights = relationship("QuestionWeight", back_populates="question", cascade="all, delete-orphan")
    answer_records = relationship("AnswerRecord", back_populates="question", cascade="all, delete-orphan")


class InterviewSession(Base):
    """模拟面试会话：保存面试官与用户的对话历史"""
    __tablename__ = "interview_sessions"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    project_id = Column(Integer, ForeignKey("projects.id"), nullable=True)
    project_name = Column(String)
    position = Column(String, default="后端开发")
    status = Column(String, default="active")  # active / ended
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    messages = relationship("InterviewMessage", back_populates="session",
                            order_by="InterviewMessage.id", cascade="all, delete-orphan")


class InterviewMessage(Base):
    """模拟面试会话中的单条消息"""
    __tablename__ = "interview_messages"

    id = Column(Integer, primary_key=True, index=True)
    session_id = Column(Integer, ForeignKey("interview_sessions.id"), nullable=False)
    role = Column(String, nullable=False)  # interviewer / candidate
    content = Column(Text, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)

    session = relationship("InterviewSession", back_populates="messages")


class QuestionCategory(Base):
    __tablename__ = "question_categories"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, nullable=False)
    parent_id = Column(Integer, ForeignKey("question_categories.id"))
    question_type = Column(String, nullable=False)

    parent = relationship("QuestionCategory", remote_side=[id])


class QuestionProject(Base):
    __tablename__ = "question_project"

    id = Column(Integer, primary_key=True, index=True)
    question_id = Column(Integer, ForeignKey("questions.id"), nullable=False)
    project_id = Column(Integer, ForeignKey("projects.id"), nullable=False)
    match_score = Column(Float, default=0.0)
    adapted_content = Column(Text)

    question = relationship("Question", back_populates="adaptations")
    project = relationship("Project", back_populates="question_adaptations")


class QuestionWeight(Base):
    __tablename__ = "question_weights"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    question_id = Column(Integer, ForeignKey("questions.id"), nullable=False)
    weight = Column(Integer, default=0)
    confused_count = Column(Integer, default=0)
    vague_count = Column(Integer, default=0)
    last_review_time = Column(DateTime)
    review_count = Column(Integer, default=0)

    user = relationship("User", back_populates="weights")
    question = relationship("Question", back_populates="weights")


class AnswerRecord(Base):
    __tablename__ = "answer_records"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    question_id = Column(Integer, ForeignKey("questions.id"), nullable=False)
    user_answer = Column(Text)
    is_correct = Column(Boolean)
    score = Column(Integer)
    answered_at = Column(DateTime, default=datetime.utcnow)

    user = relationship("User", back_populates="answer_records")
    question = relationship("Question", back_populates="answer_records")