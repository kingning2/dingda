// 60s @ 30fps = 1800 帧的时间轴

export const FPS = 30;
export const DURATION_IN_FRAMES = 1800;

export const SCENES = {
  intro: 0, // 0–7s
  accounts: 210, // 7–17s
  messages: 510, // 17–27s
  ai: 810, // 27–39s
  orders: 1170, // 39–49s
  local: 1470, // 49–60s
} as const;

export const SCENE_DURATION = {
  intro: 210,
  accounts: 300,
  messages: 300,
  ai: 360,
  orders: 300,
  local: 330,
} as const;
