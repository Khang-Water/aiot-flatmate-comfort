"use client";

import { ContactShadows, Html, OrbitControls, RoundedBox } from "@react-three/drei";
import { Canvas, useFrame, useThree } from "@react-three/fiber";
import { Component, useEffect, useMemo, useRef, useState } from "react";
import type { CSSProperties, ReactNode } from "react";
import * as THREE from "three";

import { contextLabels } from "@/lib/labels";
import type { RoomSnapshot } from "@/types/room";

export type SensorOverlay = "none" | "temperature" | "air" | "light" | "noise" | "devices";

interface ApartmentCanvasProps {
  snapshot: RoomSnapshot;
  overlay: SensorOverlay;
  reducedMotion: boolean;
}

const PLAN_WIDTH_M = 6.73;
const PLAN_DEPTH_M = 7.81;
const CEILING_HEIGHT_M = 2.45;
const DOOR_HEIGHT_M = 2.1;
const PLAN_CENTER_X = PLAN_WIDTH_M / 2;
const PLAN_CENTER_Z = PLAN_DEPTH_M / 2;

const outline = [
  [0, 0], [6.05, 0], [6.05, 1.36], [6.73, 1.36], [6.73, 5.24],
  [6.46, 5.24], [6.46, 7.81], [1.42, 7.81], [1.42, 5.83], [0, 5.83],
] as const;

function worldX(planX: number) {
  return planX - PLAN_CENTER_X;
}

function worldZ(planY: number) {
  return planY - PLAN_CENTER_Z;
}

function planPosition(planX: number, planY: number, elevation = 0): [number, number, number] {
  return [worldX(planX), elevation, worldZ(planY)];
}

const residentPlacements: Record<RoomSnapshot["inferred_context"], { labelHeight: number; position: [number, number, number]; rotation: number }> = {
  working: { labelHeight: 1.55, position: planPosition(2.05, 2.42), rotation: Math.PI },
  relaxing: { labelHeight: 1.7, position: planPosition(5.96, 3.65), rotation: -Math.PI / 2 },
  sleeping: { labelHeight: 0.55, position: planPosition(3.99, 6.56, 0.63), rotation: Math.PI / 2 },
  reading_in_bed: { labelHeight: 1.45, position: planPosition(3.8, 6.56, 0.63), rotation: Math.PI / 2 },
  away: { labelHeight: 0, position: [0, -4, 0], rotation: 0 },
};

class WebglErrorBoundary extends Component<{ children: ReactNode }, { failed: boolean }> {
  state = { failed: false };

  static getDerivedStateFromError() {
    return { failed: true };
  }

  render() {
    if (this.state.failed) {
      return (
        <div className="webgl-fallback" role="alert">
          <strong>Không dựng được căn hộ 3D.</strong>
          <span>Bảng trạng thái bên dưới vẫn dùng được. Có thể tải lại trang để thử WebGL lần nữa.</span>
          <button onClick={() => window.location.reload()} type="button">Tải lại mô hình</button>
        </div>
      );
    }
    return this.props.children;
  }
}

function createFloorTexture(kind: "wood" | "tile") {
  const canvas = document.createElement("canvas");
  canvas.width = 512;
  canvas.height = 512;
  const context = canvas.getContext("2d");
  if (!context) return new THREE.CanvasTexture(canvas);

  if (kind === "wood") {
    context.fillStyle = "#c9b08e";
    context.fillRect(0, 0, 512, 512);
    for (let plank = 0; plank < 10; plank += 1) {
      const x = plank * 51.2;
      context.fillStyle = plank % 2 ? "rgba(100, 67, 38, 0.032)" : "rgba(255, 248, 230, 0.04)";
      context.fillRect(x, 0, 51.2, 512);
      context.strokeStyle = "rgba(80, 55, 35, 0.18)";
      context.beginPath();
      context.moveTo(x, 0);
      context.lineTo(x, 512);
      context.stroke();
      const seam = (plank * 137) % 512;
      context.beginPath();
      context.moveTo(x, seam);
      context.lineTo(x + 51.2, seam);
      context.stroke();
    }
  } else {
    context.fillStyle = "#c6cecb";
    context.fillRect(0, 0, 512, 512);
    context.strokeStyle = "rgba(250, 248, 241, 0.82)";
    context.lineWidth = 7;
    for (let line = 0; line <= 512; line += 128) {
      context.beginPath();
      context.moveTo(line, 0);
      context.lineTo(line, 512);
      context.moveTo(0, line);
      context.lineTo(512, line);
      context.stroke();
    }
  }

  const texture = new THREE.CanvasTexture(canvas);
  texture.colorSpace = THREE.SRGBColorSpace;
  texture.wrapS = THREE.RepeatWrapping;
  texture.wrapT = THREE.RepeatWrapping;
  texture.repeat.set(kind === "wood" ? 4.8 : 2.3, kind === "wood" ? 5.5 : 2.3);
  return texture;
}

function useFloorTextures() {
  const textures = useMemo(() => ({ wood: createFloorTexture("wood"), tile: createFloorTexture("tile") }), []);
  useEffect(() => () => Object.values(textures).forEach((texture) => texture.dispose()), [textures]);
  return textures;
}

function FloorOutline() {
  const textures = useFloorTextures();
  const shape = useMemo(() => {
    const result = new THREE.Shape();
    outline.forEach(([planX, planY], index) => {
      const x = worldX(planX);
      const y = -worldZ(planY);
      if (index === 0) result.moveTo(x, y);
      else result.lineTo(x, y);
    });
    result.closePath();
    return result;
  }, []);

  return (
    <>
      <mesh receiveShadow position={[0, 0, 0]} rotation={[-Math.PI / 2, 0, 0]}>
        <shapeGeometry args={[shape]} />
        <meshStandardMaterial color="#d1bc9d" map={textures.wood} roughness={0.9} side={THREE.DoubleSide} />
      </mesh>
      <mesh receiveShadow position={planPosition(0.98, 5.02, 0.012)} rotation={[-Math.PI / 2, 0, 0]}>
        <planeGeometry args={[1.72, 1.42]} />
        <meshStandardMaterial color="#c8d2cf" map={textures.tile} roughness={0.92} />
      </mesh>
    </>
  );
}

