"use client";

import { ContactShadows, Grid, Html, OrbitControls, RoundedBox } from "@react-three/drei";
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
          <span>Bảng trạng thái bên dưới vẫn dùng được. Có thể tải lại trang để thử khởi tạo WebGL lần nữa.</span>
          <button onClick={() => window.location.reload()} type="button">Tải lại mô hình</button>
        </div>
      );
    }
    return this.props.children;
  }
}

const residentPositions: Record<RoomSnapshot["inferred_context"], [number, number, number]> = {
  working: [0.1, 0.58, -2.05],
  relaxing: [-0.35, 0.64, 1.85],
  sleeping: [-3.15, 0.84, -1.8],
  reading_in_bed: [-3.15, 0.88, -1.75],
  away: [0, -3, 0],
};

function kelvinColor(kelvin: number): string {
  if (kelvin < 3300) return "#ffd0a3";
  if (kelvin < 4600) return "#fff1d2";
  return "#dcecff";
}

function createSurfaceTexture(kind: "wood" | "stone" | "tile") {
  const canvas = document.createElement("canvas");
  canvas.width = 512;
  canvas.height = 512;
  const context = canvas.getContext("2d");
  if (!context) return new THREE.CanvasTexture(canvas);

  if (kind === "wood") {
    context.fillStyle = "#cdbb9f";
    context.fillRect(0, 0, 512, 512);
    for (let row = 0; row < 8; row += 1) {
      const y = row * 64;
      context.fillStyle = row % 2 ? "rgba(96, 69, 43, 0.035)" : "rgba(255, 250, 235, 0.045)";
      context.fillRect(0, y, 512, 64);
      context.strokeStyle = "rgba(82, 59, 38, 0.18)";
      context.beginPath();
      context.moveTo(0, y + 0.5);
      context.lineTo(512, y + 0.5);
      context.stroke();
      const seam = (row * 137) % 512;
      context.beginPath();
      context.moveTo(seam, y);
      context.lineTo(seam, y + 64);
      context.stroke();
      for (let grain = 0; grain < 5; grain += 1) {
        context.strokeStyle = "rgba(83, 57, 34, 0.045)";
        context.beginPath();
        const grainY = y + 9 + grain * 11;
        context.moveTo(0, grainY);
        context.bezierCurveTo(140, grainY + 4, 340, grainY - 5, 512, grainY + 2);
        context.stroke();
      }
    }
  } else if (kind === "tile") {
    context.fillStyle = "#b7c7c3";
    context.fillRect(0, 0, 512, 512);
    context.strokeStyle = "rgba(244, 244, 235, 0.72)";
    context.lineWidth = 7;
    for (let line = 0; line <= 512; line += 128) {
      context.beginPath();
      context.moveTo(line, 0);
      context.lineTo(line, 512);
      context.moveTo(0, line);
      context.lineTo(512, line);
      context.stroke();
    }
  } else {
    context.fillStyle = "#b9ad9a";
    context.fillRect(0, 0, 512, 512);
    for (let dot = 0; dot < 180; dot += 1) {
      const x = (dot * 83) % 512;
      const y = (dot * 197) % 512;
      const shade = dot % 3 === 0 ? "rgba(70, 79, 75, 0.13)" : "rgba(255, 250, 240, 0.2)";
      context.fillStyle = shade;
      context.fillRect(x, y, 2 + (dot % 3), 2 + (dot % 2));
    }
  }

  const texture = new THREE.CanvasTexture(canvas);
  texture.colorSpace = THREE.SRGBColorSpace;
  texture.wrapS = THREE.RepeatWrapping;
  texture.wrapT = THREE.RepeatWrapping;
  texture.anisotropy = 4;
  texture.repeat.set(kind === "wood" ? 5 : 4, kind === "wood" ? 3.5 : 4);
  return texture;
}

function useSurfaceTextures() {
  const textures = useMemo(() => ({
    wood: createSurfaceTexture("wood"),
    stone: createSurfaceTexture("stone"),
    tile: createSurfaceTexture("tile"),
  }), []);

  useEffect(() => () => Object.values(textures).forEach((texture) => texture.dispose()), [textures]);
  return textures;
}

function Wall({ position, size }: { position: [number, number, number]; size: [number, number, number] }) {
  return (
    <mesh castShadow receiveShadow position={position}>
      <boxGeometry args={size} />
      <meshStandardMaterial color="#eee9df" roughness={0.92} />
    </mesh>
  );
}

function Trim({ position, size }: { position: [number, number, number]; size: [number, number, number] }) {
  return (
    <mesh castShadow position={position}>
      <boxGeometry args={size} />
      <meshStandardMaterial color="#d8d0c2" roughness={0.78} />
    </mesh>
  );
}

function Door({ position, rotation = 0 }: { position: [number, number, number]; rotation?: number }) {
  return (
    <group position={position} rotation={[0, rotation, 0]}>
      <RoundedBox castShadow args={[0.88, 2.35, 0.08]} radius={0.035} smoothness={3} position={[0.44, 1.175, 0]}>
        <meshStandardMaterial color="#9b7657" roughness={0.72} />
      </RoundedBox>
      {[0.67, 1.68].map((y) => (
        <mesh key={y} position={[0.44, y, 0.046]}>
          <boxGeometry args={[0.62, 0.015, 0.012]} />
          <meshStandardMaterial color="#75543c" />
        </mesh>
      ))}
      <mesh castShadow position={[0.77, 1.14, 0.09]} rotation={[Math.PI / 2, 0, 0]}>
        <sphereGeometry args={[0.045, 16, 16]} />
        <meshStandardMaterial color="#a98752" metalness={0.68} roughness={0.28} />
      </mesh>
    </group>
  );
}

function Plant({ position, scale = 1 }: { position: [number, number, number]; scale?: number }) {
  return (
    <group position={position} scale={scale}>
      <mesh castShadow position={[0, 0.2, 0]}>
        <cylinderGeometry args={[0.18, 0.13, 0.4, 18]} />
        <meshStandardMaterial color="#a86f4f" roughness={0.92} />
      </mesh>
      {[0, 1, 2, 3, 4].map((leaf) => {
        const angle = leaf * 1.27;
        return (
          <mesh castShadow key={leaf} position={[Math.cos(angle) * 0.13, 0.55 + (leaf % 2) * 0.12, Math.sin(angle) * 0.13]} rotation={[0.35, -angle, leaf % 2 ? -0.65 : 0.65]}>
            <sphereGeometry args={[0.1, 14, 12]} />
            <meshStandardMaterial color={leaf % 2 ? "#52785d" : "#64896b"} roughness={0.9} />
          </mesh>
        );
      })}
    </group>
  );
}

function SceneLabel({ children, position, kind = "room" }: {
  children: ReactNode;
  position: [number, number, number];
  kind?: "room" | "device";
}) {
  return (
    <Html center distanceFactor={kind === "room" ? 11 : 8} position={position}>
      <span className={`scene-${kind}`}>{children}</span>
    </Html>
  );
}

