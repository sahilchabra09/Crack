'use client';

import { AudioRecorderComponent } from '@/components/AudioRecorderComponent';

export default function AudioPage() {
  const handleTranscription = (text: string) => {
    console.log('Transcription received:', text);
    // You can handle the transcription here
  };

  return (
    <main className="min-h-screen bg-linear-to-br from-gray-50 to-gray-100 p-8">
      <div className="max-w-4xl mx-auto">
        <div className="text-center mb-8">
          <h1 className="text-4xl font-bold text-gray-900 mb-2">
            Voice Activity Detection
          </h1>
          <p className="text-gray-600">
            Record audio with automatic silence detection
          </p>
        </div>

        <div className="flex justify-center">
          <AudioRecorderComponent 
            onTranscription={handleTranscription}
            silenceDurationMs={2000}
          />
        </div>

        <div className="mt-12 bg-white rounded-lg shadow-md p-6">
          <h2 className="text-xl font-semibold text-gray-800 mb-4">
            How it works:
          </h2>
          <ul className="space-y-2 text-gray-600">
            <li className="flex items-start gap-2">
              <span className="text-blue-500 mt-1">1.</span>
              <span>Click "Start Recording" to begin listening</span>
            </li>
            <li className="flex items-start gap-2">
              <span className="text-blue-500 mt-1">2.</span>
              <span>The system detects when you start speaking</span>
            </li>
            <li className="flex items-start gap-2">
              <span className="text-blue-500 mt-1">3.</span>
              <span>Recording continues while you speak</span>
            </li>
            <li className="flex items-start gap-2">
              <span className="text-blue-500 mt-1">4.</span>
              <span>Automatically stops after 2 seconds of silence</span>
            </li>
            <li className="flex items-start gap-2">
              <span className="text-blue-500 mt-1">5.</span>
              <span>Audio is sent to the backend for processing</span>
            </li>
          </ul>
        </div>
      </div>
    </main>
  );
}