function WallSegment({
  base = 0,
  color = "#ece8df",
  from,
  height = CEILING_HEIGHT_M,
  thickness = 0.12,
  to,
}: {
  base?: number;
  color?: string;
  from: [number, number];
  height?: number;
  thickness?: number;
  to: [number, number];
}) {
  const startX = worldX(from[0]);
  const startZ = worldZ(from[1]);
  const endX = worldX(to[0]);
  const endZ = worldZ(to[1]);
  const deltaX = endX - startX;
  const deltaZ = endZ - startZ;
  const length = Math.hypot(deltaX, deltaZ);
  const rotation = -Math.atan2(deltaZ, deltaX);

  return (
    <mesh
      castShadow
      receiveShadow
      position={[(startX + endX) / 2, base + height / 2, (startZ + endZ) / 2]}
      rotation={[0, rotation, 0]}
    >
      <boxGeometry args={[length, height, thickness]} />
      <meshStandardMaterial color={color} roughness={0.94} />
    </mesh>
  );
}

function WindowOpeningX({ x1, x2, planY }: { x1: number; x2: number; planY: number }) {
  const width = x2 - x1;
  const centerX = (x1 + x2) / 2;
  const sill = 0.72;
  const glassHeight = 1.38;
  return (
    <>
      <WallSegment from={[x1, planY]} height={sill} thickness={0.2} to={[x2, planY]} />
      <WallSegment base={sill + glassHeight} from={[x1, planY]} height={CEILING_HEIGHT_M - sill - glassHeight} thickness={0.2} to={[x2, planY]} />
      <group position={planPosition(centerX, planY + 0.015, sill + glassHeight / 2)}>
        <mesh><boxGeometry args={[width, glassHeight, 0.035]} /><meshPhysicalMaterial color="#b9dce3" opacity={0.48} roughness={0.08} transparent transmission={0.22} /></mesh>
        {[-width / 2, 0, width / 2].map((x) => <mesh key={x} position={[x, 0, 0.03]}><boxGeometry args={[0.04, glassHeight + 0.08, 0.06]} /><meshStandardMaterial color="#d9ddd8" metalness={0.24} /></mesh>)}
      </group>
    </>
  );
}

function WindowOpeningZ({ planX, y1, y2 }: { planX: number; y1: number; y2: number }) {
  const depth = y2 - y1;
  const centerY = (y1 + y2) / 2;
  const sill = 0.7;
  const glassHeight = 1.4;
  return (
    <>
      <WallSegment from={[planX, y1]} height={sill} thickness={0.2} to={[planX, y2]} />
      <WallSegment base={sill + glassHeight} from={[planX, y1]} height={CEILING_HEIGHT_M - sill - glassHeight} thickness={0.2} to={[planX, y2]} />
      <group position={planPosition(planX - 0.015, centerY, sill + glassHeight / 2)} rotation={[0, Math.PI / 2, 0]}>
        <mesh><boxGeometry args={[depth, glassHeight, 0.035]} /><meshPhysicalMaterial color="#b9dce3" opacity={0.48} roughness={0.08} transparent transmission={0.22} /></mesh>
        {[-depth / 2, 0, depth / 2].map((x) => <mesh key={x} position={[x, 0, 0.03]}><boxGeometry args={[0.04, glassHeight + 0.08, 0.06]} /><meshStandardMaterial color="#d9ddd8" metalness={0.24} /></mesh>)}
      </group>
    </>
  );
}

function DoorLeaf({ planX, planY, rotation, width = 0.78 }: { planX: number; planY: number; rotation: number; width?: number }) {
  return (
    <group position={planPosition(planX, planY)} rotation={[0, rotation, 0]}>
      <mesh castShadow position={[width / 2, DOOR_HEIGHT_M / 2, 0]}><boxGeometry args={[width, DOOR_HEIGHT_M, 0.055]} /><meshStandardMaterial color="#a47d59" roughness={0.78} /></mesh>
      <mesh position={[width - 0.08, 1.02, 0.045]}><sphereGeometry args={[0.035, 12, 12]} /><meshStandardMaterial color="#b99b68" metalness={0.55} /></mesh>
    </group>
  );
}

function SlidingBedroomDoor() {
  const width = 1.55;
  return (
    <group position={planPosition(5.025, 5.24, DOOR_HEIGHT_M / 2)}>
      {[-width / 4, width / 4].map((x, index) => (
        <group key={x} position={[x, 0, index * 0.035]}>
          <mesh><boxGeometry args={[width / 2 + 0.02, DOOR_HEIGHT_M - 0.08, 0.035]} /><meshPhysicalMaterial color="#c3dcdf" opacity={0.33} roughness={0.12} transparent transmission={0.18} /></mesh>
          <mesh position={[0, 0, 0.025]}><boxGeometry args={[width / 2 + 0.04, 0.045, 0.055]} /><meshStandardMaterial color="#747d79" metalness={0.35} /></mesh>
        </group>
      ))}
      <mesh position={[0, DOOR_HEIGHT_M / 2, 0]}><boxGeometry args={[width + 0.08, 0.045, 0.08]} /><meshStandardMaterial color="#747d79" /></mesh>
    </group>
  );
}

