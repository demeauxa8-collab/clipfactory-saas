"use client";

import * as React from "react";

const DITHER_INDEX = {
  bayer8: 0,
  lines: 1,
  noise: 2,
} as const;

type DitherStyle = keyof typeof DITHER_INDEX;

type DitherRevealProps = {
  image: string | { src?: string; url?: string; alt?: string };
  alt?: string;
  fit?: "cover" | "contain";
  focusY?: number;
  ditherStyle?: DitherStyle;
  dotSize?: number;
  revealRadius?: number;
  revealSoftness?: number;
  wave?: boolean;
  waveSpeed?: number;
  waveDensity?: number;
  className?: string;
  style?: React.CSSProperties;
};

const VERTEX_SHADER = `
attribute vec2 aPos;
varying vec2 vUv;

void main() {
  vUv = aPos * 0.5 + 0.5;
  gl_Position = vec4(aPos, 0.0, 1.0);
}
`;

const FRAGMENT_SHADER = `
precision highp float;

uniform sampler2D uTexture;
uniform float uTime;
uniform vec2 uMouse;
uniform float uMouseActive;
uniform float uRevealRadius;
uniform float uRevealSoftness;
uniform float uPixelSize;
uniform float uDitherStyle;
uniform float uWaveSpeed;
uniform float uWaveFrequency;
uniform float uWaveAmplitude;
uniform float uWaveMargin;
uniform float uCanvasAspect;
uniform float uImageAspect;
uniform vec2 uResolution;
uniform float uFit;
uniform float uFocusY;

varying vec2 vUv;

float bayer2(vec2 value) {
  value = floor(value);
  return fract(value.x * 0.5 + value.y * value.y * 0.75);
}

float bayer4(vec2 value) {
  return bayer2(value * 0.5) * 0.25 + bayer2(value);
}

float bayer8(vec2 value) {
  return bayer4(value * 0.5) * 0.25 + bayer2(value);
}

float noise(vec2 point) {
  return fract(52.9829189 * fract(0.06711056 * point.x + 0.00583715 * point.y));
}

float orderedTone(float gray, float threshold) {
  float adjusted = gray + (threshold - 0.5) * 0.5;
  return adjusted < 0.33 ? 0.0 : (adjusted < 0.66 ? 0.5 : 1.0);
}

float ditherTone(float gray, float pixelSize) {
  vec2 fragment = gl_FragCoord.xy / pixelSize;
  if (uDitherStyle < 0.5) return orderedTone(gray, bayer8(fragment));
  if (uDitherStyle < 1.5) {
    float period = pixelSize * 4.0;
    float value = fract((gl_FragCoord.x + gl_FragCoord.y) / period);
    return 1.0 - step(value, 1.0 - gray);
  }
  return step(noise(fragment), gray);
}

vec2 fitUv(vec2 uv) {
  vec2 cover = uCanvasAspect < uImageAspect
    ? vec2(uCanvasAspect / uImageAspect, 1.0)
    : vec2(1.0, uImageAspect / uCanvasAspect);
  vec2 scale = uFit > 0.5 ? 1.0 / cover : cover / (1.0 + 2.0 * uWaveMargin);
  vec2 outputUv = (uv - 0.5) * scale + 0.5;
  outputUv.y += (1.0 - scale.y) * (0.5 - uFocusY) * step(scale.y, 1.0);
  return outputUv;
}

void main() {
  vec2 uv = vUv;
  float waveStrength = uWaveAmplitude * 0.1;
  float revealNorm = uRevealRadius / max(min(uResolution.x, uResolution.y), 1.0);
  vec2 distortedUv = uv;

  distortedUv.x += sin(uv.y * uWaveFrequency + uTime * uWaveSpeed) * waveStrength;
  distortedUv.y += sin(uv.x * uWaveFrequency * 0.7 + uTime * uWaveSpeed * 0.8) * waveStrength * 0.5;

  if (uMouseActive > 0.01) {
    float distanceToPointer = distance(uv, uMouse);
    float influence = smoothstep(revealNorm, 0.0, distanceToPointer);
    float ripple = sin(distanceToPointer * uWaveFrequency * 5.0 - uTime * uWaveSpeed)
      * uWaveAmplitude * 0.05 * influence * uMouseActive;
    distortedUv += vec2(ripple);
  }

  vec2 sampleUv = fitUv(distortedUv);
  vec4 color = texture2D(uTexture, sampleUv);
  vec2 inside = step(vec2(0.0), sampleUv) * step(sampleUv, vec2(1.0));
  color *= inside.x * inside.y;

  float gray = dot(color.rgb, vec3(0.299, 0.587, 0.114));
  float tone = ditherTone(gray, max(uPixelSize, 0.25));
  float revealDistance = distance(uv * uResolution, uMouse * uResolution);
  float innerRadius = max(0.0, uRevealRadius * (1.0 - uRevealSoftness));
  float outerRadius = uRevealRadius * (1.0 + uRevealSoftness) + 0.001;
  float reveal = (1.0 - smoothstep(innerRadius, outerRadius, revealDistance)) * uMouseActive;

  gl_FragColor = vec4(mix(vec3(tone), color.rgb, reveal), color.a);
}
`;

