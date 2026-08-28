import fs from "node:fs";
import path from "node:path";
import {fileURLToPath} from "node:url";

const sampleRate = 48000;
const duration = 90;
const channels = 2;
const frames = sampleRate * duration;
const bytesPerSample = 2;
const dataBytes = frames * channels * bytesPerSample;
const buffer = Buffer.alloc(44 + dataBytes);

buffer.write("RIFF", 0);
buffer.writeUInt32LE(36 + dataBytes, 4);
buffer.write("WAVE", 8);
buffer.write("fmt ", 12);
buffer.writeUInt32LE(16, 16);
buffer.writeUInt16LE(1, 20);
buffer.writeUInt16LE(channels, 22);
buffer.writeUInt32LE(sampleRate, 24);
buffer.writeUInt32LE(sampleRate * channels * bytesPerSample, 28);
buffer.writeUInt16LE(channels * bytesPerSample, 32);
buffer.writeUInt16LE(16, 34);
buffer.write("data", 36);
buffer.writeUInt32LE(dataBytes, 40);

const boundaries = [0, 8, 18, 30, 42, 55, 66, 79, 90];
const chords = [
  [55, 82.41, 110, 146.83],
  [58.27, 87.31, 116.54, 146.83],
  [43.65, 65.41, 98, 130.81],
  [49, 73.42, 98, 123.47],
  [55, 82.41, 110, 164.81],
  [58.27, 87.31, 116.54, 174.61],
  [43.65, 65.41, 98, 146.83],
  [55, 82.41, 110, 146.83],
];

const smoothstep = (x) => {
  const n = Math.max(0, Math.min(1, x));
  return n * n * (3 - 2 * n);
};

const padEnvelope = (t, start, end) => smoothstep((t - start) / 1.2) * smoothstep((end - t) / 1.5);

for (let frame = 0; frame < frames; frame++) {
  const t = frame / sampleRate;
  let left = 0;
  let right = 0;

  for (let scene = 0; scene < chords.length; scene++) {
    const env = padEnvelope(t, boundaries[scene] - 0.7, boundaries[scene + 1] + 0.7);
    if (env <= 0) continue;
    for (let note = 0; note < chords[scene].length; note++) {
      const frequency = chords[scene][note];
      const level = (0.022 / (1 + note * 0.24)) * env;
      const phase = scene * 0.71 + note * 1.37;
      left += Math.sin(Math.PI * 2 * frequency * t + phase) * level;
      left += Math.sin(Math.PI * 2 * frequency * 2.003 * t + phase * 0.7) * level * 0.16;
      right += Math.sin(Math.PI * 2 * frequency * t + phase + 0.12) * level;
      right += Math.sin(Math.PI * 2 * frequency * 1.997 * t + phase * 0.8) * level * 0.16;
    }
  }

  const beat = (t * 78) / 60;
  const beatPhase = beat - Math.floor(beat);
  const pulseEnv = Math.exp(-beatPhase * 10);
  const pulse = Math.sin(Math.PI * 2 * 48 * t) * pulseEnv * 0.022;
  const shimmer = Math.sin(Math.PI * 2 * (520 + Math.sin(t * 0.08) * 35) * t) * (0.0025 + 0.0015 * Math.sin(t * 0.19));
  left += pulse + shimmer;
  right += pulse + shimmer * 0.82;

  const masterIn = smoothstep(t / 2.2);
  const masterOut = smoothstep((duration - t) / 3.5);
  const master = masterIn * masterOut * 0.86;
  const l = Math.max(-1, Math.min(1, left * master));
  const r = Math.max(-1, Math.min(1, right * master));
  const offset = 44 + frame * 4;
  buffer.writeInt16LE(Math.round(l * 32767), offset);
  buffer.writeInt16LE(Math.round(r * 32767), offset + 2);
}

const here = path.dirname(fileURLToPath(import.meta.url));
const output = path.resolve(here, "../public/audio/formal/score.wav");
fs.writeFileSync(output, buffer);
console.log(output);
