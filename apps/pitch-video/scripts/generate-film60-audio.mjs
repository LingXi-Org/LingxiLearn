import fs from "node:fs";
import path from "node:path";
import {fileURLToPath} from "node:url";

const sampleRate = 48000;
const duration = 60;
const channels = 2;
const frames = sampleRate * duration;
const dataBytes = frames * channels * 2;
const buffer = Buffer.alloc(44 + dataBytes);

buffer.write("RIFF", 0);
buffer.writeUInt32LE(36 + dataBytes, 4);
buffer.write("WAVE", 8);
buffer.write("fmt ", 12);
buffer.writeUInt32LE(16, 16);
buffer.writeUInt16LE(1, 20);
buffer.writeUInt16LE(channels, 22);
buffer.writeUInt32LE(sampleRate, 24);
buffer.writeUInt32LE(sampleRate * channels * 2, 28);
buffer.writeUInt16LE(channels * 2, 32);
buffer.writeUInt16LE(16, 34);
buffer.write("data", 36);
buffer.writeUInt32LE(dataBytes, 40);

const TAU = Math.PI * 2;
const bpm = 100;
const beatLength = 60 / bpm;
const boundaries = [0, 5, 10, 17, 28, 39, 50, 56, 60];
const chords = [
  [55, 82.41, 110, 164.81],
  [58.27, 87.31, 116.54, 174.61],
  [65.41, 98, 130.81, 196],
  [49, 73.42, 98, 146.83],
  [55, 82.41, 110, 164.81],
  [58.27, 87.31, 116.54, 174.61],
  [49, 73.42, 98, 146.83],
  [55, 82.41, 110, 164.81],
];
const intensity = [.32, .43, .56, .72, .88, 1, .75, .64];
const cues = [
  {time: 5, freq: 440}, {time: 10, freq: 523.25}, {time: 17, freq: 659.25},
  {time: 28, freq: 783.99}, {time: 39, freq: 392}, {time: 43, freq: 523.25},
  {time: 46, freq: 659.25}, {time: 50, freq: 783.99}, {time: 56, freq: 880},
];

const clamp01 = (value) => Math.max(0, Math.min(1, value));
const smooth = (value) => {
  const x = clamp01(value);
  return x * x * (3 - 2 * x);
};
const sceneEnvelope = (t, start, end) => smooth((t - start + .35) / 1.05) * smooth((end - t + .35) / 1.2);
const decay = (phase, speed) => Math.exp(-phase * speed);
const noise = (index) => {
  const value = Math.sin(index * 12.9898 + 78.233) * 43758.5453;
  return (value - Math.floor(value)) * 2 - 1;
};

let peak = 0;
let sumSquares = 0;