function clamp(
  value: number | undefined,
  min: number,
  max: number,
  fallback: number,
) {
  if (!Number.isFinite(value)) return fallback;
  return Math.min(max, Math.max(min, value as number));
}

function resolveImage(image: DitherRevealProps["image"]) {
  if (typeof image === "string") return image;
  return image.src ?? image.url ?? "";
}

export function DitherReveal({
  image,
  alt,
  fit = "cover",
  focusY = 50,
  ditherStyle = "bayer8",
  dotSize = 5,
  revealRadius = 100,
  revealSoftness = 50,
  wave = false,
  waveSpeed = 82,
  waveDensity = 25,
  className,
  style,
}: DitherRevealProps) {
  const containerRef = React.useRef<HTMLDivElement>(null);
  const canvasRef = React.useRef<HTMLCanvasElement>(null);
  const imageUrl = resolveImage(image);

  React.useEffect(() => {
    const container = containerRef.current;
    const canvas = canvasRef.current;
    if (!container || !canvas || !imageUrl) return;

    const gl = canvas.getContext("webgl", {
      antialias: false,
      premultipliedAlpha: false,
    });
    if (!gl) return;

    const compileShader = (type: number, source: string) => {
      const shader = gl.createShader(type);
      if (!shader) throw new Error("Unable to create DitherReveal shader.");
      gl.shaderSource(shader, source);
      gl.compileShader(shader);
      if (!gl.getShaderParameter(shader, gl.COMPILE_STATUS)) {
        throw new Error(
          gl.getShaderInfoLog(shader) ??
            "Unable to compile DitherReveal shader.",
        );
      }
      return shader;
    };

    const vertexShader = compileShader(gl.VERTEX_SHADER, VERTEX_SHADER);
    const fragmentShader = compileShader(gl.FRAGMENT_SHADER, FRAGMENT_SHADER);
    const program = gl.createProgram();
    if (!program) return;
    gl.attachShader(program, vertexShader);
    gl.attachShader(program, fragmentShader);
    gl.linkProgram(program);
    if (!gl.getProgramParameter(program, gl.LINK_STATUS)) return;
    gl.useProgram(program);
    gl.deleteShader(vertexShader);
    gl.deleteShader(fragmentShader);

    const buffer = gl.createBuffer();
    gl.bindBuffer(gl.ARRAY_BUFFER, buffer);
    gl.bufferData(
      gl.ARRAY_BUFFER,
      new Float32Array([-1, -1, 3, -1, -1, 3]),
      gl.STATIC_DRAW,
    );
    const position = gl.getAttribLocation(program, "aPos");
    gl.enableVertexAttribArray(position);
    gl.vertexAttribPointer(position, 2, gl.FLOAT, false, 0, 0);

    const uniform = (name: string) => gl.getUniformLocation(program, name);
    const uniforms = {
      time: uniform("uTime"),
      mouse: uniform("uMouse"),
      mouseActive: uniform("uMouseActive"),
      revealRadius: uniform("uRevealRadius"),
      revealSoftness: uniform("uRevealSoftness"),
      pixelSize: uniform("uPixelSize"),
      ditherStyle: uniform("uDitherStyle"),
      waveSpeed: uniform("uWaveSpeed"),
      waveFrequency: uniform("uWaveFrequency"),
      waveAmplitude: uniform("uWaveAmplitude"),
      waveMargin: uniform("uWaveMargin"),
      canvasAspect: uniform("uCanvasAspect"),
      imageAspect: uniform("uImageAspect"),
      resolution: uniform("uResolution"),
      fit: uniform("uFit"),
      focusY: uniform("uFocusY"),
    };

    const texture = gl.createTexture();
    gl.bindTexture(gl.TEXTURE_2D, texture);
    gl.pixelStorei(gl.UNPACK_FLIP_Y_WEBGL, true);
    gl.texImage2D(
      gl.TEXTURE_2D,
      0,
      gl.RGBA,
      1,
      1,
      0,
      gl.RGBA,
      gl.UNSIGNED_BYTE,
      new Uint8Array([20, 20, 20, 255]),
    );
    gl.texParameteri(gl.TEXTURE_2D, gl.TEXTURE_WRAP_S, gl.CLAMP_TO_EDGE);
    gl.texParameteri(gl.TEXTURE_2D, gl.TEXTURE_WRAP_T, gl.CLAMP_TO_EDGE);
    gl.texParameteri(gl.TEXTURE_2D, gl.TEXTURE_MIN_FILTER, gl.LINEAR);
    gl.texParameteri(gl.TEXTURE_2D, gl.TEXTURE_MAG_FILTER, gl.LINEAR);

    const pointer = { x: 0.5, y: 0.5, active: 0, target: 0, entered: false };
    let imageAspect = 16 / 9;
    let frame = 0;
    let startedAt = performance.now();
    let inView = true;

    const draw = () => {
      frame = 0;
      if (!inView) return;

      pointer.active += (pointer.target - pointer.active) * 0.12;
      const waveFactor = wave ? clamp(waveSpeed, 1, 100, 82) / 100 : 0;
      const margin = waveFactor * 0.4 * 0.15;
      gl.uniform1f(uniforms.time, (performance.now() - startedAt) / 1000);
      gl.uniform2f(uniforms.mouse, pointer.x, pointer.y);
      gl.uniform1f(uniforms.mouseActive, pointer.entered ? pointer.active : 0);
      gl.uniform1f(uniforms.revealRadius, clamp(revealRadius, 20, 600, 100));
      gl.uniform1f(
        uniforms.revealSoftness,
        clamp(revealSoftness, 0, 100, 50) / 100,
      );
      gl.uniform1f(uniforms.pixelSize, clamp(dotSize, 1, 20, 5) / 2);
      gl.uniform1f(uniforms.ditherStyle, DITHER_INDEX[ditherStyle]);
      gl.uniform1f(uniforms.waveSpeed, waveFactor);
      gl.uniform1f(uniforms.waveFrequency, clamp(waveDensity, 5, 100, 25) / 10);
      gl.uniform1f(uniforms.waveAmplitude, waveFactor * 0.4);
      gl.uniform1f(uniforms.waveMargin, margin);
      gl.uniform1f(uniforms.canvasAspect, canvas.width / canvas.height);
      gl.uniform1f(uniforms.imageAspect, imageAspect);
      gl.uniform2f(
        uniforms.resolution,
        container.clientWidth || 1,
        container.clientHeight || 1,
      );
      gl.uniform1f(uniforms.fit, fit === "contain" ? 1 : 0);
      gl.uniform1f(uniforms.focusY, clamp(focusY, 0, 100, 50) / 100);
      gl.drawArrays(gl.TRIANGLES, 0, 3);

      const pointerSettling = Math.abs(pointer.target - pointer.active) > 0.002;
      if (wave || pointerSettling) frame = window.requestAnimationFrame(draw);
    };

    const scheduleDraw = () => {
      if (!frame) frame = window.requestAnimationFrame(draw);
    };

    const resize = () => {
      const dpr = Math.min(window.devicePixelRatio || 1, 2);
      canvas.width = Math.max(1, Math.floor(container.clientWidth * dpr));
      canvas.height = Math.max(1, Math.floor(container.clientHeight * dpr));
      gl.viewport(0, 0, canvas.width, canvas.height);
      scheduleDraw();
    };

    const handlePointerMove = (event: PointerEvent) => {
      const rect = container.getBoundingClientRect();
      pointer.x = (event.clientX - rect.left) / rect.width;
      pointer.y = 1 - (event.clientY - rect.top) / rect.height;
      pointer.entered = true;
      pointer.target = 1;
      scheduleDraw();
    };
    const handlePointerEnter = () => {
      pointer.entered = true;
      pointer.target = 1;
      scheduleDraw();
    };
    const handlePointerLeave = () => {
      pointer.target = 0;
      scheduleDraw();
    };

    const imageElement = new window.Image();
    imageElement.decoding = "async";
    imageElement.onload = () => {
      imageAspect = imageElement.naturalWidth / imageElement.naturalHeight;
      gl.bindTexture(gl.TEXTURE_2D, texture);
      gl.texImage2D(
        gl.TEXTURE_2D,
        0,
        gl.RGBA,
        gl.RGBA,
        gl.UNSIGNED_BYTE,
        imageElement,
      );
      startedAt = performance.now();
      scheduleDraw();
    };
    imageElement.src = imageUrl;

    const resizeObserver = new ResizeObserver(resize);
    const intersectionObserver = new IntersectionObserver(([entry]) => {
      inView = entry.isIntersecting;
      if (inView) scheduleDraw();
    });
    resizeObserver.observe(container);
    intersectionObserver.observe(container);
    container.addEventListener("pointermove", handlePointerMove);
    container.addEventListener("pointerenter", handlePointerEnter);
    container.addEventListener("pointerleave", handlePointerLeave);
    resize();

    return () => {
      window.cancelAnimationFrame(frame);
      resizeObserver.disconnect();
      intersectionObserver.disconnect();
      container.removeEventListener("pointermove", handlePointerMove);
      container.removeEventListener("pointerenter", handlePointerEnter);
      container.removeEventListener("pointerleave", handlePointerLeave);
      imageElement.onload = null;
      gl.deleteProgram(program);
      gl.deleteBuffer(buffer);
      gl.deleteTexture(texture);
    };
  }, [
    ditherStyle,
    dotSize,
    fit,
    focusY,
    imageUrl,
    revealRadius,
    revealSoftness,
    wave,
    waveDensity,
    waveSpeed,
  ]);

  return (
    <div
      ref={containerRef}
      className={className}
      role="img"
      aria-label={alt ?? (typeof image === "object" ? image.alt : undefined)}
      style={{
        position: "relative",
        width: "100%",
        height: "100%",
        overflow: "hidden",
        ...style,
      }}
    >
      <canvas
        ref={canvasRef}
        aria-hidden="true"
        style={{ display: "block", width: "100%", height: "100%" }}
      />
    </div>
  );
}

export default DitherReveal;
