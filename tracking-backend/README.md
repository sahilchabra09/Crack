# MediaPipe Processing Backend

FastAPI backend for real-time video processing.

## Python Version Notice

**For Full MediaPipe Support (Recommended):**
- Use Python 3.11 or 3.12
- MediaPipe doesn't have wheels for Python 3.13 on Windows yet

**For Python 3.13:**
- Use `main_opencv.py` (lightweight version with OpenCV only)
- Face detection works, hand/pose detection are placeholders

## Setup

1. Create a virtual environment:
```bash
python -m venv venv
```

2. Activate the virtual environment:
```bash
# Windows
.\venv\Scripts\activate

# Linux/Mac
source venv/bin/activate
```

3. Install dependencies:
```bash
pip install -r requirements.txt
```

### If using Python 3.11/3.12 (Full MediaPipe):

4. Download MediaPipe models:
```bash
python download_models.py
```

5. Run the server:
```bash
python main.py
```

### If using Python 3.13 (OpenCV only):

4. Run the lightweight server:
```bash
python main_opencv.py
```

The server will start on `http://localhost:8000`

## Endpoints

- `GET /` - Health check
- `GET /health` - Health status
- `WebSocket /ws/face` - Face detection WebSocket
- `WebSocket /ws/hand` - Hand detection WebSocket
- `WebSocket /ws/pose` - Pose detection WebSocket

## WebSocket Protocol

Send frames to the WebSocket as JSON:
```json
{
  "type": "frame",
  "data": "data:image/jpeg;base64,..."
}
```

Receive detection results as JSON:
```json
{
  "faces": [...],  // or "hands" or "poses"
  "count": 1
}
```

## Features

### Full Version (Python 3.11/3.12 with MediaPipe):
- Real-time face detection with 468 landmarks and blendshapes
- Hand detection with 21 landmarks and handedness classification
- Pose detection with 33 body landmarks
- High accuracy and performance

### Lightweight Version (Python 3.13 with OpenCV):
- Face detection with bounding boxes
- Eye detection within faces
- Works with Python 3.13
- Lower accuracy but functional

## Recommendations

For the best experience, consider using Python 3.12 with full MediaPipe support.
