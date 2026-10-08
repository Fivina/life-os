import { useMemo } from "react";
import { BackSide, type MeshStandardMaterialParameters } from "three";

import { getFitnessPlanetSurface } from "./fitnessPlanetSurface";

export type OrbitBarbellView = "front" | "three-quarter" | "side";
export type OrbitBarbellVariant = "hero" | "miniature";

export interface OrbitBarbellProps {
  view?: OrbitBarbellView;
  variant?: OrbitBarbellVariant;
  planetRadius?: number;
  axisLength?: number;
  massRadius?: number;
  ringDimensions?: {
    radius?: number;
    tube?: number;
    tilt?: number;
    verticalScale?: number;
  };
  ringEmission?: number;
  cyanIntensity?: number;
  planetMaterial?: Partial<MeshStandardMaterialParameters>;
  assemblySpacing?: number;
  attention?: boolean;
}

const viewRotations: Record<OrbitBarbellView, [number, number, number]> = {
  front: [0, 0, 0],
  "three-quarter": [-0.08, -0.55, -0.12],
  side: [0, Math.PI / 2, 0],
};

const cyan = "#5fd6ff";
const ice = "#a7f0ff";
const attentionRed = "#ff4d57";

export function OrbitBarbell({
  view = "three-quarter",
  variant = "hero",
  planetRadius = 0.91,
  axisLength,
  massRadius = 0.58,
  ringDimensions,
  ringEmission = 0.72,
  cyanIntensity = 1,
  planetMaterial,
  assemblySpacing,
  attention = false,
}: OrbitBarbellProps) {
  const axisSpan = axisLength ?? planetRadius * 5.35;
  const massSpacing = assemblySpacing ?? planetRadius * 1.82;
  const primaryRingRadius = ringDimensions?.radius ?? planetRadius * 2.05;
  const primaryRingTube = ringDimensions?.tube ?? planetRadius * 0.012;
  const primaryRingTilt = ringDimensions?.tilt ?? 0.64;
  const primaryRingVerticalScale = ringDimensions?.verticalScale ?? 0.78;
  const modelScale = variant === "miniature" ? 0.72 : 1;
  const planetSurface = useMemo(getFitnessPlanetSurface, []);
  const barDepth = view === "side" ? 0.18 : planetRadius + 0.045;
  const rootYaw = viewRotations[view][1];
  const alignmentOffsetX = Math.abs(Math.cos(rootYaw)) > 0.2 ? -Math.tan(rootYaw) * barDepth : 0;

  return (
    <group name="FitnessRoot" scale={modelScale} rotation={viewRotations[view]}>
      <group name="PrimaryOrbit" position={[0, 0, -0.08]} rotation={[primaryRingTilt, 0, 0.02]}>
        <mesh name="PrimaryOrbitRing" scale={[1, primaryRingVerticalScale, 1]}>
          <torusGeometry args={[primaryRingRadius, primaryRingTube, 10, 144]} />
          <meshStandardMaterial
            color="#1e7692"
            emissive={cyan}
            emissiveIntensity={ringEmission * cyanIntensity * 1.15}
            metalness={0.72}
            roughness={0.28}
            transparent
            opacity={0.88}
          />
        </mesh>
        <mesh name="PrimaryOrbitInnerTrace" scale={[1, primaryRingVerticalScale, 1]} position={[0, 0, -0.025]}>
          <torusGeometry args={[primaryRingRadius * 0.94, primaryRingTube * 0.34, 8, 128]} />
          <meshBasicMaterial color={ice} transparent opacity={0.58 * cyanIntensity} />
        </mesh>
      </group>
      <group name="SecondaryOrbit" position={[0, 0, -0.16]} rotation={[-0.68, 0.08, -0.18]}>
        <mesh name="SecondaryOrbitTrack" scale={[1, 0.52, 1]}>
          <torusGeometry args={[planetRadius * 1.78, primaryRingTube * 0.28, 8, 144]} />
          <meshBasicMaterial color="#5bc9e9" transparent opacity={0.48 * cyanIntensity} toneMapped={false} />
        </mesh>
      </group>
      <group name="TertiaryOrbit" position={[0, 0, -0.22]} rotation={[0.78, -0.13, 0.23]}>
        <mesh name="TertiaryOrbitTrace" scale={[1, 0.28, 1]}>
          <torusGeometry args={[planetRadius * 1.92, primaryRingTube * 0.19, 7, 160]} />
          <meshBasicMaterial color="#5fc5e3" transparent opacity={0.28 * cyanIntensity} toneMapped={false} />
        </mesh>
      </group>

      <group name="PlanetCore">
        <mesh name="PlanetSurface">
          <sphereGeometry args={[planetRadius, 96, 64]} />
          <meshStandardMaterial
            color="#ffffff"
            map={planetSurface.color}
            bumpMap={planetSurface.relief}
            bumpScale={planetRadius * 0.038}
            emissive="#0c3449"
            emissiveMap={planetSurface.color}
            emissiveIntensity={0.11}
            metalness={0.06}
            roughness={0.94}
            {...planetMaterial}
          />
        </mesh>
        <mesh name="PlanetAtmosphere" scale={1.025}>
          <sphereGeometry args={[planetRadius, 48, 36]} />
          <meshBasicMaterial color="#4bcaff" side={BackSide} transparent opacity={0.29 * cyanIntensity} />
        </mesh>
        <mesh name="PlanetAtmosphereOuter" scale={1.055}>
          <sphereGeometry args={[planetRadius, 48, 36]} />
          <meshBasicMaterial color="#168bb8" side={BackSide} transparent opacity={0.08 * cyanIntensity} />
        </mesh>
      </group>

      <group name="CentralAxis" position={[alignmentOffsetX, 0, barDepth]}>
        <mesh name="AxisSleeve" rotation={[0, 0, Math.PI / 2]}>
          <cylinderGeometry args={[0.026, 0.026, axisSpan, 32]} />
          <meshStandardMaterial color="#315a70" metalness={0.78} roughness={0.24} />
        </mesh>
        <mesh name="AxisLightLine" position={[0, 0.012, 0.03]} rotation={[0, 0, Math.PI / 2]}>
          <cylinderGeometry args={[0.007, 0.007, axisSpan * 0.98, 12]} />
          <meshBasicMaterial color={cyan} toneMapped={false} />
        </mesh>
        {([-1, 1] as const).map((side) => (
          <mesh key={side} name={side < 0 ? "AxisEndLeft" : "AxisEndRight"} position={[side * axisSpan * 0.48, 0, 0]} rotation={[0, 0, Math.PI / 2]}>
            <cylinderGeometry args={[0.043, 0.043, 0.075, 32]} />
            <meshStandardMaterial color="#29495b" metalness={0.86} roughness={0.25} />
          </mesh>
        ))}
      </group>

      <MassAssembly
        name="LeftMassAssembly"
        ringName="LeftRingElements"
        side={-1}
        spacing={massSpacing}
        depth={barDepth}
        alignmentOffsetX={alignmentOffsetX}
        radius={massRadius}
        cyanIntensity={cyanIntensity}
        attention={attention}
      />
      <MassAssembly
        name="RightMassAssembly"
        ringName="RightRingElements"
        side={1}
        spacing={massSpacing}
        depth={barDepth}
        alignmentOffsetX={alignmentOffsetX}
        radius={massRadius}
        cyanIntensity={cyanIntensity}
        attention={attention}
      />

      {attention ? (
        <group name="AttentionAccents">
          <mesh name="AttentionSignalNode" position={[alignmentOffsetX + massSpacing + massRadius * 0.78, massRadius * 0.64, barDepth + 0.255]}>
            <sphereGeometry args={[0.035, 16, 12]} />
            <meshBasicMaterial color={attentionRed} />
          </mesh>
          <mesh
            name="AttentionEdgeSegment"
            position={[alignmentOffsetX + massSpacing, 0, barDepth + 0.225]}
            rotation={[0, 0, Math.PI / 5]}
          >
            <torusGeometry args={[massRadius * 1.05, 0.018, 8, 40, Math.PI * 0.3]} />
            <meshStandardMaterial color={attentionRed} emissive={attentionRed} emissiveIntensity={0.7} />
          </mesh>
        </group>
      ) : null}

      <group name="MoonAnchors">
        <group name="MoonAnchorTraining" position={[-planetRadius * 1.26, planetRadius * 1.24, 0.28]} />
        <group name="MoonAnchorNutrition" position={[planetRadius * 1.28, planetRadius * 1.15, -0.22]} />
        <group name="MoonAnchorRecovery" position={[-planetRadius * 1.3, -planetRadius * 1.22, -0.2]} />
        <group name="MoonAnchorBody" position={[planetRadius * 1.31, -planetRadius * 1.16, 0.24]} />
      </group>
    </group>
  );
}

