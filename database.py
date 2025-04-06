from sqlalchemy import create_engine, Column, Integer, String, DateTime, Float, Boolean, LargeBinary, ForeignKey, func, Text
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, relationship
import os
import datetime
import logging
from pathlib import Path
import shutil
import zipfile
import tempfile
import json

# Configure logging
logger = logging.getLogger(__name__)

# Create database directory if it doesn't exist
DB_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'database')
os.makedirs(DB_DIR, exist_ok=True)

# Database file path
DB_PATH = os.path.join(DB_DIR, 'smartnvr.db')

# Create SQLAlchemy engine
engine = create_engine(f'sqlite:///{DB_PATH}', connect_args={'check_same_thread': False})
Base = declarative_base()
Session = sessionmaker(bind=engine)

class Recording(Base):
    """Model for video recordings"""
    __tablename__ = 'recordings'
    
    id = Column(Integer, primary_key=True)
    stream_id = Column(String(36), nullable=False)
    camera_name = Column(String(100), nullable=False)
    timestamp = Column(DateTime, default=datetime.datetime.utcnow, index=True)
    duration = Column(Float, default=0.0)  # Duration in seconds
    size_bytes = Column(Integer, default=0)
    format = Column(String(10), default='mp4')
    path = Column(String(255), nullable=True)  # Physical path for hybrid storage
    content = Column(LargeBinary, nullable=True)  # Binary content for full DB storage
    has_file = Column(Boolean, default=False)  # Indicates if recording exists as file
    has_content = Column(Boolean, default=False)  # Indicates if content stored in DB
    
    # Metadata
    width = Column(Integer, nullable=True)
    height = Column(Integer, nullable=True)
    fps = Column(Float, nullable=True)
    bitrate = Column(Integer, nullable=True)
    
    # Event metadata
    event_id = Column(String(36), nullable=True)
    tags = Column(Text, nullable=True)  # JSON serialized tags
    
    def __repr__(self):
        return f"Recording(id={self.id}, camera={self.camera_name}, timestamp={self.timestamp})"


def init_db():
    """Initialize the database"""
    try:
        Base.metadata.create_all(engine)
        logger.info(f"Database initialized at {DB_PATH}")
    except Exception as e:
        logger.error(f"Failed to initialize database: {e}")
        raise


def get_session():
    """Get a database session"""
    return Session()


def store_recording(stream_id, camera_name, filepath, store_binary=False):
    """Store recording information in database
    
    Args:
        stream_id: ID of the stream
        camera_name: Name of the camera
        filepath: Path to the recording file
        store_binary: Whether to store the binary content in DB (hybrid mode if False)
        
    Returns:
        Recording object
    """
    try:
        session = get_session()
        
        # Get file information
        file_path = Path(filepath)
        if not file_path.exists():
            logger.error(f"Recording file not found: {filepath}")
            return None
            
        file_size = file_path.stat().st_size
        file_mtime = datetime.datetime.fromtimestamp(file_path.stat().st_mtime)
        
        # Create recording object
        recording = Recording(
            stream_id=stream_id,
            camera_name=camera_name,
            timestamp=file_mtime,
            size_bytes=file_size,
            format=file_path.suffix[1:],  # Remove the dot
            path=str(filepath),
            has_file=True
        )
        
        # Store binary content if requested (hybrid mode)
        if store_binary:
            with open(filepath, 'rb') as f:
                recording.content = f.read()
                recording.has_content = True
        
        # Save to database
        session.add(recording)
        session.commit()
        
        logger.info(f"Recording stored in database: {recording}")
        return recording
        
    except Exception as e:
        logger.error(f"Failed to store recording: {e}")
        if session:
            session.rollback()
        return None
    finally:
        if session:
            session.close()


def get_recordings_by_date_range(start_date, end_date, stream_id=None):
    """Get recordings within a date range
    
    Args:
        start_date: Start date (datetime.datetime)
        end_date: End date (datetime.datetime)
        stream_id: Optional stream ID to filter by
        
    Returns:
        List of Recording objects
    """
    try:
        session = get_session()
        query = session.query(Recording).filter(
            Recording.timestamp >= start_date,
            Recording.timestamp <= end_date
        )
        
        if stream_id:
            query = query.filter(Recording.stream_id == stream_id)
            
        recordings = query.order_by(Recording.timestamp.desc()).all()
        return recordings
        
    except Exception as e:
        logger.error(f"Failed to get recordings: {e}")
        return []
    finally:
        if session:
            session.close()


