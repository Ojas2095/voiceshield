const SAMPLE_RATE = 16000;
const CHUNK_DURATION_MS = 500;
const SAMPLES_PER_CHUNK = (SAMPLE_RATE * CHUNK_DURATION_MS) / 1000; // 8000

class MicProcessor extends AudioWorkletProcessor {
  constructor() {
    super();
    this.buffer = new Float32Array(SAMPLES_PER_CHUNK);
    this.bufferIndex = 0;
  }

  process(inputs, outputs, parameters) {
    const input = inputs && inputs[0];
    if (input && input.length > 0) {
      const channelData = input[0];
      for (let i = 0; i < channelData.length; i++) {
        this.buffer[this.bufferIndex] = channelData[i];
        this.bufferIndex++;

        if (this.bufferIndex >= SAMPLES_PER_CHUNK) {
          // We have a full 500ms chunk. Convert to Int16 and post.
          const int16Buffer = new Int16Array(SAMPLES_PER_CHUNK);
          for (let j = 0; j < SAMPLES_PER_CHUNK; j++) {
            // Clamp and convert to 16-bit PCM
            let s = Math.max(-1, Math.min(1, this.buffer[j]));
            int16Buffer[j] = s < 0 ? s * 0x8000 : s * 0x7FFF;
          }
          
          this.port.postMessage(int16Buffer.buffer, [int16Buffer.buffer]);
          this.bufferIndex = 0;
        }
      }
    }
    return true; // Keep processor alive
  }
}

registerProcessor('mic-processor', MicProcessor);
