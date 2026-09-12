import { AnimatePresence, motion, useReducedMotion } from "motion/react";
import { useLocation, useOutlet } from "react-router-dom";

import { cn } from "@v2/ui-primitives/utils";
import { routePageVariants, routePageVariantsReduced } from "@/routes/route-transition";

interface AnimatedOutletProps {
  className?: string;
}

export function AnimatedOutlet({ className }: AnimatedOutletProps) {
  const element = useOutlet();
  const location = useLocation();
  const reduceMotion = useReducedMotion();
  const variants = reduceMotion ? routePageVariantsReduced : routePageVariants;

  return (
    <div className={cn(className)}>
      <AnimatePresence mode="wait">
        {element ? (
          <motion.div
            key={location.pathname}
            className="h-full min-h-0"
            variants={variants}
            initial="initial"
            animate="animate"
            exit="exit"
          >
            {element}
          </motion.div>
        ) : null}
      </AnimatePresence>
    </div>
  );
}
