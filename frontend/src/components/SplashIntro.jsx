import React, { useEffect, useState } from 'react';
import { motion, AnimatePresence } from 'framer-motion';

export default function SplashIntro({ onFinish, color = "#3b82f6" }) {
  const [phase, setPhase] = useState(0);

  useEffect(() => {
    // Phase 0: Initial blue dot (handled by initial state)
    // Phase 1: Morph to "o" (turns white, inner dot fades out)
    const p1 = setTimeout(() => setPhase(1), 800);
    
    // Phase 2: Expand "d" and "t" from sides
    const p2 = setTimeout(() => setPhase(2), 1400);
    
    // Phase 3: Pop in the final "."
    const p3 = setTimeout(() => setPhase(3), 2200);
    
    // Phase 4: Trigger exit transition
    const p4 = setTimeout(() => onFinish(), 3500);

    return () => {
      clearTimeout(p1);
      clearTimeout(p2);
      clearTimeout(p3);
      clearTimeout(p4);
    };
  }, [onFinish]);

  return (
    <motion.div
      initial={{ opacity: 1 }}
      exit={{ opacity: 0 }}
      transition={{ duration: 0.8, ease: "easeInOut" }}
      className="fixed inset-0 z-[9999] bg-black flex items-center justify-center overflow-hidden"
    >
      <div className="flex items-baseline font-sans text-white text-7xl md:text-9xl font-bold tracking-tighter">
        
        {/* Letter "d" sliding in from the left */}
        <AnimatePresence>
          {phase >= 2 && (
            <motion.span
              initial={{ width: 0, opacity: 0, filter: "blur(10px)" }}
              animate={{ width: "auto", opacity: 1, filter: "blur(0px)" }}
              transition={{ duration: 0.8, ease: [0.16, 1, 0.3, 1] }}
              className="overflow-hidden whitespace-nowrap inline-flex justify-end"
            >
              <motion.span
                initial={{ x: 20 }}
                animate={{ x: 0 }}
                transition={{ duration: 0.8, ease: [0.16, 1, 0.3, 1] }}
              >
                d
              </motion.span>
            </motion.span>
          )}
        </AnimatePresence>

        {/* The "o" morphing from a solid blue dot to a hollow white ring */}
        <motion.div
          className="inline-block rounded-full"
          initial={{
            width: "0.55em",
            height: "0.55em",
            backgroundColor: color,
            borderColor: color,
            borderStyle: "solid",
            borderWidth: "0em",
            boxShadow: `0 0 30px ${color}cc`
          }}
          animate={{
            // Framer Motion can't tween a hex color to the literal keyword
            // "transparent" (warns every splash play, i.e. every login) —
            // `${color}00` is the same hex channel with alpha 0, so it's a
            // real animatable color value and lands on the same fully
            // transparent visual result.
            backgroundColor: phase >= 1 ? `${color}00` : color,
            borderColor: phase >= 1 ? "#ffffff" : color,
            borderWidth: phase >= 1 ? "0.12em" : "0em",
            boxShadow: phase >= 1 ? "0 0 0px rgba(0,0,0,0)" : `0 0 30px ${color}cc`
          }}
          transition={{ duration: 0.5, ease: "easeInOut" }}
          style={{ margin: "0 0.05em" }}
        />

        {/* Letter "t" sliding in from the right */}
        <AnimatePresence>
          {phase >= 2 && (
            <motion.span
              initial={{ width: 0, opacity: 0, filter: "blur(10px)" }}
              animate={{ width: "auto", opacity: 1, filter: "blur(0px)" }}
              transition={{ duration: 0.8, ease: [0.16, 1, 0.3, 1] }}
              className="overflow-hidden whitespace-nowrap inline-flex justify-start"
            >
              <motion.span
                initial={{ x: -20 }}
                animate={{ x: 0 }}
                transition={{ duration: 0.8, ease: [0.16, 1, 0.3, 1] }}
              >
                t
              </motion.span>
            </motion.span>
          )}
        </AnimatePresence>

        {/* Final Period "." popping in */}
        <AnimatePresence>
          {phase >= 3 && (
            <motion.span
              initial={{ width: 0, opacity: 0 }}
              animate={{ width: "auto", opacity: 1 }}
              transition={{ duration: 0.3 }}
              className="overflow-hidden whitespace-nowrap inline-flex justify-start"
              style={{ color }}
            >
              <motion.span
                initial={{ scale: 0, opacity: 0 }}
                animate={{ scale: 1, opacity: 1 }}
                transition={{ duration: 0.4, type: "spring", stiffness: 200, damping: 10 }}
              >
                .
              </motion.span>
            </motion.span>
          )}
        </AnimatePresence>

      </div>
    </motion.div>
  );
}
