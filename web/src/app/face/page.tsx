'use client'

import { useEffect, useRef, useState } from 'react'
import { FaceLandmarker, FilesetResolver, DrawingUtils } from '@mediapipe/tasks-vision'

export default function FaceTracker() {
  const videoRef = useRef<HTMLVideoElement>(null)
  const canvasRef = useRef<HTMLCanvasElement>(null)
  const [faceLandmarker, setFaceLandmarker] = useState<FaceLandmarker | null>(null)
  const [status, setStatus] = useState('Loading...')
  const animationFrameRef = useRef<number | null>(null)

  // Initialize MediaPipe
  useEffect(() => {
    async function init() {
      try {
        const vision = await FilesetResolver.forVisionTasks(
          "https://cdn.jsdelivr.net/npm/@mediapipe/tasks-vision@0.10.0/wasm"
        )
        
        const landmarker = await FaceLandmarker.createFromOptions(vision, {
          baseOptions: {
            modelAssetPath: `https://storage.googleapis.com/mediapipe-models/face_landmarker/face_landmarker/float16/1/face_landmarker.task`,
            delegate: "GPU"
          },
          outputFaceBlendshapes: false, // Disable blendshapes for better performance
          runningMode: "VIDEO",
          numFaces: 1
        })
        
        setFaceLandmarker(landmarker)
        setStatus('Ready! Starting camera...')
      } catch (error) {
        console.error('Init error:', error)
        setStatus('Failed to load face detection model')
      }
    }
    
    init()
    
    return () => {
      if (animationFrameRef.current) {
        cancelAnimationFrame(animationFrameRef.current)
      }
    }
  }, [])

  // Start camera when faceLandmarker is ready
  useEffect(() => {
    if (!faceLandmarker) return
    
    async function startCamera() {
      try {
        // Lower resolution for better performance on mobile
        const stream = await navigator.mediaDevices.getUserMedia({
          video: { 
            facingMode: 'user', 
            width: { ideal: 480 }, 
            height: { ideal: 360 },
            frameRate: { ideal: 30, max: 30 }
          }
        })
        
        if (videoRef.current) {
          videoRef.current.srcObject = stream
          videoRef.current.onloadeddata = () => {
            if (videoRef.current) {
              videoRef.current.play()
              setStatus('Camera ready! Detecting faces...')
              detectFaces()
            }
          }
        }
      } catch (error) {
        setStatus('Camera access denied')
        console.error('Camera error:', error)
      }
    }
    
    startCamera()
  }, [faceLandmarker])

  // Detect faces in real-time - optimized for low latency
  const detectFaces = () => {
    const video = videoRef.current
    const canvas = canvasRef.current
    
    if (!faceLandmarker || !video || !canvas) {
      console.log('Not ready:', { 
        faceLandmarker: !!faceLandmarker, 
        video: !!video, 
        canvas: !!canvas 
      })
      return
    }
    
    const ctx = canvas.getContext('2d', { 
      willReadFrequently: false,
      alpha: true,
      desynchronized: true // Low latency hint
    })
    if (!ctx) return
    
    let lastVideoTime = -1
    
    const detect = () => {
      if (!video || !canvas) return
      
      const startTimeMs = performance.now()
      
      // Only process if we have a new frame
      if (lastVideoTime !== video.currentTime) {
        lastVideoTime = video.currentTime
        
        try {
          const results = faceLandmarker.detectForVideo(video, startTimeMs)
          
          // Clear canvas
          ctx.clearRect(0, 0, canvas.width, canvas.height)
          
          // Draw landmarks
          if (results.faceLandmarks && results.faceLandmarks.length > 0) {
            const drawingUtils = new DrawingUtils(ctx)
            
            for (const landmarks of results.faceLandmarks) {
              // Only draw essential landmarks for performance
              
              // Draw face oval
              drawingUtils.drawConnectors(
                landmarks,
                FaceLandmarker.FACE_LANDMARKS_FACE_OVAL,
                { color: "#00FF00", lineWidth: 1 }
              )
              
              // Draw right eye
              drawingUtils.drawConnectors(
                landmarks,
                FaceLandmarker.FACE_LANDMARKS_RIGHT_EYE,
                { color: "#FF3030", lineWidth: 1 }
              )
              
              // Draw left eye
              drawingUtils.drawConnectors(
                landmarks,
                FaceLandmarker.FACE_LANDMARKS_LEFT_EYE,
                { color: "#FF3030", lineWidth: 1 }
              )
              
              // Draw lips
              drawingUtils.drawConnectors(
                landmarks,
                FaceLandmarker.FACE_LANDMARKS_LIPS,
                { color: "#E0E0E0", lineWidth: 1 }
              )
            }
            
            setStatus(`✓ Tracking ${results.faceLandmarks[0].length} landmarks`)
          } else {
            setStatus('Looking for faces...')
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
          width="480"
          height="360"
        />
        <canvas
          ref={canvasRef}
          className="absolute top-0 left-0 rounded-lg"
          width="480"
          height="360"
        />
      </div>
      
      <div className="text-xs text-gray-400 text-center max-w-md">
        Optimized for mobile • Real-time tracking enabled
      </div>
    </div>
  )
}
