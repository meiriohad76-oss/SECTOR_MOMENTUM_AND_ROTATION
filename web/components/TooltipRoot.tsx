"use client";

/**
 * Global floating tooltip engine.
 *
 * Renders a single fixed <div> that follows the cursor whenever the pointer
 * is over any element with a [data-tooltip] attribute. Works in both HTML
 * and SVG contexts (SVG fires the same mouse events).
 *
 * Usage: render <TooltipRoot /> once in the root layout. Then add
 *   data-tooltip="Your explanation here"
 * to any element to opt in.
 */
import { useEffect, useRef, useState } from "react";

const OFFSET_X = 16; // px right of cursor
const OFFSET_Y = 12; // px below cursor
const FLIP_MARGIN = 24; // px from viewport edge before flipping

function findTooltip(el: Element | null): string | null {
  let node: Element | null = el;
  while (node) {
    const t = node.getAttribute("data-tooltip");
    if (t) return t;
    node = node.parentElement;
  }
  return null;
}

export default function TooltipRoot() {
  const [text, setText] = useState<string | null>(null);
  const [pos, setPos] = useState({ x: 0, y: 0 });
  const boxRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    let lastText: string | null = null;

    function onMove(e: MouseEvent) {
      const t = findTooltip(e.target as Element);
      if (t !== lastText) {
        lastText = t;
        setText(t);
      }
      if (t) setPos({ x: e.clientX, y: e.clientY });
    }

    function onLeave() {
      lastText = null;
      setText(null);
    }

    document.addEventListener("mousemove", onMove);
    document.addEventListener("mouseleave", onLeave);
    return () => {
      document.removeEventListener("mousemove", onMove);
      document.removeEventListener("mouseleave", onLeave);
    };
  }, []);

  if (!text) return null;

  // Smart positioning: flip horizontally or vertically near viewport edges
  const boxW = boxRef.current?.offsetWidth ?? 320;
  const boxH = boxRef.current?.offsetHeight ?? 80;
  const vw = typeof window !== "undefined" ? window.innerWidth : 1200;
  const vh = typeof window !== "undefined" ? window.innerHeight : 800;

  const left = pos.x + OFFSET_X + boxW + FLIP_MARGIN > vw
    ? pos.x - boxW - OFFSET_X
    : pos.x + OFFSET_X;

  const top = pos.y + OFFSET_Y + boxH + FLIP_MARGIN > vh
    ? pos.y - boxH - OFFSET_Y
    : pos.y + OFFSET_Y;

  return (
    <div
      ref={boxRef}
      className="global-tooltip"
      style={{ left, top }}
      role="tooltip"
      aria-hidden="true"
    >
      {text}
    </div>
  );
}
