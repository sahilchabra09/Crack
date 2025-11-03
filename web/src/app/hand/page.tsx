'use client'

import { useEffect, useRef, useState } from 'react'
import { HandLandmarker, FilesetResolver, DrawingUtils } from '@mediapipe/tasks-vision'

export default function HandTracker() {
  const videoRef = useRef<HTMLVideoElement>(null)
  const canvasRef = useRef<HTMLCanvasElement>(null)
  const [handLandmarker, setHandLandmarker] = useState<HandLandmarker | null>(null)
  const [status, setStatus] = useState('Loading MediaPipe...')
  const animationFrameRef = useRef<number | null>(null)

  // Initialize MediaPipe Hand Landmarker
  useEffect(() => {
    async function init() {
      try {
        const vision = await FilesetResolver.forVisionTasks(
          "https://cdn.jsdelivr.net/npm/@mediapipe/tasks-vision@0.10.0/wasm"
        )
        
        const landmarker = await HandLandmarker.createFromOptions(vision, {
          baseOptions: {
            modelAssetPath: "https://storage.googleapis.com/mediapipe-models/hand_landmarker/hand_landmarker/float16/1/hand_landmarker.task",
            delegate: "GPU"
          },
          runningMode: "VIDEO",
          numHands: 1,  // Track only 1 hand for better performance
          minHandDetectionConfidence: 0.5,
          minHandPresenceConfidence: 0.5,
          minTrackingConfidence: 0.5
        })
        
        setHandLandmarker(landmarker)
        setStatus('Hand Landmarker loaded! Starting camera...')
      } catch (error) {
        console.error('Error initializing:', error)
        setStatus('Error loading MediaPipe')
      }
    }
    
    init()
    
    return () => {
      if (animationFrameRef.current) {
        cancelAnimationFrame(animationFrameRef.current)
      }
    }
  }, [])

  // Start camera when handLandmarker is ready
  useEffect(() => {
    if (!handLandmarker) return
    
    async function startCamera() {
      try {
        // Much lower resolution for hand tracking performance
        const stream = await navigator.mediaDevices.getUserMedia({
          video: { 
            facingMode: 'user',
            width: { ideal: 320 },
            height: { ideal: 240 },
            frameRate: { ideal: 24, max: 24 }
          }
        })
        
        if (videoRef.current) {
          videoRef.current.srcObject = stream
          videoRef.current.onloadeddata = () => {
            if (videoRef.current) {
              videoRef.current.play()
              setStatus('Camera ready! Show your hands...')
              detectHands()
            }
          }
        }
      } catch (error) {
        console.error('Camera error:', error)
        setStatus('Camera access denied')
      }
    }
    
    startCamera()
  }, [handLandmarker])

  // Detection loop - optimized for mobile without lag
  const detectHands = () => {
    const video = videoRef.current
    const canvas = canvasRef.current

    if (!handLandmarker || !video || !canvas) {
      console.log('Not ready:', { 
        handLandmarker: !!handLandmarker, 
        video: !!video, 
        canvas: !!canvas 
      })
      return
    }

    const ctx = canvas.getContext('2d', { 
      willReadFrequently: false,
      alpha: true,
      desynchronized: true
    })
    
    if (!ctx) return

    let lastVideoTime = -1

    const detect = () => {
      if (!video || !canvas) {
        animationFrameRef.current = requestAnimationFrame(detect)
        return
      }

      const currentTime = video.currentTime
      
      if (lastVideoTime !== currentTime) {
        lastVideoTime = currentTime
        
        try {
          const startTimeMs = performance.now()
          const results = handLandmarker.detectForVideo(video, startTimeMs)
          
          // Clear canvas
          ctx.clearRect(0, 0, canvas.width, canvas.height)
          
          // Draw if hands detected
          if (results.landmarks && results.landmarks.length > 0) {
            const drawingUtils = new DrawingUtils(ctx)
            
            for (let i = 0; i < results.landmarks.length; i++) {
              const landmarks = results.landmarks[i]
              const handedness = results.handednesses?.[i]?.[0]?.displayName || 'Unknown'
              
              // Choose color based on hand
              const color = handedness === "Left" ? "#00FF00" : "#FF0000"
              
              // Draw only connectors (bones) - no joints for performance
              drawingUtils.drawConnectors(
                landmarks,
                HandLandmarker.HAND_CONNECTIONS,
                { color, lineWidth: 2 }
              )
            }
            
            setStatus(`✋ Tracking hand`)
          } else {
            setStatus('👋 Show your hand...')
          }
        } catch (error) {
          console.error('Detection error:', error)
        }
      }
      
      animationFrameRef.current = requestAnimationFrame(detect)
    }

    detect()
  }

  return (
    <div className="flex flex-col items-center gap-4 p-4 min-h-screen bg-black">
      <h1 className="text-xl font-bold text-white">{status}</h1>
      
      <div className="relative max-w-full">
        <video
          ref={videoRef}
          autoPlay
          playsInline
          muted
          className="rounded-lg max-w-full"
          width="320"
          height="240"
        />
        <canvas
          ref={canvasRef}
          className="absolute top-0 left-0 rounded-lg"
          width="320"
          height="240"
        />
      </div>
      
      <div className="text-xs text-gray-400 text-center max-w-md">
        <div className="flex gap-4 justify-center mb-2">
          <span className="text-green-500">🟢 Left Hand</span>
          <span className="text-red-500">🔴 Right Hand</span>
        </div>
        Ultra-optimized for mobile • Real-time tracking • Low resolution
      </div>
    </div>
  )
}
