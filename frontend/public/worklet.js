/**
 * VoiceShield AudioWorklet Processor
 * Buffers microphone audio, performs hardware sample rate normalization to 16kHz,
 * converts to 16-bit PCM, and posts 500ms chunks (8000 samples @ 16kHz).
 */
class MicProcessor extends AudioWorkletProcessor {
  constructor() {
    super();
    this.targetSR = 16000;
    this.targetSamples = 8000; // 500ms at 16kHz
    this.accumulatedSamples = [];
  }

  process(inputs, outputs, parameters) {
    const input = inputs && inputs[0];
    if (input && input.length > 0) {
      const channelData = input[0];
      for (let i = 0; i < channelData.length; i++) {
        this.accumulatedSamples.push(channelData[i]);
      }

      // AudioWorkletGlobalScope provides global `sampleRate` of the AudioContext
      const currentSR = typeof sampleRate !== 'undefined' ? sampleRate : 16000;
      const ratio = currentSR / this.targetSR;
      const neededInputSamples = Math.floor(this.targetSamples * ratio);

      while (this.accumulatedSamples.length >= neededInputSamples) {
        const int16Buffer = new Int16Array(this.targetSamples);
        
        for (let j = 0; j < this.targetSamples; j++) {
          const srcIdx = j * ratio;
          const idx = Math.floor(srcIdx);
          const frac = srcIdx - idx;
          const s0 = this.accumulatedSamples[idx] || 0;
          const s1 = (idx + 1 < this.accumulatedSamples.length) ? this.accumulatedSamples[idx + 1] : s0;
          const interp = s0 + frac * (s1 - s0);
          
          const clamped = Math.max(-1.0, Math.min(1.0, interp));
          int16Buffer[j] = clamped < 0 ? clamped * 0x8000 : clamped * 0x7FFF;
        }

        this.accumulatedSamples.splice(0, neededInputSamples);
        this.port.postMessage(int16Buffer.buffer, [int16Buffer.buffer]);
      }
    }
    return true; // Keep processor alive
  }
}

registerProcessor('mic-processor', MicProcessor);