function SensorNode({ label, value, position, color }: {
  label: string;
  value: string;
  position: [number, number, number];
  color: string;
}) {
  return (
    <group position={position}>
      <mesh castShadow>
        <cylinderGeometry args={[0.11, 0.11, 0.055, 24]} />
        <meshStandardMaterial color="#f5f2ea" metalness={0.08} roughness={0.55} />
      </mesh>
      <mesh position={[0, 0.035, 0]}>
        <cylinderGeometry args={[0.052, 0.052, 0.012, 18]} />
        <meshBasicMaterial color={color} />
      </mesh>
      <Html center distanceFactor={7} position={[0, 0.55, 0]}>
        <div className="sensor-pin" style={{ "--sensor-color": color } as CSSProperties}>
          <span>{label}</span>
          <strong>{value}</strong>
        </div>
      </Html>
    </group>
  );
}

function Resident({ snapshot, reducedMotion }: Omit<ApartmentCanvasProps, "overlay">) {
  const group = useRef<THREE.Group>(null);
  const target = residentPositions[snapshot.inferred_context];
  const targetVector = useMemo(() => new THREE.Vector3(...target), [target]);
  const isSleeping = snapshot.inferred_context === "sleeping";
  const isReading = snapshot.inferred_context === "reading_in_bed";
  const isSeated = snapshot.inferred_context === "working" || snapshot.inferred_context === "relaxing";
  const targetRotation = isSleeping ? Math.PI / 2 : isReading ? Math.PI / 3.25 : 0;
  const targetYaw = snapshot.inferred_context === "relaxing" ? -Math.PI / 2 : 0;

  useFrame(({ clock }, delta) => {
    if (!group.current) return;
    group.current.position.lerp(targetVector, Math.min(1, delta * (reducedMotion ? 20 : 3.5)));
    group.current.rotation.z = THREE.MathUtils.lerp(
      group.current.rotation.z,
      targetRotation,
      Math.min(1, delta * 4),
    );
    group.current.rotation.y = THREE.MathUtils.lerp(
      group.current.rotation.y,
      targetYaw,
      Math.min(1, delta * 4),
    );
    if (!reducedMotion && !isSleeping) {
      group.current.position.y = target[1] + Math.sin(clock.elapsedTime * 2.3) * 0.025;
    }
  });

  if (!snapshot.occupancy.room_present) return null;

  return (
    <group ref={group} position={target}>
      <mesh castShadow position={[0, 0.65, 0]}>
        <sphereGeometry args={[0.21, 24, 24]} />
        <meshStandardMaterial color="#7c4e39" />
      </mesh>
      <mesh castShadow position={[-0.03, 0.8, -0.06]} rotation={[0.2, 0, 0]}>
        <sphereGeometry args={[0.22, 20, 18, 0, Math.PI * 2, 0, Math.PI / 2]} />
        <meshStandardMaterial color="#302d29" roughness={0.95} />
      </mesh>
      <mesh castShadow position={[0, 0.17, 0]}>
        <capsuleGeometry args={[0.23, 0.55, 8, 16]} />
        <meshStandardMaterial color={isReading ? "#c36b4f" : "#4d7861"} />
      </mesh>
      {[-0.13, 0.13].map((x) => (
        <mesh castShadow key={x} position={[x, isSeated ? -0.3 : -0.43, isSeated ? 0.17 : 0]} rotation={[isSeated ? -0.75 : 0, 0, 0]}>
          <capsuleGeometry args={[0.075, 0.4, 6, 12]} />
          <meshStandardMaterial color="#3d4b45" />
        </mesh>
      ))}
      {[-0.27, 0.27].map((x) => (
        <mesh castShadow key={x} position={[x, 0.2, isReading ? 0.12 : 0]} rotation={[isReading ? -0.8 : 0, 0, x < 0 ? -0.28 : 0.28]}>
          <capsuleGeometry args={[0.055, 0.38, 6, 12]} />
          <meshStandardMaterial color="#8b5943" />
        </mesh>
      ))}
      {isReading ? (
        <group position={[0, 0.03, 0.32]} rotation={[0.05, 0, 0]}>
          {[-0.13, 0.13].map((x) => (
            <mesh castShadow key={x} position={[x, 0, 0]} rotation={[0, x < 0 ? 0.18 : -0.18, 0]}>
              <boxGeometry args={[0.25, 0.025, 0.34]} />
              <meshStandardMaterial color="#d9c48d" roughness={0.85} />
            </mesh>
          ))}
        </group>
      ) : null}
      <Html center distanceFactor={8} position={[0, 1.12, 0]}>
        <span className="scene-label resident-label">{contextLabels[snapshot.inferred_context]}</span>
      </Html>
    </group>
  );
}

function Bed() {
  return (
    <group position={[-3.2, 0, -1.8]}>
      <RoundedBox castShadow receiveShadow args={[1.75, 0.28, 2.18]} radius={0.08} smoothness={4} position={[0, 0.25, 0]}>
        <meshStandardMaterial color="#725744" />
      </RoundedBox>
      <RoundedBox castShadow args={[1.62, 0.24, 2.02]} radius={0.12} smoothness={4} position={[0, 0.49, 0]}>
        <meshStandardMaterial color="#ece7dc" />
      </RoundedBox>
      <RoundedBox castShadow args={[1.48, 0.11, 1.3]} radius={0.08} smoothness={4} position={[0, 0.66, 0.24]}>
        <meshStandardMaterial color="#7d9a8c" roughness={0.95} />
      </RoundedBox>
      {[-0.43, 0.43].map((x) => (
        <RoundedBox castShadow args={[0.62, 0.14, 0.44]} key={x} radius={0.1} smoothness={4} position={[x, 0.7, -0.69]}>
          <meshStandardMaterial color="#f5efe5" />
        </RoundedBox>
      ))}
      <mesh castShadow position={[0, 0.82, -1.04]}>
        <boxGeometry args={[1.82, 1.18, 0.12]} />
        <meshStandardMaterial color="#725744" />
      </mesh>
      <group position={[-1.17, 0, -0.78]}>
        <mesh castShadow position={[0, 0.36, 0]}><boxGeometry args={[0.52, 0.55, 0.48]} /><meshStandardMaterial color="#98755a" /></mesh>
      </group>
    </group>
  );
}