function ApartmentShell() {
  return (
    <>
      <FloorOutline />

      <WallSegment from={[0, 0]} thickness={0.2} to={[0.25, 0]} />
      <WindowOpeningX planY={0} x1={0.25} x2={2.75} />
      <WallSegment from={[2.75, 0]} thickness={0.2} to={[3.55, 0]} />
      <WindowOpeningX planY={0} x1={3.55} x2={5.67} />
      <WallSegment from={[5.67, 0]} thickness={0.2} to={[6.05, 0]} />
      <WallSegment from={[6.05, 0]} thickness={0.2} to={[6.05, 1.36]} />
      <WallSegment from={[6.05, 1.36]} thickness={0.2} to={[6.73, 1.36]} />
      <WallSegment from={[6.73, 1.36]} thickness={0.2} to={[6.73, 5.24]} />
      <WallSegment from={[6.73, 5.24]} thickness={0.2} to={[6.46, 5.24]} />
      <WallSegment from={[6.46, 5.24]} thickness={0.2} to={[6.46, 5.62]} />
      <WindowOpeningZ planX={6.46} y1={5.62} y2={6.85} />
      <WallSegment from={[6.46, 6.85]} thickness={0.2} to={[6.46, 7.81]} />
      <WallSegment from={[1.42, 7.81]} thickness={0.2} to={[1.74, 7.81]} />
      <WallSegment base={DOOR_HEIGHT_M} from={[1.74, 7.81]} height={CEILING_HEIGHT_M - DOOR_HEIGHT_M} thickness={0.2} to={[2.52, 7.81]} />
      <WallSegment from={[2.52, 7.81]} thickness={0.2} to={[6.46, 7.81]} />
      <DoorLeaf planX={2.52} planY={7.72} rotation={2.36} />
      <WallSegment from={[1.42, 5.83]} thickness={0.2} to={[1.42, 7.81]} />
      <WallSegment from={[0, 5.83]} thickness={0.2} to={[1.42, 5.83]} />
      <WallSegment from={[0, 0]} thickness={0.2} to={[0, 5.83]} />

      <WallSegment from={[0, 4.21]} to={[1.96, 4.21]} />
      <WallSegment from={[1.96, 4.21]} to={[1.96, 4.61]} />
      <WallSegment base={DOOR_HEIGHT_M} from={[1.96, 4.61]} height={CEILING_HEIGHT_M - DOOR_HEIGHT_M} to={[1.96, 5.31]} />
      <WallSegment from={[1.96, 5.31]} to={[1.96, 5.83]} />
      <DoorLeaf planX={1.93} planY={5.31} rotation={2.45} width={0.7} />
      <WallSegment from={[1.42, 5.83]} to={[1.96, 5.83]} />
      <WallSegment from={[2.92, 5.2]} to={[2.92, 7.81]} />
      <WallSegment from={[2.92, 5.24]} to={[4.25, 5.24]} />
      <WallSegment base={DOOR_HEIGHT_M} from={[4.25, 5.24]} height={CEILING_HEIGHT_M - DOOR_HEIGHT_M} to={[5.8, 5.24]} />
      <SlidingBedroomDoor />
      <WallSegment from={[5.8, 5.24]} to={[6.46, 5.24]} />

      <WallSegment from={[2.83, 0]} to={[2.83, 1.37]} />
      <WallSegment from={[2.83, 1.37]} to={[2.83, 2.25]} />
      <WallSegment from={[2.83, 1.37]} to={[3.83, 1.37]} />
      <WallSegment from={[5.2, 1.37]} to={[6.05, 1.37]} />
      <WallSegment base={DOOR_HEIGHT_M} from={[3.83, 1.37]} height={CEILING_HEIGHT_M - DOOR_HEIGHT_M} to={[5.2, 1.37]} />
      <group position={planPosition(4.515, 1.37, DOOR_HEIGHT_M / 2)}>
        <mesh><boxGeometry args={[1.37, DOOR_HEIGHT_M - 0.06, 0.035]} /><meshPhysicalMaterial color="#d4e1df" opacity={0.27} roughness={0.15} transparent transmission={0.16} /></mesh>
        <mesh position={[0, -DOOR_HEIGHT_M / 2 + 0.025, 0]}><boxGeometry args={[1.41, 0.05, 0.07]} /><meshStandardMaterial color="#747d79" metalness={0.35} /></mesh>
      </group>

      <RoomLabel position={planPosition(1.45, 3.45, 0.07)}>KITCHEN</RoomLabel>
      <RoomLabel position={planPosition(4.62, 4.45, 0.07)}>LIVING ROOM</RoomLabel>
      <RoomLabel position={planPosition(4.7, 7.2, 0.07)}>BEDROOM</RoomLabel>
      <RoomLabel position={planPosition(1.0, 5.45, 0.07)}>BATHROOM</RoomLabel>
      <RoomLabel position={planPosition(2.16, 7.18, 0.07)}>HALL</RoomLabel>
      <RoomLabel position={planPosition(4.82, 0.82, 0.07)}>CLOSET BALCONY</RoomLabel>
    </>
  );
}

function RoomLabel({ children, position }: { children: ReactNode; position: [number, number, number] }) {
  return <Html center distanceFactor={10} position={position}><span className="scene-room">{children}</span></Html>;
}

function Chair({ position, rotation = 0 }: { position: [number, number, number]; rotation?: number }) {
  return (
    <group position={position} rotation={[0, rotation, 0]}>
      <RoundedBox args={[0.46, 0.12, 0.46]} castShadow position={[0, 0.48, 0]} radius={0.06} smoothness={3}><meshStandardMaterial color="#879e93" roughness={0.86} /></RoundedBox>
      <RoundedBox args={[0.46, 0.55, 0.09]} castShadow position={[0, 0.79, 0.2]} radius={0.05} smoothness={3}><meshStandardMaterial color="#718c80" /></RoundedBox>
      {[-0.18, 0.18].flatMap((x) => [-0.18, 0.18].map((z) => <mesh castShadow key={`${x}-${z}`} position={[x, 0.23, z]}><boxGeometry args={[0.045, 0.46, 0.045]} /><meshStandardMaterial color="#615b52" /></mesh>))}
    </group>
  );
}

function Laptop({ active }: { active: boolean }) {
  return (
    <group position={[0, 0, 0]}>
      <mesh castShadow><boxGeometry args={[0.38, 0.025, 0.27]} /><meshStandardMaterial color="#4d5350" metalness={0.28} /></mesh>
      <mesh castShadow position={[0, 0.16, -0.13]} rotation={[-0.55, 0, 0]}><boxGeometry args={[0.38, 0.27, 0.025]} /><meshStandardMaterial color="#353c39" emissive={active ? "#74a99c" : "#000000"} emissiveIntensity={active ? 0.7 : 0} /></mesh>
    </group>
  );
}

function KitchenDining({ computerOn }: { computerOn: boolean }) {
  const table = planPosition(2.05, 1.93);
  return (
    <group>
      <group position={planPosition(0.51, 1.43)}>
        <RoundedBox args={[0.6, 1.9, 0.7]} castShadow position={[0, 0.95, 0]} radius={0.05} smoothness={3}><meshStandardMaterial color="#d8dad5" metalness={0.12} /></RoundedBox>
        <mesh position={[0.22, 1.0, 0.36]}><boxGeometry args={[0.025, 0.3, 0.025]} /><meshStandardMaterial color="#737b77" /></mesh>
      </group>

      <group position={planPosition(0.5, 3.25)}>
        <mesh castShadow position={[0, 0.45, 0]}><boxGeometry args={[0.6, 0.9, 1.8]} /><meshStandardMaterial color="#c5b59f" /></mesh>
        <mesh castShadow position={[0, 0.93, 0]}><boxGeometry args={[0.66, 0.07, 1.8]} /><meshStandardMaterial color="#525a56" /></mesh>
        <group position={[0, 0.99, 0.35]}>{[-0.16, 0.16].flatMap((x) => [-0.2, 0.2].map((z) => <mesh key={`${x}-${z}`} position={[x, 0, z]}><cylinderGeometry args={[0.11, 0.11, 0.025, 20]} /><meshStandardMaterial color="#252927" /></mesh>))}</group>
      </group>
      <group position={planPosition(1.49, 3.85)}>
        <mesh castShadow position={[0, 0.45, 0]}><boxGeometry args={[1.38, 0.9, 0.6]} /><meshStandardMaterial color="#c5b59f" /></mesh>
        <mesh castShadow position={[0, 0.93, 0]}><boxGeometry args={[1.44, 0.07, 0.66]} /><meshStandardMaterial color="#525a56" /></mesh>
        <mesh position={[-0.43, 0.98, 0]}><boxGeometry args={[0.52, 0.025, 0.38]} /><meshStandardMaterial color="#909b96" /></mesh>
        <mesh castShadow position={[-0.43, 1.15, -0.12]} rotation={[0, 0, Math.PI / 2]}><torusGeometry args={[0.16, 0.022, 10, 22, Math.PI]} /><meshStandardMaterial color="#7c8581" metalness={0.6} /></mesh>
      </group>

      <group position={table}>
        <mesh castShadow position={[0, 0.72, 0]}><cylinderGeometry args={[0.54, 0.54, 0.08, 40]} /><meshStandardMaterial color="#a77f5e" roughness={0.82} /></mesh>
        <mesh castShadow position={[0, 0.36, 0]}><cylinderGeometry args={[0.08, 0.13, 0.68, 20]} /><meshStandardMaterial color="#5b5851" /></mesh>
        <mesh castShadow position={[0, 0.04, 0]}><cylinderGeometry args={[0.34, 0.34, 0.05, 30]} /><meshStandardMaterial color="#5b5851" /></mesh>
        <group position={[0.05, 0.78, -0.05]} rotation={[0, -0.3, 0]}><Laptop active={computerOn} /></group>
      </group>
      <Chair position={planPosition(2.05, 1.43)} rotation={Math.PI} />
      <Chair position={planPosition(2.05, 2.42)} />
      <Chair position={planPosition(1.66, 1.93)} rotation={-Math.PI / 2} />
      <Chair position={planPosition(2.54, 1.93)} rotation={Math.PI / 2} />
    </group>
  );
}

