# 🧪 Clipo AI Video Processing Backend

A FastAPI-based backend service for video upload, processing, and metadata extraction using Celery background tasks.

## 🔧 Tech Stack

- **Python 3.11+**
- **FastAPI** - Async web framework
- **MongoDB** - Database using pymongo
- **Celery + Redis** - Background task processing
- **FFmpeg** - Video metadata extraction & thumbnail generation
- **Docker** - Containerization

## ✨ Features

- **Async video upload** with file validation
- **Background processing** using Celery workers
- **Video duration extraction** using FFmpeg
- **Thumbnail generation** at 10% of video duration
- **Real-time status tracking** (pending → processing → done)
- **RESTful API** with comprehensive error handling
- **Docker support** for easy deployment
- **Static file serving** for thumbnails

## 🚀 Quick Start

### Option 1: Using Docker (Recommended)

1. **Clone and navigate to the project:**
```bash
git clone <repository-url>
cd clipo-ai-backend
```

2. **Start all services:**
```bash
docker-compose up -d
```

3. **Check if services are running:**
```bash
docker-compose ps
```

4. **Access the API:**
- API: http://localhost:8000
- API Documentation: http://localhost:8000/docs
- Celery Flower (monitoring): http://localhost:5555

### Option 2: Local Development

1. **Install dependencies:**
```bash
pip install -r requirements.txt
```

2. **Install FFmpeg:**
```bash
# Ubuntu/Debian
sudo apt-get update && sudo apt-get install ffmpeg

# macOS
brew install ffmpeg

# Windows
# Download from https://ffmpeg.org/download.html
```

3. **Start MongoDB and Redis:**
```bash
# Using Docker
docker run -d --name mongodb -p 27017:27017 mongo:7.0
docker run -d --name redis -p 6379:6379 redis:7.2-alpine
```

4. **Start the services:**
```bash
# Terminal 1: FastAPI server
uvicorn main:app --reload

# Terminal 2: Celery worker
celery -A tasks worker --loglevel=info

# Terminal 3: Celery monitoring (optional)
celery -A tasks flower
```

## 📚 API Endpoints

### 1. Upload Video
```bash
POST /upload-video/
```

**Example:**
```bash
curl -X POST "http://localhost:8000/upload-video/" \
  -H "accept: application/json" \
  -H "Content-Type: multipart/form-data" \
  -F "file=@sample_video.mp4"
```

**Response:**
```json
{
  "id": "6475a1b2c3d4e5f6g7h8i9j0",
  "filename": "sample_video.mp4",
  "message": "Video uploaded successfully. Processing started."
}
```

### 2. Check Video Status
```bash
GET /video-status/{id}
```

**Example:**
```bash
curl -X GET "http://localhost:8000/video-status/6475a1b2c3d4e5f6g7h8i9j0"
```

**Response:**
```json
{
  "id": "6475a1b2c3d4e5f6g7h8i9j0",
  "status": "processing"
}
```

### 3. Get Video Metadata
```bash
GET /video-metadata/{id}
```

**Example:**
```bash
curl -X GET "http://localhost:8000/video-metadata/6475a1b2c3d4e5f6g7h8i9j0"
```

**Response:**
```json
{
  "id": "6475a1b2c3d4e5f6g7h8i9j0",
  "filename": "sample_video.mp4",
  "upload_time": "2025-06-16T10:00:00",
  "status": "done",
  "duration": "00:02:45",
  "thumbnail_url": "/thumbnails/thumb_uuid.jpg"
}
```

### 4. List All Videos (Bonus)
```bash
GET /videos/
```

**Example:**
```bash
curl -X GET "http://localhost:8000/videos/"
```

## 🛠 FFmpeg Commands Used

### Duration Extraction:
```bash
ffprobe -v quiet -print_format json -show_format video.mp4
```

### Thumbnail Generation:
```bash
ffmpeg -i video.mp4 -ss {10%_time} -vframes 1 -vf scale=320:240 -q:v 2 -y thumbnail.jpg
```

## 🏗 Project Structure

```
clipo-ai-backend/
├── main.py              # FastAPI application
├── tasks.py             # Celery background tasks
├── requirements.txt     # Python dependencies
├── Dockerfile          # Docker configuration
├── docker-compose.yml  # Multi-container setup
├── .env                # Environment variables
├── README.md           # This file
├── uploads/            # Video files directory
└── thumbnails/         # Generated thumbnails
```

## 🔧 Configuration

Environment variables (`.env` file):

```env
MONGODB_URL=mongodb://localhost:27017
REDIS_URL=redis://localhost:6379
UPLOAD_DIR=./uploads
THUMBNAIL_DIR=./thumbnails
DATABASE_NAME=clipo_ai
COLLECTION_NAME=videos
```

## 🧪 Testing

### Using Postman:
1. Import the following collection:
   - POST `http://localhost:8000/upload-video/` with form-data file
   - GET `http://localhost:8000/video-status/{id}`
   - GET `http://localhost:8000/video-metadata/{id}`

### Using curl:
```bash
# Upload a video
curl -X POST "http://localhost:8000/upload-video/" \
  -H "Content-Type: multipart/form-data" \
  -F "file=@test_video.mp4"

# Check status (replace with actual ID)
curl "http://localhost:8000/video-status/YOUR_VIDEO_ID"

# Get metadata
curl "http://localhost:8000/video-metadata/YOUR_VIDEO_ID"
```

## 📊 Monitoring

- **API Documentation**: http://localhost:8000/docs
- **Celery Flower**: http://localhost:5555 (task monitoring)
- **Logs**: `docker-compose logs -f [service_name]`

## 🔍 Troubleshooting

### Common Issues:

1. **FFmpeg not found:**
   - Ensure FFmpeg is installed and accessible in PATH
   - For Docker: It's included in the Dockerfile

2. **MongoDB connection error:**
   - Check if MongoDB is running: `docker-compose ps`
   - Verify connection string in `.env`

3. **Redis connection error:**
   - Ensure Redis is running: `docker-compose ps`
   - Check Redis URL in environment variables

4. **Celery worker not processing:**
   - Check worker logs: `docker-compose logs celery-worker`
   - Restart worker: `docker-compose restart celery-worker`

## 🎯 Status Flow

```
Upload → pending → processing → done
                      ↓
                   (failed)
```

## 🏆 Bonus Features Implemented

- ✅ **Docker Compose** for easy setup
- ✅ **Environment variable** support
- ✅ **Clean architecture** with proper error handling
- ✅ **Additional endpoints** for better usability
- ✅ **Celery Flower** for task monitoring
- ✅ **Comprehensive logging**
- ✅ **CORS support** for frontend integration

## 📝 API Documentation

Visit `http://localhost:8000/docs` for interactive API documentation powered by Swagger UI.

## 🚀 Deployment

The application is containerized and ready for deployment on any Docker-compatible platform (AWS ECS, Google Cloud Run, Azure Container Instances, etc.).

---

**Developed for Clipo AI Backend Assignment** 🎬
