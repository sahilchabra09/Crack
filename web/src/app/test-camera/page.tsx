'use client';

import { useEffect, useRef } from 'react';

export default function TestCamera() {
  const videoRef = useRef<HTMLVideoElement>(null);
  const canvasRef = useRef<HTMLCanvasElement>(null);

  useEffect(() => {
    const startCamera = async () => {
      try {
        console.log('Requesting camera...');
        const stream = await navigator.mediaDevices.getUserMedia({ 
          video: { width: 640, height: 480 } 
        });
        
        if (videoRef.current) {
          videoRef.current.srcObject = stream;
          console.log('Camera started!');
        }
      } catch (error) {
        console.error('Camera error:', error);
        alert('Cannot access camera: ' + error);
      }
    };

    startCamera();

    // Draw video to canvas
    const draw = () => {
      if (videoRef.current && canvasRef.current) {
        const video = videoRef.current;
        const canvas = canvasRef.current;
        const ctx = canvas.getContext('2d');
        
        if (video.videoWidth > 0 && ctx) {
          canvas.width = video.videoWidth;
          canvas.height = video.videoHeight;
          ctx.drawImage(video, 0, 0);
          
          // Draw a test circle
          ctx.fillStyle = 'red';
          ctx.beginPath();
          ctx.arc(100, 100, 50, 0, 2 * Math.PI);
          ctx.fill();
        }
      }
      requestAnimationFrame(draw);
    };
    draw();
  }, []);

  return (
    <div className="p-8 bg-gray-900 min-h-screen">
      <h1 className="text-white text-3xl mb-4">Camera Test</h1>
      
      <div className="mb-4">
        <h2 className="text-white text-xl mb-2">Video Element:</h2>
        <video 
          ref={videoRef} 
          autoPlay 
          playsInline 
          muted
          className="border-2 border-green-500"
          style={{ width: '640px', height: '480px' }}
        />
      </div>
      
      <div>
        <h2 className="text-white text-xl mb-2">Canvas (should show video + red circle):</h2>
        <canvas 
          ref={canvasRef}
          className="border-2 border-blue-500"
        />
      </div>
      
      <div className="mt-4 text-white">
        <p>✅ If you see video in both: Camera works!</p>
        <p>❌ If both are black: Camera permission issue</p>
        <p>⚠️ If only video shows: Canvas drawing issue</p>
      </div>
    </div>
  );
}
