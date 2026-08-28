import type {ReactNode} from "react";
import {AbsoluteFill, Easing, interpolate, useCurrentFrame} from "remotion";

const clamp = {extrapolateLeft: "clamp", extrapolateRight: "clamp"} as const;

export const TRANSITION_FRAMES = 18;

export const SceneTransition: React.FC<{
  children: ReactNode;
  reveal?: "paper" | "dark" | "none";
}> = ({children, reveal = "paper"}) => {
  const frame = useCurrentFrame();
  if (reveal === "none") return <AbsoluteFill>{children}</AbsoluteFill>;

  const eased = interpolate(frame, [0, TRANSITION_FRAMES], [0, 1], {
    ...clamp,
    easing: Easing.bezier(.22, 1, .36, 1),
  });
  const veilColor = reveal === "dark" ? "#07090C" : "#F5F5F1";

  return (
    <AbsoluteFill
      style={{
        overflow: "hidden",
        backgroundColor: veilColor,
        clipPath: `inset(${(1 - eased) * 5.5}% 0 0 0 round ${Math.round((1 - eased) * 34)}px)`,
        opacity: interpolate(eased, [0, .24, 1], [.72, .97, 1], clamp),
        transform: `translateY(${(1 - eased) * 34}px) scale(${.992 + eased * .008})`,
        filter: `blur(${(1 - eased) * 7}px)`,
        willChange: "clip-path, transform, filter, opacity",
      }}
    >
      {children}
      <AbsoluteFill
        style={{
          pointerEvents: "none",
          background: reveal === "dark"
            ? "linear-gradient(180deg,rgba(255,255,255,.05),transparent 18%)"
            : "linear-gradient(180deg,rgba(255,255,255,.9),rgba(255,255,255,0) 16%)",
          opacity: 1 - eased,
        }}
      />
    </AbsoluteFill>
  );
};
