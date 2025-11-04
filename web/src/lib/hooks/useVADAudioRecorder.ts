'use client';

import { useRef, useCallback, useState, useEffect } from 'react';
import { MicVAD } from '@ricky0123/vad-web';

interface UseVADAudioRecorderOptions {
  onRecordingComplete?: (audioBlob: Blob) => void;
  onError?: (error: Error) => void;
  silenceDurationMs?: number; // Time of silence to trigger stop
  onSpeechStart?: () => void;
  onSpeechEnd?: () => void;
}

export function useVADAudioRecorder(
  options: UseVADAudioRecorderOptions = {}
) {
  const {
    onRecordingComplete,
    onError,
    silenceDurationMs = 1500,
    onSpeechStart,
    onSpeechEnd,
  } = options;

  const mediaRecorderRef = useRef<MediaRecorder | null>(null);
  const audioChunksRef = useRef<Blob[]>([]);
  const streamRef = useRef<MediaStream | null>(null);
  const vadRef = useRef<MicVAD | null>(null);
  const silenceTimeoutRef = useRef<NodeJS.Timeout | null>(null);

  const [isRecording, setIsRecording] = useState(false);
  const [isVadReady, setIsVadReady] = useState(false);
  const [isSpeechDetected, setIsSpeechDetected] = useState(false);

  // Initialize VAD
  useEffect(() => {
    let mounted = true;

    const initVAD = async () => {
      try {
        const vad = await MicVAD.new({
          onSpeechStart: () => {
            console.log('🎤 Speech detected');
            setIsSpeechDetected(true);
            onSpeechStart?.();
            
            // Clear silence timeout when speech is detected
            if (silenceTimeoutRef.current) {
              clearTimeout(silenceTimeoutRef.current);
              silenceTimeoutRef.current = null;
            }
          },
          onSpeechEnd: () => {
            console.log('🔇 Speech ended');
            setIsSpeechDetected(false);
            onSpeechEnd?.();
            
            // Start silence timeout
            if (mediaRecorderRef.current && isRecording) {
              silenceTimeoutRef.current = setTimeout(() => {
                console.log('⏱️ Silence detected, stopping recording');
                stopRecording();
              }, silenceDurationMs);
            }
          },
          onVADMisfire: () => {
            console.log('⚠️ VAD misfire');
          },
          model: 'v5',
          baseAssetPath: '/vad',
          onnxWASMBasePath: '/vad',
          ortConfig(ort) {
            ort.env.wasm.wasmPaths = '/vad/';
          },
        });

        if (mounted) {
          vadRef.current = vad;
          setIsVadReady(true);
          console.log('✅ VAD initialized');
        }
      } catch (error) {
        if (mounted) {
          console.error('❌ VAD initialization error:', error);
          onError?.(
            error instanceof Error ? error : new Error('Failed to init VAD')
          );
        }
      }
    };

    initVAD();

    return () => {
      mounted = false;
      if (vadRef.current) {
        vadRef.current.destroy();
      }
    };
  }, [onError, silenceDurationMs, onSpeechStart, onSpeechEnd]);

  const startRecording = useCallback(async () => {
    try {
      if (!isVadReady || !vadRef.current) {
        throw new Error('VAD not ready yet');
      }

      console.log('🎙️ Starting recording...');
      
      // Get microphone stream
      const stream = await navigator.mediaDevices.getUserMedia({
        audio: {
          echoCancellation: true,
          noiseSuppression: true,
          autoGainControl: false,
          sampleRate: 16000,
        },
      });

      streamRef.current = stream;
      audioChunksRef.current = [];

      // Setup MediaRecorder
      const mimeType = MediaRecorder.isTypeSupported('audio/webm;codecs=opus')
        ? 'audio/webm;codecs=opus'
        : 'audio/webm';

      const mediaRecorder = new MediaRecorder(stream, { 
        mimeType,
        audioBitsPerSecond: 128000,
      });
      
      mediaRecorderRef.current = mediaRecorder;

      mediaRecorder.ondataavailable = (event) => {
        if (event.data.size > 0) {
          audioChunksRef.current.push(event.data);
        }
      };

      mediaRecorder.onstop = () => {
        console.log('🛑 Recording stopped');
        const audioBlob = new Blob(audioChunksRef.current, { type: mimeType });
        onRecordingComplete?.(audioBlob);

        // Cleanup stream
        stream.getTracks().forEach((track) => track.stop());
      };

      // Start recording
      mediaRecorder.start();
      
      // Start VAD
      await vadRef.current.start();
      
      setIsRecording(true);
      console.log('✅ Recording started');
    } catch (error) {
      console.error('❌ Recording error:', error);
      onError?.(error instanceof Error ? error : new Error('Recording failed'));
    }
  }, [isVadReady, onRecordingComplete, onError]);

  const stopRecording = useCallback(() => {
    if (mediaRecorderRef.current && isRecording) {
      console.log('⏹️ Stopping recording...');
      
      // Clear silence timeout
      if (silenceTimeoutRef.current) {
        clearTimeout(silenceTimeoutRef.current);
        silenceTimeoutRef.current = null;
      }

      // Stop VAD
      if (vadRef.current) {
        vadRef.current.pause();
      }

      // Stop MediaRecorder
      mediaRecorderRef.current.stop();
      setIsRecording(false);
      setIsSpeechDetected(false);
    }
  }, [isRecording]);

  return {
    startRecording,
    stopRecording,
    isRecording,
    isVadReady,
    isSpeechDetected,
  };
}