function Workstation({ computerOn, monitorOn }: { computerOn: boolean; monitorOn: boolean }) {
  return (
    <group position={[0.2, 0, -2.35]}>
      <mesh castShadow position={[0, 0.76, 0]}><boxGeometry args={[1.4, 0.09, 0.7]} /><meshStandardMaterial color="#8c684e" /></mesh>
      {[-0.58, 0.58].flatMap((x) => [-0.25, 0.25].map((z) => (
        <mesh castShadow key={`${x}-${z}`} position={[x, 0.37, z]}><boxGeometry args={[0.07, 0.74, 0.07]} /><meshStandardMaterial color="#4c4943" /></mesh>
      )))}
      <mesh castShadow position={[0, 1.26, -0.14]}><boxGeometry args={[0.9, 0.54, 0.055]} /><meshStandardMaterial color="#1e2928" emissive="#4d8575" emissiveIntensity={monitorOn ? 0.8 : 0.02} /></mesh>
      {monitorOn ? (
        <group position={[0, 1.26, -0.108]}>
          <mesh position={[-0.21, 0.07, 0]}><planeGeometry args={[0.32, 0.25]} /><meshBasicMaterial color="#8fc5b6" /></mesh>
          {[0.12, 0.02, -0.08].map((y, index) => <mesh key={y} position={[0.23, y, 0.002]}><planeGeometry args={[0.25 - index * 0.04, 0.025]} /><meshBasicMaterial color={index === 0 ? "#d6e6cf" : "#79a99e"} /></mesh>)}
        </group>
      ) : null}
      <mesh castShadow position={[0, 0.96, -0.14]}><boxGeometry args={[0.08, 0.28, 0.08]} /><meshStandardMaterial color="#3e4542" /></mesh>
      <mesh castShadow position={[0, 0.83, 0.12]}><boxGeometry args={[0.65, 0.025, 0.22]} /><meshStandardMaterial color="#d5d0c6" /></mesh>
      <mesh castShadow position={[0.48, 0.84, 0.12]}><boxGeometry args={[0.16, 0.035, 0.22]} /><meshStandardMaterial color="#393d3c" /></mesh>
      <group position={[-0.49, 0.88, 0.12]}>
        <mesh castShadow><cylinderGeometry args={[0.09, 0.075, 0.18, 18]} /><meshStandardMaterial color="#d6c7ad" /></mesh>
        <mesh castShadow position={[0.1, 0.03, 0]} rotation={[Math.PI / 2, 0, 0]}><torusGeometry args={[0.065, 0.018, 8, 18, Math.PI * 1.55]} /><meshStandardMaterial color="#d6c7ad" /></mesh>
      </group>
      <group position={[0.48, 0.39, -0.03]}>
        <RoundedBox castShadow args={[0.3, 0.66, 0.48]} radius={0.045} smoothness={4}><meshStandardMaterial color="#252c2a" /></RoundedBox>
        {[0.15, -0.08].map((y) => <mesh key={y} position={[0, y, 0.245]} rotation={[Math.PI / 2, 0, 0]}><torusGeometry args={[0.075, 0.012, 8, 24]} /><meshStandardMaterial color="#69736e" /></mesh>)}
        <mesh position={[0.09, 0.24, 0.245]}><sphereGeometry args={[0.018, 12, 12]} /><meshBasicMaterial color={computerOn ? "#53d58a" : "#666c69"} /></mesh>
      </group>
      <group position={[0, 0, 0.72]}>
        <mesh castShadow position={[0, 0.48, 0]}><RoundedBox args={[0.52, 0.12, 0.52]} radius={0.08} smoothness={4}><meshStandardMaterial color="#a3775f" /></RoundedBox></mesh>
        <mesh castShadow position={[0, 0.9, 0.22]} rotation={[-0.12, 0, 0]}><RoundedBox args={[0.55, 0.68, 0.12]} radius={0.07} smoothness={4}><meshStandardMaterial color="#a3775f" /></RoundedBox></mesh>
        <mesh castShadow position={[0, 0.24, 0]}><cylinderGeometry args={[0.045, 0.045, 0.45, 12]} /><meshStandardMaterial color="#454946" /></mesh>
        <mesh castShadow position={[0, 0.04, 0]}><cylinderGeometry args={[0.33, 0.33, 0.045, 20]} /><meshStandardMaterial color="#454946" /></mesh>
      </group>
    </group>
  );
}

function LivingRoom() {
  return (
    <group>
      <RoundedBox receiveShadow args={[3.35, 0.045, 2.25]} radius={0.08} smoothness={3} position={[0.65, 0.025, 1.85]}><meshStandardMaterial color="#b96f51" roughness={1} /></RoundedBox>
      <mesh receiveShadow position={[0.65, 0.052, 1.85]} rotation={[-Math.PI / 2, 0, 0]}><ringGeometry args={[0.66, 0.7, 48]} /><meshBasicMaterial color="#d8a07c" transparent opacity={0.72} /></mesh>
      <group position={[-0.45, 0, 1.85]} rotation={[0, -Math.PI / 2, 0]}>
        <RoundedBox castShadow args={[2.25, 0.48, 0.82]} radius={0.16} smoothness={4} position={[0, 0.42, 0]}><meshStandardMaterial color="#d3c0a5" /></RoundedBox>
        <RoundedBox castShadow args={[2.05, 0.62, 0.18]} radius={0.08} smoothness={4} position={[0, 0.82, 0.28]} rotation={[-0.14, 0, 0]}><meshStandardMaterial color="#c5ad8d" /></RoundedBox>
        {[-0.72, 0, 0.72].map((x) => <RoundedBox castShadow args={[0.62, 0.14, 0.62]} key={x} radius={0.08} smoothness={4} position={[x, 0.72, -0.08]}><meshStandardMaterial color="#e0cfb7" /></RoundedBox>)}
        {[-1.08, 1.08].map((x) => <RoundedBox castShadow args={[0.15, 0.55, 0.8]} key={x} radius={0.06} smoothness={4} position={[x, 0.55, 0]}><meshStandardMaterial color="#c5ad8d" /></RoundedBox>)}
      </group>
      <group position={[0.75, 0, 1.85]} rotation={[0, Math.PI / 2, 0]}>
        <RoundedBox castShadow args={[1.22, 0.12, 0.62]} radius={0.09} smoothness={4} position={[0, 0.43, 0]}><meshStandardMaterial color="#a77c59" /></RoundedBox>
        {[-0.48, 0.48].flatMap((x) => [-0.2, 0.2].map((z) => <mesh castShadow key={`${x}-${z}`} position={[x, 0.21, z]}><boxGeometry args={[0.045, 0.42, 0.045]} /><meshStandardMaterial color="#4c4943" /></mesh>))}
        <mesh castShadow position={[-0.18, 0.51, 0]} rotation={[0, 0.22, 0]}><cylinderGeometry args={[0.11, 0.09, 0.14, 18]} /><meshStandardMaterial color="#728e82" /></mesh>
        <mesh castShadow position={[0.19, 0.51, 0]} rotation={[Math.PI / 2, 0.08, 0]}><boxGeometry args={[0.32, 0.025, 0.24]} /><meshStandardMaterial color="#ded1b8" /></mesh>
      </group>
      <group position={[2.42, 0, 1.85]} rotation={[0, -Math.PI / 2, 0]}>
        <mesh castShadow position={[0, 0.36, 0]}><boxGeometry args={[1.7, 0.55, 0.42]} /><meshStandardMaterial color="#765d49" /></mesh>
        <mesh castShadow position={[0, 1.22, -0.02]}><boxGeometry args={[1.5, 0.84, 0.06]} /><meshStandardMaterial color="#1d2524" emissive="#365b52" emissiveIntensity={0.12} /></mesh>
        <mesh position={[0, 1.22, 0.018]}><planeGeometry args={[1.36, 0.7]} /><meshBasicMaterial color="#29413d" /></mesh>
      </group>
      <Plant position={[1.6, 0, 3.08]} scale={1.15} />
    </group>
  );
}

