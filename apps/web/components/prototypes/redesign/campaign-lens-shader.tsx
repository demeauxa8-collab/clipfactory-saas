"use client";

import type { MotionValue } from "motion/react";
import Image from "next/image";
import * as React from "react";

const VERTEX_SHADER = `
attribute vec2 aPosition;
varying vec2 vUv;

void main() {
  vUv = aPosition * 0.5 + 0.5;
  gl_Position = vec4(aPosition, 0.0, 1.0);
}
`;

const FRAGMENT_SHADER = `
precision highp float;

uniform sampler2D uTexture;
uniform float uCanvasAspect;
uniform float uImageAspect;
uniform float uLensProgress;
uniform vec2 uLensSize;
uniform float uLensSideMargin;
uniform float uLensCenterY;
uniform float uLensRadius;
uniform float uReducedTransparency;
uniform float uHigherContrast;
uniform vec2 uViewport;

varying vec2 vUv;

float roundedBoxDistance(vec2 point, vec2 halfSize, float radius) {
  vec2 offset = abs(point) - halfSize + radius;
  return min(max(offset.x, offset.y), 0.0)
    + length(max(offset, 0.0))
    - radius;
}

vec2 coverUv(vec2 uv) {
  vec2 visibleArea = uCanvasAspect > uImageAspect
    ? vec2(1.0, uImageAspect / uCanvasAspect)
    : vec2(uCanvasAspect / uImageAspect, 1.0);

  return (uv - 0.5) * visibleArea + 0.5;
}

void main() {
  vec2 sampleUv = coverUv(vUv);
  vec4 source = texture2D(uTexture, sampleUv);

  float luminance = dot(source.rgb, vec3(0.2126, 0.7152, 0.0722));
  vec3 coolBlack = vec3(0.012, 0.014, 0.018);
  vec3 monochrome = mix(coolBlack, vec3(luminance), 0.58);
  vec3 outsideColor = mix(monochrome, source.rgb, 0.045);
  outsideColor *= mix(0.72, 0.62, uHigherContrast);

  // Geometry is supplied in CSS pixels by the same model that positions the
  // HTML aperture. Keeping both renderers in one coordinate space prevents
  // drift from viewport caps, breakpoints, margins, and non-centred layouts.
  vec2 lensHalfSize = max(uLensSize * 0.5, vec2(1.0));
  float minimumCenter = lensHalfSize.x + uLensSideMargin;
  float maximumCenter = max(
    minimumCenter,
    uViewport.x - lensHalfSize.x - uLensSideMargin
  );
  float centerX = mix(minimumCenter, maximumCenter, clamp(uLensProgress, 0.0, 1.0));

  vec2 point = vec2(
    vUv.x * uViewport.x - centerX,
    (1.0 - vUv.y) * uViewport.y - uLensCenterY
  );
  float distanceToLens = roundedBoxDistance(
    point,
    lensHalfSize,
    min(uLensRadius, min(lensHalfSize.x, lensHalfSize.y) - 1.0)
  );

  float softFeather = 3.5;
  float crispFeather = 1.25;
  float feather = mix(softFeather, crispFeather, uReducedTransparency);
  float lensMask = 1.0 - smoothstep(-feather, feather, distanceToLens);

  vec3 color = mix(outsideColor, source.rgb, lensMask);

  // A quiet directional rim makes the lens read as a material boundary. It is
  // static and tied to the crop geometry, never to an idle animation clock.
  float rim = 1.0 - smoothstep(feather * 0.7, feather * 3.2, abs(distanceToLens));
  float topLight = mix(1.0, 0.42, clamp(point.y / max(lensHalfSize.y, 1.0) + 0.5, 0.0, 1.0));
  float rimStrength = mix(0.12, 0.22, max(uReducedTransparency, uHigherContrast));
  color += vec3(rim * topLight * rimStrength);

  gl_FragColor = vec4(clamp(color, 0.0, 1.0), source.a);
}
`;

