from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
import base64
import cv2
import numpy as np
import json
import logging

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(title="OpenCV Processing Server")

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://localhost:3001"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# OpenCV Face Detection
class OpenCVProcessor:
    def __init__(self):
        self.face_cascade = None
        self.eye_cascade = None
        
    def initialize_face_detector(self):
        """Initialize OpenCV Face Detection"""
        try:
            # Using Haar Cascade for face detection
            self.face_cascade = cv2.CascadeClassifier(cv2.data.haarcascades + 'haarcascade_frontalface_default.xml')
            self.eye_cascade = cv2.CascadeClassifier(cv2.data.haarcascades + 'haarcascade_eye.xml')
            logger.info("Face detector initialized")
        except Exception as e:
            logger.error(f"Error initializing face detector: {e}")
    
    def process_face(self, image: np.ndarray):
        """Process image for face detection"""
        if self.face_cascade is None:
            return {"error": "Face detector not initialized"}
        
        try:
            gray = cv2.cvtColor(image, cv2.COLOR_RGB2GRAY)
            faces = self.face_cascade.detectMultiScale(gray, 1.3, 5)
            
            face_data = []
            for (x, y, w, h) in faces:
                # Normalize coordinates
                face_dict = {
                    "x": float(x / image.shape[1]),
                    "y": float(y / image.shape[0]),
                    "width": float(w / image.shape[1]),
                    "height": float(h / image.shape[0])
                }
                
                # Detect eyes within the face region
                roi_gray = gray[y:y+h, x:x+w]
                eyes = self.eye_cascade.detectMultiScale(roi_gray)
                
                eye_data = []
                for (ex, ey, ew, eh) in eyes:
                    eye_data.append({
                        "x": float((x + ex) / image.shape[1]),
                        "y": float((y + ey) / image.shape[0]),
                        "width": float(ew / image.shape[1]),
                        "height": float(eh / image.shape[0])
                    })
                
                face_dict["eyes"] = eye_data
                face_data.append(face_dict)
            
            return {"faces": face_data, "count": len(face_data)}
        except Exception as e:
            logger.error(f"Error processing face: {e}")
            return {"error": str(e)}

# Global processor instance
processor = OpenCVProcessor()

@app.on_event("startup")
async def startup_event():
    """Initialize models on startup"""
    logger.info("Starting up server...")
    processor.initialize_face_detector()

@app.get("/")
async def root():
    return {
        "message": "OpenCV Processing Server is running",
        "note": "This is a lightweight version using OpenCV. For full MediaPipe support, use Python 3.11 or 3.12"
    }

@app.get("/health")
async def health():
    return {"status": "healthy"}

@app.websocket("/ws/face")
async def websocket_face(websocket: WebSocket):
    """WebSocket endpoint for face detection"""
    await websocket.accept()
    logger.info("Face detection WebSocket connected")
    
    try:
        while True:
            # Receive base64 encoded image
            data = await websocket.receive_text()
            message = json.loads(data)
            
            if message.get("type") == "frame":
                # Decode base64 image
                image_data = base64.b64decode(message["data"].split(",")[1])
                nparr = np.frombuffer(image_data, np.uint8)
                image = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
                image_rgb = cv2.cvtColor(image, cv2.COLOR_BGR2RGB)
                
                # Process image
                result = processor.process_face(image_rgb)
                
                # Send result back
                await websocket.send_json(result)
            
    except WebSocketDisconnect:
        logger.info("Face detection WebSocket disconnected")
    except Exception as e:
        logger.error(f"Error in face WebSocket: {e}")
        await websocket.close()

@app.websocket("/ws/hand")
async def websocket_hand(websocket: WebSocket):
    """WebSocket endpoint for hand detection (placeholder)"""
    await websocket.accept()
    logger.info("Hand detection WebSocket connected (basic mode)")
    
    try:
        while True:
            data = await websocket.receive_text()
            message = json.loads(data)
            
            if message.get("type") == "frame":
                # For now, return empty result
                # You can add hand detection using skin color detection or other methods
                await websocket.send_json({
                    "hands": [],
                    "count": 0,
                    "note": "Full hand detection requires MediaPipe (Python 3.11/3.12)"
                })
            
    except WebSocketDisconnect:
        logger.info("Hand detection WebSocket disconnected")
    except Exception as e:
        logger.error(f"Error in hand WebSocket: {e}")
        await websocket.close()

@app.websocket("/ws/pose")
async def websocket_pose(websocket: WebSocket):
    """WebSocket endpoint for pose detection (placeholder)"""
    await websocket.accept()
    logger.info("Pose detection WebSocket connected (basic mode)")
    
    try:
        while True:
            data = await websocket.receive_text()
            message = json.loads(data)
            
            if message.get("type") == "frame":
                # For now, return empty result
                await websocket.send_json({
                    "poses": [],
                    "count": 0,
                    "note": "Full pose detection requires MediaPipe (Python 3.11/3.12)"
                })
            
    except WebSocketDisconnect:
        logger.info("Pose detection WebSocket disconnected")
    except Exception as e:
        logger.error(f"Error in pose WebSocket: {e}")
        await websocket.close()

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
