import { useState, useRef, useCallback } from 'react';

export function useMicStream(onAudioChunk: (chunk: ArrayBuffer) => void) {
  const [isRecording, setIsRecording] = useState(false);
  const [error, setError] = useState<string | null>(null);
  
  const audioContextRef = useRef<AudioContext | null>(null);
  const streamRef = useRef<MediaStream | null>(null);
  const sourceNodeRef = useRef<MediaStreamAudioSourceNode | null>(null);
  const workletNodeRef = useRef<AudioWorkletNode | null>(null);

  const startMic = useCallback(async () => {
    try {
      const stream = await navigator.mediaDevices.getUserMedia({ 
        audio: {
          channelCount: 1,
          sampleRate: 16000,
          echoCancellation: true,
          noiseSuppression: true
        } 
      });
      streamRef.current = stream;

      const audioContext = new AudioContext({ sampleRate: 16000 });
      audioContextRef.current = audioContext;

      if (audioContext.state === 'suspended') {
        await audioContext.resume();
      }

      await audioContext.audioWorklet.addModule('/worklet.js');

      const sourceNode = audioContext.createMediaStreamSource(stream);
      sourceNodeRef.current = sourceNode;

      const workletNode = new AudioWorkletNode(audioContext, 'mic-processor');
      workletNodeRef.current = workletNode;

      workletNode.port.onmessage = (event) => {
        onAudioChunk(event.data);
      };

      sourceNode.connect(workletNode);
      // Note: We do NOT connect workletNode to audioContext.destination to avoid feedback
      
      setIsRecording(true);
      setError(null);
    } catch (err) {
      console.error('Failed to start microphone', err);
      const msg = 'Microphone access denied or unavailable.';
      setError(msg);
      throw new Error(msg);
    }
  }, [onAudioChunk]);

  const stopMic = useCallback(() => {
    try {
      if (workletNodeRef.current) {
        workletNodeRef.current.disconnect();
        workletNodeRef.current = null;
      }
      if (sourceNodeRef.current) {
        sourceNodeRef.current.disconnect();
        sourceNodeRef.current = null;
      }
      if (audioContextRef.current) {
        if (audioContextRef.current.state !== 'closed') {
          audioContextRef.current.close().catch(() => {});
        }
        audioContextRef.current = null;
      }
    } catch {
      /* ignore */
    } finally {
      if (streamRef.current) {
        streamRef.current.getTracks().forEach(track => track.stop());
        streamRef.current = null;
      }
      setIsRecording(false);
    }
  }, []);

  return { isRecording, error, startMic, stopMic };
}