function Sofa({ position }: { position: [number, number, number] }) {
  return (
    <group position={position} rotation={[0, Math.PI / 2, 0]}>
      <RoundedBox args={[2.25, 0.46, 0.9]} castShadow position={[0, 0.38, 0]} radius={0.13} smoothness={4}><meshStandardMaterial color="#c9b49a" roughness={0.9} /></RoundedBox>
      <RoundedBox args={[2.06, 0.58, 0.15]} castShadow position={[0, 0.8, 0.33]} radius={0.07} smoothness={4} rotation={[-0.12, 0, 0]}><meshStandardMaterial color="#bca387" /></RoundedBox>
      {[-0.72, 0, 0.72].map((x) => <RoundedBox args={[0.62, 0.13, 0.62]} castShadow key={x} position={[x, 0.69, -0.08]} radius={0.07} smoothness={4}><meshStandardMaterial color="#dfd0ba" /></RoundedBox>)}
      {[-1.08, 1.08].map((x) => <RoundedBox args={[0.14, 0.55, 0.86]} castShadow key={x} position={[x, 0.55, 0]} radius={0.05} smoothness={4}><meshStandardMaterial color="#bca387" /></RoundedBox>)}
    </group>
  );
}

function Armchair({ position, rotation }: { position: [number, number, number]; rotation: number }) {
  return (
    <group position={position} rotation={[0, rotation, 0]}>
      <RoundedBox args={[0.86, 0.43, 0.84]} castShadow position={[0, 0.36, 0]} radius={0.13} smoothness={4}><meshStandardMaterial color="#d7c4a9" /></RoundedBox>
      <RoundedBox args={[0.72, 0.58, 0.14]} castShadow position={[0, 0.76, 0.3]} radius={0.07} smoothness={4}><meshStandardMaterial color="#c3aa8b" /></RoundedBox>
      {[-0.42, 0.42].map((x) => <RoundedBox args={[0.12, 0.48, 0.8]} castShadow key={x} position={[x, 0.5, 0]} radius={0.05} smoothness={4}><meshStandardMaterial color="#c3aa8b" /></RoundedBox>)}
    </group>
  );
}

function LivingRoom() {
  return (
    <group>
      <Sofa position={planPosition(5.96, 3.65)} />
      <Armchair position={planPosition(4.92, 2.0)} rotation={2.94} />
      <RoundedBox args={[0.52, 0.34, 0.52]} castShadow position={planPosition(4.8, 2.85, 0.2)} radius={0.1} smoothness={4}><meshStandardMaterial color="#9dad9f" /></RoundedBox>
      <group position={planPosition(4.58, 3.65)}>
        <mesh castShadow position={[0, 0.4, 0]}><cylinderGeometry args={[0.34, 0.34, 0.08, 36]} /><meshStandardMaterial color="#9d7655" /></mesh>
        <mesh castShadow position={[0, 0.2, 0]}><cylinderGeometry args={[0.07, 0.1, 0.38, 18]} /><meshStandardMaterial color="#525651" /></mesh>
      </group>
      <group position={planPosition(3.3, 3.65)} rotation={[0, Math.PI / 2, 0]}>
        <mesh castShadow position={[0, 0.34, 0]}><boxGeometry args={[1.05, 0.55, 0.6]} /><meshStandardMaterial color="#80634c" /></mesh>
        <mesh castShadow position={[0, 1.06, -0.28]}><boxGeometry args={[0.96, 0.62, 0.06]} /><meshStandardMaterial color="#242c2a" emissive="#35534c" emissiveIntensity={0.12} /></mesh>
      </group>
    </group>
  );
}

function Bed() {
  return (
    <group position={planPosition(3.99, 6.56)} rotation={[0, Math.PI / 2, 0]}>
      <RoundedBox args={[1.56, 0.28, 1.9]} castShadow position={[0, 0.24, 0]} radius={0.07} smoothness={4}><meshStandardMaterial color="#765a46" /></RoundedBox>
      <RoundedBox args={[1.48, 0.22, 1.8]} castShadow position={[0, 0.47, 0]} radius={0.1} smoothness={4}><meshStandardMaterial color="#eee9de" /></RoundedBox>
      <RoundedBox args={[1.4, 0.1, 1.05]} castShadow position={[0, 0.64, 0.24]} radius={0.06} smoothness={4}><meshStandardMaterial color="#819b8f" /></RoundedBox>
      {[-0.4, 0.4].map((x) => <RoundedBox args={[0.58, 0.13, 0.42]} castShadow key={x} position={[x, 0.68, -0.62]} radius={0.09} smoothness={4}><meshStandardMaterial color="#f7f1e7" /></RoundedBox>)}
      <mesh castShadow position={[0, 0.8, -0.92]}><boxGeometry args={[1.6, 1.05, 0.1]} /><meshStandardMaterial color="#765a46" /></mesh>
    </group>
  );
}