for (let frame = 0; frame < frames; frame++) {
  const t = frame / sampleRate;
  const beat = t / beatLength;
  const beatIndex = Math.floor(beat);
  const beatPhase = beat - beatIndex;
  const halfBeat = beat * 2;
  const halfPhase = halfBeat - Math.floor(halfBeat);
  let left = 0;
  let right = 0;

  let scene = boundaries.length - 2;
  for (let i = 0; i < boundaries.length - 1; i++) {
    if (t < boundaries[i + 1]) {
      scene = i;
      break;
    }
  }
  const energy = intensity[scene];
  const chord = chords[scene];

  // Wide harmonic bed: continuous through the full film.
  for (let layer = 0; layer < chords.length; layer++) {
    const envelope = sceneEnvelope(t, boundaries[layer], boundaries[layer + 1]);
    if (envelope <= 0) continue;
    chords[layer].forEach((frequency, note) => {
      const gain = .027 * envelope / (1 + note * .3);
      const phase = layer * .71 + note * 1.17;
      left += Math.sin(TAU * frequency * t + phase) * gain;
      right += Math.sin(TAU * frequency * t + phase + .2) * gain;
      left += Math.sin(TAU * frequency * 2.003 * t + phase) * gain * .14;
      right += Math.sin(TAU * frequency * 1.997 * t + phase) * gain * .14;
    });
  }

  // Tonal bass gives every section a clear musical foundation.
  const bassFrequency = chord[0] / 2;
  const bassEnvelope = .44 + decay(beatPhase, 4.2) * .56;
  const bass = (Math.sin(TAU * bassFrequency * t) + Math.sin(TAU * bassFrequency * 2 * t) * .16) * .075 * energy * bassEnvelope;
  left += bass;
  right += bass;

  // Eighth-note glass arpeggio; opens up as the product story develops.
  if (t >= 7.5 && t < 56.8) {
    const step = Math.floor(halfBeat);
    const note = chord[[0, 2, 1, 3, 2, 1, 3, 1][step % 8]] * 4;
    const arpEnvelope = decay(halfPhase, 7.5);
    const arp = (Math.sin(TAU * note * t) + Math.sin(TAU * note * 2.01 * t) * .22) * arpEnvelope * .032 * energy;
    const pan = Math.sin(step * 1.7) * .22;
    left += arp * (1 - pan);
    right += arp * (1 + pan);
  }

  // Restrained corporate pulse, kick, clap and hi-hat form a complete rhythm bed.
  const kick = Math.sin(TAU * (48 - beatPhase * 17) * t) * decay(beatPhase, 13) * .09 * energy;
  left += kick;
  right += kick;

  if (t >= 14) {
    const backbeatPhase = (beat + 1) % 2;
    if (backbeatPhase < 1) {
      const clap = noise(frame) * decay(backbeatPhase, 18) * .027 * energy;
      left += clap;
      right += clap * .9;
    }
    const hat = noise(frame + 931) * decay(halfPhase, 27) * .012 * energy;
    left += hat;
    right += hat * .82;
  }

  // Scene-change risers connect the visual chapters instead of leaving silent gaps.
  for (const boundary of boundaries.slice(1, -1)) {
    const dt = boundary - t;
    if (dt > 0 && dt < .72) {
      const rise = smooth(1 - dt / .72);
      const sweepFrequency = 260 + rise * 720;
      const sweep = (Math.sin(TAU * sweepFrequency * t) * .018 + noise(frame + Math.round(boundary * 10)) * .009) * rise;
      left += sweep;
      right -= sweep * .55;
    }
  }

  // UI/semantic transition accents.
  for (const cue of cues) {
    const dt = t - cue.time;
    if (dt >= 0 && dt < 1.35) {
      const envelope = Math.exp(-dt * 4.4);
      const chime = (Math.sin(TAU * cue.freq * dt) + Math.sin(TAU * cue.freq * 1.5 * dt) * .35 + Math.sin(TAU * cue.freq * 2 * dt) * .12) * .085 * envelope;
      left += chime;
      right += chime * .9;
    }
  }

  // The final four seconds resolve into a clean, held brand chord.
  if (t >= 56) {
    const resolve = smooth((t - 56) / 1.2);
    const lead = Math.sin(TAU * 440 * t) * .025 + Math.sin(TAU * 659.25 * t) * .017;
    left += lead * resolve;
    right += lead * resolve * .92;
  }

  const masterEnvelope = smooth(t / 1.15) * smooth((duration - t) / 2.4);
  // Soft saturation preserves detail while preventing transient clipping.
  const l = Math.tanh(left * 1.42) * masterEnvelope * .88;
  const r = Math.tanh(right * 1.42) * masterEnvelope * .88;
  peak = Math.max(peak, Math.abs(l), Math.abs(r));
  sumSquares += l * l + r * r;
  const offset = 44 + frame * 4;
  buffer.writeInt16LE(Math.round(l * 32767), offset);
  buffer.writeInt16LE(Math.round(r * 32767), offset + 2);
}

const here = path.dirname(fileURLToPath(import.meta.url));
const directory = path.resolve(here, "../public/audio/film60");
fs.mkdirSync(directory, {recursive: true});
const output = path.join(directory, "master-score.wav");
fs.writeFileSync(output, buffer);
const rms = Math.sqrt(sumSquares / (frames * channels));
console.log(`${output}\npeak=${peak.toFixed(4)} rms=${rms.toFixed(4)} duration=${duration}s`);