type RendererState = "loading" | "ready" | "fallback";

export type CampaignLensShaderProps = {
  imageSrc: string;
  alt: string;
  lensProgress: MotionValue<number>;
  lensHeightRatio?: number;
  lensHeightPx?: number;
  lensWidthPx?: number;
  lensSideMarginPx?: number;
  lensCenterYRatio?: number;
  lensRadiusPx?: number;
  priority?: boolean;
  className?: string;
};

function clamp(value: number, minimum: number, maximum: number) {
  return Math.min(maximum, Math.max(minimum, value));
}

function compileShader(
  gl: WebGLRenderingContext,
  type: number,
  source: string,
) {
  const shader = gl.createShader(type);
  if (!shader) throw new Error("Unable to create the campaign lens shader.");

  gl.shaderSource(shader, source);
  gl.compileShader(shader);

  if (!gl.getShaderParameter(shader, gl.COMPILE_STATUS)) {
    const message =
      gl.getShaderInfoLog(shader) ??
      "Unable to compile the campaign lens shader.";
    gl.deleteShader(shader);
    throw new Error(message);
  }

  return shader;
}

function getUniform(
  gl: WebGLRenderingContext,
  program: WebGLProgram,
  name: string,
) {
  const location = gl.getUniformLocation(program, name);
  if (location === null) throw new Error(`Missing WebGL uniform: ${name}`);
  return location;
}

