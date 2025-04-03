import os
import logging
import asyncio
from typing import Optional, List
from datetime import datetime
from fastapi import FastAPI, Depends, HTTPException, status, Request, Response, Form
from fastapi.security import OAuth2PasswordRequestForm
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session
from starlette.middleware.sessions import SessionMiddleware
from starlette.responses import RedirectResponse, StreamingResponse, FileResponse, JSONResponse
from pydantic import BaseModel

from database import get_db
from models import User, Camera, Recording, SystemSettings, CameraEvent
from security import (
    authenticate_user,
    get_current_user,
    create_user
)
from camera_stream import camera_manager
from camera_record import recording_manager
from system_monitor import system_monitor

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Initialize FastAPI app
app = FastAPI(title="Smart NVR")

# Add session middleware
app.add_middleware(
    SessionMiddleware,
    secret_key=os.getenv("SECRET_KEY", "your-secret-key-here"),
    max_age=3600  # 1 hour
)

# Get the current directory
current_dir = os.path.dirname(os.path.abspath(__file__))

# Mount static files
app.mount("/static", StaticFiles(directory=os.path.join(current_dir, "static")), name="static")

# Initialize templates
templates = Jinja2Templates(directory=os.path.join(current_dir, "templates"))

# Pydantic models for request/response
class CameraCreate(BaseModel):
    name: str
    url: str
    ai_enabled: bool = True

class CameraUpdate(BaseModel):
    name: Optional[str]
    url: Optional[str]
    ai_enabled: Optional[bool]

class CameraResponse(BaseModel):
    id: int
    name: str
    url: str
    ai_enabled: bool
    status: dict

class SystemStatus(BaseModel):
    cpu_percent: float
    memory_percent: float
    disk_percent: float

class StorageInfo(BaseModel):
    total_space_gb: float
    recording_count: int

@app.get("/")
async def root(request: Request, db: Session = Depends(get_db)):
    """Root endpoint - redirects to login/dashboard."""
    user_id = request.session.get("user_id")
    if not user_id:
        return RedirectResponse(url="/login", status_code=status.HTTP_302_FOUND)
    
    return RedirectResponse(url="/dashboard", status_code=status.HTTP_302_FOUND)

@app.get("/register")
async def register_page(request: Request):
    """Registration page."""
    return templates.TemplateResponse("register.html", {"request": request})

@app.post("/api/register")
async def register(
    request: Request,
    db: Session = Depends(get_db),
    email: str = Form(...),
    password: str = Form(...),
    username: Optional[str] = Form(None)
):
    """Register a new user."""
    try:
        user = await create_user(db, email, password, username)
        return RedirectResponse(url="/login", status_code=status.HTTP_302_FOUND)
    except HTTPException as e:
        raise e
    except Exception as e:
        logger.error(f"Registration error: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )

@app.get("/login")
async def login_page(request: Request):
    """Login page."""
    return templates.TemplateResponse("login.html", {"request": request})

@app.post("/api/login")
async def login(
    request: Request,
    response: Response,
    db: Session = Depends(get_db),
    email: str = Form(...),
    password: str = Form(...)
):
    """Login with email and password."""
    user = authenticate_user(db, email, password)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password"
        )
    
    request.session["user_id"] = user.id
    return RedirectResponse(url="/dashboard", status_code=status.HTTP_302_FOUND)

@app.get("/logout")
async def logout(request: Request):
    """Logout endpoint - clears session."""
    request.session.clear()
    return RedirectResponse(url="/login", status_code=status.HTTP_302_FOUND)

