import {AbsoluteFill, Audio, Sequence, staticFile} from "remotion";
import {Scene01Problem} from "./scenes/Scene01Problem";
import {Scene02BrandPremise} from "./scenes/Scene02BrandPremise";
import {Scene03Goal} from "./scenes/Scene03Goal";
import {Scene04StateSkills} from "./scenes/Scene04StateSkills";
import {Scene05LearningExperience} from "./scenes/Scene05LearningExperience";
import {Scene06AdaptationHero} from "./scenes/Scene06AdaptationHero";
import {Scene07Philosophy} from "./scenes/Scene07Philosophy";
import {Scene08BrandClose} from "./scenes/Scene08BrandClose";
import {SCENES} from "./constants";
import {FILM_THEME as T} from "./theme";

const timeline = [
  [SCENES.problem, Scene01Problem],
  [SCENES.premise, Scene02BrandPremise],
  [SCENES.goal, Scene03Goal],
  [SCENES.stateSkills, Scene04StateSkills],
  [SCENES.experience, Scene05LearningExperience],
  [SCENES.adaptation, Scene06AdaptationHero],
  [SCENES.philosophy, Scene07Philosophy],
  [SCENES.close, Scene08BrandClose],
] as const;

export const LingxiLearnFilm: React.FC = () => (
  <AbsoluteFill style={{backgroundColor: T.paper, color: T.ink}}>
    <Audio src={staticFile("audio/film60/master-score.wav")} volume={0.92} />
    {timeline.map(([scene, Component], index) => (
      <Sequence key={index} from={scene.from} durationInFrames={scene.duration} premountFor={30}>
        <Component />
      </Sequence>
    ))}
  </AbsoluteFill>
);
