import logging
from sqlalchemy.exc import SQLAlchemyError
from database import engine, Base, SessionLocal
from models import User, Camera, Recording, SystemSettings, CameraEvent

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def init_db():
    try:
        # Create all tables
        Base.metadata.create_all(bind=engine)
        logger.info("Database tables created successfully")

        # Initialize system settings
        db = SessionLocal()
        try:
            # Check if settings already exist
            settings = db.query(SystemSettings).all()
            if not settings:
                default_settings = [
                    SystemSettings(key="storage_path", value="recordings"),
                    SystemSettings(key="max_storage_gb", value="500"),
                    SystemSettings(key="retention_days", value="30"),
                    SystemSettings(key="motion_sensitivity", value="0.3"),
                    SystemSettings(key="person_confidence", value="0.5"),
                    SystemSettings(key="recording_fps", value="15"),
                    SystemSettings(key="recording_resolution", value="1280x720"),
                    SystemSettings(key="rtsp_timeout", value="10"),
                    SystemSettings(key="reconnect_attempts", value="3"),
                    SystemSettings(key="max_cameras_per_user", value="10")
                ]
                db.bulk_save_objects(default_settings)
                db.commit()
                logger.info("Default system settings initialized")
        except SQLAlchemyError as e:
            db.rollback()
            logger.error(f"Error initializing system settings: {str(e)}")
        finally:
            db.close()

    except Exception as e:
        logger.error(f"Database initialization error: {str(e)}")
        raise

def reset_db():
    """Reset the database by dropping and recreating all tables."""
    try:
        Base.metadata.drop_all(bind=engine)
        logger.info("Database tables dropped successfully")
        init_db()
        logger.info("Database reset completed successfully")
    except Exception as e:
        logger.error(f"Database reset error: {str(e)}")
        raise

if __name__ == "__main__":
    logger.info("Initializing database...")
    init_db()
    logger.info("Database initialization completed")
