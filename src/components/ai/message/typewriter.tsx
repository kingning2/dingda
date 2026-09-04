import type { ReactNode } from "react";
import { useEffect, useRef, useState } from "react";
import { motion, useReducedMotion } from "motion/react";

const DEFAULT_CHAR_MS = 28;

interface UseTypewriterTextOptions {
  active: boolean;
  charMs?: number;
}

export function useTypewriterText(text: string, { active, charMs = DEFAULT_CHAR_MS }: UseTypewriterTextOptions) {
  const [visible, setVisible] = useState(active ? "" : text);
  const indexRef = useRef(active ? 0 : text.length);
  const textRef = useRef(text);

  useEffect(() => {
    textRef.current = text;

    if (!active) {
      indexRef.current = text.length;
      setVisible(text);
      return;
    }

    if (indexRef.current > text.length) {
      indexRef.current = 0;
      setVisible("");
    }

    let frame = 0;
    let lastTick = performance.now();

    const step = (now: number) => {
      const currentText = textRef.current;
      if (indexRef.current >= currentText.length) {
        setVisible(currentText);
        return;
      }

      if (now - lastTick >= charMs) {
        indexRef.current = Math.min(indexRef.current + 1, currentText.length);
        setVisible(currentText.slice(0, indexRef.current));
        lastTick = now;
      }

      frame = requestAnimationFrame(step);
    };

    frame = requestAnimationFrame(step);
    return () => cancelAnimationFrame(frame);
  }, [text, active, charMs]);

  const typing = active && visible.length < text.length;

  return { visible, typing };
}

export function TypewriterCursor() {
  return (
    <motion.span
      aria-hidden
      className="ml-0.5 inline-block font-normal text-foreground/60"
      animate={{ opacity: [1, 0.2, 1] }}
      transition={{ duration: 0.75, repeat: Infinity, ease: "easeInOut" }}
    >
      |
    </motion.span>
  );
}

interface TypewriterMarkdownProps {
  text: string;
  active: boolean;
  busy?: boolean;
  onComplete?: () => void;
  render: (visibleText: string) => ReactNode;
}

export function TypewriterMarkdown({
  text,
  active,
  busy = false,
  onComplete,
  render,
}: TypewriterMarkdownProps) {
  const reduceMotion = useReducedMotion();
  const shouldAnimate = active && !reduceMotion;
  const { visible, typing } = useTypewriterText(text, { active: shouldAnimate });

  useEffect(() => {
    if (!shouldAnimate) {
      if (active && !busy) onComplete?.();
      return;
    }
    if (!typing && !busy) {
      onComplete?.();
    }
  }, [typing, busy, shouldAnimate, active, onComplete]);

  if (!text) return null;

  return (
    <>
      {render(shouldAnimate ? visible : text)}
      {typing ? <TypewriterCursor /> : null}
    </>
  );
}
