import "./index.css";
import {Composition} from "remotion";
import {PitchVideoComposition} from "./Composition";
import {LingxiLearnFilm} from "./compositions/LingxiLearnFilm/LingxiLearnFilm";
import {FILM_DURATION, FILM_FPS} from "./compositions/LingxiLearnFilm/constants";
import {LingxiLearnHybridFilm} from "./compositions/LingxiLearnHybridFilm/LingxiLearnHybridFilm";

export const RemotionRoot: React.FC = () => (
  <>
    <PitchVideoComposition />
    <Composition id="LingxiLearnSaaSFilm" component={LingxiLearnFilm} durationInFrames={FILM_DURATION} fps={FILM_FPS} width={1920} height={1080} />
    <Composition
      id="LingxiLearnHybrid3D"
      component={LingxiLearnHybridFilm}
      durationInFrames={1800}
      fps={30}
      width={1920}
      height={1080}
    />
  </>
);
