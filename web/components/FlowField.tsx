"use client";

// The home page's moving ground: a slowly advecting ocean current field, rendered as one
// full-screen WebGL quad.
//
// Two deliberate choices make this belong to UDGAM rather than being generic ambience:
//  1. It is a *flow field* — domain-warped noise advected over time, the same visual grammar as
//     the backward-drift stage. The background is a preview of what stage 2 does.
//  2. It carries faint radar speckle, the grain of the SAR imagery the whole project reads.
// It is deliberately COLD (slate-cyan). Orange means drift particles everywhere else in this
// app, so the background must never borrow it.
//
// Cost discipline (CLAUDE.md — "the demo lives or dies" on the map's framerate): one quad, no
// per-frame allocation, DPR capped at 1.5, and the loop is suspended whenever the tab is hidden
// or the canvas scrolls out of view. This component is only ever mounted on "/", never on a
// case screen where deck.gl owns the GPU.

import { useEffect, useRef } from "react";

const VERT = `
attribute vec2 aPos;
void main() { gl_Position = vec4(aPos, 0.0, 1.0); }
`;

const FRAG = `
precision highp float;
uniform vec2  uRes;
uniform float uTime;

vec2 hash2(vec2 p) {
  p = vec2(dot(p, vec2(127.1, 311.7)), dot(p, vec2(269.5, 183.3)));
  return -1.0 + 2.0 * fract(sin(p) * 43758.5453123);
}

float noise(vec2 p) {
  vec2 i = floor(p);
  vec2 f = fract(p);
  vec2 u = f * f * (3.0 - 2.0 * f);
  return mix(
    mix(dot(hash2(i + vec2(0.0, 0.0)), f - vec2(0.0, 0.0)),
        dot(hash2(i + vec2(1.0, 0.0)), f - vec2(1.0, 0.0)), u.x),
    mix(dot(hash2(i + vec2(0.0, 1.0)), f - vec2(0.0, 1.0)),
        dot(hash2(i + vec2(1.0, 1.0)), f - vec2(1.0, 1.0)), u.x),
    u.y);
}

float fbm(vec2 p) {
  float v = 0.0;
  float a = 0.5;
  mat2 m = mat2(1.6, 1.2, -1.2, 1.6);
  for (int i = 0; i < 5; i++) {
    v += a * noise(p);
    p = m * p;
    a *= 0.5;
  }
  return v;
}

void main() {
  vec2 uv = gl_FragCoord.xy / uRes;
  vec2 p  = (gl_FragCoord.xy - 0.5 * uRes) / uRes.y;

  float t = uTime * 0.016;

  // Two levels of domain warp: large gyres carrying finer filaments inside them.
  vec2 q = vec2(fbm(p * 1.5 + vec2(0.0, t)),
                fbm(p * 1.5 + vec2(5.2, 1.3) - t * 0.62));
  vec2 r = vec2(fbm(p * 2.1 + 2.6 * q + vec2(1.7, 9.2) + t * 0.9),
                fbm(p * 2.1 + 2.6 * q + vec2(8.3, 2.8) - t * 0.75));
  float f = fbm(p * 2.4 + 2.2 * r);

  // Iso-contours of the warped field read as current filaments.
  float band = abs(fract(f * 6.5 + t * 1.6) - 0.5);
  float fil  = smoothstep(0.06, 0.0, band);
  fil *= 0.28 + 0.72 * smoothstep(-0.45, 0.55, f);

  // A broad slow glow where the field is strongest, so the filaments sit in water.
  float glow = smoothstep(-0.1, 0.75, f);

  // Depth gradient: lighter at the horizon, near-black at the bottom of the frame.
  vec3 col = mix(vec3(0.016, 0.028, 0.044), vec3(0.008, 0.014, 0.022), 1.0 - uv.y);
  col += vec3(0.040, 0.098, 0.128) * glow * 1.05;
  col += vec3(0.34, 0.62, 0.74) * fil * 0.30;

  // A slow scan band descending the frame — the same gesture the detector's sweep makes.
  float scan = exp(-pow((uv.y - fract(uTime * 0.021)) * 7.0, 2.0));
  col += vec3(0.12, 0.30, 0.38) * scan * 0.10;

  // Radar speckle: the grain of the SAR scenes this project reads.
  float grain = fract(sin(dot(gl_FragCoord.xy + floor(uTime * 12.0), vec2(12.9898, 78.233))) * 43758.5453);
  col += (grain - 0.5) * 0.016;

  // Vignette keeps the headline legible over the busiest part of the field.
  float vig = smoothstep(1.55, 0.30, length(p * vec2(0.80, 1.0)));
  col *= 0.62 + 0.38 * vig;

  gl_FragColor = vec4(col, 1.0);
}
`;