function Kitchen() {
  return (
    <group position={[3.85, 0, -2.72]}>
      <mesh receiveShadow position={[-0.3, 1.46, -0.37]}><boxGeometry args={[1.65, 0.82, 0.06]} /><meshStandardMaterial color="#d8d1c2" /></mesh>
      {[0.33, 0.68, 1.03, 1.38, 1.73].map((y, index) => (
        <mesh key={y} position={[-0.3, y, -0.332]}><boxGeometry args={[1.6, 0.012, 0.01]} /><meshBasicMaterial color={index % 2 ? "#a5b1ac" : "#c3cbc6"} /></mesh>
      ))}
      <mesh castShadow position={[-0.35, 0.46, 0]}><boxGeometry args={[1.5, 0.9, 0.66]} /><meshStandardMaterial color="#c2b29b" /></mesh>
      <mesh castShadow position={[-0.35, 0.94, 0]}><boxGeometry args={[1.58, 0.08, 0.72]} /><meshStandardMaterial color="#4f5652" /></mesh>
      {[-0.72, -0.35, 0.02].map((x) => <mesh key={x} position={[x, 0.48, 0.345]}><boxGeometry args={[0.02, 0.78, 0.018]} /><meshBasicMaterial color="#827663" /></mesh>)}
      {[-0.72, -0.35, 0.02].map((x) => <mesh key={`handle-${x}`} position={[x, 0.56, 0.37]}><boxGeometry args={[0.2, 0.025, 0.025]} /><meshStandardMaterial color="#746d61" metalness={0.48} /></mesh>)}
      <mesh position={[-0.66, 0.995, 0]}><boxGeometry args={[0.48, 0.025, 0.38]} /><meshStandardMaterial color="#87918d" /></mesh>
      <mesh castShadow position={[-0.66, 1.19, -0.12]} rotation={[0, 0, Math.PI / 2]}><torusGeometry args={[0.18, 0.025, 10, 24, Math.PI]} /><meshStandardMaterial color="#767f7b" metalness={0.7} /></mesh>
      {[-0.15, 0.15].flatMap((x) => [-0.14, 0.16].map((z) => <mesh key={`${x}-${z}`} position={[x, 1, z]}><cylinderGeometry args={[0.12, 0.12, 0.02, 24]} /><meshStandardMaterial color="#252827" /></mesh>))}
      <group position={[0.08, 1.09, 0.02]}>
        <mesh castShadow><cylinderGeometry args={[0.14, 0.14, 0.14, 20]} /><meshStandardMaterial color="#89765d" /></mesh>
        {[0, 1, 2].map((item) => <mesh castShadow key={item} position={[(item - 1) * 0.06, 0.2 + item * 0.03, 0]} rotation={[0.1, 0, (item - 1) * 0.18]}><cylinderGeometry args={[0.014, 0.014, 0.36, 10]} /><meshStandardMaterial color="#6a6e66" metalness={0.5} /></mesh>)}
      </group>
      <group position={[0.79, 0, -0.04]}>
        <RoundedBox castShadow args={[0.68, 1.92, 0.7]} radius={0.06} smoothness={4} position={[0, 0.96, 0]}><meshStandardMaterial color="#d5d8d4" metalness={0.15} /></RoundedBox>
        <mesh position={[0.23, 1.05, 0.36]}><boxGeometry args={[0.025, 0.32, 0.025]} /><meshStandardMaterial color="#727b77" /></mesh>
        <mesh position={[0, 1.35, 0.36]}><boxGeometry args={[0.54, 0.015, 0.012]} /><meshStandardMaterial color="#b3b8b4" /></mesh>
      </group>
    </group>
  );
}

function Bathroom() {
  return (
    <group position={[3.95, 0, 2.15]}>
      <mesh receiveShadow position={[0, 0.018, 0]}><boxGeometry args={[2.0, 0.035, 2.35]} /><meshStandardMaterial color="#b9c8c5" roughness={0.95} /></mesh>
      <group position={[0.48, 0, 0.55]}>
        <RoundedBox castShadow args={[0.45, 0.42, 0.64]} radius={0.16} smoothness={4} position={[0, 0.28, 0]}><meshStandardMaterial color="#f1f1eb" /></RoundedBox>
        <mesh castShadow position={[0, 0.7, 0.22]}><boxGeometry args={[0.5, 0.68, 0.22]} /><meshStandardMaterial color="#f1f1eb" /></mesh>
        <mesh position={[0, 0.57, -0.21]} rotation={[-Math.PI / 2, 0, 0]}><torusGeometry args={[0.17, 0.025, 12, 28]} /><meshStandardMaterial color="#e6e6df" /></mesh>
      </group>
      <group position={[-0.5, 0, 0.57]}>
        <mesh castShadow position={[0, 0.43, 0]}><boxGeometry args={[0.76, 0.72, 0.48]} /><meshStandardMaterial color="#8da49e" /></mesh>
        <RoundedBox castShadow args={[0.82, 0.12, 0.54]} radius={0.09} smoothness={4} position={[0, 0.84, 0]}><meshStandardMaterial color="#f0f0eb" /></RoundedBox>
        <mesh position={[0, 1.43, 0.22]}><boxGeometry args={[0.62, 0.85, 0.025]} /><meshStandardMaterial color="#9fc8d1" metalness={0.2} /></mesh>
        <mesh castShadow position={[0, 1.0, 0.2]} rotation={[Math.PI / 2, 0, 0]}><torusGeometry args={[0.11, 0.02, 10, 24, Math.PI]} /><meshStandardMaterial color="#89938f" metalness={0.65} /></mesh>
      </group>
      <group position={[-0.45, 0, -0.55]}>
        <mesh position={[0, 1.05, 0]}><cylinderGeometry args={[0.025, 0.025, 2.05, 12]} /><meshStandardMaterial color="#777f7c" /></mesh>
        <mesh position={[0.14, 2.02, 0]} rotation={[0, 0, Math.PI / 2]}><cylinderGeometry args={[0.025, 0.025, 0.28, 12]} /><meshStandardMaterial color="#777f7c" /></mesh>
        <mesh position={[0.28, 1.98, 0]} rotation={[Math.PI / 2, 0, 0]}><cylinderGeometry args={[0.18, 0.18, 0.035, 24]} /><meshStandardMaterial color="#a7afac" /></mesh>
        <mesh position={[0.25, 1.05, 0]}><boxGeometry args={[0.7, 1.9, 0.025]} /><meshStandardMaterial color="#bce1e5" transparent opacity={0.25} /></mesh>
        <mesh position={[0.25, 0.09, 0.02]} rotation={[-Math.PI / 2, 0, 0]}><cylinderGeometry args={[0.09, 0.09, 0.012, 24]} /><meshStandardMaterial color="#838b87" metalness={0.55} /></mesh>
      </group>
      <mesh castShadow position={[0.4, 1.45, 1.03]}><boxGeometry args={[0.82, 0.06, 0.18]} /><meshStandardMaterial color="#97735c" /></mesh>
      {[0.16, 0.4, 0.64].map((x, index) => <mesh castShadow key={x} position={[x, 1.62 + index * 0.015, 1.03]}><boxGeometry args={[0.12, 0.28 + index * 0.04, 0.14]} /><meshStandardMaterial color={index === 1 ? "#6f8c83" : "#dfd7c9"} /></mesh>)}
    </group>
  );
}

