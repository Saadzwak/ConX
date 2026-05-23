/**
 * useCountUp — animation count-up sur les chiffres clés (CHANTIER 6 du
 * brief 2026-05-23). Implémentation simple via requestAnimationFrame, pas
 * de lib externe. Easing easeOutQuart pour un sentiment "punchy" sans
 * rebond.
 *
 * Usage :
 *   const animated = useCountUp(96, { duration: 700 });
 *   return <span>{animated.toFixed(0)}</span>;
 *
 * Respecte `prefers-reduced-motion` : si l'utilisateur a désactivé les
 * animations, on retourne directement la valeur cible.
 */
import { useEffect, useRef, useState } from "react";

interface Options {
  duration?: number; // ms, défaut 700
  startAt?: number; // valeur de départ, défaut 0
}

const easeOutQuart = (t: number): number => 1 - Math.pow(1 - t, 4);

export function useCountUp(target: number, opts: Options = {}): number {
  const { duration = 700, startAt = 0 } = opts;
  const [value, setValue] = useState<number>(startAt);
  const rafRef = useRef<number | null>(null);
  const startTimeRef = useRef<number | null>(null);
  const startValueRef = useRef<number>(startAt);

  useEffect(() => {
    if (typeof window === "undefined") return;

    // Reduced motion : skip l'animation
    const prefersReduced =
      window.matchMedia?.("(prefers-reduced-motion: reduce)").matches ?? false;
    if (prefersReduced) {
      setValue(target);
      return;
    }

    if (target === value) return;

    // Démarre depuis la valeur courante affichée (interrompt anim. précédente
    // proprement si target change en cours de route).
    startValueRef.current = value;
    startTimeRef.current = null;

    const step = (now: number) => {
      if (startTimeRef.current === null) startTimeRef.current = now;
      const elapsed = now - startTimeRef.current;
      const t = Math.min(1, elapsed / duration);
      const eased = easeOutQuart(t);
      const next = startValueRef.current + (target - startValueRef.current) * eased;
      setValue(next);
      if (t < 1) {
        rafRef.current = requestAnimationFrame(step);
      } else {
        setValue(target);
      }
    };

    rafRef.current = requestAnimationFrame(step);
    return () => {
      if (rafRef.current !== null) cancelAnimationFrame(rafRef.current);
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [target, duration]);

  return value;
}
