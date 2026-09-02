"use client";

import { RefObject, useEffect, useRef, useState } from "react";
import { usePathname } from "next/navigation";
import gsap from "gsap";
import { ScrollTrigger } from "gsap/ScrollTrigger";
import { useGSAP } from "@gsap/react";

gsap.registerPlugin(ScrollTrigger, useGSAP);

function MotionController({ scope }: { scope: RefObject<HTMLDivElement | null> }) {
  useGSAP(
    () => {
      if (window.matchMedia("(prefers-reduced-motion: reduce)").matches) return;

      gsap.utils.toArray<HTMLElement>(".motion-reveal").forEach((element) => {
        gsap.fromTo(
          element,
          { opacity: 0, y: 42 },
          {
            opacity: 1,
            y: 0,
            duration: 0.9,
            ease: "power3.out",
            scrollTrigger: {
              trigger: element,
              start: "top 88%",
              once: true,
            },
          },
        );
      });

      gsap.utils.toArray<HTMLElement>(".image-reveal").forEach((element) => {
        gsap.fromTo(
          element,
          { opacity: 0.42, scale: 0.84 },
          {
            opacity: 1,
            scale: 1,
            ease: "none",
            scrollTrigger: {
              trigger: element,
              start: "top 92%",
              end: "center 48%",
              scrub: 0.7,
            },
          },
        );
      });

      const words = gsap.utils.toArray<HTMLElement>(".scrub-word");
      if (words.length) {
        gsap.fromTo(
          words,
          { opacity: 0.12 },
          {
            opacity: 1,
            stagger: 0.04,
            ease: "none",
            scrollTrigger: {
              trigger: ".scrub-copy",
              start: "top 84%",
              end: "bottom 48%",
              scrub: 0.8,
            },
          },
        );
      }
    },
    { scope },
  );

  return null;
}

export function MotionProvider({ children }: { children: React.ReactNode }) {
  const scope = useRef<HTMLDivElement>(null);
  const pathname = usePathname();
  const [ready, setReady] = useState(false);

  useEffect(() => {
    const timer = window.setTimeout(() => setReady(true), 250);
    return () => window.clearTimeout(timer);
  }, []);

  return (
    <div className="motion-root" ref={scope}>
      {children}
      {ready ? <MotionController key={pathname} scope={scope} /> : null}
    </div>
  );
}
