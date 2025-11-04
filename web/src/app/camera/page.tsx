'use client';

import { useEffect, useRef, useState } from 'react';

export default function CameraPage() {
  const videoRef = useRef<HTMLVideoElement>(null);
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const wsRef = useRef<WebSocket | null>(null);
  const [isStreaming, setIsStreaming] = useState(false);
  const [trackingMode, setTrackingMode] = useState<'face-pose' | 'hand'>('face-pose');
  const [fps, setFps] = useState(0);
  const [detectionData, setDetectionData] = useState<any>(null);
  const animationFrameRef = useRef<number | undefined>(undefined);
  const lastFrameTimeRef = useRef<number>(0);
  const frameCountRef = useRef<number>(0);
  const renderLoopRef = useRef<number | undefined>(undefined);
  const lastSentFrameTimeRef = useRef<number>(0);
  const TARGET_FPS = trackingMode === 'hand' ? 20 : 20; // Increase face-pose to 20 FPS
  const FRAME_INTERVAL = 1000 / TARGET_FPS;

  // Bot control state
  const [botConnected, setBotConnected] = useState(false);
  const [botTracking, setBotTracking] = useState(false);
  const [botStatus, setBotStatus] = useState<string>('Not Connected');

  // Audio recording state
  const [isRecording, setIsRecording] = useState(false);
  const [audioStatus, setAudioStatus] = useState<string>('Ready to record');
  const [aiResponse, setAiResponse] = useState<string>('');
  const [transcription, setTranscription] = useState<string>('');
  const [isSpeaking, setIsSpeaking] = useState(false);
  const mediaRecorderRef = useRef<MediaRecorder | null>(null);
  const audioChunksRef = useRef<Blob[]>([]);

  // Get backend URLs from environment variables
  const BACKEND_URL = process.env.NEXT_PUBLIC_BACKEND_URL || 'http://localhost:8000';
  const WS_URL = process.env.NEXT_PUBLIC_WS_URL || 'ws://localhost:8000';

  useEffect(() => {
    startCamera();
    
    return () => {
      stopCamera();
      if (wsRef.current) {
        wsRef.current.close();
      }
      if (renderLoopRef.current) {
        cancelAnimationFrame(renderLoopRef.current);
      }
    };
  }, []);

  useEffect(() => {
    // Start drawing video to canvas immediately with detections overlaid
    const drawVideoToCanvas = () => {
      if (videoRef.current && canvasRef.current) {
        const video = videoRef.current;
        const canvas = canvasRef.current;
        const ctx = canvas.getContext('2d');
        
        if (video.videoWidth > 0 && ctx) {
          // Set canvas size if changed
          if (canvas.width !== video.videoWidth || canvas.height !== video.videoHeight) {
            canvas.width = video.videoWidth;
            canvas.height = video.videoHeight;
          }
          
          // Draw video frame
          ctx.drawImage(video, 0, 0);
          
          // Draw detection results on top if available
          if (detectionData) {
            drawDetectionOverlay(ctx, canvas.width, canvas.height);
          }
        }
      }
      renderLoopRef.current = requestAnimationFrame(drawVideoToCanvas);
    };
    drawVideoToCanvas();
    
    return () => {
      if (renderLoopRef.current) {
        cancelAnimationFrame(renderLoopRef.current);
      }
    };
  }, [detectionData, trackingMode]);

  const startCamera = async () => {
    try {
      console.log('📷 Requesting camera access...');
      const stream = await navigator.mediaDevices.getUserMedia({
        video: {
          width: { ideal: 1280 },
          height: { ideal: 720 },
          facingMode: 'user'
        }
      });

      if (videoRef.current) {
        videoRef.current.srcObject = stream;
        console.log('✅ Camera stream started');
        
        // Wait for video to be ready
        videoRef.current.onloadedmetadata = () => {
          console.log(`✅ Video loaded: ${videoRef.current?.videoWidth}x${videoRef.current?.videoHeight}`);
        };
      }
    } catch (error) {
      console.error('❌ Error accessing camera:', error);
      alert('Unable to access camera. Please ensure you have granted camera permissions.');
    }
  };

  const stopCamera = () => {
    if (videoRef.current?.srcObject) {
      const stream = videoRef.current.srcObject as MediaStream;
      stream.getTracks().forEach(track => track.stop());
    }
    if (animationFrameRef.current) {
      cancelAnimationFrame(animationFrameRef.current);
    }
  };

  const connectWebSocket = () => {
    const endpoint = trackingMode === 'hand' ? 'hand' : 'face';
    const wsUrl = `${WS_URL}/ws/${endpoint}`;
    const ws = new WebSocket(wsUrl);

    ws.onopen = () => {
      console.log(`✅ WebSocket connected to ${trackingMode} tracking`);
      setIsStreaming(true);
      startStreaming();
    };

    ws.onmessage = (event) => {
      try {
        const data = JSON.parse(event.data);
        console.log('📦 Received data:', data);
        setDetectionData(data);
        // No need to call drawResults here - the continuous loop will draw it
      } catch (error) {
        console.error('❌ Error parsing message:', error);
      }
    };

    ws.onerror = (error) => {
      console.error('❌ WebSocket error:', error);
      alert('Unable to connect to processing server. Make sure the Python backend is running on port 8000.');
    };

    ws.onclose = () => {
      console.log('🔌 WebSocket disconnected');
      setIsStreaming(false);
      if (animationFrameRef.current) {
        cancelAnimationFrame(animationFrameRef.current);
      }
    };

    wsRef.current = ws;
  };

  const startStreaming = () => {
    const sendFrame = () => {
      if (videoRef.current && canvasRef.current && wsRef.current?.readyState === WebSocket.OPEN) {
        const now = performance.now();
        
        // Throttle frame sending to TARGET_FPS
        if (now - lastSentFrameTimeRef.current < FRAME_INTERVAL) {
          animationFrameRef.current = requestAnimationFrame(sendFrame);
          return;
        }
        lastSentFrameTimeRef.current = now;
        
        const canvas = canvasRef.current;
        const video = videoRef.current;
        
        // Make sure video is playing and has dimensions
        if (video.videoWidth === 0 || video.videoHeight === 0) {
          console.log('⏳ Waiting for video to load...');
          animationFrameRef.current = requestAnimationFrame(sendFrame);
          return;
        }
        
        // Create a temporary smaller canvas for sending (optimized for face-pose)
        const tempCanvas = document.createElement('canvas');
        const scale = trackingMode === 'hand' ? 0.4 : 0.25; // Smaller for face-pose mode (25% = faster)
        tempCanvas.width = video.videoWidth * scale;
        tempCanvas.height = video.videoHeight * scale;
        const tempCtx = tempCanvas.getContext('2d');
        
        if (tempCtx) {
          // Draw scaled down video
          tempCtx.drawImage(video, 0, 0, tempCanvas.width, tempCanvas.height);
          
          // Convert to base64 with quality based on mode (lower = faster)
          const quality = trackingMode === 'hand' ? 0.5 : 0.25;
          const imageData = tempCanvas.toDataURL('image/jpeg', quality);
          
          try {
            // Send to WebSocket
            wsRef.current.send(JSON.stringify({
              type: 'frame',
              data: imageData
            }));
          } catch (error) {
            console.error('❌ Error sending frame:', error);
          }

          // Calculate FPS
          frameCountRef.current++;
          if (now - lastFrameTimeRef.current >= 1000) {
            setFps(frameCountRef.current);
            frameCountRef.current = 0;
            lastFrameTimeRef.current = now;
          }
        }
      }
      
      animationFrameRef.current = requestAnimationFrame(sendFrame);
    };

    sendFrame();
  };

  // Bot Control Functions
  const connectBot = async () => {
    try {
      setBotStatus('Connecting...');
      const response = await fetch(`${BACKEND_URL}/bot/connect`, {
        method: 'POST',
      });
      const data = await response.json();
      
      if (data.status === 'connected') {
        setBotConnected(true);
        setBotStatus('Connected');
        console.log('✅ Bot connected:', data);
      } else {
        setBotStatus('Connection failed');
        console.error('❌ Bot connection failed:', data);
      }
    } catch (error) {
      setBotStatus('Connection error');
      console.error('❌ Bot connection error:', error);
    }
  };

  const disconnectBot = async () => {
    try {
      await fetch(`${BACKEND_URL}/bot/disconnect`, {
        method: 'POST',
      });
      setBotConnected(false);
      setBotTracking(false);
      setBotStatus('Disconnected');
      console.log('🔌 Bot disconnected');
    } catch (error) {
      console.error('❌ Bot disconnect error:', error);
    }
  };

  // Text-to-Speech Functions
  const speakText = (text: string) => {
    // Cancel any ongoing speech
    window.speechSynthesis.cancel();
    
    if (!text) return;
    
    // Create speech utterance
    const utterance = new SpeechSynthesisUtterance(text);
    
    // Configure voice settings
    utterance.rate = 1.0;  // Speech rate (0.1 to 10)
    utterance.pitch = 1.0; // Pitch (0 to 2)
    utterance.volume = 1.0; // Volume (0 to 1)
    
    // Try to select a good quality voice (prefer female voices for AI assistant)
    const voices = window.speechSynthesis.getVoices();
    const preferredVoice = voices.find(voice => 
      voice.name.includes('Female') || 
      voice.name.includes('Samantha') ||
      voice.name.includes('Google US English') ||
      voice.lang.includes('en-US')
    );
    
    if (preferredVoice) {
      utterance.voice = preferredVoice;
    }
    
    // Event handlers
    utterance.onstart = () => {
      setIsSpeaking(true);
      console.log('🔊 Speaking...');
    };
    
    utterance.onend = () => {
      setIsSpeaking(false);
      console.log('✅ Speech finished');
    };
    
    utterance.onerror = (error) => {
      setIsSpeaking(false);
      console.error('❌ Speech error:', error);
    };
    
    // Speak the text
    window.speechSynthesis.speak(utterance);
  };

  const stopSpeaking = () => {
    window.speechSynthesis.cancel();
    setIsSpeaking(false);
  };

  const replaySpeech = () => {
    if (aiResponse) {
      speakText(aiResponse);
    }
  };

  // Audio Recording Functions
  const startAudioRecording = async () => {
    try {
      setAudioStatus('Requesting microphone permission...');
      
      const stream = await navigator.mediaDevices.getUserMedia({
        audio: {
          echoCancellation: true,
          noiseSuppression: true,
          autoGainControl: true,
          sampleRate: 16000,
          channelCount: 1
        }
      });

      // Determine best audio format
      let mimeType = 'audio/webm';
      if (MediaRecorder.isTypeSupported('audio/webm;codecs=opus')) {
        mimeType = 'audio/webm;codecs=opus';
      } else if (MediaRecorder.isTypeSupported('audio/mp4')) {
        mimeType = 'audio/mp4';
      } else if (MediaRecorder.isTypeSupported('audio/ogg;codecs=opus')) {
        mimeType = 'audio/ogg;codecs=opus';
      }

      const mediaRecorder = new MediaRecorder(stream, { mimeType });
      mediaRecorderRef.current = mediaRecorder;
      audioChunksRef.current = [];

      mediaRecorder.ondataavailable = (event) => {
        if (event.data && event.data.size > 0) {
          audioChunksRef.current.push(event.data);
        }
      };

      mediaRecorder.onstop = () => {
        if (audioChunksRef.current.length === 0) {
          setAudioStatus('No audio recorded');
          return;
        }

        const audioBlob = new Blob(audioChunksRef.current, { type: mimeType });
        sendAudioToBackend(audioBlob);
        
        // Stop all tracks to release microphone
        stream.getTracks().forEach(track => track.stop());
      };

      mediaRecorder.start(100);
      setIsRecording(true);
      setAudioStatus('🔴 Recording... Click to stop');
      console.log('🎤 Audio recording started');
      
    } catch (error) {
      console.error('❌ Microphone error:', error);
      let errorMessage = 'Microphone access failed. ';
      
      if (error instanceof Error) {
        if (error.name === 'NotAllowedError') {
          errorMessage += 'Please allow microphone access.';
        } else if (error.name === 'NotFoundError') {
          errorMessage += 'No microphone found.';
        } else if (error.name === 'NotReadableError') {
          errorMessage += 'Microphone in use by another app.';
        } else {
          errorMessage += error.message;
        }
      }
      
      setAudioStatus(errorMessage);
      setIsRecording(false);
    }
  };

  const stopAudioRecording = () => {
    if (mediaRecorderRef.current && mediaRecorderRef.current.state === 'recording') {
      mediaRecorderRef.current.stop();
      setIsRecording(false);
      setAudioStatus('Processing audio...');
      console.log('🛑 Audio recording stopped');
    }
  };

  const toggleAudioRecording = () => {
    if (isRecording) {
      stopAudioRecording();
    } else {
      startAudioRecording();
    }
  };

  const sendAudioToBackend = async (audioBlob: Blob) => {
    if (!audioBlob || audioBlob.size === 0) {
      setAudioStatus('No audio to send');
      return;
    }

    setAudioStatus('Sending audio to AI...');
    
    const formData = new FormData();
    const fileName = `audio.${audioBlob.type.includes('mp4') ? 'mp4' : audioBlob.type.includes('ogg') ? 'ogg' : 'webm'}`;
    
    // API expects 'audio' field name (not 'audio_file')
    formData.append('audio', audioBlob, fileName);
    
    // Optional: Add conversation_id if you want to maintain context
    // formData.append('conversation_id', 'your-session-id');

    try {
      const response = await fetch('https://bbhkf952-8000.inc1.devtunnels.ms/input/audio', {
        method: 'POST',
        body: formData,
      });

      if (!response.ok) {
        const errorText = await response.text();
        throw new Error(`Server error (${response.status}): ${errorText}`);
      }

      const responseData = await response.json();
      
      console.log('✅ AI Response:', responseData);
      
      // Store transcription and response
      if (responseData.transcription) {
        setTranscription(responseData.transcription);
        console.log('📝 Transcription:', responseData.transcription);
      }
      
      // Display the final response from the API
      if (responseData.final_response) {
        setAiResponse(responseData.final_response);
        setAudioStatus(`✅ Response received`);
        speakText(responseData.final_response); // Auto-speak the response
      } else if (responseData.bot_response) {
        setAiResponse(responseData.bot_response);
        setAudioStatus(`✅ Response received`);
        speakText(responseData.bot_response); // Auto-speak the response
      } else {
        setAiResponse(responseData.query || 'Command received');
        setAudioStatus(`✅ Processed`);
      }
      
      // Log additional info
      if (responseData.subsystems_activated) {
        console.log('⚙️ Subsystems:', responseData.subsystems_activated);
      }
      
    } catch (error) {
      console.error('❌ Audio processing error:', error);
      const errorMessage = error instanceof Error ? error.message : 'Unknown error';
      setAudioStatus(`❌ Failed: ${errorMessage}`);
    }
  };

  const startBotTracking = async () => {
    if (!botConnected) {
      alert('Please connect to bot first!');
      return;
    }
    
    try {
      const mode = trackingMode === 'face-pose' ? 'face' : 'hand';
      const response = await fetch(`${BACKEND_URL}/bot/tracking/start?mode=${mode}`, {
        method: 'POST',
      });
      const data = await response.json();
      
      if (data.status === 'success') {
        setBotTracking(true);
        setBotStatus(`Tracking: ${mode}`);
        console.log('🤖 Bot tracking started:', data);
      } else {
        console.error('❌ Failed to start tracking:', data);
      }
    } catch (error) {
      console.error('❌ Error starting bot tracking:', error);
    }
  };

  const stopBotTracking = async () => {
    try {
      await fetch(`${BACKEND_URL}/bot/tracking/stop`, {
        method: 'POST',
      });
      setBotTracking(false);
      setBotStatus('Connected');
      console.log('⏹️ Bot tracking stopped');
    } catch (error) {
      console.error('❌ Error stopping bot tracking:', error);
    }
  };

  const stopBot = async () => {
    try {
      await fetch(`${BACKEND_URL}/bot/stop`, {
        method: 'POST',
      });
      console.log('🛑 Bot emergency stop');
    } catch (error) {
      console.error('❌ Error stopping bot:', error);
    }
  };

  const drawDetectionOverlay = (ctx: CanvasRenderingContext2D, width: number, height: number) => {
    const data = detectionData;
    if (!data) return;

    // Draw faces with green boxes
    // If no face detected but pose is available, use pose face landmarks as fallback
    let facesDrawn = false;
    
    if (data.faces && data.faces.length > 0) {
      data.faces.forEach((face: any, faceIndex: number) => {
        const x = face.x * width;
        const y = face.y * height;
        const w = face.width * width;
        const h = face.height * height;
        
        drawFaceBox(ctx, x, y, w, h, faceIndex);
        facesDrawn = true;
      });
    }
    
    // Fallback: Use pose face landmarks to draw face box if face detector failed
    if (!facesDrawn && data.poses && data.poses.length > 0) {
      data.poses.forEach((pose: any, poseIndex: number) => {
        const landmarks = pose.landmarks;
        // Face landmarks in pose: 0-10 are face/head landmarks
        const faceLandmarks = landmarks.slice(0, 11);
        const visibleFaceLandmarks = faceLandmarks.filter((lm: any) => lm.visibility > 0.3);
        
        if (visibleFaceLandmarks.length >= 3) {
          // Calculate bounding box from pose face landmarks
          const xs = visibleFaceLandmarks.map((lm: any) => lm.x * width);
          const ys = visibleFaceLandmarks.map((lm: any) => lm.y * height);
          
          const minX = Math.min(...xs);
          const maxX = Math.max(...xs);
          const minY = Math.min(...ys);
          const maxY = Math.max(...ys);
          
          // Add padding
          const boxWidth = maxX - minX;
          const boxHeight = maxY - minY;
          const padding = 0.3; // 30% padding for head
          
          const x = Math.max(0, minX - boxWidth * padding);
          const y = Math.max(0, minY - boxHeight * padding);
          const w = boxWidth * (1 + padding * 2);
          const h = boxHeight * (1 + padding * 2);
          
          drawFaceBox(ctx, x, y, w, h, poseIndex, true);
          facesDrawn = true;
        }
      });
    }

    // Draw hands with cyan/blue landmarks and connections
    if (data.hands && data.hands.length > 0) {
      data.hands.forEach((hand: any) => {
        const landmarks = hand.landmarks;
        const handedness = hand.handedness;
        const color = handedness === 'Left' ? '#00FFFF' : '#0099FF'; // Cyan for left, blue for right
        
        // Define hand connections (MediaPipe hand topology)
        const connections = [
          // Thumb
          [0, 1], [1, 2], [2, 3], [3, 4],
          // Index finger
          [0, 5], [5, 6], [6, 7], [7, 8],
          // Middle finger
          [0, 9], [9, 10], [10, 11], [11, 12],
          // Ring finger
          [0, 13], [13, 14], [14, 15], [15, 16],
          // Pinky
          [0, 17], [17, 18], [18, 19], [19, 20],
          // Palm
          [5, 9], [9, 13], [13, 17]
        ];
        
        // Draw connections
        ctx.strokeStyle = color;
        ctx.lineWidth = 3;
        ctx.beginPath();
        connections.forEach(([start, end]) => {
          if (landmarks[start] && landmarks[end]) {
            const startX = landmarks[start].x * width;
            const startY = landmarks[start].y * height;
            const endX = landmarks[end].x * width;
            const endY = landmarks[end].y * height;
            ctx.moveTo(startX, startY);
            ctx.lineTo(endX, endY);
          }
        });
        ctx.stroke();
        
        // Draw all landmarks - full detail in hand-only mode
        ctx.fillStyle = color;
        landmarks.forEach((landmark: any, idx: number) => {
          const x = landmark.x * width;
          const y = landmark.y * height;
          // Larger dots for key points (wrist and fingertips)
          const radius = [0, 4, 8, 12, 16, 20].includes(idx) ? 6 : 4;
          ctx.beginPath();
          ctx.arc(x, y, radius, 0, 2 * Math.PI);
          ctx.fill();
          
          // Draw white center for fingertips
          if ([4, 8, 12, 16, 20].includes(idx)) {
            ctx.fillStyle = '#FFFFFF';
            ctx.beginPath();
            ctx.arc(x, y, 2, 0, 2 * Math.PI);
            ctx.fill();
            ctx.fillStyle = color;
          }
        });
        
        // Draw label
        if (landmarks[0]) {
          const x = landmarks[0].x * width;
          const y = landmarks[0].y * height;
          const label = `${handedness} Hand`;
          ctx.font = 'bold 16px Arial';
          const textWidth = ctx.measureText(label).width;
          ctx.fillStyle = `${color}DD`;
          ctx.fillRect(x - 8, y - 38, textWidth + 16, 26);
          ctx.fillStyle = '#000000';
          ctx.fillText(label, x, y - 18);
        }
      });
    }

    // Draw pose (upper body) with yellow landmarks and skeleton
    if (data.poses && data.poses.length > 0) {
      data.poses.forEach((pose: any) => {
        const landmarks = pose.landmarks;
        const color = '#FFFF00'; // Yellow
        
        // Define upper body connections
        const connections = [
          // Face
          [0, 1], [1, 2], [2, 3], [3, 7],
          [0, 4], [4, 5], [5, 6], [6, 8],
          [9, 10],
          // Shoulders and torso
          [11, 12], [11, 13], [13, 15], [12, 14], [14, 16],
          [11, 23], [12, 24], [23, 24]
        ];
        
        // Draw connections with optimized checks
        ctx.strokeStyle = color;
        ctx.lineWidth = 2;
        ctx.beginPath();
        connections.forEach(([start, end]) => {
          if (landmarks[start] && landmarks[end] && 
              landmarks[start].visibility > 0.5 && landmarks[end].visibility > 0.5) {
            ctx.moveTo(landmarks[start].x * width, landmarks[start].y * height);
            ctx.lineTo(landmarks[end].x * width, landmarks[end].y * height);
          }
        });
        ctx.stroke();
        
        // Draw only key landmarks for performance (shoulders, elbows, wrists)
        ctx.fillStyle = color;
        [11, 12, 13, 14, 15, 16, 23, 24].forEach((idx) => {
          if (landmarks[idx] && landmarks[idx].visibility > 0.5) {
            const x = landmarks[idx].x * width;
            const y = landmarks[idx].y * height;
            const radius = [11, 12].includes(idx) ? 5 : 4; // Larger for shoulders
            ctx.beginPath();
            ctx.arc(x, y, radius, 0, 2 * Math.PI);
            ctx.fill();
          }
        });
        
        // Draw label at shoulder midpoint
        if (landmarks[11] && landmarks[12] && landmarks[11].visibility > 0.5 && landmarks[12].visibility > 0.5) {
          const x = ((landmarks[11].x + landmarks[12].x) / 2) * width;
          const y = ((landmarks[11].y + landmarks[12].y) / 2) * height;
          const label = 'Pose';
          ctx.font = 'bold 14px Arial';
          const textWidth = ctx.measureText(label).width;
          ctx.fillStyle = `${color}CC`;
          ctx.fillRect(x - textWidth / 2 - 8, y - 35, textWidth + 16, 22);
          ctx.fillStyle = '#000000';
          ctx.fillText(label, x - textWidth / 2, y - 18);
        }
      });
    }
  };

  // Helper function to draw face box with corner markers
  const drawFaceBox = (ctx: CanvasRenderingContext2D, x: number, y: number, w: number, h: number, index: number, fromPose: boolean = false) => {
    // Draw rectangle
    ctx.strokeStyle = fromPose ? '#00DD00' : '#00FF00'; // Slightly different green if from pose
    ctx.lineWidth = 2;
    ctx.strokeRect(x, y, w, h);
    
    // Draw simplified corner markers
    const cornerSize = 12;
    ctx.lineWidth = 3;
    ctx.beginPath();
    // Top-left
    ctx.moveTo(x, y + cornerSize);
    ctx.lineTo(x, y);
    ctx.lineTo(x + cornerSize, y);
    // Top-right
    ctx.moveTo(x + w - cornerSize, y);
    ctx.lineTo(x + w, y);
    ctx.lineTo(x + w, y + cornerSize);
    // Bottom-left
    ctx.moveTo(x, y + h - cornerSize);
    ctx.lineTo(x, y + h);
    ctx.lineTo(x + cornerSize, y + h);
    // Bottom-right
    ctx.moveTo(x + w - cornerSize, y + h);
    ctx.lineTo(x + w, y + h);
    ctx.lineTo(x + w, y + h - cornerSize);
    ctx.stroke();
    
    // Draw label
    const label = fromPose ? 'Face (Pose)' : 'Face';
    ctx.font = 'bold 16px Arial';
    const textWidth = ctx.measureText(label).width;
    ctx.fillStyle = fromPose ? 'rgba(0, 221, 0, 0.8)' : 'rgba(0, 255, 0, 0.8)';
    ctx.fillRect(x, y - 28, textWidth + 16, 24);
    ctx.fillStyle = '#000000';
    ctx.fillText(label, x + 8, y - 10);
  };

  const toggleStreaming = () => {
    if (isStreaming) {
      wsRef.current?.close();
      setIsStreaming(false);
      if (animationFrameRef.current) {
        cancelAnimationFrame(animationFrameRef.current);
      }
    } else {
      connectWebSocket();
    }
  };

  const changeDetectionType = (mode: 'face-pose' | 'hand') => {
    if (isStreaming) {
      wsRef.current?.close();
      setIsStreaming(false);
      if (animationFrameRef.current) {
        cancelAnimationFrame(animationFrameRef.current);
      }
    }
    setTrackingMode(mode);
    setDetectionData(null);
  };

  return (
    <div className="min-h-screen bg-gray-900 text-white p-8">
      <div className="max-w-6xl mx-auto">
        <h1 className="text-4xl font-bold mb-8 text-center">MediaPipe Body Tracking</h1>
        
        <div className="bg-gray-800 rounded-lg p-6 mb-6">
          <div className="flex gap-4 mb-4 flex-wrap items-center">
            <h2 className="text-2xl font-bold text-white">
              {trackingMode === 'face-pose' ? 'Face + Pose Tracking' : 'Hand Tracking'}
            </h2>
            {trackingMode === 'face-pose' && (
              <span className="px-3 py-1 bg-purple-600 text-white text-sm font-semibold rounded-full">
                ⚡ Multithreaded
              </span>
            )}
            
            <div className="flex gap-2">
              <button
                onClick={() => changeDetectionType('face-pose')}
                disabled={isStreaming}
                className={`px-4 py-2 rounded-lg font-semibold transition ${
                  trackingMode === 'face-pose'
                    ? 'bg-blue-600 text-white'
                    : 'bg-gray-700 text-gray-300 hover:bg-gray-600'
                } ${isStreaming ? 'opacity-50 cursor-not-allowed' : ''}`}
              >
                👤 Face + Pose
              </button>
              <button
                onClick={() => changeDetectionType('hand')}
                disabled={isStreaming}
                className={`px-4 py-2 rounded-lg font-semibold transition ${
                  trackingMode === 'hand'
                    ? 'bg-blue-600 text-white'
                    : 'bg-gray-700 text-gray-300 hover:bg-gray-600'
                } ${isStreaming ? 'opacity-50 cursor-not-allowed' : ''}`}
              >
                ✋ Hands
              </button>
            </div>
            
            <button
              onClick={toggleStreaming}
              className={`px-6 py-2 rounded-lg font-semibold transition ml-auto ${
                isStreaming
                  ? 'bg-red-600 hover:bg-red-700'
                  : 'bg-green-600 hover:bg-green-700'
              }`}
            >
              {isStreaming ? '⏹ Stop Tracking' : '▶ Start Tracking'}
            </button>
          </div>

          <div className="grid grid-cols-2 md:grid-cols-5 gap-4 mb-4">
            <div className="bg-gray-700 p-4 rounded-lg">
              <p className="text-sm text-gray-400">Status</p>
              <p className="text-xl font-bold">
                {isStreaming ? '🟢 Active' : '🔴 Stopped'}
              </p>
            </div>
            <div className="bg-gray-700 p-4 rounded-lg">
              <p className="text-sm text-gray-400">FPS</p>
              <p className="text-xl font-bold">{fps}</p>
            </div>
            {trackingMode === 'face-pose' ? (
              <>
                <div className="bg-green-900/30 border border-green-500 p-4 rounded-lg">
                  <p className="text-sm text-green-400">Faces</p>
                  <p className="text-xl font-bold text-green-300">
                    {detectionData?.count ?? 0}
                  </p>
                </div>
                <div className="bg-yellow-900/30 border border-yellow-500 p-4 rounded-lg col-span-2">
                  <p className="text-sm text-yellow-400">Poses</p>
                  <p className="text-xl font-bold text-yellow-300">
                    {detectionData?.poses_count ?? 0}
                  </p>
                </div>
              </>
            ) : (
              <div className="bg-cyan-900/30 border border-cyan-500 p-4 rounded-lg col-span-3">
                <p className="text-sm text-cyan-400">Hands Detected</p>
                <p className="text-xl font-bold text-cyan-300">
                  {detectionData?.hands_count ?? 0}
                </p>
              </div>
            )}
          </div>
        </div>

        <div className="relative bg-black rounded-lg overflow-hidden">
          <video
            ref={videoRef}
            autoPlay
            playsInline
            muted
            className="absolute top-0 left-0 w-full h-auto"
            style={{ opacity: 0, pointerEvents: 'none' }}
          />
          <canvas
            ref={canvasRef}
            className="w-full h-auto block"
            style={{ minHeight: '480px', backgroundColor: '#000' }}
          />
          {!isStreaming && (
            <div className="absolute inset-0 flex items-center justify-center bg-black bg-opacity-50">
              <p className="text-2xl font-bold">Click &quot;Start Tracking&quot; to begin</p>
            </div>
          )}
        </div>

        <div className="mt-6 bg-gray-800 rounded-lg p-6">
          <h2 className="text-xl font-bold mb-4">🤖 Bot Control Panel</h2>
          
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4 mb-4">
            {/* Connection Status */}
            <div className="bg-gray-700 p-4 rounded-lg">
              <p className="text-sm text-gray-400">Bot Status</p>
              <p className={`text-xl font-bold ${botConnected ? 'text-green-400' : 'text-red-400'}`}>
                {botStatus}
              </p>
            </div>
            
            {/* Tracking Status */}
            <div className="bg-gray-700 p-4 rounded-lg">
              <p className="text-sm text-gray-400">Tracking Status</p>
              <p className={`text-xl font-bold ${botTracking ? 'text-green-400' : 'text-gray-400'}`}>
                {botTracking ? '🟢 Active' : '⚫ Inactive'}
              </p>
            </div>
          </div>

          {/* Control Buttons */}
          <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
            <button
              onClick={connectBot}
              disabled={botConnected}
              className={`px-4 py-3 rounded-lg font-semibold transition ${
                botConnected
                  ? 'bg-gray-600 text-gray-400 cursor-not-allowed'
                  : 'bg-blue-600 hover:bg-blue-700 text-white'
              }`}
            >
              {botConnected ? '✓ Connected' : '🔌 Connect Bot'}
            </button>

            <button
              onClick={startBotTracking}
              disabled={!botConnected || botTracking || !isStreaming}
              className={`px-4 py-3 rounded-lg font-semibold transition ${
                !botConnected || botTracking || !isStreaming
                  ? 'bg-gray-600 text-gray-400 cursor-not-allowed'
                  : 'bg-green-600 hover:bg-green-700 text-white'
              }`}
            >
              {botTracking ? '✓ Tracking' : '🎯 Start Tracking'}
            </button>

            <button
              onClick={stopBotTracking}
              disabled={!botTracking}
              className={`px-4 py-3 rounded-lg font-semibold transition ${
                !botTracking
                  ? 'bg-gray-600 text-gray-400 cursor-not-allowed'
                  : 'bg-yellow-600 hover:bg-yellow-700 text-white'
              }`}
            >
              ⏸️ Stop Tracking
            </button>

            <button
              onClick={stopBot}
              disabled={!botConnected}
              className={`px-4 py-3 rounded-lg font-semibold transition ${
                !botConnected
                  ? 'bg-gray-600 text-gray-400 cursor-not-allowed'
                  : 'bg-red-600 hover:bg-red-700 text-white'
              }`}
            >
              🛑 Emergency Stop
            </button>
          </div>

          {/* Audio Recording Control */}
          <div className="mt-4 p-4 bg-purple-900/20 border border-purple-500 rounded-lg">
            <h3 className="text-lg font-bold text-purple-400 mb-2">🎤 Voice Commands</h3>
            <p className="text-sm text-gray-400 mb-3">{audioStatus}</p>
            
            {/* Transcription Display */}
            {transcription && (
              <div className="mb-3 p-3 bg-gray-700 rounded-lg">
                <p className="text-xs text-gray-400 mb-1">📝 You said:</p>
                <p className="text-sm text-white italic">&quot;{transcription}&quot;</p>
              </div>
            )}
            
            {/* AI Response Display */}
            {aiResponse && (
              <div className="mb-3">
                <div className="p-3 bg-purple-800/30 rounded-lg max-h-32 overflow-y-auto mb-2">
                  <p className="text-xs text-purple-300 mb-1">🤖 AI Response:</p>
                  <p className="text-sm text-white">{aiResponse}</p>
                </div>
                
                {/* TTS Control Buttons */}
                <div className="flex gap-2">
                  <button
                    onClick={replaySpeech}
                    disabled={isSpeaking}
                    className={`flex-1 px-3 py-2 rounded-lg text-sm font-semibold transition ${
                      isSpeaking
                        ? 'bg-gray-600 text-gray-400 cursor-not-allowed'
                        : 'bg-green-600 hover:bg-green-700 text-white'
                    }`}
                  >
                    {isSpeaking ? '🔊 Speaking...' : '🔊 Replay'}
                  </button>
                  
                  {isSpeaking && (
                    <button
                      onClick={stopSpeaking}
                      className="px-3 py-2 rounded-lg text-sm font-semibold bg-red-600 hover:bg-red-700 text-white transition"
                    >
                      🔇 Stop
                    </button>
                  )}
                </div>
              </div>
            )}
            
            <button
              onClick={toggleAudioRecording}
              className={`w-full px-4 py-3 rounded-lg font-semibold transition ${
                isRecording
                  ? 'bg-red-600 hover:bg-red-700 text-white animate-pulse'
                  : 'bg-purple-600 hover:bg-purple-700 text-white'
              }`}
            >
              {isRecording ? '🔴 Stop Recording' : '🎤 Start Voice Recording'}
            </button>
          </div>

          <button
            onClick={disconnectBot}
            disabled={!botConnected}
            className={`mt-3 w-full px-4 py-2 rounded-lg font-semibold transition ${
              !botConnected
                ? 'bg-gray-600 text-gray-400 cursor-not-allowed'
                : 'bg-gray-700 hover:bg-gray-600 text-white'
            }`}
          >
            🔌 Disconnect Bot
          </button>

          <div className="mt-4 p-4 bg-yellow-900/20 border border-yellow-500 rounded">
            <p className="text-yellow-400 mb-2">⚠️ <strong>Important:</strong></p>
            <ul className="list-disc list-inside space-y-1 text-sm text-yellow-300">
              <li>Make sure your bot is powered on and connected to WiFi</li>
              <li>Start camera tracking BEFORE starting bot tracking</li>
              <li>Bot will follow the first detected face/hand</li>
              <li>Use Emergency Stop if bot behaves unexpectedly</li>
            </ul>
          </div>
        </div>

        <div className="mt-6 bg-gray-800 rounded-lg p-6">
          <h2 className="text-xl font-bold mb-4">📋 Quick Start</h2>
          <ol className="list-decimal list-inside space-y-2 text-gray-300">
            <li>Make sure the Python backend is running: <code className="bg-gray-700 px-2 py-1 rounded">python main.py</code></li>
            <li>Choose your tracking mode (Face + Pose or Hands)</li>
            <li>Click &quot;Start Tracking&quot; to begin</li>
            <li>Position yourself in front of the camera</li>
          </ol>
          <div className="mt-4 p-4 bg-blue-900/20 border border-blue-500 rounded">
            <p className="text-blue-400 mb-2">✨ <strong>Two Optimized Modes:</strong></p>
            <ul className="list-disc list-inside space-y-1 text-sm">
              <li><strong>Face + Pose Mode (15 FPS):</strong> <span className="text-green-400">Green boxes</span> for face + <span className="text-yellow-400">Yellow skeleton</span> for upper body
                <span className="ml-2 text-purple-400">⚡ Multithreaded processing!</span>
              </li>
              <li><strong>Hand Mode (20 FPS):</strong> <span className="text-cyan-400">Cyan/Blue skeleton</span> with detailed finger tracking (left/right hands)</li>
            </ul>
            <p className="text-green-300 mt-2 text-xs">💡 Smart fallback: If face detector loses tracking (extreme side profile), pose face landmarks automatically create the green box!</p>
          </div>
        </div>
      </div>
    </div>
  );
}
