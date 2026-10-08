"use client";

import { useEffect, useRef } from "react";

const SIZE = 250;
const DOTS = 270;
const RADIUS = 84;
const FALLBACK_RGB = "15 118 110";

/** "#0f766e" or "#0f7" -> "15 118 110"; anything else falls back to the light-theme teal. */
export function hexToRgbChannels(value: string): string {
  const hex = value.trim().replace(/^#/, "");
  const full = hex.length === 3 ? [...hex].map((c) => c + c).join("") : hex;
  if (!/^[0-9a-f]{6}$/i.test(full)) return FALLBACK_RGB;
  const n = Number.parseInt(full, 16);
  return `${(n >> 16) & 255} ${(n >> 8) & 255} ${n & 255}`;
}

const SPHERE = Array.from({ length: DOTS }, (_, i) => {
  const phi = Math.acos(1 - 2 * ((i + 0.5) / DOTS));
  const theta = Math.PI * (1 + Math.sqrt(5)) * i;
  return {
    x: Math.cos(theta) * Math.sin(phi),
    y: Math.sin(theta) * Math.sin(phi),
    z: Math.cos(phi),
  };
});

/**
 * A rotating dot sphere shown while the atlas is being traced. Colour follows the --cluster
 * token (light and dark theme); with reduced motion it draws one still frame.
 */
export function ThinkingOrb({ label }: { label: string }) {
  const canvasRef = useRef<HTMLCanvasElement>(null);

  useEffect(() => {
    const canvas = canvasRef.current;
    const context = canvas?.getContext("2d");
    if (!canvas || !context) return;
    const reduced = window.matchMedia?.("(prefers-reduced-motion: reduce)").matches ?? false;
    const rgb = hexToRgbChannels(
      getComputedStyle(document.documentElement).getPropertyValue("--cluster"),
    );
    const dpr = Math.min(window.devicePixelRatio || 1, 2);
    canvas.width = SIZE * dpr;
    canvas.height = SIZE * dpr;
    context.setTransform(dpr, 0, 0, dpr, 0, 0);

    let frame = 0;
    let time = 0;
    const center = SIZE / 2;
    const draw = () => {
      context.clearRect(0, 0, SIZE, SIZE);
      const rotation = time * 0.7;
      for (const dot of SPHERE) {
        const x = dot.x * Math.cos(rotation) - dot.z * Math.sin(rotation);
        const z = dot.x * Math.sin(rotation) + dot.z * Math.cos(rotation);
        const depth = (z + 1) / 2;
        const pulse = 0.78 + Math.sin(time * 3 + dot.y * 7) * 0.22;
        context.beginPath();
        context.fillStyle = `rgb(${rgb} / ${0.12 + depth * 0.74})`;
        context.arc(
          center + x * RADIUS,
          center + dot.y * RADIUS,
          (1.1 + depth * 1.9) * pulse,
          0,
          Math.PI * 2,
        );
        context.fill();
      }
      if (reduced) return;
      time += 0.012;
      frame = requestAnimationFrame(draw);
    };
    draw();
    return () => cancelAnimationFrame(frame);
  }, []);

  return (
    <canvas
      ref={canvasRef}
      className="size-[250px] max-w-full"
      role="img"
      aria-label={`Animated evidence sphere: ${label}`}
    />
  );
}