function Bedroom() {
  return (
    <group>
      <Bed />
      {[5.5, 7.53].map((planY, index) => (
        <group key={planY} position={planPosition(3.22, planY)}>
          <RoundedBox args={[0.42, 0.48, 0.34]} castShadow position={[0, 0.24, 0]} radius={0.04} smoothness={3}><meshStandardMaterial color="#9a7558" /></RoundedBox>
          {index === 0 ? <mesh position={[0, 0.5, 0]}><cylinderGeometry args={[0.13, 0.19, 0.3, 22]} /><meshStandardMaterial color="#d5b887" /></mesh> : null}
        </group>
      ))}
      <group position={planPosition(6.0, 7.42)}>
        <RoundedBox args={[0.72, 1.95, 0.58]} castShadow position={[0, 0.975, 0]} radius={0.045} smoothness={3}><meshStandardMaterial color="#9d7b60" /></RoundedBox>
        <mesh position={[0, 1.0, 0.3]}><boxGeometry args={[0.02, 1.7, 0.02]} /><meshStandardMaterial color="#755b46" /></mesh>
      </group>
    </group>
  );
}

function Bathroom() {
  return (
    <group>
      <group position={planPosition(1.0, 5.42)}>
        <RoundedBox args={[1.7, 0.5, 0.7]} castShadow position={[0, 0.28, 0]} radius={0.16} smoothness={4}><meshStandardMaterial color="#f0f0ea" /></RoundedBox>
        <RoundedBox args={[1.48, 0.08, 0.5]} position={[0, 0.48, 0]} radius={0.14} smoothness={4}><meshStandardMaterial color="#c3e0e2" /></RoundedBox>
        <mesh castShadow position={[-0.62, 0.88, 0]} rotation={[0, 0, Math.PI / 2]}><torusGeometry args={[0.18, 0.022, 10, 24, Math.PI]} /><meshStandardMaterial color="#7d8783" metalness={0.62} /></mesh>
      </group>
      <group position={planPosition(0.48, 4.56)} rotation={[0, Math.PI, 0]}>
        <RoundedBox args={[0.42, 0.4, 0.62]} castShadow position={[0, 0.28, 0]} radius={0.15} smoothness={4}><meshStandardMaterial color="#f2f2ec" /></RoundedBox>
        <mesh castShadow position={[0, 0.7, 0.22]}><boxGeometry args={[0.48, 0.66, 0.2]} /><meshStandardMaterial color="#f2f2ec" /></mesh>
      </group>
      <group position={planPosition(1.34, 4.48)}>
        <mesh castShadow position={[0, 0.4, 0]}><boxGeometry args={[0.62, 0.72, 0.46]} /><meshStandardMaterial color="#8ca39c" /></mesh>
        <RoundedBox args={[0.68, 0.11, 0.5]} castShadow position={[0, 0.82, 0]} radius={0.08} smoothness={4}><meshStandardMaterial color="#efefea" /></RoundedBox>
        <mesh position={[0, 1.38, -0.22]}><boxGeometry args={[0.58, 0.75, 0.025]} /><meshStandardMaterial color="#9fc6ce" metalness={0.16} /></mesh>
      </group>
    </group>
  );
}

function HallAndCloset() {
  return (
    <group>
      <group position={planPosition(1.76, 7.19)} rotation={[0, Math.PI / 2, 0]}>
        <RoundedBox args={[0.7, 0.52, 0.3]} castShadow position={[0, 0.26, 0]} radius={0.05} smoothness={3}><meshStandardMaterial color="#98765a" /></RoundedBox>
        {[-0.23, 0, 0.23].map((x) => <mesh key={x} position={[x, 0.3, 0.16]}><boxGeometry args={[0.02, 0.32, 0.02]} /><meshStandardMaterial color="#716050" /></mesh>)}
      </group>
      <group position={planPosition(5.66, 0.74)}>
        <RoundedBox args={[0.58, 1.9, 0.72]} castShadow position={[0, 0.95, 0]} radius={0.04} smoothness={3}><meshStandardMaterial color="#9a785c" /></RoundedBox>
        <mesh position={[0, 0.98, 0.37]}><boxGeometry args={[0.02, 1.65, 0.02]} /><meshStandardMaterial color="#715744" /></mesh>
      </group>
      <Chair position={planPosition(5.06, 0.74)} rotation={-Math.PI / 2} />
    </group>
  );
}

function SceneLabel({ children, position }: { children: ReactNode; position: [number, number, number] }) {
  return <Html center distanceFactor={8} position={position}><span className="scene-device">{children}</span></Html>;
}

function SensorNode({ color, label, labelOffset = [0, 0.5, 0], mountRotation = [0, 0, 0], position, value }: { color: string; label: string; labelOffset?: [number, number, number]; mountRotation?: [number, number, number]; position: [number, number, number]; value: string }) {
  return (
    <group position={position}>
      <group rotation={mountRotation}>
        <mesh castShadow><cylinderGeometry args={[0.09, 0.09, 0.055, 22]} /><meshStandardMaterial color="#f5f2ea" roughness={0.55} /></mesh>
        <mesh position={[0, 0.034, 0]}><cylinderGeometry args={[0.045, 0.045, 0.012, 18]} /><meshBasicMaterial color={color} /></mesh>
      </group>
      <Html center distanceFactor={7} position={labelOffset}>
        <div className="sensor-pin" style={{ "--sensor-color": color } as CSSProperties}><span>{label}</span><strong>{value}</strong></div>
      </Html>
    </group>
  );
}

function ContextSensor({ kind, label, position, rotation = [0, 0, 0], showLabel }: { kind: "contact" | "motion"; label: string; position: [number, number, number]; rotation?: [number, number, number]; showLabel: boolean }) {
  const contact = kind === "contact";
  return (
    <group position={position}>
      <group rotation={rotation}>
        {contact ? (
          <>
            <mesh castShadow position={[-0.055, 0, 0]}><boxGeometry args={[0.08, 0.18, 0.035]} /><meshStandardMaterial color="#f1eee6" /></mesh>
            <mesh castShadow position={[0.055, 0, 0]}><boxGeometry args={[0.04, 0.13, 0.03]} /><meshStandardMaterial color="#d9d8d2" /></mesh>
          </>
        ) : (
          <mesh castShadow><cylinderGeometry args={[0.09, 0.09, 0.045, 24]} /><meshStandardMaterial color="#f1eee6" /></mesh>
        )}
        <mesh position={[contact ? -0.055 : 0, 0.027, contact ? 0.019 : 0]}><sphereGeometry args={[0.012, 10, 10]} /><meshBasicMaterial color="#55b77d" /></mesh>
      </group>
      {showLabel ? <SceneLabel position={[0, 0.3, 0]}>{label}</SceneLabel> : null}
    </group>
  );
}

