import {
  ClampToEdgeWrapping,
  DataTexture,
  LinearFilter,
  LinearMipmapLinearFilter,
  RGBAFormat,
  RepeatWrapping,
  SRGBColorSpace,
} from "three";

export interface FitnessPlanetSurfaceMaps {
  color: DataTexture;
  relief: DataTexture;
}

const width = 512;
const height = 256;
let cachedSurface: FitnessPlanetSurfaceMaps | undefined;

export function getFitnessPlanetSurface() {
  cachedSurface ??= createFitnessPlanetSurface();
  return cachedSurface;
}

export function createFitnessPlanetSurface(): FitnessPlanetSurfaceMaps {
  const colorPixels = new Uint8Array(width * height * 4);
  const reliefPixels = new Uint8Array(width * height * 4);

  for (let row = 0; row < height; row += 1) {
    const latitude = (0.5 - (row + 0.5) / height) * Math.PI;
    const latitudeRadius = Math.cos(latitude);
    const y = Math.sin(latitude);

    for (let column = 0; column < width; column += 1) {
      const longitude = ((column + 0.5) / width) * Math.PI * 2;
      const x = latitudeRadius * Math.cos(longitude);
      const z = latitudeRadius * Math.sin(longitude);

      const macro = fractalNoise(x, y, z, 2.1);
      const meso = fractalNoise(x, y, z, 5.2);
      const fine = fractalNoise(x, y, z, 17);
      const micro = valueNoise3(x * 39, y * 39, z * 39);
      const detail = fractalNoise(x, y, z, 23);
      const warp = fractalNoise(x, y, z, 4.4);
      const terrain = macro * 0.55 + meso * 0.25 + fine * 0.15 + micro * 0.05;
      const warpedTerrain = clamp(terrain + (warp - 0.5) * 0.1, 0, 1);
      const continents = smoothstep(0.43, 0.64, warpedTerrain);
      const cloudEdge = smoothstep(0.46, 0.65, meso * 0.58 + fine * 0.42);
      const fineFracture = smoothstep(0.54, 0.8, micro * 0.42 + fine * 0.58);
      const ridgeField = 1 - Math.abs(detail * 2 - 1);
      const ridgeCracks = smoothstep(0.58, 0.83, ridgeField) * continents;
      const iceVeins = Math.max(0, cloudEdge - smoothstep(0.73, 0.87, warpedTerrain)) * (0.28 + fineFracture * 0.72);
      const luminance = clamp(continents * (0.08 + macro * 0.22 + meso * 0.12 + fine * 0.05) + iceVeins * 0.35 + ridgeCracks * 0.18, 0, 1);
      const highIce = clamp(smoothstep(0.59, 0.86, ridgeField) * continents * 0.5 + smoothstep(0.68, 0.9, luminance) * fineFracture * 0.24, 0, 0.62);

      const pixelIndex = (row * width + column) * 4;
      colorPixels[pixelIndex] = Math.round(2 + luminance * 16 + highIce * 30);
      colorPixels[pixelIndex + 1] = Math.round(7 + luminance * 68 + highIce * 95);
      colorPixels[pixelIndex + 2] = Math.round(18 + luminance * 100 + highIce * 108);
      colorPixels[pixelIndex + 3] = 255;

      const relief = Math.round(46 + macro * 76 + meso * 48 + fine * 37 + micro * 24 + ridgeCracks * 18);
      reliefPixels[pixelIndex] = relief;
      reliefPixels[pixelIndex + 1] = relief;
      reliefPixels[pixelIndex + 2] = relief;
      reliefPixels[pixelIndex + 3] = 255;
    }
  }

  return {
    color: configureTexture(new DataTexture(colorPixels, width, height, RGBAFormat), true),
    relief: configureTexture(new DataTexture(reliefPixels, width, height, RGBAFormat), false),
  };
}

function configureTexture(texture: DataTexture, isColor: boolean) {
  texture.wrapS = RepeatWrapping;
  texture.wrapT = ClampToEdgeWrapping;
  texture.magFilter = LinearFilter;
  texture.minFilter = LinearMipmapLinearFilter;
  texture.generateMipmaps = true;
  if (isColor) texture.colorSpace = SRGBColorSpace;
  texture.needsUpdate = true;
  return texture;
}

function fractalNoise(x: number, y: number, z: number, frequency: number) {
  let value = 0;
  let amplitude = 0.5;
  let amplitudeSum = 0;

  for (let octave = 0; octave < 4; octave += 1) {
    value += valueNoise3(x * frequency, y * frequency, z * frequency) * amplitude;
    amplitudeSum += amplitude;
    frequency *= 2.03;
    amplitude *= 0.5;
  }

  return value / amplitudeSum;
}

function valueNoise3(x: number, y: number, z: number) {
  const x0 = Math.floor(x);
  const y0 = Math.floor(y);
  const z0 = Math.floor(z);
  const fx = fade(x - x0);
  const fy = fade(y - y0);
  const fz = fade(z - z0);

  const x00 = lerp(hash3(x0, y0, z0), hash3(x0 + 1, y0, z0), fx);
  const x10 = lerp(hash3(x0, y0 + 1, z0), hash3(x0 + 1, y0 + 1, z0), fx);
  const x01 = lerp(hash3(x0, y0, z0 + 1), hash3(x0 + 1, y0, z0 + 1), fx);
  const x11 = lerp(hash3(x0, y0 + 1, z0 + 1), hash3(x0 + 1, y0 + 1, z0 + 1), fx);

  return lerp(lerp(x00, x10, fy), lerp(x01, x11, fy), fz);
}

function hash3(x: number, y: number, z: number) {
  let value = Math.imul(x, 374761393) + Math.imul(y, 668265263) + Math.imul(z, 2246822519);
  value = Math.imul(value ^ (value >>> 13), 1274126177);
  return ((value ^ (value >>> 16)) >>> 0) / 0xffffffff;
}

function fade(value: number) {
  return value * value * value * (value * (value * 6 - 15) + 10);
}

function lerp(start: number, end: number, amount: number) {
  return start + (end - start) * amount;
}

function smoothstep(start: number, end: number, value: number) {
  const amount = clamp((value - start) / (end - start), 0, 1);
  return amount * amount * (3 - 2 * amount);
}

function clamp(value: number, min: number, max: number) {
  return Math.min(max, Math.max(min, value));
}