@app.get("/dashboard")
async def dashboard(
    request: Request,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Dashboard page with camera feeds and system status."""
    cameras = db.query(Camera).filter(Camera.owner_id == current_user.id).all()
    
    # Get stream status for each camera
    camera_data = []
    for camera in cameras:
        stream = camera_manager.get_stream(camera.id, camera.url, camera.ai_enabled)
        status = stream.get_stream_status()
        camera_data.append({
            "id": camera.id,
            "name": camera.name,
            "url": camera.url,
            "ai_enabled": camera.ai_enabled,
            "status": status
        })
    
    return templates.TemplateResponse(
        "dashboard.html",
        {
            "request": request,
            "user": current_user,
            "cameras": camera_data
        }
    )

@app.get("/api/cameras")
async def list_cameras(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
) -> List[CameraResponse]:
    """List all cameras for current user."""
    cameras = db.query(Camera).filter(Camera.owner_id == current_user.id).all()
    return [
        CameraResponse(
            id=camera.id,
            name=camera.name,
            url=camera.url,
            ai_enabled=camera.ai_enabled,
            status=camera_manager.get_stream(camera.id, camera.url).get_stream_status()
        )
        for camera in cameras
    ]

@app.post("/api/cameras")
async def add_camera(
    camera: CameraCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Add a new camera."""
    try:
        # Check if camera name already exists for this user
        existing_camera = db.query(Camera).filter(
            Camera.owner_id == current_user.id,
            Camera.name == camera.name
        ).first()
        
        if existing_camera:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Camera with this name already exists"
            )

        # Create camera record
        db_camera = Camera(
            name=camera.name,
            url=camera.url,
            owner_id=current_user.id,
            ai_enabled=camera.ai_enabled
        )
        db.add(db_camera)
        db.commit()
        db.refresh(db_camera)

        # Initialize camera stream
        stream = camera_manager.get_stream(db_camera.id, camera.url, camera.ai_enabled)
        stream.start()

        return {
            "message": "Camera added successfully",
            "camera": CameraResponse(
                id=db_camera.id,
                name=db_camera.name,
                url=db_camera.url,
                ai_enabled=db_camera.ai_enabled,
                status=stream.get_stream_status()
            )
        }
    except HTTPException as e:
        raise e
    except Exception as e:
        logger.error(f"Error adding camera: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )

@app.put("/api/cameras/{camera_id}")
async def update_camera(
    camera_id: int,
    camera_update: CameraUpdate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Update camera settings."""
    camera = db.query(Camera).filter(
        Camera.id == camera_id,
        Camera.owner_id == current_user.id
    ).first()
    
    if not camera:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Camera not found"
        )

    # If name is being updated, check it doesn't conflict
    if camera_update.name is not None and camera_update.name != camera.name:
        existing_camera = db.query(Camera).filter(
            Camera.owner_id == current_user.id,
            Camera.name == camera_update.name
        ).first()
        
        if existing_camera:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Camera with this name already exists"
            )
        camera.name = camera_update.name

    # Update other fields if provided
    if camera_update.url is not None:
        camera.url = camera_update.url
    if camera_update.ai_enabled is not None:
        camera.ai_enabled = camera_update.ai_enabled

    db.commit()

    # Update stream if URL or AI setting changed
    if camera_update.url is not None or camera_update.ai_enabled is not None:
        stream = camera_manager.get_stream(camera.id, camera.url, camera.ai_enabled)
        stream.stop()
        stream.start()

    return {
        "message": "Camera updated successfully",
        "camera": CameraResponse(
            id=camera.id,
            name=camera.name,
            url=camera.url,
            ai_enabled=camera.ai_enabled,
            status=camera_manager.get_stream(camera.id, camera.url).get_stream_status()
        )
    }

@app.get("/video_feed/{camera_id}")
async def video_feed(
    camera_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Stream video feed from a camera."""
    camera = db.query(Camera).filter(
        Camera.id == camera_id,
        Camera.owner_id == current_user.id
    ).first()
    
    if not camera:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Camera not found"
        )

    stream = camera_manager.get_stream(camera.id, camera.url, camera.ai_enabled)
    if not stream.is_running:
        stream.start()
    
    async def generate():
        while True:
            frame = stream.get_frame()
            if frame is None:
                await asyncio.sleep(0.1)  # Short sleep to prevent CPU overload
                continue
            yield (b'--frame\r\n'
                   b'Content-Type: image/jpeg\r\n\r\n' + frame + b'\r\n')

    return StreamingResponse(
        generate(),
        media_type='multipart/x-mixed-replace; boundary=frame'
    )

@app.post("/api/cameras/{camera_id}/ai_toggle")
async def toggle_ai(
    camera_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Toggle AI detection for a camera."""
    camera = db.query(Camera).filter(
        Camera.id == camera_id,
        Camera.owner_id == current_user.id
    ).first()
    
    if not camera:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Camera not found"
        )

    # Toggle AI state
    camera.ai_enabled = not camera.ai_enabled
    db.commit()

    # Update stream
    stream = camera_manager.get_stream(camera.id, camera.url)
    stream.ai_enabled = camera.ai_enabled

    return {
        "ai_enabled": camera.ai_enabled,
        "status": stream.get_stream_status()
    }

@app.get("/api/system/status")
async def get_system_status(current_user: User = Depends(get_current_user)):
    """Get system status metrics."""
    return SystemStatus(
        cpu_percent=system_monitor.get_cpu_percent(),
        memory_percent=system_monitor.get_memory_percent(),
        disk_percent=system_monitor.get_disk_percent()
    )

@app.get("/api/system/storage")
async def get_storage_info(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Get storage usage information."""
    recording_count = db.query(Recording).count()
    total_space = system_monitor.get_total_space_gb()
    
    return StorageInfo(
        total_space_gb=total_space,
        recording_count=recording_count
    )

@app.get("/api/cameras/{camera_id}/status")
async def get_camera_status(
    camera_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Get detailed status for a specific camera."""
    camera = db.query(Camera).filter(
        Camera.id == camera_id,
        Camera.owner_id == current_user.id
    ).first()
    
    if not camera:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Camera not found"
        )

    stream = camera_manager.get_stream(camera.id, camera.url)
    return {
        "camera": CameraResponse(
            id=camera.id,
            name=camera.name,
            url=camera.url,
            ai_enabled=camera.ai_enabled,
            status=stream.get_stream_status()
        )
    }

@app.post("/api/cameras/{camera_id}/events")
async def log_camera_event(
    camera_id: int,
    event_type: str,
    details: Optional[str] = None,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Log a camera event."""
    camera = db.query(Camera).filter(
        Camera.id == camera_id,
        Camera.owner_id == current_user.id
    ).first()
    
    if not camera:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Camera not found"
        )

    event = CameraEvent(
        camera_id=camera_id,
        event_type=event_type,
        details=details
    )
    db.add(event)
    db.commit()
    db.refresh(event)

    return {"message": "Event logged successfully", "event_id": event.id}