function Sensors({ overlay, snapshot }: Pick<ApartmentCanvasProps, "overlay" | "snapshot">) {
  const wallStation = planPosition(3.01, 4.45, 1.35);
  const wallMount: [number, number, number] = [0, 0, -Math.PI / 2];
  const showContextLabels = overlay === "devices";
  return (
    <>
      {overlay === "temperature" ? <SensorNode color="#e37b56" label="Trạm môi trường · nhiệt ẩm" mountRotation={wallMount} position={wallStation} value={`${snapshot.environment.temperature_c.toFixed(1)}°C · ${snapshot.environment.humidity_percent.toFixed(0)}%`} /> : null}
      {overlay === "air" ? <SensorNode color="#4f9b73" label="Trạm môi trường · không khí" mountRotation={wallMount} position={wallStation} value={`CO₂ ${snapshot.environment.co2_ppm.toFixed(0)} ppm · PM2.5 ${snapshot.environment.pm25_ug_m3.toFixed(1)} µg/m³`} /> : null}
      {overlay === "light" ? <SensorNode color="#d8aa45" label="Ánh sáng mặt bàn" labelOffset={[-0.55, 0.35, 0]} position={planPosition(2.28, 2.2, 0.79)} value={`${snapshot.environment.ambient_light_lux.toFixed(0)} lux`} /> : null}
      {overlay === "noise" ? <SensorNode color="#8e6cab" label="Trạm môi trường · tiếng ồn" mountRotation={wallMount} position={wallStation} value={`${snapshot.environment.noise_db.toFixed(1)} dB`} /> : null}
      <ContextSensor kind="contact" label="Cửa ra vào" position={planPosition(1.8, 7.7, 1.96)} showLabel={showContextLabels} />
      <ContextSensor kind="contact" label="Cửa sổ phòng ngủ" position={planPosition(6.36, 6.23, 1.45)} rotation={[0, Math.PI / 2, 0]} showLabel={showContextLabels} />
      <ContextSensor kind="motion" label="Chuyển động sảnh" position={planPosition(2.25, 6.65, 2.39)} showLabel={showContextLabels} />
      {/* ponytail: context sensor states are static; connect backend telemetry when occupancy topics exist. */}
    </>
  );
}

function Fan({ active, lightActive, lightBrightness, reducedMotion, speed }: { active: boolean; lightActive: boolean; lightBrightness: number; reducedMotion: boolean; speed: number }) {
  const blades = useRef<THREE.Group>(null);
  useFrame((_, delta) => {
    if (blades.current && active && !reducedMotion) blades.current.rotation.y -= delta * Math.max(speed, 1) * 2.4;
  });
  return (
    <group position={planPosition(4.75, 3.55, 2.3)}>
      <mesh position={[0, 0.08, 0]}><cylinderGeometry args={[0.04, 0.04, 0.18, 14]} /><meshStandardMaterial color="#626a65" /></mesh>
      <group ref={blades}>{[0, Math.PI / 2, Math.PI, Math.PI * 1.5].map((angle) => <mesh key={angle} position={[Math.cos(angle) * 0.32, 0, Math.sin(angle) * 0.32]} rotation={[0, -angle, 0]}><boxGeometry args={[0.58, 0.035, 0.13]} /><meshStandardMaterial color={active ? "#81998d" : "#a5a6a0"} /></mesh>)}</group>
      <mesh><cylinderGeometry args={[0.1, 0.13, 0.1, 18]} /><meshStandardMaterial color="#56615b" /></mesh>
      <mesh position={[0, -0.07, 0]}><cylinderGeometry args={[0.18, 0.15, 0.08, 28]} /><meshStandardMaterial color={lightActive ? "#fff0c7" : "#aaa8a0"} emissive={lightActive ? "#ffd99c" : "#000000"} emissiveIntensity={lightActive ? 0.2 + lightBrightness / 180 : 0} /></mesh>
    </group>
  );
}

function BedroomCurtain({ openPercent }: { openPercent: number }) {
  const openness = THREE.MathUtils.clamp(openPercent / 100, 0, 1);
  const panelDepth = THREE.MathUtils.lerp(0.58, 0.16, openness);
  return (
    <group position={planPosition(6.28, 6.23, 1.45)}>
      {[-1, 1].map((side) => (
        <RoundedBox args={[0.08, 1.85, panelDepth]} castShadow key={side} position={[0, 0, side * (0.61 - panelDepth / 2)]} radius={0.035} smoothness={3}>
          <meshStandardMaterial color="#d4b58f" roughness={0.96} />
        </RoundedBox>
      ))}
    </group>
  );
}

function SmartDevices({ overlay, reducedMotion, snapshot }: ApartmentCanvasProps) {
  const showLabels = overlay === "devices";
  return (
    <>
      <group position={planPosition(6.53, 2.15, 2.13)} rotation={[0, -Math.PI / 2, 0]}>
        <RoundedBox args={[1.15, 0.4, 0.19]} castShadow radius={0.07} smoothness={4}><meshStandardMaterial color={snapshot.devices.ac.power ? "#f4f4ed" : "#b8bab6"} /></RoundedBox>
        <mesh position={[0.45, 0, 0.105]}><sphereGeometry args={[0.025, 12, 12]} /><meshBasicMaterial color={snapshot.devices.ac.power ? "#4fc77f" : "#6c716e"} /></mesh>
        {showLabels ? <SceneLabel position={[0, 0.45, 0]}>Điều hòa · {snapshot.devices.ac.temperature_c}°C</SceneLabel> : null}
      </group>
      <Fan active={snapshot.devices.fan.power} lightActive={snapshot.devices.main_light.power} lightBrightness={snapshot.devices.main_light.brightness_percent} reducedMotion={reducedMotion} speed={snapshot.devices.fan.speed} />
      {showLabels ? <SceneLabel position={planPosition(4.75, 3.55, 2.72)}>Quạt · mức {snapshot.devices.fan.speed} · đèn {snapshot.devices.main_light.brightness_percent}%</SceneLabel> : null}
      <group position={planPosition(3.35, 4.65, 0.42)}>
        <RoundedBox args={[0.48, 0.84, 0.44]} castShadow radius={0.09} smoothness={4}><meshStandardMaterial color={snapshot.devices.air_purifier.power ? "#dbe8e0" : "#b8bbb7"} /></RoundedBox>
        <mesh position={[0, 0.15, 0.23]}><boxGeometry args={[0.27, 0.13, 0.02]} /><meshBasicMaterial color={snapshot.devices.air_purifier.power ? "#55b77d" : "#707773"} /></mesh>
        {showLabels ? <SceneLabel position={[0, 0.76, 0]}>Máy lọc · mức {snapshot.devices.air_purifier.speed}</SceneLabel> : null}
      </group>
      <group position={planPosition(5.05, 4.65, 0.32)}>
        <RoundedBox args={[0.34, 0.64, 0.32]} castShadow radius={0.07} smoothness={4}><meshStandardMaterial color={snapshot.devices.humidity_device.power ? "#d6e7e8" : "#b9bcba"} /></RoundedBox>
        <mesh position={[0, 0.12, 0.17]}><boxGeometry args={[0.2, 0.1, 0.02]} /><meshBasicMaterial color={snapshot.devices.humidity_device.power ? "#54a9bd" : "#717775"} /></mesh>
        {showLabels ? <SceneLabel position={[0, 0.65, 0]}>{snapshot.devices.humidity_device.mode === "humidify" ? "Máy tạo ẩm" : "Máy hút ẩm"} · {snapshot.devices.humidity_device.target_humidity_percent}%</SceneLabel> : null}
      </group>
      <BedroomCurtain openPercent={snapshot.devices.curtain.position_percent} />
      {showLabels ? <SceneLabel position={planPosition(3.22, 5.5, 1.45)}>Đèn đầu giường · {snapshot.devices.bedside_light.brightness_percent}%</SceneLabel> : null}
      {showLabels ? <SceneLabel position={planPosition(6.08, 6.24, 2.05)}>Rèm · mở {snapshot.devices.curtain.position_percent}%</SceneLabel> : null}
      {showLabels ? <SceneLabel position={planPosition(2.05, 1.93, 1.5)}>Máy tính · {snapshot.power.smart_plugs.desk_computer.state === "on" ? "bật" : "tắt"}</SceneLabel> : null}
    </>
  );
}