interface MassAssemblyProps {
  name: string;
  ringName: string;
  side: -1 | 1;
  spacing: number;
  depth: number;
  alignmentOffsetX: number;
  radius: number;
  cyanIntensity: number;
  attention: boolean;
}

function MassAssembly({ name, ringName, side, spacing, depth, alignmentOffsetX, radius, cyanIntensity, attention }: MassAssemblyProps) {
  return (
    <group name={name} position={[alignmentOffsetX + side * spacing, 0, depth]}>
      <group name={ringName}>
        <AxialPlate name={`${name}InnerPlate`} side={side} offset={-side * radius * 0.3} radius={radius * 0.76} thickness={radius * 0.12} cyanIntensity={cyanIntensity} brightRim={side < 0} />
        <AxialPlate name={`${name}CenterPlate`} side={side} offset={0} radius={radius * 0.96} thickness={radius * 0.14} cyanIntensity={cyanIntensity} />
        <AxialPlate name={`${name}OuterPlate`} side={side} offset={side * radius * 0.3} radius={radius * 0.86} thickness={radius * 0.16} cyanIntensity={cyanIntensity} brightRim />
        <mesh name={`${name}InnerHub`} rotation={[0, 0, Math.PI / 2]}>
          <cylinderGeometry args={[radius * 0.24, radius * 0.24, radius * 0.3, 40]} />
          <meshStandardMaterial color="#1e4b61" emissive={ice} emissiveIntensity={0.11 * cyanIntensity} metalness={0.82} roughness={0.24} />
        </mesh>
        {attention && side > 0 ? (
          <mesh name="AttentionMassTint" rotation={[0, Math.PI / 2, 0]} position={[radius * 0.35, 0, 0]}>
            <torusGeometry args={[radius * 0.9, radius * 0.018, 8, 48, Math.PI * 0.28]} />
            <meshStandardMaterial color={attentionRed} emissive={attentionRed} emissiveIntensity={0.7} />
          </mesh>
        ) : null}
      </group>
    </group>
  );
}