function Fan({ snapshot, reducedMotion }: Omit<ApartmentCanvasProps, "overlay">) {
  const blades = useRef<THREE.Group>(null);
  useFrame((_, delta) => {
    if (blades.current && snapshot.devices.fan.power && !reducedMotion) blades.current.rotation.z -= delta * snapshot.devices.fan.speed * 3.5;
  });
  return (
    <group position={[1.55, 1.2, 0.65]} rotation={[0, -0.5, 0]}>
      <mesh castShadow position={[0, -0.64, 0]}><cylinderGeometry args={[0.075, 0.14, 1.28, 16]} /><meshStandardMaterial color="#c2b7a4" /></mesh>
      <mesh castShadow rotation={[Math.PI / 2, 0, 0]}><torusGeometry args={[0.46, 0.035, 10, 32]} /><meshStandardMaterial color="#66736c" /></mesh>
      <group ref={blades}>{[0, Math.PI / 2, Math.PI, Math.PI * 1.5].map((rotation) => <mesh castShadow key={rotation} rotation={[0, 0, rotation]} position={[0.21 * Math.cos(rotation), 0.21 * Math.sin(rotation), 0]}><boxGeometry args={[0.4, 0.1, 0.025]} /><meshStandardMaterial color={snapshot.devices.fan.power ? "#83a18f" : "#b8b7ad"} /></mesh>)}</group>
      <mesh position={[0, 0, 0.04]}><sphereGeometry args={[0.085, 16, 16]} /><meshStandardMaterial color="#4b5b52" /></mesh>
    </group>
  );
}

function Curtain({ openPercent }: { openPercent: number }) {
  const openness = THREE.MathUtils.clamp(openPercent / 100, 0, 1);
  const spread = THREE.MathUtils.lerp(1.18, 0.26, openness);
  return (
    <group position={[-3.15, 1.7, -3.2]}>
      <mesh position={[0, 1.02, 0]}><boxGeometry args={[2.85, 0.05, 0.05]} /><meshStandardMaterial color="#8d806f" /></mesh>
      {[-1, 1].flatMap((side) => Array.from({ length: 10 }, (_, fold) => {
        const progress = fold / 9;
        return (
          <mesh castShadow key={`${side}-${fold}`} position={[side * (1.34 - progress * spread), 0, 0.08 + (fold % 2) * 0.035]}>
            <boxGeometry args={[0.16, 2.08, 0.055]} />
            <meshStandardMaterial color={fold % 2 ? "#cfa87b" : "#dfbd91"} roughness={0.96} />
          </mesh>
        );
      }))}
    </group>
  );
}

