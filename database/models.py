from sqlalchemy import create_engine, Column, Integer, String, DateTime, ForeignKey, Enum as SQLEnum
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import relationship
from datetime import datetime
import enum

Base = declarative_base()

class VideoStatus(enum.Enum):
    NEW = 'new'
    PROCESSED = 'processed'
    ARCHIVED = 'archived'

class K2SStatus(enum.Enum):
    PENDING = 'pending'
    QUEUED = 'queued'
    UPLOADING = 'uploading'
    UPLOADED = 'uploaded'
    FAILED = 'failed'
    EXPIRED = 'expired'

class TelegramStatus(enum.Enum):
    PENDING = 'pending'
    UPLOADED = 'uploaded'
    FAILED = 'failed'

class Video(Base):
    __tablename__ = 'videos'

    id = Column(Integer, primary_key=True)
    filename = Column(String)
    path = Column(String)
    status = Column(SQLEnum(VideoStatus), default=VideoStatus.NEW)
    k2s_status = Column(SQLEnum(K2SStatus), default=K2SStatus.PENDING)
    k2s_link = Column(String)
    created_at = Column(DateTime, default=datetime.utcnow)

    clips = relationship("Clip", back_populates="video")

class Clip(Base):
    __tablename__ = 'clips'

    id = Column(Integer, primary_key=True)
    video_id = Column(Integer, ForeignKey('videos.id'))
    filename = Column(String)
    path = Column(String)
    start_time = Column(Integer)
    end_time = Column(Integer)
    k2s_link = Column(String)
    telegram_status = Column(SQLEnum(TelegramStatus), default=TelegramStatus.PENDING)
    telegram_link = Column(String)
    created_at = Column(DateTime, default=datetime.utcnow)

    video = relationship("Video", back_populates="clips") 