function ResidentHead({ position }: { position: [number, number, number] }) {
  return (
    <group position={position}>
      <mesh castShadow><sphereGeometry args={[0.115, 20, 20]} /><meshStandardMaterial color="#c98e70" roughness={0.82} /></mesh>
      <mesh castShadow position={[0, 0.07, -0.015]} scale={[1.03, 0.58, 1.02]}><sphereGeometry args={[0.116, 20, 20]} /><meshStandardMaterial color="#3c302b" roughness={0.96} /></mesh>
      <mesh position={[0, -0.005, 0.112]}><sphereGeometry args={[0.018, 10, 10]} /><meshStandardMaterial color="#b9785d" /></mesh>
      {[-0.038, 0.038].map((x) => <mesh key={x} position={[x, 0.025, 0.105]}><sphereGeometry args={[0.009, 8, 8]} /><meshBasicMaterial color="#292624" /></mesh>)}
    </group>
  );
}

function SeatedResident({ seatHeight, working = false }: { seatHeight: number; working?: boolean }) {
  return (
    <group>
      <RoundedBox args={[0.34, 0.46, 0.2]} castShadow position={[0, seatHeight + 0.36, -0.015]} radius={0.08} smoothness={4}><meshStandardMaterial color="#54796f" roughness={0.9} /></RoundedBox>
      <ResidentHead position={[0, seatHeight + 0.72, 0]} />
      {[-0.1, 0.1].map((x) => (
        <group key={x}>
          <RoundedBox args={[0.13, 0.13, 0.38]} castShadow position={[x, seatHeight + 0.04, 0.2]} radius={0.055} smoothness={3}><meshStandardMaterial color="#394e54" /></RoundedBox>
          <RoundedBox args={[0.12, Math.max(0.32, seatHeight - 0.08), 0.12]} castShadow position={[x, Math.max(0.2, seatHeight / 2), 0.38]} radius={0.05} smoothness={3}><meshStandardMaterial color="#394e54" /></RoundedBox>
          <RoundedBox args={[0.13, 0.08, 0.25]} castShadow position={[x, 0.06, 0.47]} radius={0.04} smoothness={3}><meshStandardMaterial color="#3a3835" /></RoundedBox>
        </group>
      ))}
      {[-0.22, 0.22].map((x) => (
        <group key={x}>
          <RoundedBox args={[0.1, 0.32, 0.1]} castShadow position={[x, seatHeight + 0.38, 0.07]} radius={0.045} rotation={[-0.55, 0, 0]} smoothness={3}><meshStandardMaterial color="#c98e70" /></RoundedBox>
          <RoundedBox args={[0.095, 0.1, working ? 0.34 : 0.24]} castShadow position={[x, seatHeight + 0.22, working ? 0.27 : 0.2]} radius={0.04} smoothness={3}><meshStandardMaterial color="#c98e70" /></RoundedBox>
        </group>
      ))}
    </group>
  );
}

function SleepingResident() {
  return (
    <group>
      <ResidentHead position={[0, 0.12, -0.62]} />
      <RoundedBox args={[0.36, 0.2, 0.55]} castShadow position={[0, 0.09, -0.24]} radius={0.09} smoothness={4}><meshStandardMaterial color="#54796f" /></RoundedBox>
      {[-0.1, 0.1].map((x) => <RoundedBox args={[0.13, 0.14, 0.7]} castShadow key={x} position={[x, 0.07, 0.39]} radius={0.055} smoothness={3}><meshStandardMaterial color="#394e54" /></RoundedBox>)}
      {[-0.24, 0.24].map((x) => <RoundedBox args={[0.1, 0.12, 0.48]} castShadow key={x} position={[x, 0.08, -0.18]} radius={0.045} smoothness={3}><meshStandardMaterial color="#c98e70" /></RoundedBox>)}
    </group>
  );
}

function ReadingResident() {
  return (
    <group>
      <RoundedBox args={[0.34, 0.48, 0.2]} castShadow position={[0, 0.43, -0.35]} radius={0.08} rotation={[-0.42, 0, 0]} smoothness={4}><meshStandardMaterial color="#54796f" /></RoundedBox>
      <ResidentHead position={[0, 0.78, -0.52]} />
      {[-0.1, 0.1].map((x) => <RoundedBox args={[0.13, 0.14, 0.78]} castShadow key={x} position={[x, 0.08, 0.18]} radius={0.055} smoothness={3}><meshStandardMaterial color="#394e54" /></RoundedBox>)}
      {[-0.2, 0.2].map((x) => <RoundedBox args={[0.1, 0.1, 0.38]} castShadow key={x} position={[x, 0.44, -0.05]} radius={0.045} rotation={[-0.35, 0, x < 0 ? -0.2 : 0.2]} smoothness={3}><meshStandardMaterial color="#c98e70" /></RoundedBox>)}
      <group position={[0, 0.46, 0.12]} rotation={[-0.25, 0, 0]}>
        {[-0.11, 0.11].map((x) => <mesh castShadow key={x} position={[x, 0, 0]} rotation={[0, x < 0 ? -0.18 : 0.18, 0]}><boxGeometry args={[0.22, 0.025, 0.3]} /><meshStandardMaterial color="#aa664e" roughness={0.88} /></mesh>)}
      </group>
    </group>
  );
}

