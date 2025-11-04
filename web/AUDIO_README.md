# Voice Activity Detection (VAD) Audio Recorder

This implementation provides automatic voice recording with silence detection using the [@ricky0123/vad-web](https://github.com/ricky0123/vad) library.

## Features

- 🎤 **Real-time Voice Activity Detection**: Automatically detects when speech starts and ends
- 🔇 **Automatic Stop on Silence**: Recording stops after a configurable silence period (default: 2 seconds)
- 📊 **Visual Feedback**: Live indicators for recording status and speech detection
- 🚀 **Optimized Performance**: Uses AudioWorklet for efficient audio processing
- 📦 **Easy Integration**: Simple React hook API

## Files Structure

```
src/
├── lib/
│   └── hooks/
│       └── useVADAudioRecorder.ts   # Main VAD recording hook
├── components/
│   └── AudioRecorderComponent.tsx    # UI component
├── app/
│   ├── audio/
│   │   └── page.tsx                  # Demo page
│   └── api/
│       └── audio/
│           └── process/
│               └── route.ts          # API endpoint for audio processing
public/
└── vad/                              # VAD model files (auto-copied)
    ├── silero_vad_v5.onnx           # VAD ML model
    ├── vad.worklet.bundle.min.js    # Audio worklet
    └── *.wasm                        # ONNX runtime files
```

## Usage

### Basic Usage

```tsx
import { AudioRecorderComponent } from '@/components/AudioRecorderComponent';

export default function MyPage() {
  return (
    <AudioRecorderComponent 
      onTranscription={(text) => console.log(text)}
      silenceDurationMs={2000}
    />
  );
}
```

### Advanced: Using the Hook Directly

```tsx
import { useVADAudioRecorder } from '@/lib/hooks/useVADAudioRecorder';

function MyComponent() {
  const { startRecording, stopRecording, isRecording, isVadReady, isSpeechDetected } = 
    useVADAudioRecorder({
      onRecordingComplete: (audioBlob) => {
        // Handle the audio blob
        console.log('Recording complete:', audioBlob);
      },
      onError: (error) => {
        console.error('Recording error:', error);
      },
      silenceDurationMs: 2000,
      onSpeechStart: () => console.log('Speech started'),
      onSpeechEnd: () => console.log('Speech ended'),
    });

  return (
    <div>
      <button onClick={startRecording} disabled={!isVadReady}>
        Start
      </button>
      <button onClick={stopRecording} disabled={!isRecording}>
        Stop
      </button>
      {isSpeechDetected && <span>Speaking...</span>}
    </div>
  );
}
```

## How It Works

1. **Initialization**: VAD model loads on component mount
2. **Start Recording**: 
   - Gets microphone access
   - Starts MediaRecorder to capture audio
   - Starts VAD to monitor speech activity
3. **Speech Detection**:
   - VAD continuously analyzes audio in real-time
   - Triggers `onSpeechStart` when speech is detected
   - Triggers `onSpeechEnd` when speech stops
4. **Automatic Stop**:
   - When speech ends, starts a silence timer
   - If no new speech is detected within the timeout period, stops recording
   - Sends the audio blob to the backend
5. **Processing**: Backend receives audio and can:
   - Save to disk
   - Send to transcription service (Whisper, etc.)
   - Process for other purposes

## Configuration Options

### useVADAudioRecorder Hook

| Option | Type | Default | Description |
|--------|------|---------|-------------|
| `onRecordingComplete` | `(blob: Blob) => void` | - | Callback when recording finishes |
| `onError` | `(error: Error) => void` | - | Error handler |
| `silenceDurationMs` | `number` | 1500 | Silence duration before auto-stop (ms) |
| `onSpeechStart` | `() => void` | - | Called when speech starts |
| `onSpeechEnd` | `() => void` | - | Called when speech ends |

### AudioRecorderComponent

| Prop | Type | Default | Description |
|------|------|---------|-------------|
| `onTranscription` | `(text: string) => void` | - | Callback for transcription result |
| `silenceDurationMs` | `number` | 2000 | Silence duration before auto-stop (ms) |

## Backend Integration

### Next.js API Route (Included)

The built-in API route at `/api/audio/process` handles audio uploads and saves them to the `recordings/` directory.

### External Backend Integration

To send audio to your Python/Hono backend:

```typescript
const response = await fetch('http://localhost:8000/api/audio/process', {
  method: 'POST',
  body: formData,
});
```

### Python Backend Example

```python
from fastapi import FastAPI, File, UploadFile
import shutil

app = FastAPI()

@app.post("/api/audio/process")
async def process_audio(audio: UploadFile = File(...)):
    # Save file
    file_path = f"recordings/{audio.filename}"
    with open(file_path, "wb") as buffer:
        shutil.copyfileobj(audio.file, buffer)
    
    # Process audio (transcription, etc.)
    # transcript = transcribe_audio(file_path)
    
    return {
        "message": "Audio processed",
        "path": file_path,
        # "transcript": transcript
    }
```

## Audio Format

- **Format**: WebM with Opus codec (fallback to WebM)
- **Sample Rate**: 16 kHz (optimal for speech)
- **Bitrate**: 128 kbps
- **Channels**: Mono (1 channel)

## Browser Compatibility

- ✅ Chrome/Edge (Chromium-based): Full support
- ✅ Firefox: Full support
- ✅ Safari: Supported (may need WebM to MP4 conversion for processing)
- ❌ IE: Not supported

## Troubleshooting

### VAD Not Initializing

**Problem**: "VAD not ready yet" message persists

**Solutions**:
- Check browser console for errors
- Ensure `/vad/` files are accessible (check Network tab)
- Verify WASM files are present in `public/vad/`

### Microphone Access Denied

**Problem**: Cannot access microphone

**Solutions**:
- Check browser permissions
- Ensure HTTPS (required for production)
- Test on localhost first

### Recording Stops Immediately

**Problem**: Recording stops right after starting

**Solutions**:
- Increase `silenceDurationMs` to a higher value (e.g., 3000)
- Check if VAD is too sensitive (try speaking louder)
- Verify microphone is working properly

### Audio Not Uploading

**Problem**: Upload fails or times out

**Solutions**:
- Check backend URL is correct
- Verify CORS settings on backend
- Check file size limits
- Monitor network requests in DevTools

## Performance Tips

1. **Optimize VAD Settings**: Adjust sensitivity based on environment
2. **Limit Recording Length**: Set a maximum recording duration
3. **Compress Audio**: Use appropriate bitrate for your use case
4. **Cleanup Resources**: Always stop streams when component unmounts

## Integration with Speech-to-Text

### OpenAI Whisper Example

```typescript
import OpenAI from 'openai';

const openai = new OpenAI({ apiKey: process.env.OPENAI_API_KEY });

async function transcribeAudio(filePath: string) {
  const transcription = await openai.audio.transcriptions.create({
    file: fs.createReadStream(filePath),
    model: 'whisper-1',
    language: 'en',
  });
  
  return transcription.text;
}
```

## Demo

Visit `/audio` to see the recorder in action.

## Dependencies

- `@ricky0123/vad-web`: Voice Activity Detection
- `next`: Next.js framework
- `react`: React library

## License

This implementation follows the license of the VAD library (MIT).

## Credits

- VAD implementation by [@ricky0123](https://github.com/ricky0123/vad)
- Silero VAD model by Silero Team