def export_recordings_by_timeline(start_date, end_date, export_path, stream_ids=None, format="zip"):
    """Export recordings within a date range to a zip file or directory
    
    Args:
        start_date: Start date (datetime.datetime)
        end_date: End date (datetime.datetime)
        export_path: Path to save the export
        stream_ids: Optional list of stream IDs to filter by
        format: Export format ('zip' or 'directory')
        
    Returns:
        Path to the export file/directory or None if failed
    """
    try:
        session = get_session()
        query = session.query(Recording).filter(
            Recording.timestamp >= start_date,
            Recording.timestamp <= end_date
        )
        
        if stream_ids:
            if isinstance(stream_ids, list):
                query = query.filter(Recording.stream_id.in_(stream_ids))
            else:
                query = query.filter(Recording.stream_id == stream_ids)
        
        recordings = query.order_by(Recording.timestamp).all()
        
        if not recordings:
            logger.info(f"No recordings found for the specified timeline")
            return None
            
        # Create metadata
        metadata = {
            "export_date": datetime.datetime.now().isoformat(),
            "start_date": start_date.isoformat(),
            "end_date": end_date.isoformat(),
            "recording_count": len(recordings),
            "streams": list(set(rec.stream_id for rec in recordings)),
            "cameras": list(set(rec.camera_name for rec in recordings)),
            "recordings": [{
                "id": rec.id,
                "stream_id": rec.stream_id,
                "camera_name": rec.camera_name,
                "timestamp": rec.timestamp.isoformat(),
                "duration": rec.duration,
                "size_bytes": rec.size_bytes,
                "format": rec.format,
                "filename": f"{rec.camera_name}_{rec.timestamp.strftime('%Y%m%d_%H%M%S')}.{rec.format}"
            } for rec in recordings]
        }
        
        if format == "zip":
            # Create a temporary directory
            temp_dir = tempfile.mkdtemp()
            try:
                # Create zip file
                zip_path = export_path if export_path.endswith('.zip') else f"{export_path}.zip"
                
                # Save metadata
                with open(os.path.join(temp_dir, "metadata.json"), "w") as f:
                    json.dump(metadata, f, indent=2)
                
                with zipfile.ZipFile(zip_path, 'w', zipfile.ZIP_DEFLATED) as zipf:
                    # Add metadata to zip
                    zipf.write(os.path.join(temp_dir, "metadata.json"), "metadata.json")
                    
                    # Add recordings to zip
                    for rec in recordings:
                        if rec.has_file and rec.path and os.path.exists(rec.path):
                            # Generate filename based on camera and timestamp
                            filename = f"{rec.camera_name}_{rec.timestamp.strftime('%Y%m%d_%H%M%S')}.{rec.format}"
                            zipf.write(rec.path, f"recordings/{filename}")
                        elif rec.has_content and rec.content:
                            # For recordings stored directly in the database
                            filename = f"{rec.camera_name}_{rec.timestamp.strftime('%Y%m%d_%H%M%S')}.{rec.format}"
                            temp_file = os.path.join(temp_dir, filename)
                            with open(temp_file, 'wb') as f:
                                f.write(rec.content)
                            zipf.write(temp_file, f"recordings/{filename}")
                
                logger.info(f"Exported {len(recordings)} recordings to {zip_path}")
                return zip_path
                
            finally:
                shutil.rmtree(temp_dir)  # Clean up temp directory
                
        elif format == "directory":
            # Create export directory
            os.makedirs(export_path, exist_ok=True)
            
            # Save metadata
            with open(os.path.join(export_path, "metadata.json"), "w") as f:
                json.dump(metadata, f, indent=2)
                
            # Copy recordings to directory
            recordings_dir = os.path.join(export_path, "recordings")
            os.makedirs(recordings_dir, exist_ok=True)
            
            for rec in recordings:
                if rec.has_file and rec.path and os.path.exists(rec.path):
                    # Generate filename based on camera and timestamp
                    filename = f"{rec.camera_name}_{rec.timestamp.strftime('%Y%m%d_%H%M%S')}.{rec.format}"
                    shutil.copy2(rec.path, os.path.join(recordings_dir, filename))
                elif rec.has_content and rec.content:
                    # For recordings stored directly in the database
                    filename = f"{rec.camera_name}_{rec.timestamp.strftime('%Y%m%d_%H%M%S')}.{rec.format}"
                    with open(os.path.join(recordings_dir, filename), 'wb') as f:
                        f.write(rec.content)
            
            logger.info(f"Exported {len(recordings)} recordings to directory {export_path}")
            return export_path
        
        else:
            logger.error(f"Unsupported export format: {format}")
            return None
            
    except Exception as e:
        logger.error(f"Failed to export recordings: {e}")
        return None
    finally:
        if session:
            session.close()


def clean_old_recordings(retention_days, max_space_gb):
    """Clean old recordings based on retention policy
    
    Args:
        retention_days: Days to keep recordings
        max_space_gb: Maximum space to use for recordings in GB
        
    Returns:
        Number of recordings deleted
    """
    try:
        session = get_session()
        cutoff_date = datetime.datetime.now() - datetime.timedelta(days=retention_days)
        
        # Delete recordings older than retention period
        old_recordings = session.query(Recording).filter(Recording.timestamp < cutoff_date).all()
        deleted_count = len(old_recordings)
        
        for rec in old_recordings:
            # Delete file if exists
            if rec.has_file and rec.path and os.path.exists(rec.path):
                try:
                    os.remove(rec.path)
                except Exception as e:
                    logger.error(f"Failed to delete recording file: {e}")
            
            # Delete from database
            session.delete(rec)
        
        # Enforce storage limit
        total_size = session.query(func.sum(Recording.size_bytes)).scalar() or 0
        total_size_gb = total_size / (1024**3)
        
        if total_size_gb > max_space_gb:
            # Get recordings sorted by date (oldest first)
            space_recordings = session.query(Recording).order_by(Recording.timestamp.asc()).all()
            
            for rec in space_recordings:
                # Delete file if exists
                if rec.has_file and rec.path and os.path.exists(rec.path):
                    try:
                        os.remove(rec.path)
                    except Exception as e:
                        logger.error(f"Failed to delete recording file: {e}")
                
                # Reduce the total size and delete from database
                total_size -= rec.size_bytes
                total_size_gb = total_size / (1024**3)
                session.delete(rec)
                deleted_count += 1
                
                if total_size_gb <= max_space_gb * 0.9:  # 90% of limit
                    break
        
        session.commit()
        return deleted_count
        
    except Exception as e:
        logger.error(f"Failed to clean old recordings: {e}")
        if session:
            session.rollback()
        return 0
    finally:
        if session:
            session.close()