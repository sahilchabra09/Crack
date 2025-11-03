"""
Script to download MediaPipe models
Run this once before starting the server
"""

import urllib.request
import os

# Create models directory
os.makedirs('models', exist_ok=True)

models = {
    'face_landmarker.task': 'https://storage.googleapis.com/mediapipe-models/face_landmarker/face_landmarker/float16/1/face_landmarker.task',
    'hand_landmarker.task': 'https://storage.googleapis.com/mediapipe-models/hand_landmarker/hand_landmarker/float16/1/hand_landmarker.task',
    'pose_landmarker_lite.task': 'https://storage.googleapis.com/mediapipe-models/pose_landmarker/pose_landmarker_lite/float16/1/pose_landmarker_lite.task',
}

print("Downloading MediaPipe models...")
for filename, url in models.items():
    filepath = os.path.join('models', filename)
    if os.path.exists(filepath):
        print(f"✓ {filename} already exists")
    else:
        print(f"Downloading {filename}...")
        urllib.request.urlretrieve(url, filepath)
        print(f"✓ {filename} downloaded")

print("\nAll models downloaded successfully!")
print("You can now run: python main.py")
