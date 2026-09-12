import type { Transition, Variants } from "motion/react";

/**
 * 页面切换的动效参数。
 *
 * 原先在 apps/web/src/routes/route-transition.ts。它是 AnimatedOutlet 的私有参数集，
 * 而 AnimatedOutlet 属于外壳的内容区渲染 —— 放在应用里会逼着 @v2/ui-layout
 * 反向 import 应用源码（包依赖应用，方向是反的）。整体挪进外壳包，方向才顺。
 */

export const routeEase = [0, 0, 0.2, 1] as const;

export const routeTransition: Transition = {
  duration: 0.22,
  ease: routeEase,
};

export const routePageVariants: Variants = {
  initial: {
    opacity: 0,
    y: 10,
  },
  animate: {
    opacity: 1,
    y: 0,
    transition: routeTransition,
  },
  exit: {
    opacity: 0,
    y: -6,
    transition: {
      ...routeTransition,
      duration: 0.16,
    },
  },
};

export const routePageVariantsReduced: Variants = {
  initial: { opacity: 1 },
  animate: { opacity: 1 },
  exit: { opacity: 1 },
};
