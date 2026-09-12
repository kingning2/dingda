import type { Transition, Variants } from "motion/react";

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
