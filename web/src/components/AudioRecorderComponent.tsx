'use client';

import { useState } from 'react';
import { useVADAudioRecorder } from '@/lib/hooks/useVADAudioRecorder';

interface AudioRecorderComponentProps {
  onTranscription?: (text: string) => void;
  silenceDurationMs?: number;
}

export function AudioRecorderComponent({ 
  onTranscription, 
  silenceDurationMs = 2000 
}: AudioRecorderComponentProps) {
  const [isLoading, setIsLoading] = useState(false);
  const [statusMessage, setStatusMessage] = useState('');
  const [transcription, setTranscription] = useState('');

  const handleAudioReady = async (audioBlob: Blob) => {
    setIsLoading(true);
    setStatusMessage('Sending audio to backend...');

    try {
      const formData = new FormData();
      formData.append('audio', audioBlob, 'recording.webm');

      // Send to Next.js API route
      const response = await fetch('/api/audio/process', {
        method: 'POST',
        body: formData,
      });

      if (!response.ok) {
        throw new Error('Upload failed');
      }

      const result = await response.json();
      setStatusMessage(`Success: ${result.message}`);
      
      if (result.transcript) {
        setTranscription(result.transcript);
        onTranscription?.(result.transcript);
      }
    } catch (error) {
      const errorMsg = error instanceof Error ? error.message : 'Unknown error';
      setStatusMessage(`Error: ${errorMsg}`);
      console.error('Audio upload error:', error);
    } finally {
      setIsLoading(false);
    }
  };

  const { startRecording, stopRecording, isRecording, isVadReady, isSpeechDetected } =
    useVADAudioRecorder({
      onRecordingComplete: handleAudioReady,
      onError: (error) => {
        setStatusMessage(`Error: ${error.message}`);
        console.error('Recording error:', error);
      },
      silenceDurationMs,
      onSpeechStart: () => {
        setStatusMessage('🎤 Speech detected...');
      },
      onSpeechEnd: () => {
        setStatusMessage('🔇 Speech ended, waiting for silence...');
      },
    });

  return (
    <div className="flex flex-col gap-4 p-6 bg-white rounded-lg shadow-md max-w-md">
      <h2 className="text-2xl font-bold text-gray-800">Voice Recorder</h2>
      
      {/* Status Indicator */}
      <div className="flex items-center gap-2">
        <div className={`w-3 h-3 rounded-full ${
          !isVadReady ? 'bg-gray-400' :
          isRecording && isSpeechDetected ? 'bg-green-500 animate-pulse' :
          isRecording ? 'bg-yellow-500 animate-pulse' :
          'bg-gray-400'
        }`} />
        <span className="text-sm text-gray-600">
          {!isVadReady ? 'Initializing...' :
           isRecording && isSpeechDetected ? 'Speaking' :
           isRecording ? 'Listening' :
           'Ready'}
        </span>
      </div>

      {/* Control Buttons */}
      <div className="flex gap-2">
        <button
          onClick={startRecording}
          disabled={isRecording || !isVadReady || isLoading}
          className={`flex-1 px-4 py-3 rounded-lg font-medium transition-colors ${
            isRecording || !isVadReady || isLoading
              ? 'bg-gray-300 text-gray-500 cursor-not-allowed'
              : 'bg-blue-500 text-white hover:bg-blue-600 active:bg-blue-700'
          }`}
        >
          {!isVadReady
            ? 'Initializing VAD...'
            : isRecording
              ? '🎙️ Recording...'
              : '🎤 Start Recording'}
        </button>

        <button
          onClick={stopRecording}
          disabled={!isRecording}
          className={`flex-1 px-4 py-3 rounded-lg font-medium transition-colors ${
            !isRecording
              ? 'bg-gray-300 text-gray-500 cursor-not-allowed'
              : 'bg-red-500 text-white hover:bg-red-600 active:bg-red-700'
          }`}
        >
          ⏹️ Stop
        </button>
      </div>

      {/* Status Message */}
      {statusMessage && (
        <div className={`p-3 rounded-lg text-sm ${
          statusMessage.includes('Error') 
            ? 'bg-red-50 text-red-700' 
            : statusMessage.includes('Success')
            ? 'bg-green-50 text-green-700'
            : 'bg-blue-50 text-blue-700'
        }`}>
          {statusMessage}
        </div>
      )}

      {/* Transcription Display */}
      {transcription && (
        <div className="p-4 bg-gray-50 rounded-lg">
          <h3 className="text-sm font-semibold text-gray-700 mb-2">Transcription:</h3>
          <p className="text-gray-800">{transcription}</p>
        </div>
      )}

      {/* Info Text */}
      <p className="text-xs text-gray-500">
        Recording will automatically stop after {silenceDurationMs / 1000} seconds of silence.
      </p>
    </div>
  );
}