function compile(gl: WebGLRenderingContext, type: number, src: string) {
  const sh = gl.createShader(type);
  if (!sh) return null;
  gl.shaderSource(sh, src);
  gl.compileShader(sh);
  if (!gl.getShaderParameter(sh, gl.COMPILE_STATUS)) {
    gl.deleteShader(sh);
    return null;
  }
  return sh;
}

export default function FlowField({ className = "" }: { className?: string }) {
  const ref = useRef<HTMLCanvasElement>(null);

  useEffect(() => {
    const canvas = ref.current;
    if (!canvas) return;

    const gl = canvas.getContext("webgl", {
      alpha: false,
      antialias: false,
      depth: false,
      stencil: false,
      powerPreference: "low-power",
    });
    // No WebGL (or a blocked context): the CSS gradient underneath is the whole fallback.
    // Nothing to clean up, nothing to report — the page is still correct without it.
    if (!gl) return;

    const vs = compile(gl, gl.VERTEX_SHADER, VERT);
    const fs = compile(gl, gl.FRAGMENT_SHADER, FRAG);
    const prog = gl.createProgram();
    if (!vs || !fs || !prog) return;
    gl.attachShader(prog, vs);
    gl.attachShader(prog, fs);
    gl.linkProgram(prog);
    if (!gl.getProgramParameter(prog, gl.LINK_STATUS)) return;
    gl.useProgram(prog);

    const buf = gl.createBuffer();
    gl.bindBuffer(gl.ARRAY_BUFFER, buf);
    gl.bufferData(
      gl.ARRAY_BUFFER,
      new Float32Array([-1, -1, 3, -1, -1, 3]),
      gl.STATIC_DRAW,
    );
    const aPos = gl.getAttribLocation(prog, "aPos");
    gl.enableVertexAttribArray(aPos);
    gl.vertexAttribPointer(aPos, 2, gl.FLOAT, false, 0, 0);

    const uRes = gl.getUniformLocation(prog, "uRes");
    const uTime = gl.getUniformLocation(prog, "uTime");

    const reduced = window.matchMedia("(prefers-reduced-motion: reduce)").matches;

    const resize = () => {
      const dpr = Math.min(window.devicePixelRatio || 1, 1.5);
      const w = Math.floor(canvas.clientWidth * dpr);
      const h = Math.floor(canvas.clientHeight * dpr);
      if (w === 0 || h === 0 || (canvas.width === w && canvas.height === h)) return;
      canvas.width = w;
      canvas.height = h;
      gl.viewport(0, 0, w, h);
    };

    const draw = (time: number) => {
      gl.uniform2f(uRes, canvas.width, canvas.height);
      gl.uniform1f(uTime, time);
      gl.drawArrays(gl.TRIANGLES, 0, 3);
    };

    resize();

    // Reduced motion: render one still frame of the field and stop. The page keeps its ground,
    // nothing animates.
    if (reduced) {
      draw(12.0);
      const ro = new ResizeObserver(() => {
        resize();
        draw(12.0);
      });
      ro.observe(canvas);
      return () => ro.disconnect();
    }

    let raf = 0;
    let start = performance.now();
    let elapsed = 0;
    let visible = true;

    const tick = (now: number) => {
      elapsed += (now - start) / 1000;
      start = now;
      resize();
      draw(elapsed);
      raf = requestAnimationFrame(tick);
    };

    const play = () => {
      if (raf !== 0) return;
      start = performance.now();
      raf = requestAnimationFrame(tick);
    };
    const pause = () => {
      if (raf === 0) return;
      cancelAnimationFrame(raf);
      raf = 0;
    };

    // Suspend whenever the field is not actually being looked at.
    const onVisibility = () => (document.hidden || !visible ? pause() : play());
    const io = new IntersectionObserver(
      ([entry]) => {
        visible = entry.isIntersecting;
        onVisibility();
      },
      { threshold: 0 },
    );
    io.observe(canvas);
    document.addEventListener("visibilitychange", onVisibility);

    const ro = new ResizeObserver(resize);
    ro.observe(canvas);

    play();

    return () => {
      pause();
      io.disconnect();
      ro.disconnect();
      document.removeEventListener("visibilitychange", onVisibility);
      gl.deleteBuffer(buf);
      gl.deleteProgram(prog);
      gl.deleteShader(vs);
      gl.deleteShader(fs);
    };
  }, []);

  return (
    <canvas
      ref={ref}
      aria-hidden
      className={className}
      // The gradient is what shows if WebGL is unavailable — the page never falls back to flat
      // black, and the canvas simply paints over it when it can.
      style={{
        background:
          "radial-gradient(120% 80% at 50% 0%, #0a1520 0%, #060b12 45%, #04070b 100%)",
      }}
    />
  );
}
