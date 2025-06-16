import os
import subprocess
import logging
from datetime import datetime
from celery import Celery
from pymongo import MongoClient
from bson import ObjectId

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Environment variables
MONGODB_URL = os.getenv("MONGODB_URL", "mongodb://localhost:27017")
REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379")
THUMBNAIL_DIR = os.getenv("THUMBNAIL_DIR", "./thumbnails")
DATABASE_NAME = os.getenv("DATABASE_NAME", "clipo_ai")
COLLECTION_NAME = os.getenv("COLLECTION_NAME", "videos")

# Create directories
os.makedirs(THUMBNAIL_DIR, exist_ok=True)

# Celery app
celery_app = Celery(
    "video_processor",
    broker=REDIS_URL,
    backend=REDIS_URL
)

celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="UTC",
    enable_utc=True,
)

# MongoDB connection
mongo_client = MongoClient(MONGODB_URL)
db = mongo_client[DATABASE_NAME]
videos_collection = db[COLLECTION_NAME]

def get_video_duration(video_path):
    """
    Extract video duration using FFmpeg
    """
    try:
        cmd = [
            'ffprobe',
            '-v', 'quiet',
            '-print_format', 'json',
            '-show_format',
            video_path
        ]
        
        result = subprocess.run(cmd, capture_output=True, text=True, check=True)
        
        if result.returncode != 0:
            raise Exception(f"FFprobe failed: {result.stderr}")
        
        import json
        metadata = json.loads(result.stdout)
        
        duration_seconds = float(metadata['format']['duration'])
        
        # Convert to HH:MM:SS format
        hours = int(duration_seconds // 3600)
        minutes = int((duration_seconds % 3600) // 60)
        seconds = int(duration_seconds % 60)
        
        duration_str = f"{hours:02d}:{minutes:02d}:{seconds:02d}"
        
        return duration_str, duration_seconds
        
    except subprocess.CalledProcessError as e:
        logger.error(f"FFprobe command failed: {e}")
        raise Exception(f"Failed to extract duration: {e}")
    except Exception as e:
        logger.error(f"Error extracting duration: {e}")
        raise

def generate_thumbnail(video_path, output_path, duration_seconds):
    """
    Generate thumbnail at 10% of video duration using FFmpeg
    """
    try:
        # Calculate 10% of duration
        thumbnail_time = duration_seconds * 0.1
        
        cmd = [
            'ffmpeg',
            '-i', video_path,
            '-ss', str(thumbnail_time),
            '-vframes', '1',
            '-vf', 'scale=320:240',  # Resize to reasonable thumbnail size
            '-q:v', '2',  # High quality
            '-y',  # Overwrite output file
            output_path
        ]
        
        result = subprocess.run(cmd, capture_output=True, text=True, check=True)
        
        if result.returncode != 0:
            raise Exception(f"FFmpeg failed: {result.stderr}")
        
        logger.info(f"Thumbnail generated successfully: {output_path}")
        return True
        
    except subprocess.CalledProcessError as e:
        logger.error(f"FFmpeg command failed: {e}")
        raise Exception(f"Failed to generate thumbnail: {e}")
    except Exception as e:
        logger.error(f"Error generating thumbnail: {e}")
        raise

@celery_app.task(bind=True)
def process_video(self, video_id, video_path, stored_filename):
    """
    Background task to process video: extract duration and generate thumbnail
    """
    try:
        logger.info(f"Starting video processing for ID: {video_id}")
        
        # Update status to processing
        videos_collection.update_one(
            {"_id": ObjectId(video_id)},
            {"$set": {"status": "processing"}}
        )
        
        # Extract video duration
        logger.info(f"Extracting duration for: {video_path}")
        duration_str, duration_seconds = get_video_duration(video_path)
        logger.info(f"Duration extracted: {duration_str}")
        
        # Generate thumbnail
        thumbnail_filename = f"thumb_{os.path.splitext(stored_filename)[0]}.jpg"
        thumbnail_path = os.path.join(THUMBNAIL_DIR, thumbnail_filename)
        
        logger.info(f"Generating thumbnail: {thumbnail_path}")
        generate_thumbnail(video_path, thumbnail_path, duration_seconds)
        
        # Update MongoDB with results
        update_data = {
            "status": "done",
            "duration": duration_str,
            "thumbnail_filename": thumbnail_filename,
            "processed_time": datetime.utcnow().isoformat()
        }
        
        videos_collection.update_one(
            {"_id": ObjectId(video_id)},
            {"$set": update_data}
        )
        
        logger.info(f"Video processing completed for ID: {video_id}")
        
        return {
            "video_id": video_id,
            "status": "done",
            "duration": duration_str,
            "thumbnail_filename": thumbnail_filename
        }
        
    except Exception as e:
        logger.error(f"Error processing video {video_id}: {e}")
        
        # Update status to failed
        videos_collection.update_one(
            {"_id": ObjectId(video_id)},
            {"$set": {
                "status": "failed",
                "error_message": str(e),
                "processed_time": datetime.utcnow().isoformat()
            }}
        )
        
        # Re-raise exception to mark task as failed
        raise self.retry(exc=e, countdown=60, max_retries=3)
