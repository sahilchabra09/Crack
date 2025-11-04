import { MicVAD } from '@ricky0123/vad-web';

interface VadWorkerState {
  vad: MicVAD | null;
  sampleRate: number;
}

const state: VadWorkerState = {
  vad: null,
  sampleRate: 16000,
};

self.onmessage = async (event: MessageEvent) => {
  const { type, data } = event.data;

  switch (type) {
    case 'init': {
      try {
        state.sampleRate = data?.sampleRate || 16000;
        
        // Initialize VAD with MicVAD for real-time processing
        state.vad = await MicVAD.new({
          modelURL: '/vad/silero_vad.onnx',
          workletURL: '/vad/vad.worklet.bundle.min.js',
          onSpeechStart: () => {
            self.postMessage({ type: 'speechStart' });
          },
          onSpeechEnd: () => {
            self.postMessage({ type: 'speechEnd' });
          },
          onVADMisfire: () => {
            self.postMessage({ type: 'vadMisfire' });
          },
        });
        
        self.postMessage({ type: 'initComplete' });
      } catch (error) {
        self.postMessage({
          type: 'error',
          error: error instanceof Error ? error.message : 'VAD init failed',
        });
      }
      break;
    }

    case 'start': {
      try {
        if (!state.vad) {
          throw new Error('VAD not initialized');
        }
        await state.vad.start();
        self.postMessage({ type: 'started' });
      } catch (error) {
        self.postMessage({
          type: 'error',
          error: error instanceof Error ? error.message : 'Start failed',
        });
      }
      break;
    }

    case 'pause': {
      try {
        if (!state.vad) {
          throw new Error('VAD not initialized');
        }
        state.vad.pause();
        self.postMessage({ type: 'paused' });
      } catch (error) {
        self.postMessage({
          type: 'error',
          error: error instanceof Error ? error.message : 'Pause failed',
        });
      }
      break;
    }

    case 'terminate': {
      try {
        if (state.vad) {
          state.vad.destroy();
          state.vad = null;
        }
        self.postMessage({ type: 'terminated' });
      } catch (error) {
        self.postMessage({
          type: 'error',
          error: error instanceof Error ? error.message : 'Terminate failed',
        });
      }
      break;
    }
  }
};

export {};
