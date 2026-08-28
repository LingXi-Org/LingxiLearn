export const FILM_FPS = 30;
export const FILM_DURATION = 1800;

export const SCENES = {
  problem: {from: 0, duration: 150},
  premise: {from: 150, duration: 150},
  goal: {from: 300, duration: 210},
  stateSkills: {from: 510, duration: 330},
  experience: {from: 840, duration: 330},
  adaptation: {from: 1170, duration: 330},
  philosophy: {from: 1500, duration: 180},
  close: {from: 1680, duration: 120},
} as const;

export const SKILLS = ["Explain", "Visualize", "Practice", "Assess"] as const;
export const STATES = ["Current knowledge", "Weak concepts", "Learning goal", "Previous evidence"] as const;