interface AxialPlateProps {
  name: string;
  side: -1 | 1;
  offset: number;
  radius: number;
  thickness: number;
  cyanIntensity: number;
  brightRim?: boolean;
}

function AxialPlate({ name, side, offset, radius, thickness, cyanIntensity, brightRim = false }: AxialPlateProps) {
  const faceX = offset + thickness / 2 + 0.003;

  return (
    <group name={name}>
      <mesh position={[offset, 0, 0]} rotation={[0, 0, Math.PI / 2]}>
        <cylinderGeometry args={[radius, radius * 0.94, thickness, 64, 1]} />
        <meshStandardMaterial
          color={brightRim ? "#244e64" : "#163b50"}
          emissive="#0a3043"
          emissiveIntensity={0.16 * cyanIntensity}
          metalness={0.86}
          roughness={0.28}
        />
      </mesh>
      <mesh position={[faceX, 0, 0]} rotation={[0, Math.PI / 2, 0]}>
        <torusGeometry args={[radius * 0.91, radius * (brightRim ? 0.032 : 0.021), 10, 64]} />
        <meshStandardMaterial
          color={brightRim ? "#5bb4cd" : "#28647c"}
          emissive={brightRim ? cyan : "#0d607c"}
          emissiveIntensity={(brightRim ? 0.72 : 0.26) * cyanIntensity}
          metalness={0.66}
          roughness={0.25}
        />
      </mesh>
      <mesh position={[faceX + side * 0.002, 0, 0]} rotation={[0, Math.PI / 2, 0]}>
        <torusGeometry args={[radius * 0.68, radius * 0.009, 6, 64]} />
        <meshBasicMaterial color={ice} toneMapped={false} transparent opacity={brightRim ? 0.72 * cyanIntensity : 0.36 * cyanIntensity} />
      </mesh>
    </group>
  );
}