function Devices({ snapshot, showLabels, reducedMotion }: { snapshot: RoomSnapshot; showLabels: boolean; reducedMotion: boolean }) {
  const computerPlug = snapshot.power.smart_plugs.desk_computer;
  const monitorPlug = snapshot.power.smart_plugs.monitor;
  return (
    <>
      <group position={[0.35, 2.65, -3.42]}>
        <RoundedBox castShadow args={[1.35, 0.48, 0.22]} radius={0.08} smoothness={4}><meshStandardMaterial color={snapshot.devices.ac.power ? "#f5f5ee" : "#babbb6"} /></RoundedBox>
        <mesh position={[0, -0.13, 0.125]} rotation={[0.16, 0, 0]}><boxGeometry args={[1.04, 0.1, 0.035]} /><meshStandardMaterial color="#69736e" /></mesh>
        {snapshot.devices.ac.power ? [-0.34, -0.11, 0.12, 0.35].map((x) => (
          <mesh key={x} position={[x, -0.56, 0.23]} rotation={[0.28, 0, 0]}>
            <boxGeometry args={[0.028, 0.7, 0.015]} />
            <meshBasicMaterial color="#a9d8dc" transparent opacity={0.28} />
          </mesh>
        )) : null}
        <mesh position={[0.45, 0, 0.13]}><sphereGeometry args={[0.035, 12, 12]} /><meshBasicMaterial color={snapshot.devices.ac.power ? "#45b978" : "#696969"} /></mesh>
        {showLabels ? <SceneLabel kind="device" position={[0, 0.58, 0]}>Điều hòa · {snapshot.devices.ac.temperature_c}°C</SceneLabel> : null}
      </group>
      <Fan snapshot={snapshot} reducedMotion={reducedMotion} />
      {showLabels ? <SceneLabel kind="device" position={[1.55, 2.15, 0.65]}>Quạt · mức {snapshot.devices.fan.speed}</SceneLabel> : null}
      <group position={[2.15, 0.45, 0.55]}>
        <RoundedBox castShadow args={[0.56, 0.9, 0.48]} radius={0.1} smoothness={4}><meshStandardMaterial color={snapshot.devices.air_purifier.power ? "#dfeae3" : "#b8bcb8"} /></RoundedBox>
        {[-0.15, -0.05, 0.05, 0.15].map((x) => <mesh key={x} position={[x, 0.455, 0]}><boxGeometry args={[0.025, 0.012, 0.3]} /><meshStandardMaterial color="#7c8982" /></mesh>)}
        <mesh position={[0, 0.18, 0.25]}><boxGeometry args={[0.34, 0.17, 0.02]} /><meshBasicMaterial color={snapshot.devices.air_purifier.power ? "#54af7a" : "#6c746f"} /></mesh>
        {showLabels ? <SceneLabel kind="device" position={[0, 0.82, 0]}>Máy lọc · mức {snapshot.devices.air_purifier.speed}</SceneLabel> : null}
      </group>
      <group position={[-4.4, 0.46, -0.1]}>
        <RoundedBox castShadow args={[0.5, 0.92, 0.5]} radius={0.12} smoothness={4}><meshStandardMaterial color={snapshot.devices.humidity_device.power ? "#b8d8d2" : "#c1c3bd"} /></RoundedBox>
        <mesh position={[0, 0.48, 0]}><cylinderGeometry args={[0.1, 0.16, 0.08, 20]} /><meshBasicMaterial color={snapshot.devices.humidity_device.power ? "#8ddbd0" : "#9da5a1"} /></mesh>
        {snapshot.devices.humidity_device.power ? [0, 1, 2].map((particle) => <mesh key={particle} position={[(particle - 1) * 0.055, 0.7 + particle * 0.16, 0]}><sphereGeometry args={[0.035 + particle * 0.01, 12, 12]} /><meshBasicMaterial color="#c7eeea" transparent opacity={0.34 - particle * 0.07} /></mesh>) : null}
        {showLabels ? <SceneLabel kind="device" position={[0, 0.9, 0]}>Máy tạo ẩm</SceneLabel> : null}
      </group>
      <group position={[-1.75, 2.78, 1.25]}>
        <mesh><cylinderGeometry args={[0.34, 0.22, 0.16, 32]} /><meshStandardMaterial color={snapshot.devices.main_light.power ? kelvinColor(snapshot.devices.main_light.color_temperature_kelvin) : "#aaa89f"} emissive={snapshot.devices.main_light.power ? kelvinColor(snapshot.devices.main_light.color_temperature_kelvin) : "#000000"} emissiveIntensity={0.45} /></mesh>
        <mesh position={[0, 0.09, 0]}><torusGeometry args={[0.27, 0.025, 10, 32]} /><meshStandardMaterial color="#736d62" metalness={0.42} /></mesh>
        {showLabels ? <SceneLabel kind="device" position={[0, 0.42, 0]}>Đèn chính · {snapshot.devices.main_light.brightness_percent}%</SceneLabel> : null}
      </group>
      <group position={[-4.37, 0.78, -2.58]}>
        <mesh castShadow><cylinderGeometry args={[0.2, 0.3, 0.38, 24]} /><meshStandardMaterial color={snapshot.devices.bedside_light.power ? kelvinColor(snapshot.devices.bedside_light.color_temperature_kelvin) : "#b7aa98"} emissive={snapshot.devices.bedside_light.power ? kelvinColor(snapshot.devices.bedside_light.color_temperature_kelvin) : "#000000"} emissiveIntensity={0.35} /></mesh>
        <mesh position={[0, 0.17, 0]}><torusGeometry args={[0.2, 0.018, 8, 24]} /><meshStandardMaterial color="#745f4c" /></mesh>
        <mesh castShadow position={[0, -0.23, 0]}><cylinderGeometry args={[0.035, 0.035, 0.35, 12]} /><meshStandardMaterial color="#6b5848" /></mesh>
        {showLabels ? <SceneLabel kind="device" position={[0, 0.48, 0]}>Đèn đầu giường · {snapshot.devices.bedside_light.brightness_percent}%</SceneLabel> : null}
      </group>
      {[{ id: "PC", x: 0.88, plug: computerPlug }, { id: "Màn hình", x: 1.18, plug: monitorPlug }].map(({ id, x, plug }) => (
        <group key={id} position={[x, 0.4, -3.4]} rotation={[Math.PI / 2, 0, 0]}>
          <RoundedBox castShadow args={[0.22, 0.3, 0.07]} radius={0.035} smoothness={4}><meshStandardMaterial color="#f0eee7" /></RoundedBox>
          <mesh position={[0, 0.03, 0.04]}><cylinderGeometry args={[0.045, 0.045, 0.018, 18]} /><meshBasicMaterial color={plug.state === "on" ? "#4fbd7b" : "#858b87"} /></mesh>
          {showLabels ? <SceneLabel kind="device" position={[0, 0.55, 0]}>Ổ cắm {id} · {plug.state === "on" ? "bật" : "tắt"}</SceneLabel> : null}
        </group>
      ))}
      {showLabels ? <SceneLabel kind="device" position={[0.2, 1.75, -2.25]}>Máy tính · {computerPlug.state === "on" ? "bật" : "tắt"}</SceneLabel> : null}
      {showLabels ? <SceneLabel kind="device" position={[0.2, 2.05, -2.35]}>Màn hình · {monitorPlug.state === "on" ? "bật" : "tắt"}</SceneLabel> : null}
      {showLabels ? <SceneLabel kind="device" position={[-3.15, 3.18, -3.25]}>Rèm · mở {snapshot.devices.curtain.position_percent}%</SceneLabel> : null}
      {showLabels ? <SceneLabel kind="device" position={[-3.15, 2.9, -3.2]}>Cửa sổ · {snapshot.openings.window_state === "open" ? "mở" : "đóng"}</SceneLabel> : null}
    </>
  );
}

function Sensors({ snapshot, overlay }: Pick<ApartmentCanvasProps, "snapshot" | "overlay">) {
  return (
    <>
      {overlay === "temperature" ? <SensorNode color="#e37b56" label="Nhiệt độ · độ ẩm" position={[-1.08, 1.35, -1.7]} value={`${snapshot.environment.temperature_c.toFixed(1)}°C · ${snapshot.environment.humidity_percent.toFixed(0)}%`} /> : null}
      {overlay === "air" ? <SensorNode color="#4f9b73" label="CO₂" position={[-1.08, 1.35, -1.45]} value={`${snapshot.environment.co2_ppm.toFixed(0)} ppm`} /> : null}
      {overlay === "air" ? <SensorNode color="#609db1" label="PM2.5" position={[1.2, 0.82, 2.05]} value={`${snapshot.environment.pm25_ug_m3.toFixed(1)} µg/m³`} /> : null}
      {overlay === "light" ? <SensorNode color="#d8aa45" label="Ánh sáng bàn" position={[0.72, 1.02, -2.15]} value={`${snapshot.environment.ambient_light_lux.toFixed(0)} lux`} /> : null}
      {overlay === "noise" ? <SensorNode color="#8e6cab" label="Tiếng ồn sinh hoạt" position={[-0.15, 0.78, 2.68]} value={`${snapshot.environment.noise_db.toFixed(1)} dB`} /> : null}
    </>
  );
}

