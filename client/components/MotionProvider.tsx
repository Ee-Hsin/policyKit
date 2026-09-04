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
          { opacity: 0, y: 24 },
          {
            opacity: 1,
            y: 0,
            duration: 0.65,
            ease: "power3.out",
            scrollTrigger: {
              trigger: element,
              start: "top 88%",
              once: true,
            },
          },
        );
      });

      const panels = gsap.utils.toArray<HTMLElement>(
        ".policy-table-card, .admin-card, .posting-panel, .agent-panel, .findings-section",
      );
      if (panels.length) {
        gsap.fromTo(panels, { opacity: 0.84, y: 10 }, {
          opacity: 1,
          y: 0,
          duration: 0.55,
          ease: "power2.out",
          stagger: 0.05,
        });
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