function Resident({ reducedMotion, snapshot }: Omit<ApartmentCanvasProps, "overlay">) {
  const group = useRef<THREE.Group>(null);
  const context = snapshot.inferred_context;
  const placement = residentPlacements[context];
  const targetVector = useMemo(() => new THREE.Vector3(...placement.position), [placement.position]);
  useFrame((_, delta) => {
    if (!group.current) return;
    const speed = reducedMotion ? 24 : 3.8;
    group.current.position.lerp(targetVector, Math.min(1, delta * speed));
    group.current.rotation.y = THREE.MathUtils.damp(group.current.rotation.y, placement.rotation, speed, delta);
  });
  if (!snapshot.occupancy.room_present) return null;
  return (
    <group ref={group} position={placement.position} rotation={[0, placement.rotation, 0]}>
      {context === "working" ? <SeatedResident seatHeight={0.56} working /> : null}
      {context === "relaxing" ? <SeatedResident seatHeight={0.76} /> : null}
      {context === "sleeping" ? <SleepingResident /> : null}
      {context === "reading_in_bed" ? <ReadingResident /> : null}
      <Html center distanceFactor={8} position={[0, placement.labelHeight, 0]}><span className="scene-label resident-label">{contextLabels[context]}</span></Html>
    </group>
  );
}

function StudioScene(props: ApartmentCanvasProps) {
  const { snapshot } = props;
  const daylight = THREE.MathUtils.clamp(snapshot.environment.ambient_light_lux / 1_300, 0.08, 1.2);
  const background = new THREE.Color("#c7d4d1").lerp(new THREE.Color("#eadfc9"), Math.min(1, daylight));
  return (
    <>
      <color args={[background]} attach="background" />
      <fog args={[background, 13, 23]} attach="fog" />
      <ambientLight intensity={0.3 + daylight * 0.24} />
      <hemisphereLight color="#fff2dc" groundColor="#756b5e" intensity={0.48 + daylight * 0.3} />
      <directionalLight castShadow color="#fff0d2" intensity={0.45 + daylight} position={[-4, 9, 5]} shadow-bias={-0.00035} shadow-camera-bottom={-5} shadow-camera-far={20} shadow-camera-left={-6} shadow-camera-right={6} shadow-camera-top={6} shadow-mapSize={[2048, 2048]} />
      {snapshot.devices.main_light.power ? <pointLight castShadow color="#ffe5b4" decay={2} distance={6} intensity={snapshot.devices.main_light.brightness_percent / 50} position={planPosition(4.75, 3.55, 2.25)} shadow-mapSize={[512, 512]} /> : null}
      {snapshot.devices.bedside_light.power ? <pointLight castShadow color="#ffd8a6" decay={2} distance={3.5} intensity={snapshot.devices.bedside_light.brightness_percent / 44} position={planPosition(3.22, 5.5, 0.95)} shadow-mapSize={[512, 512]} /> : null}

      <ApartmentShell />
      <KitchenDining computerOn={snapshot.power.smart_plugs.desk_computer.state === "on"} />
      <LivingRoom />
      <Bedroom />
      <Bathroom />
      <HallAndCloset />
      <SmartDevices {...props} />
      <Sensors overlay={props.overlay} snapshot={snapshot} />
      <Resident reducedMotion={props.reducedMotion} snapshot={snapshot} />
      <ContactShadows blur={2.2} color="#3a3128" far={3.5} frames={1} opacity={0.28} position={[0, 0.025, 0]} resolution={512} scale={[8, 9]} />

      {/* ponytail: elevations and device mounts are inferred; replace after measured survey or authored BIM/Blender model exists. */}
      <OrbitControls dampingFactor={0.08} enableDamping enablePan maxDistance={15} maxPolarAngle={1.42} minDistance={6} minPolarAngle={0.35} target={[0, 0.45, 0]} />
    </>
  );
}

function ResponsiveCamera() {
  const { camera, size } = useThree();
  useEffect(() => {
    if (!(camera instanceof THREE.PerspectiveCamera)) return;
    const portrait = size.width <= 760 && size.height > size.width;
    const tablet = size.width <= 1200;
    const position: [number, number, number] = portrait ? [8.8, 17, 11.7] : tablet ? [7.1, 14.2, 9.4] : [5.8, 12, 7.7];
    camera.position.set(...position);
    camera.lookAt(0, 0.45, 0);
    camera.fov = portrait ? 54 : tablet ? 47 : 40;
    camera.updateProjectionMatrix();
  }, [camera, size.height, size.width]);
  return null;
}

export default function ApartmentCanvas(props: ApartmentCanvasProps) {
  const [cameraKey, setCameraKey] = useState(0);
  return (
    <div className="apartment-canvas-wrap">
      <WebglErrorBoundary>
        <Canvas
          camera={{ fov: 40, position: [5.8, 12, 7.7] }}
          dpr={[1, 1.65]}
          fallback={<div className="webgl-fallback">WebGL không khả dụng. Dùng bảng trạng thái bên dưới.</div>}
          gl={{ antialias: true, powerPreference: "high-performance" }}
          key={cameraKey}
          onCreated={({ gl }) => {
            gl.toneMapping = THREE.ACESFilmicToneMapping;
            gl.toneMappingExposure = 1.05;
          }}
          shadows
        >
          <ResponsiveCamera />
          <StudioScene {...props} />
        </Canvas>
      </WebglErrorBoundary>
      <div className="scene-hud" aria-hidden="true">
        <span className={props.snapshot.occupancy.room_present ? "occupied" : "away"} />
        <div><strong>{contextLabels[props.snapshot.inferred_context]}</strong><small>{props.snapshot.environment.temperature_c.toFixed(1)}°C · CO₂ {props.snapshot.environment.co2_ppm.toFixed(0)} ppm</small></div>
      </div>
      <div className="scene-compass" aria-hidden="true"><span>B</span></div>
      <div className="scene-instructions" aria-hidden="true">Kéo để xoay · cuộn để thu phóng</div>
      <div className="scene-scale" aria-hidden="true">6,73 × 7,81 m · trần 2,45 m</div>
      <button className="camera-reset" onClick={() => setCameraKey((value) => value + 1)} type="button">Đặt lại góc nhìn</button>
    </div>
  );
}