function SensorField({ snapshot, overlay }: Pick<ApartmentCanvasProps, "snapshot" | "overlay">) {
  const fieldColor = snapshot.environment.temperature_c < 22
    ? "#66a9cf"
    : snapshot.environment.temperature_c > 28
      ? "#df7659"
      : "#deb566";
  const airRisk = Math.max(
    snapshot.environment.co2_ppm / 1_500,
    snapshot.environment.pm25_ug_m3 / 35,
  );
  const airColor = airRisk > 1 ? "#d36b58" : airRisk > 0.65 ? "#d7ad56" : "#5fa57c";

  return (
    <group>
      {overlay === "temperature" ? (
        <>
          <mesh position={[0, 0.036, 0]} rotation={[-Math.PI / 2, 0, 0]} renderOrder={2}>
            <planeGeometry args={[9.75, 6.75]} />
            <meshBasicMaterial color={fieldColor} depthWrite={false} transparent opacity={0.08} />
          </mesh>
          {[[-3.2, -1.8, 1.45], [0.2, -2.35, 1.15], [-0.7, 1.7, 1.7]].map(([x, z, radius], index) => (
            <mesh key={index} position={[x, 0.041, z]} rotation={[-Math.PI / 2, 0, 0]} renderOrder={3}>
              <circleGeometry args={[radius, 48]} />
              <meshBasicMaterial color={fieldColor} depthWrite={false} transparent opacity={0.08 + index * 0.025} />
            </mesh>
          ))}
        </>
      ) : null}
      {overlay === "air" ? (
        <>
          {[1.0, 1.55, 2.1].map((radius, index) => (
            <mesh key={radius} position={[2.15, 0.042 + index * 0.002, 0.55]} rotation={[-Math.PI / 2, 0, 0]} renderOrder={3}>
              <ringGeometry args={[radius - 0.035, radius, 64]} />
              <meshBasicMaterial color={airColor} depthWrite={false} transparent opacity={0.34 - index * 0.07} />
            </mesh>
          ))}
          <mesh position={[-0.2, 0.039, -0.2]} rotation={[-Math.PI / 2, 0, 0]} renderOrder={2}>
            <circleGeometry args={[3.7, 64]} />
            <meshBasicMaterial color={airColor} depthWrite={false} transparent opacity={0.055} />
          </mesh>
        </>
      ) : null}
      {overlay === "light" ? (
        <>
          <mesh position={[-3.15, 0.041, -1.65]} rotation={[-Math.PI / 2, 0, -0.12]} renderOrder={3}>
            <circleGeometry args={[1.55, 48]} />
            <meshBasicMaterial color="#f1c766" depthWrite={false} transparent opacity={0.17} />
          </mesh>
          <mesh position={[-1.75, 0.043, 1.25]} rotation={[-Math.PI / 2, 0, 0]} renderOrder={3}>
            <ringGeometry args={[1.55, 1.62, 64]} />
            <meshBasicMaterial color="#f4d88b" depthWrite={false} transparent opacity={0.42} />
          </mesh>
        </>
      ) : null}
      {overlay === "noise" ? [0.8, 1.35, 1.9].map((radius, index) => (
        <mesh key={radius} position={[1.55, 0.042 + index * 0.002, 0.65]} rotation={[-Math.PI / 2, 0, 0]} renderOrder={3}>
          <ringGeometry args={[radius - 0.045, radius, 64]} />
          <meshBasicMaterial color="#906cac" depthWrite={false} transparent opacity={0.42 - index * 0.09} />
        </mesh>
      )) : null}
    </group>
  );
}

function WindowPanel({ hingeX, panelOffset, openAngle }: { hingeX: number; panelOffset: number; openAngle: number }) {
  return (
    <group position={[hingeX, 1.72, -3.38]} rotation={[0, openAngle, 0]}>
      <mesh castShadow position={[panelOffset, 0, 0]}>
        <boxGeometry args={[1.35, 1.86, 0.035]} />
        <meshPhysicalMaterial color="#b9e0e6" roughness={0.08} transmission={0.35} transparent opacity={0.58} />
      </mesh>
      {[-0.675, 0.675].map((x) => <mesh castShadow key={x} position={[panelOffset + x, 0, 0.01]}><boxGeometry args={[0.045, 1.92, 0.055]} /><meshStandardMaterial color="#667877" metalness={0.5} roughness={0.35} /></mesh>)}
      {[-0.94, 0, 0.94].map((y) => <mesh castShadow key={y} position={[panelOffset, y, 0.01]}><boxGeometry args={[1.39, 0.045, 0.055]} /><meshStandardMaterial color="#667877" metalness={0.5} roughness={0.35} /></mesh>)}
      <mesh position={[panelOffset - Math.sign(panelOffset) * 0.09, 0, 0.07]}><boxGeometry args={[0.025, 0.27, 0.025]} /><meshStandardMaterial color="#53605e" metalness={0.55} /></mesh>
    </group>
  );
}

function FloorPlan({ windowState }: { windowState: "open" | "closed" }) {
  const open = windowState === "open";
  const textures = useSurfaceTextures();
  return (
    <>
      <mesh receiveShadow rotation={[-Math.PI / 2, 0, 0]}><planeGeometry args={[10, 7]} /><meshStandardMaterial map={textures.wood} color="#d2c2aa" roughness={0.88} /></mesh>
      <mesh receiveShadow position={[3.85, 0.014, -2.27]} rotation={[-Math.PI / 2, 0, 0]}><planeGeometry args={[2.3, 2.42]} /><meshStandardMaterial map={textures.stone} color="#c8bca8" roughness={0.84} /></mesh>
      <mesh receiveShadow position={[3.86, 0.018, 2.31]} rotation={[-Math.PI / 2, 0, 0]}><planeGeometry args={[2.15, 2.25]} /><meshStandardMaterial map={textures.tile} color="#c5d2ce" roughness={0.82} /></mesh>
      <Grid args={[10, 7]} position={[0, 0.028, 0]} cellColor="#6e7a72" cellSize={1} cellThickness={0.28} fadeDistance={18} fadeStrength={1.5} sectionColor="#52645a" sectionSize={5} sectionThickness={0.5} />

      <Wall position={[-4.75, 1.55, -3.5]} size={[0.5, 3.1, 0.14]} />
      <Wall position={[1.6, 1.55, -3.5]} size={[6.8, 3.1, 0.14]} />
      <Wall position={[-3.15, 0.36, -3.5]} size={[2.7, 0.72, 0.14]} />
      <Wall position={[-3.15, 2.9, -3.5]} size={[2.7, 0.4, 0.14]} />
      <Wall position={[-5, 1.55, 0]} size={[0.14, 3.1, 7]} />
      <Wall position={[5, 1.55, -2.25]} size={[0.14, 3.1, 2.5]} />
      <Wall position={[5, 0.18, 1.25]} size={[0.14, 0.36, 4.5]} />
      <Wall position={[0, 0.18, 3.5]} size={[10, 0.36, 0.14]} />

      <Wall position={[-1.12, 1.55, -2.325]} size={[0.12, 3.1, 2.35]} />
      <Wall position={[-1.12, 1.55, 0.25]} size={[0.12, 3.1, 1.1]} />
      <Wall position={[-1.12, 2.75, -0.725]} size={[0.12, 0.8, 0.85]} />
      <Wall position={[-1.12, 1.55, 0.82]} size={[0.17, 3.1, 0.17]} />

      <Wall position={[3.86, 1.55, 1.15]} size={[2.28, 3.1, 0.12]} />
      <Wall position={[2.72, 1.55, 1.875]} size={[0.12, 3.1, 1.45]} />
      <Wall position={[2.72, 2.75, 3.025]} size={[0.12, 0.8, 0.85]} />

      <Trim position={[-3.15, 0.74, -3.34]} size={[2.88, 0.12, 0.28]} />
      <WindowPanel hingeX={-4.5} panelOffset={0.675} openAngle={open ? -0.72 : 0} />
      <WindowPanel hingeX={-1.8} panelOffset={-0.675} openAngle={open ? 0.72 : 0} />
      <Door position={[2.66, 0, 2.6]} rotation={-Math.PI / 2} />

      <Trim position={[1.6, 0.1, -3.4]} size={[6.8, 0.2, 0.08]} />
      <Trim position={[-4.9, 0.1, 0]} size={[0.08, 0.2, 7]} />
      <Trim position={[-1.03, 0.1, -2.325]} size={[0.07, 0.2, 2.35]} />
      <Trim position={[-1.03, 0.1, 0.25]} size={[0.07, 0.2, 1.1]} />
      <Trim position={[4.9, 0.1, -2.25]} size={[0.08, 0.2, 2.5]} />
      <SceneLabel position={[-3.1, 0.08, -2.95]}>PHÒNG NGỦ</SceneLabel>
      <SceneLabel position={[0.35, 0.08, -3.0]}>GÓC LÀM VIỆC</SceneLabel>
      <SceneLabel position={[0.65, 0.08, 3.15]}>PHÒNG KHÁCH</SceneLabel>
      <SceneLabel position={[3.8, 0.08, -3.15]}>BẾP</SceneLabel>
      <SceneLabel position={[3.9, 0.08, 2.75]}>PHÒNG TẮM</SceneLabel>
    </>
  );
}

