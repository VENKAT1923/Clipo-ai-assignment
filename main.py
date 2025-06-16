import os
import uuid
from datetime import datetime
from typing import Optional
from fastapi import FastAPI, File, UploadFile, HTTPException, status
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from pymongo import MongoClient
from celery import Celery
import asyncio
import aiofiles
from bson import ObjectId
from pydantic import BaseModel
import logging

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Environment variables
MONGODB_URL = os.getenv("MONGODB_URL", "mongodb://localhost:27017")
REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379")
UPLOAD_DIR = os.getenv("UPLOAD_DIR", "./uploads")
THUMBNAIL_DIR = os.getenv("THUMBNAIL_DIR", "./thumbnails")
DATABASE_NAME = os.getenv("DATABASE_NAME", "clipo_ai")
COLLECTION_NAME = os.getenv("COLLECTION_NAME", "videos")

# Create directories
os.makedirs(UPLOAD_DIR, exist_ok=True)
os.makedirs(THUMBNAIL_DIR, exist_ok=True)

# FastAPI app
app = FastAPI(
    title="Clipo AI Video Processing API",
    description="Backend service for video upload and processing",
    version="1.0.0"
)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Serve static files
app.mount("/thumbnails", StaticFiles(directory=THUMBNAIL_DIR), name="thumbnails")

# MongoDB connection
try:
    mongo_client = MongoClient(MONGODB_URL)
    db = mongo_client[DATABASE_NAME]
    videos_collection = db[COLLECTION_NAME]
    logger.info("Connected to MongoDB successfully")
except Exception as e:
    logger.error(f"Failed to connect to MongoDB: {e}")
    raise

# Celery configuration
celery_app = Celery(
    "video_processor",
    broker=REDIS_URL,
    backend=REDIS_URL,
    include=["tasks"]
)

celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="UTC",
    enable_utc=True,
)

# Pydantic models
class VideoStatus(BaseModel):
    id: str
    status: str

class VideoMetadata(BaseModel):
    id: str
    filename: str
    upload_time: str
    status: str
    duration: Optional[str] = None
    thumbnail_url: Optional[str] = None

class UploadResponse(BaseModel):
    id: str
    filename: str
    message: str

# Helper functions
def serialize_video_doc(doc):
    """Convert MongoDB document to JSON serializable format"""
    if doc:
        doc["id"] = str(doc["_id"])
        del doc["_id"]
    return doc

async def save_upload_file(upload_file: UploadFile, destination: str):
    """Save uploaded file to destination"""
    async with aiofiles.open(destination, 'wb') as f:
        while chunk := await upload_file.read(1024):
            await f.write(chunk)

# API Endpoints
@app.get("/")
async def root():
    """Health check endpoint"""
    return {"message": "Clipo AI Video Processing API is running!"}

@app.post("/upload-video/", response_model=UploadResponse)
async def upload_video(file: UploadFile = File(...)):
    """
    Upload a video file and start background processing
    """
    try:
        # Validate file type
        if not file.content_type or not file.content_type.startswith('video/'):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Only video files are allowed"
            )
        
        # Generate unique filename
        file_extension = os.path.splitext(file.filename)[1]
        unique_filename = f"{uuid.uuid4()}{file_extension}"
        file_path = os.path.join(UPLOAD_DIR, unique_filename)
        
        # Save file
        await save_upload_file(file, file_path)
        
        # Insert initial record to MongoDB
        video_doc = {
            "filename": file.filename,
            "stored_filename": unique_filename,
            "file_path": file_path,
            "upload_time": datetime.utcnow().isoformat(),
            "status": "pending",
            "duration": None,
            "thumbnail_url": None
        }
        
        result = videos_collection.insert_one(video_doc)
        video_id = str(result.inserted_id)
        
        # Trigger Celery background task
        from tasks import process_video
        task = process_video.delay(video_id, file_path, unique_filename)
        
        # Update document with task ID
        videos_collection.update_one(
            {"_id": result.inserted_id},
            {"$set": {"task_id": task.id}}
        )
        
        logger.info(f"Video uploaded successfully: {unique_filename}, ID: {video_id}")
        
        return UploadResponse(
            id=video_id,
            filename=file.filename,
            message="Video uploaded successfully. Processing started."
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error uploading video: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to upload video: {str(e)}"
        )

@app.get("/video-status/{video_id}", response_model=VideoStatus)
async def get_video_status(video_id: str):
    """
    Get the current processing status of a video
    """
    try:
        # Validate ObjectId
        if not ObjectId.is_valid(video_id):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid video ID format"
            )
        
        # Find video in database
        video_doc = videos_collection.find_one({"_id": ObjectId(video_id)})
        
        if not video_doc:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Video not found"
            )
        
        return VideoStatus(
            id=video_id,
            status=video_doc["status"]
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting video status: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get video status: {str(e)}"
        )

@app.get("/video-metadata/{video_id}", response_model=VideoMetadata)
async def get_video_metadata(video_id: str):
    """
    Get complete metadata for a video
    """
    try:
        # Validate ObjectId
        if not ObjectId.is_valid(video_id):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid video ID format"
            )
        
        # Find video in database
        video_doc = videos_collection.find_one({"_id": ObjectId(video_id)})
        
        if not video_doc:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Video not found"
            )
        
        # Prepare thumbnail URL if available
        thumbnail_url = None
        if video_doc.get("thumbnail_filename"):
            thumbnail_url = f"/thumbnails/{video_doc['thumbnail_filename']}"
        
        return VideoMetadata(
            id=video_id,
            filename=video_doc["filename"],
            upload_time=video_doc["upload_time"],
            status=video_doc["status"],
            duration=video_doc.get("duration"),
            thumbnail_url=thumbnail_url
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting video metadata: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get video metadata: {str(e)}"
        )

@app.get("/videos/")
async def list_videos():
    """
    List all videos (bonus endpoint for easier testing)
    """
    try:
        videos = list(videos_collection.find().sort("upload_time", -1))
        serialized_videos = [serialize_video_doc(video) for video in videos]
        return {"videos": serialized_videos}
        
    except Exception as e:
        logger.error(f"Error listing videos: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to list videos: {str(e)}"
        )

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=8000,
        reload=True,
        log_level="info"
    )
