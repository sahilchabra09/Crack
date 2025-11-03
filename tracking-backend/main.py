from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
import base64
import cv2
import numpy as np
import mediapipe as mp
from mediapipe.tasks import python
from mediapipe.tasks.python import vision
import json
from typing import Optional
import logging
import os
import asyncio
from concurrent.futures import ThreadPoolExecutor
import threading

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(title="MediaPipe Processing Server")

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://localhost:3001"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# MediaPipe configurations
class MediaPipeProcessor:
    def __init__(self):
        self.face_detector = None
        self.hand_detector = None
        self.pose_detector = None
        
    def initialize_face_detector(self):
        """Initialize MediaPipe Face Landmarker for better side profile detection"""
        try:
            base_options = python.BaseOptions(model_asset_path='models/face_landmarker.task')
            options = vision.FaceLandmarkerOptions(
                base_options=base_options,
                output_face_blendshapes=False,
                output_facial_transformation_matrixes=False,
                num_faces=2,  # Support multiple faces
                min_face_detection_confidence=0.3,  # Lower threshold for side profiles
                min_face_presence_confidence=0.3,
                min_tracking_confidence=0.3,
                running_mode=vision.RunningMode.IMAGE
            )
            self.face_detector = vision.FaceLandmarker.create_from_options(options)
            logger.info("Face landmarker initialized for side profile tracking")
        except Exception as e:
            logger.error(f"Error initializing face detector: {e}")
    
    def initialize_hand_detector(self):
        """Initialize MediaPipe Hand Landmarker"""
        try:
            base_options = python.BaseOptions(model_asset_path='models/hand_landmarker.task')
            options = vision.HandLandmarkerOptions(
                base_options=base_options,
                num_hands=2,
                min_hand_detection_confidence=0.5,  # Higher threshold for faster processing
                min_hand_presence_confidence=0.5,
                min_tracking_confidence=0.5,
                running_mode=vision.RunningMode.IMAGE
            )
            self.hand_detector = vision.HandLandmarker.create_from_options(options)
            logger.info("Hand landmarker initialized")
        except Exception as e:
            logger.error(f"Error initializing hand detector: {e}")
    
    def initialize_pose_detector(self):
        """Initialize MediaPipe Pose Landmarker"""
        try:
            # Use lite model for better performance
            base_options = python.BaseOptions(
                model_asset_path='models/pose_landmarker_lite.task'
            )
            options = vision.PoseLandmarkerOptions(
                base_options=base_options,
                min_pose_detection_confidence=0.5,  # Higher threshold for faster processing
                min_pose_presence_confidence=0.5,
                min_tracking_confidence=0.5,
                running_mode=vision.RunningMode.IMAGE
            )
            self.pose_detector = vision.PoseLandmarker.create_from_options(options)
            logger.info("Pose landmarker initialized")
        except Exception as e:
            logger.error(f"Error initializing pose detector: {e}")
            logger.info("Continuing without pose detection")
    
    def process_face(self, image: np.ndarray):
        """Process image for face detection - return bounding boxes from landmarks"""
        if self.face_detector is None:
            return {"error": "Face detector not initialized"}
        
        try:
            mp_image = mp.Image(image_format=mp.ImageFormat.SRGB, data=image)
            detection_result = self.face_detector.detect(mp_image)
            
            faces = []
            # Using FaceLandmarker - calculate bbox from landmarks for better side profile tracking
            if detection_result.face_landmarks:
                for face_landmarks in detection_result.face_landmarks:
                    # Get all landmark positions
                    xs = [lm.x for lm in face_landmarks]
                    ys = [lm.y for lm in face_landmarks]
                    
                    # Calculate bounding box with padding
                    x_min, x_max = min(xs), max(xs)
                    y_min, y_max = min(ys), max(ys)
                    
                    # Add padding to make the box more visible
                    width = x_max - x_min
                    height = y_max - y_min
                    padding = 0.1  # 10% padding
                    
                    x_min = max(0, x_min - width * padding)
                    y_min = max(0, y_min - height * padding)
                    x_max = min(1, x_max + width * padding)
                    y_max = min(1, y_max + height * padding)
                    
                    faces.append({
                        "x": x_min,
                        "y": y_min,
                        "width": x_max - x_min,
                        "height": y_max - y_min,
                        "score": 1.0
                    })
            
            return {"faces": faces, "count": len(faces)}
            
        except Exception as e:
            logger.error(f"Error processing face: {e}")
            return {"error": str(e)}
    
    def process_hands(self, image: np.ndarray):
        """Process image for hand detection - return key landmarks only for performance"""
        if self.hand_detector is None:
            return {"error": "Hand detector not initialized"}
        
        try:
            mp_image = mp.Image(image_format=mp.ImageFormat.SRGB, data=image)
            detection_result = self.hand_detector.detect(mp_image)
            
            hands = []
            if detection_result.hand_landmarks:
                for idx, hand_landmarks in enumerate(detection_result.hand_landmarks):
                    # Get handedness (left or right)
                    handedness = "Right" if idx < len(detection_result.handedness) else "Unknown"
                    if idx < len(detection_result.handedness):
                        handedness = detection_result.handedness[idx][0].category_name
                    
                    # Send all landmarks but optimize data structure
                    landmarks = [{"x": lm.x, "y": lm.y} for lm in hand_landmarks]  # Remove z for speed
                    
                    hands.append({
                        "landmarks": landmarks,
                        "handedness": handedness
                    })
            
            return {"hands": hands, "count": len(hands)}
            
        except Exception as e:
            logger.error(f"Error processing hands: {e}")
            return {"error": str(e)}
    
    def process_pose(self, image: np.ndarray):
        """Process image for pose detection - return upper body landmarks only"""
        if self.pose_detector is None:
            return {"error": "Pose detector not initialized"}
        
        try:
            mp_image = mp.Image(image_format=mp.ImageFormat.SRGB, data=image)
            detection_result = self.pose_detector.detect(mp_image)
            
            poses = []
            if detection_result.pose_landmarks:
                for pose_landmarks in detection_result.pose_landmarks:
                    # Only send upper body landmarks (0-24) without z-depth for performance
                    landmarks = [{"x": lm.x, "y": lm.y, "visibility": lm.visibility} 
                                for lm in pose_landmarks[:25]]  # First 25 landmarks = upper body
                    
                    poses.append({
                        "landmarks": landmarks
                    })
            
            return {"poses": poses, "count": len(poses)}
            
        except Exception as e:
            logger.error(f"Error processing pose: {e}")
            return {"error": str(e)}
    
    def process_all(self, image: np.ndarray):
        """Process image for face, hands, and pose detection simultaneously"""
        results = {}
        
        # Process face
        if self.face_detector:
            face_result = self.process_face(image)
            results.update(face_result)
        else:
            results["faces"] = []
            results["count"] = 0
        
        # Process hands
        if self.hand_detector:
            hand_result = self.process_hands(image)
            results["hands"] = hand_result.get("hands", [])
            results["hands_count"] = hand_result.get("count", 0)
        else:
            results["hands"] = []
            results["hands_count"] = 0
        
        # Process pose
        if self.pose_detector:
            pose_result = self.process_pose(image)
            results["poses"] = pose_result.get("poses", [])
            results["poses_count"] = pose_result.get("count", 0)
        else:
            results["poses"] = []
            results["poses_count"] = 0
        
        return results

