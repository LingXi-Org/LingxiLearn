import {Audio} from "@remotion/media";
import {AbsoluteFill, interpolate, Sequence, staticFile} from "remotion";
import {Scene01Problem} from "../LingxiLearnFilm/scenes/Scene01Problem";
import {Scene02BrandPremise} from "../LingxiLearnFilm/scenes/Scene02BrandPremise";
import {Scene03Goal} from "../LingxiLearnFilm/scenes/Scene03Goal";
import {Scene07Philosophy} from "../LingxiLearnFilm/scenes/Scene07Philosophy";
import {SCENES} from "../LingxiLearnFilm/constants";
import {Scene03SkiaBrand} from "./scenes/Scene03SkiaBrand";
import {Scene04StateSkills3D} from "./scenes/Scene04StateSkills3D";
import {Scene05PromptExperience} from "./scenes/Scene05PromptExperience";
import {Scene06PromptAdaptation} from "./scenes/Scene06PromptAdaptation";
import {SceneTransition, TRANSITION_FRAMES} from "./components/SceneTransition";

export const LingxiLearnHybridFilm: React.FC = () => (
  <AbsoluteFill style={{backgroundColor: "#07090C"}}>
    <Audio
      src={staticFile("audio/film60/bgm-clean.mp3")}
      volume={(frame) => interpolate(frame, [0, 18, 1710, 1799], [0, .52, .52, 0], {
        extrapolateLeft: "clamp",
        extrapolateRight: "clamp",
      })}
    />
    <Sequence name="01 · Problem" from={SCENES.problem.from} durationInFrames={SCENES.problem.duration + TRANSITION_FRAMES} premountFor={30}>
      <Scene01Problem />
    </Sequence>
    <Sequence name="02 · Brand Premise · outgoing hold" from={SCENES.premise.from} durationInFrames={SCENES.premise.duration + TRANSITION_FRAMES} premountFor={30}>
      <SceneTransition><Scene02BrandPremise /></SceneTransition>
    </Sequence>
    <Sequence name="03 · Goal · outgoing hold" from={SCENES.goal.from} durationInFrames={SCENES.goal.duration + TRANSITION_FRAMES} premountFor={30}>
      <SceneTransition><Scene03Goal /></SceneTransition>
    </Sequence>
    <Sequence name="04 · State × Skills · 3D · outgoing hold" from={SCENES.stateSkills.from} durationInFrames={SCENES.stateSkills.duration + TRANSITION_FRAMES} premountFor={30}>
      <SceneTransition><Scene04StateSkills3D /></SceneTransition>
    </Sequence>
    <Sequence name="05 · Learning Experience · Prompt UI · outgoing hold" from={SCENES.experience.from} durationInFrames={SCENES.experience.duration + TRANSITION_FRAMES} premountFor={30}>
      <SceneTransition><Scene05PromptExperience /></SceneTransition>
    </Sequence>
    <Sequence name="06 · Adaptation Hero · Prompt UI · outgoing hold" from={SCENES.adaptation.from} durationInFrames={SCENES.adaptation.duration + TRANSITION_FRAMES} premountFor={30}>
      <SceneTransition reveal="none"><Scene06PromptAdaptation /></SceneTransition>
    </Sequence>
    <Sequence name="07 · Philosophy · outgoing hold" from={SCENES.philosophy.from} durationInFrames={SCENES.philosophy.duration + TRANSITION_FRAMES} premountFor={30}>
      <SceneTransition reveal="dark"><Scene07Philosophy /></SceneTransition>
    </Sequence>
    <Sequence name="08 · Brand Close · Skia" from={SCENES.close.from} durationInFrames={SCENES.close.duration} premountFor={30}>
      <SceneTransition reveal="dark"><Scene03SkiaBrand /></SceneTransition>
    </Sequence>
  </AbsoluteFill>
);
