import { AnimatePresence, motion, useReducedMotion } from "motion/react";
import { useLocation, useOutlet } from "react-router-dom";

import { cn } from "@v2/ui-primitives/utils";
import { routePageVariants, routePageVariantsReduced } from "./route-transition";

/**
 * 带切换动效的内容区出口。
 *
 * 用 useOutlet() 取当前子路由，在切换时做淡入位移。之所以归在外壳包而不是应用：
 * EntryShell 的内容区就是它渲染的，外壳必须自己认识这个出口；反过来让外壳去
 * import 应用里的实现，就成了「包依赖应用」。
 */
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