# Global processor instance
processor = MediaPipeProcessor()

# Thread pool for parallel processing
executor = ThreadPoolExecutor(max_workers=2)  # One for face, one for pose

def process_face_thread(image: np.ndarray):
    """Thread-safe face processing"""
    try:
        return processor.process_face(image)
    except Exception as e:
        logger.error(f"Error in face thread: {e}")
        return {"faces": [], "count": 0}

def process_pose_thread(image: np.ndarray):
    """Thread-safe pose processing"""
    try:
        return processor.process_pose(image)
    except Exception as e:
        logger.error(f"Error in pose thread: {e}")
        return {"poses": [], "count": 0}

@app.on_event("startup")
async def startup_event():
    """Initialize MediaPipe models on startup"""
    logger.info("Starting up server with multithreading support...")
    logger.info("Thread pool initialized with 2 workers (face + pose)")
    # Models will be initialized on demand when WebSocket connects

@app.on_event("shutdown")
async def shutdown_event():
    """Cleanup on shutdown"""
    logger.info("Shutting down server...")
    executor.shutdown(wait=True)
    logger.info("Thread pool shutdown complete")

@app.get("/")
async def root():
    return {"message": "MediaPipe Processing Server is running"}

@app.get("/health")
async def health():
    return {"status": "healthy"}

@app.websocket("/ws/face")
async def websocket_face(websocket: WebSocket):
    """WebSocket endpoint for face and pose detection with multithreading"""
    await websocket.accept()
    logger.info("Face + Pose detection WebSocket connected (Multithreaded)")
    
    # Initialize face and pose detectors only
    if processor.face_detector is None:
        processor.initialize_face_detector()
    if processor.pose_detector is None:
        processor.initialize_pose_detector()
    
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
                
                # Process face and pose in parallel threads
                loop = asyncio.get_event_loop()
                
                # Submit both tasks to thread pool simultaneously
                face_future = loop.run_in_executor(executor, process_face_thread, image_rgb.copy())
                pose_future = loop.run_in_executor(executor, process_pose_thread, image_rgb.copy())
                
                # Wait for both to complete in parallel
                face_result, pose_result = await asyncio.gather(face_future, pose_future)
                
                # Combine results
                result = {}
                result.update(face_result)
                result["poses"] = pose_result.get("poses", [])
                result["poses_count"] = pose_result.get("count", 0)
                
                # No hands in this mode
                result["hands"] = []
                result["hands_count"] = 0
                
                # Send result back
                await websocket.send_json(result)
            
    except WebSocketDisconnect:
        logger.info("Face + Pose detection WebSocket disconnected")
    except Exception as e:
        logger.error(f"Error in WebSocket: {e}")
        await websocket.close()

@app.websocket("/ws/hand")
async def websocket_hand(websocket: WebSocket):
    """WebSocket endpoint for hand tracking only (optimized)"""
    await websocket.accept()
    logger.info("Hand tracking WebSocket connected")
    
    # Initialize hand detector only
    if processor.hand_detector is None:
        processor.initialize_hand_detector()
    
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
                
                # Process only hands
                result = {}
                
                if processor.hand_detector:
                    hand_result = processor.process_hands(image_rgb)
                    result["hands"] = hand_result.get("hands", [])
                    result["hands_count"] = hand_result.get("count", 0)
                else:
                    result["hands"] = []
                    result["hands_count"] = 0
                
                # No face or pose
                result["faces"] = []
                result["count"] = 0
                result["poses"] = []
                result["poses_count"] = 0
                
                # Send result back
                await websocket.send_json(result)
            
    except WebSocketDisconnect:
        logger.info("Hand tracking WebSocket disconnected")
    except Exception as e:
        logger.error(f"Error in hand WebSocket: {e}")
        await websocket.close()

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
