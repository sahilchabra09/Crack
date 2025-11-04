import { NextRequest, NextResponse } from 'next/server';
import { writeFile } from 'fs/promises';
import path from 'path';
import { existsSync, mkdirSync } from 'fs';

export async function POST(request: NextRequest) {
  try {
    // Get form data from request
    const formData = await request.formData();
    const audioBlob = formData.get('audio') as Blob | null;

    if (!audioBlob) {
      return NextResponse.json(
        { error: 'No audio file provided' },
        { status: 400 }
      );
    }

    // Convert blob to buffer
    const bytes = await audioBlob.arrayBuffer();
    const buffer = Buffer.from(bytes);

    // Create uploads directory if it doesn't exist
    const uploadsDir = path.join(process.cwd(), 'recordings');
    if (!existsSync(uploadsDir)) {
      mkdirSync(uploadsDir, { recursive: true });
    }

    // Save to file
    const timestamp = Date.now();
    const filePath = path.join(uploadsDir, `audio-${timestamp}.webm`);
    await writeFile(filePath, buffer);

    console.log(`✅ Audio saved: ${filePath} (${buffer.length} bytes)`);

    // TODO: Add your audio processing logic here
    // Examples:
    // - Send to OpenAI Whisper for transcription
    // - Send to your Python backend
    // - Process with other speech-to-text services

    // Example response
    return NextResponse.json({
      message: 'Audio processed successfully',
      audioPath: filePath,
      size: buffer.length,
      timestamp,
      // transcript: 'Add transcription here',
    });
  } catch (error) {
    console.error('Audio processing error:', error);
    return NextResponse.json(
      {
        error:
          error instanceof Error
            ? error.message
            : 'Audio processing failed',
      },
      { status: 500 }
    );
  }
}

// Optional: Add GET method to check if the endpoint is working
export async function GET() {
  return NextResponse.json({
    status: 'ready',
    message: 'Audio processing endpoint is ready',
  });
}