export function CampaignLensShader({
  imageSrc,
  alt,
  lensProgress,
  lensHeightRatio = 0.78,
  lensHeightPx,
  lensWidthPx,
  lensSideMarginPx,
  lensCenterYRatio = 0.5,
  lensRadiusPx = 27,
  priority = false,
  className,
}: CampaignLensShaderProps) {
  const containerRef = React.useRef<HTMLDivElement>(null);
  const canvasRef = React.useRef<HTMLCanvasElement>(null);
  const [rendererState, setRendererState] =
    React.useState<RendererState>("loading");
  const [contextRevision, setContextRevision] = React.useState(0);

  React.useEffect(() => {
    const container = containerRef.current;
    const canvas = canvasRef.current;
    if (!container || !canvas || !imageSrc) {
      setRendererState("fallback");
      return;
    }

    let disposed = false;
    let contextLost = false;
    let imageLoaded = false;
    let inView = typeof IntersectionObserver === "undefined";
    let frame = 0;
    let imageAspect = 16 / 9;
    let viewportWidth = 1;
    let viewportHeight = 1;
    let currentProgress = clamp(lensProgress.get(), 0, 1);
    let announcedReady = false;
    let cleaned = false;
    let resizeObserver: ResizeObserver | null = null;
    let intersectionObserver: IntersectionObserver | null = null;
    let textureImage: HTMLImageElement | null = null;
    const ancillaryCleanups: Array<() => void> = [];

    let gl: WebGLRenderingContext | null = null;
    let vertexShader: WebGLShader | null = null;
    let fragmentShader: WebGLShader | null = null;
    let program: WebGLProgram | null = null;
    let buffer: WebGLBuffer | null = null;
    let texture: WebGLTexture | null = null;

    const reducedTransparency = window.matchMedia(
      "(prefers-reduced-transparency: reduce)",
    );
    const higherContrast = window.matchMedia("(prefers-contrast: more)");

    const handleContextLost = (event: Event) => {
      event.preventDefault();
      contextLost = true;
      if (frame) window.cancelAnimationFrame(frame);
      frame = 0;
      if (!disposed) setRendererState("fallback");
    };

    const handleContextRestored = () => {
      if (!disposed) setContextRevision((revision) => revision + 1);
    };

    canvas.addEventListener("webglcontextlost", handleContextLost);
    canvas.addEventListener("webglcontextrestored", handleContextRestored);

    const disposeGlResources = () => {
      if (!gl) return;
      if (vertexShader) gl.deleteShader(vertexShader);
      if (fragmentShader) gl.deleteShader(fragmentShader);
      if (texture) gl.deleteTexture(texture);
      if (buffer) gl.deleteBuffer(buffer);
      if (program) gl.deleteProgram(program);
      texture = null;
      buffer = null;
      program = null;
      vertexShader = null;
      fragmentShader = null;
    };

    const cleanup = () => {
      if (cleaned) return;
      cleaned = true;
      disposed = true;
      if (frame) window.cancelAnimationFrame(frame);
      frame = 0;
      resizeObserver?.disconnect();
      intersectionObserver?.disconnect();
      ancillaryCleanups.splice(0).forEach((dispose) => dispose());
      if (textureImage) {
        textureImage.onload = null;
        textureImage.onerror = null;
      }
      canvas.removeEventListener("webglcontextlost", handleContextLost);
      canvas.removeEventListener("webglcontextrestored", handleContextRestored);
      disposeGlResources();
    };

    try {
      gl = canvas.getContext("webgl", {
        alpha: true,
        antialias: false,
        depth: false,
        stencil: false,
        premultipliedAlpha: false,
        preserveDrawingBuffer: false,
        powerPreference: "high-performance",
      });

      if (!gl) throw new Error("WebGL is unavailable.");

      vertexShader = compileShader(gl, gl.VERTEX_SHADER, VERTEX_SHADER);
      fragmentShader = compileShader(gl, gl.FRAGMENT_SHADER, FRAGMENT_SHADER);
      program = gl.createProgram();

      if (!program) {
        gl.deleteShader(vertexShader);
        gl.deleteShader(fragmentShader);
        throw new Error("Unable to create the campaign lens program.");
      }

      gl.attachShader(program, vertexShader);
      gl.attachShader(program, fragmentShader);
      gl.linkProgram(program);
      gl.deleteShader(vertexShader);
      gl.deleteShader(fragmentShader);
      vertexShader = null;
      fragmentShader = null;

      if (!gl.getProgramParameter(program, gl.LINK_STATUS)) {
        throw new Error(
          gl.getProgramInfoLog(program) ??
            "Unable to link the campaign lens program.",
        );
      }

      gl.useProgram(program);
      gl.disable(gl.DEPTH_TEST);
      gl.disable(gl.BLEND);

      buffer = gl.createBuffer();
      if (!buffer)
        throw new Error("Unable to create the campaign lens buffer.");

      gl.bindBuffer(gl.ARRAY_BUFFER, buffer);
      gl.bufferData(
        gl.ARRAY_BUFFER,
        new Float32Array([-1, -1, 3, -1, -1, 3]),
        gl.STATIC_DRAW,
      );

      const position = gl.getAttribLocation(program, "aPosition");
      if (position < 0) throw new Error("Missing WebGL attribute: aPosition");
      gl.enableVertexAttribArray(position);
      gl.vertexAttribPointer(position, 2, gl.FLOAT, false, 0, 0);

      texture = gl.createTexture();
      if (!texture)
        throw new Error("Unable to create the campaign lens texture.");

      gl.activeTexture(gl.TEXTURE0);
      gl.bindTexture(gl.TEXTURE_2D, texture);
      gl.texParameteri(gl.TEXTURE_2D, gl.TEXTURE_WRAP_S, gl.CLAMP_TO_EDGE);
      gl.texParameteri(gl.TEXTURE_2D, gl.TEXTURE_WRAP_T, gl.CLAMP_TO_EDGE);
      gl.texParameteri(gl.TEXTURE_2D, gl.TEXTURE_MIN_FILTER, gl.LINEAR);
      gl.texParameteri(gl.TEXTURE_2D, gl.TEXTURE_MAG_FILTER, gl.LINEAR);
      gl.pixelStorei(gl.UNPACK_FLIP_Y_WEBGL, true);

      const uniforms = {
        texture: getUniform(gl, program, "uTexture"),
        canvasAspect: getUniform(gl, program, "uCanvasAspect"),
        imageAspect: getUniform(gl, program, "uImageAspect"),
        lensProgress: getUniform(gl, program, "uLensProgress"),
        lensSize: getUniform(gl, program, "uLensSize"),
        lensSideMargin: getUniform(gl, program, "uLensSideMargin"),
        lensCenterY: getUniform(gl, program, "uLensCenterY"),
        lensRadius: getUniform(gl, program, "uLensRadius"),
        reducedTransparency: getUniform(gl, program, "uReducedTransparency"),
        higherContrast: getUniform(gl, program, "uHigherContrast"),
        viewport: getUniform(gl, program, "uViewport"),
      };

      gl.uniform1i(uniforms.texture, 0);
      gl.clearColor(0, 0, 0, 0);
      gl.clear(gl.COLOR_BUFFER_BIT);

      const draw = () => {
        frame = 0;
        if (
          disposed ||
          contextLost ||
          !inView ||
          !imageLoaded ||
          !gl ||
          !program
        ) {
          return;
        }

        gl.useProgram(program);
        gl.uniform1f(uniforms.canvasAspect, viewportWidth / viewportHeight);
        gl.uniform1f(uniforms.imageAspect, imageAspect);
        gl.uniform1f(uniforms.lensProgress, currentProgress);
        const sideMargin = Math.max(
          0,
          lensSideMarginPx ?? Math.min(28, viewportWidth * 0.04),
        );
        const requestedHeight =
          lensHeightPx ?? viewportHeight * clamp(lensHeightRatio, 0.32, 0.94);
        const widthLimitedHeight =
          Math.max(2, viewportWidth - sideMargin * 2) / (9 / 16);
        const resolvedHeight = Math.max(
          2,
          Math.min(requestedHeight, widthLimitedHeight),
        );
        const resolvedWidth = Math.max(
          2,
          Math.min(
            lensWidthPx ?? resolvedHeight * (9 / 16),
            viewportWidth - sideMargin * 2,
          ),
        );
        gl.uniform2f(uniforms.lensSize, resolvedWidth, resolvedHeight);
        gl.uniform1f(uniforms.lensSideMargin, sideMargin);
        gl.uniform1f(
          uniforms.lensCenterY,
          viewportHeight * clamp(lensCenterYRatio, 0, 1),
        );
        gl.uniform1f(uniforms.lensRadius, Math.max(1, lensRadiusPx));
        gl.uniform1f(
          uniforms.reducedTransparency,
          reducedTransparency.matches ? 1 : 0,
        );
        gl.uniform1f(uniforms.higherContrast, higherContrast.matches ? 1 : 0);
        gl.uniform2f(uniforms.viewport, viewportWidth, viewportHeight);
        gl.drawArrays(gl.TRIANGLES, 0, 3);

        if (!announcedReady) {
          announcedReady = true;
          setRendererState("ready");
        }
      };

      const scheduleDraw = () => {
        if (!frame && !disposed && !contextLost) {
          frame = window.requestAnimationFrame(draw);
        }
      };

      const resize = () => {
        if (!gl || disposed || contextLost) return;

        const bounds = container.getBoundingClientRect();
        viewportWidth = Math.max(1, bounds.width);
        viewportHeight = Math.max(1, bounds.height);
        const dpr = Math.min(Math.max(window.devicePixelRatio || 1, 1), 2);
        const nextWidth = Math.max(1, Math.round(viewportWidth * dpr));
        const nextHeight = Math.max(1, Math.round(viewportHeight * dpr));

        if (canvas.width !== nextWidth || canvas.height !== nextHeight) {
          canvas.width = nextWidth;
          canvas.height = nextHeight;
          gl.viewport(0, 0, nextWidth, nextHeight);
        }

        scheduleDraw();
      };

      const handlePreferenceChange = () => scheduleDraw();
      reducedTransparency.addEventListener("change", handlePreferenceChange);
      higherContrast.addEventListener("change", handlePreferenceChange);
      ancillaryCleanups.push(() => {
        reducedTransparency.removeEventListener(
          "change",
          handlePreferenceChange,
        );
        higherContrast.removeEventListener("change", handlePreferenceChange);
      });

      const unsubscribeProgress = lensProgress.on("change", (value) => {
        // Reduced motion requires no alternate path: this renderer has no
        // autonomous animation and follows the caller's explicit value 1:1.
        currentProgress = clamp(value, 0, 1);
        scheduleDraw();
      });
      ancillaryCleanups.push(unsubscribeProgress);

      if (typeof ResizeObserver !== "undefined") {
        resizeObserver = new ResizeObserver(resize);
        resizeObserver.observe(container);
      }
      window.addEventListener("resize", resize, { passive: true });
      ancillaryCleanups.push(() =>
        window.removeEventListener("resize", resize),
      );

      if (typeof IntersectionObserver !== "undefined") {
        intersectionObserver = new IntersectionObserver(
          ([entry]) => {
            inView = entry?.isIntersecting ?? false;
            if (inView) {
              resize();
              scheduleDraw();
            }
          },
          { rootMargin: "160px 0px" },
        );
        intersectionObserver.observe(container);
      }

      const image = new window.Image();
      textureImage = image;
      image.decoding = "async";
      image.fetchPriority = priority ? "high" : "auto";
      if (!imageSrc.startsWith("data:") && !imageSrc.startsWith("blob:")) {
        image.crossOrigin = "anonymous";
      }

      image.onload = () => {
        if (disposed || contextLost || !gl || !texture) return;

        try {
          imageAspect =
            Math.max(image.naturalWidth, 1) / Math.max(image.naturalHeight, 1);
          gl.activeTexture(gl.TEXTURE0);
          gl.bindTexture(gl.TEXTURE_2D, texture);
          gl.pixelStorei(gl.UNPACK_FLIP_Y_WEBGL, true);
          gl.texImage2D(
            gl.TEXTURE_2D,
            0,
            gl.RGBA,
            gl.RGBA,
            gl.UNSIGNED_BYTE,
            image,
          );
          imageLoaded = true;
          resize();
          scheduleDraw();
        } catch {
          if (!disposed) setRendererState("fallback");
        }
      };

      image.onerror = () => {
        if (!disposed) setRendererState("fallback");
      };

      setRendererState("loading");
      resize();
      image.src = imageSrc;

      return cleanup;
    } catch {
      cleanup();
      setRendererState("fallback");
      return cleanup;
    }
  }, [
    contextRevision,
    imageSrc,
    lensCenterYRatio,
    lensHeightPx,
    lensHeightRatio,
    lensProgress,
    lensRadiusPx,
    lensSideMarginPx,
    lensWidthPx,
    priority,
  ]);

  return (
    <div
      ref={containerRef}
      className={className}
      data-ready={rendererState === "ready" ? "true" : "false"}
      data-renderer-state={rendererState}
      style={{
        position: "relative",
        width: "100%",
        height: "100%",
        minWidth: 1,
        minHeight: 1,
        overflow: "hidden",
        isolation: "isolate",
        backgroundColor: "var(--background, #0b0b0d)",
      }}
    >
      {/* The semantic image stays mounted below the canvas and is the visual
          fallback for unsupported WebGL, CORS failures, and context loss. */}
      <Image
        src={imageSrc}
        alt={alt}
        fill
        priority={priority}
        fetchPriority={priority ? "high" : "auto"}
        unoptimized
        sizes="100vw"
        style={{
          position: "absolute",
          inset: 0,
          zIndex: 0,
          display: "block",
          objectFit: "cover",
        }}
      />
      <canvas
        ref={canvasRef}
        aria-hidden="true"
        data-ready={rendererState === "ready" ? "true" : "false"}
        style={{
          position: "absolute",
          inset: 0,
          zIndex: 1,
          display: "block",
          width: "100%",
          height: "100%",
          pointerEvents: "none",
          opacity: rendererState === "ready" ? 1 : 0,
        }}
      />
    </div>
  );
}

export default CampaignLensShader;
