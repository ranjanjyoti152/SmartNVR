from sqlalchemy import Boolean, Column, ForeignKey, Integer, String, DateTime, Float, UniqueConstraint
from sqlalchemy.orm import relationship
from datetime import datetime
from database import Base

class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    email = Column(String, unique=True, index=True)
    username = Column(String, unique=True, index=True)
    hashed_password = Column(String)
    created_at = Column(DateTime, default=datetime.utcnow)
    is_active = Column(Boolean, default=True)

    # Relationships
    cameras = relationship("Camera", back_populates="owner")
    recordings = relationship("Recording", back_populates="owner")

class Camera(Base):
    __tablename__ = "cameras"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, index=True)
    url = Column(String)
    owner_id = Column(Integer, ForeignKey("users.id"))
    created_at = Column(DateTime, default=datetime.utcnow)
    last_active = Column(DateTime, nullable=True)
    ai_enabled = Column(Boolean, default=True)
    is_recording = Column(Boolean, default=False)
    status = Column(String, default="offline")  # offline, online, error

    # Relationships
    owner = relationship("User", back_populates="cameras")
    recordings = relationship("Recording", back_populates="camera")

    # Allow multiple cameras with same URL but unique names per user
    __table_args__ = (
        UniqueConstraint('owner_id', 'name', name='unique_camera_name_per_user'),
    )

class Recording(Base):
    __tablename__ = "recordings"

    id = Column(Integer, primary_key=True, index=True)
    camera_id = Column(Integer, ForeignKey("cameras.id"))
    owner_id = Column(Integer, ForeignKey("users.id"))
    filename = Column(String)
    start_time = Column(DateTime, default=datetime.utcnow)
    end_time = Column(DateTime, nullable=True)
    file_size = Column(Float, default=0.0)  # Size in MB
    duration = Column(Float, default=0.0)    # Duration in seconds
    has_motion = Column(Boolean, default=False)
    has_person = Column(Boolean, default=False)

    # Relationships
    camera = relationship("Camera", back_populates="recordings")
    owner = relationship("User", back_populates="recordings")

class SystemSettings(Base):
    __tablename__ = "system_settings"

    id = Column(Integer, primary_key=True, index=True)
    key = Column(String, unique=True, index=True)
    value = Column(String)
    updated_at = Column(DateTime, default=datetime.utcnow)

class CameraEvent(Base):
    __tablename__ = "camera_events"

    id = Column(Integer, primary_key=True, index=True)
    camera_id = Column(Integer, ForeignKey("cameras.id"))
    event_type = Column(String, index=True)  # motion, person, error, etc.
    timestamp = Column(DateTime, default=datetime.utcnow)
    details = Column(String, nullable=True)
    
    # Relationships
    camera = relationship("Camera")