function StudioScene(props: ApartmentCanvasProps) {
  const { snapshot } = props;
  const daylight = THREE.MathUtils.clamp(snapshot.environment.ambient_light_lux / 1_400, 0.06, 1.35);
  const mainLight = snapshot.devices.main_light;
  const bedsideLight = snapshot.devices.bedside_light;
  const curtainLight = snapshot.devices.curtain.position_percent / 100;
  const background = new THREE.Color("#c8d3cf").lerp(new THREE.Color("#eadfca"), Math.min(1, daylight));

  return (
    <>
      <color attach="background" args={[background]} />
      <fog attach="fog" args={[background, 14, 25]} />
      <ambientLight intensity={0.28 + daylight * 0.28} />
      <hemisphereLight color="#fff2da" groundColor="#796b5c" intensity={0.42 + daylight * 0.34} />
      <directionalLight
        castShadow
        color="#fff0d2"
        intensity={0.35 + daylight * 1.05}
        position={[-4, 9, -4]}
        shadow-bias={-0.00035}
        shadow-camera-bottom={-6}
        shadow-camera-far={22}
        shadow-camera-left={-7}
        shadow-camera-right={7}
        shadow-camera-top={6}
        shadow-mapSize={[2048, 2048]}
      />
      {mainLight.power ? <pointLight castShadow color={kelvinColor(mainLight.color_temperature_kelvin)} decay={2} distance={7} intensity={mainLight.brightness_percent / 46} position={[-1.75, 2.68, 1.25]} shadow-mapSize={[512, 512]} /> : null}
      {bedsideLight.power ? <pointLight castShadow color={kelvinColor(bedsideLight.color_temperature_kelvin)} decay={2} distance={4.5} intensity={bedsideLight.brightness_percent / 38} position={[-4.35, 1.15, -2.58]} shadow-mapSize={[512, 512]} /> : null}
      <mesh position={[-3.15, 0.032, -1.65]} rotation={[-Math.PI / 2, 0, -0.12]}>
        <planeGeometry args={[2.5, 1.65]} />
        <meshBasicMaterial color="#f6c878" depthWrite={false} transparent opacity={Math.min(0.3, daylight * curtainLight * 0.24)} />
      </mesh>

      <FloorPlan windowState={snapshot.openings.window_state} />
      <Curtain openPercent={snapshot.devices.curtain.position_percent} />
      <Bed />
      <Workstation
        computerOn={snapshot.power.smart_plugs.desk_computer.state === "on"}
        monitorOn={snapshot.power.smart_plugs.monitor.state === "on"}
      />
      <LivingRoom />
      <Kitchen />
      <Bathroom />
      <Devices snapshot={snapshot} showLabels={props.overlay === "devices"} reducedMotion={props.reducedMotion} />
      <SensorField snapshot={snapshot} overlay={props.overlay} />
      <Sensors snapshot={snapshot} overlay={props.overlay} />
      <Resident snapshot={snapshot} reducedMotion={props.reducedMotion} />
      <ContactShadows blur={2.2} color="#3b3228" far={3.8} frames={1} opacity={0.3} position={[0, 0.035, 0]} resolution={512} scale={[11, 8]} />

      {/* ponytail: primitive geometry keeps demo offline; replace components with compressed local glTF when photorealism matters. */}
      <OrbitControls dampingFactor={0.08} enableDamping enablePan maxDistance={16} maxPolarAngle={1.35} minDistance={8} minPolarAngle={0.42} target={[0, 0.65, -0.15]} />
    </>
  );
}

function ResponsiveCamera() {
  const { camera, size } = useThree();

  useEffect(() => {
    if (!(camera instanceof THREE.PerspectiveCamera)) return;

    const portrait = size.width <= 760 && size.height > size.width;
    const tablet = size.width <= 1200;
    const position: [number, number, number] = portrait
      ? [15, 13.5, 18]
      : tablet
        ? [12, 10.5, 14]
        : [9.8, 8.6, 11.5];

    camera.position.set(...position);
    camera.fov = portrait ? 54 : tablet ? 46 : 39;
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
          key={cameraKey}
          camera={{ position: [9.8, 8.6, 11.5], fov: 39 }}
          dpr={[1, 1.65]}
          fallback={<div className="webgl-fallback">WebGL không khả dụng. Dùng bảng trạng thái bên dưới.</div>}
          gl={{ antialias: true, powerPreference: "high-performance" }}
          onCreated={({ gl }) => {
            gl.toneMapping = THREE.ACESFilmicToneMapping;
            gl.toneMappingExposure = 1.06;
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
      <div className="scene-scale" aria-hidden="true">1 ô ≈ 1 mét · mô hình 10 × 7 m</div>
      <button className="camera-reset" onClick={() => setCameraKey((value) => value + 1)} type="button">Đặt lại góc nhìn</button>
    </div>
  );
}
