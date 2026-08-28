import {Easing, interpolate} from "remotion";

export const clamp = {extrapolateLeft: "clamp", extrapolateRight: "clamp"} as const;

export const progress = (frame: number, from: number, to: number) =>
  interpolate(frame, [from, to], [0, 1], {...clamp, easing: Easing.out(Easing.cubic)});

export const enter = (frame: number, from = 0, duration = 24) => progress(frame, from, from + duration);

export const exit = (frame: number, from: number, duration = 20) =>
  interpolate(frame, [from, from + duration], [1, 0], {...clamp, easing: Easing.inOut(Easing.cubic)});

export const mix = (a: number, b: number, p: number) => a + (b - a) * p;
