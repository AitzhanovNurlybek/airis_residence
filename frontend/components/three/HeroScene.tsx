"use client";

import { useEffect, useMemo, useRef } from "react";
import { Canvas, useFrame, useThree } from "@react-three/fiber";
import { Float, RoundedBox } from "@react-three/drei";
import * as THREE from "three";

/**
 * Абстрактная сцена в hero: арка + парящие панели.
 * Всё процедурное — ни одного внешнего ассета и HDRI, поэтому
 * сцена весит только код и стартует мгновенно.
 *
 * Реагирует на: прокрутку страницы (вращение + отъезд камеры)
 * и на положение курсора (лёгкий параллакс).
 */

const WINE = "#a01a54";
const SAND = "#c5aa7c";

function Dust({ count = 220 }: { count?: number }) {
  const ref = useRef<THREE.Points>(null);

  const positions = useMemo(() => {
    const arr = new Float32Array(count * 3);
    for (let i = 0; i < count; i++) {
      arr[i * 3] = (Math.random() - 0.5) * 14;
      arr[i * 3 + 1] = (Math.random() - 0.5) * 9;
      arr[i * 3 + 2] = (Math.random() - 0.5) * 10 - 2;
    }
    return arr;
  }, [count]);

  useFrame((state) => {
    if (!ref.current) return;
    ref.current.rotation.y = state.clock.elapsedTime * 0.02;
    ref.current.position.y = Math.sin(state.clock.elapsedTime * 0.15) * 0.2;
  });

  return (
    <points ref={ref}>
      <bufferGeometry>
        <bufferAttribute attach="attributes-position" args={[positions, 3]} />
      </bufferGeometry>
      <pointsMaterial
        size={0.035}
        color={SAND}
        transparent
        opacity={0.55}
        sizeAttenuation
        depthWrite={false}
      />
    </points>
  );
}

/** Арка — отсылка к дверному проёму из логотипа. */
function Arch() {
  const ref = useRef<THREE.Mesh>(null);

  useFrame((state) => {
    if (!ref.current) return;
    ref.current.rotation.z = Math.sin(state.clock.elapsedTime * 0.12) * 0.05;
  });

  return (
    <mesh ref={ref} position={[0, 0, -1.5]} rotation={[0, 0, 0]}>
      <torusGeometry args={[2.6, 0.035, 16, 128, Math.PI]} />
      <meshStandardMaterial
        color={SAND}
        metalness={0.95}
        roughness={0.22}
        emissive={SAND}
        emissiveIntensity={0.12}
      />
    </mesh>
  );
}

function Panel({
  position,
  rotation,
  scale = 1,
  tone = "dark",
}: {
  position: [number, number, number];
  rotation: [number, number, number];
  scale?: number;
  tone?: "dark" | "wine" | "sand";
}) {
  const color = tone === "wine" ? WINE : tone === "sand" ? "#3a3128" : "#1a151a";
  return (
    <Float speed={1.1} rotationIntensity={0.25} floatIntensity={0.5}>
      <RoundedBox
        args={[1.55, 2.25, 0.06]}
        radius={0.12}
        smoothness={4}
        position={position}
        rotation={rotation}
        scale={scale}
      >
        <meshStandardMaterial
          color={color}
          metalness={0.75}
          roughness={0.28}
          envMapIntensity={0.6}
        />
      </RoundedBox>
    </Float>
  );
}

function Rig({ scrollRef }: { scrollRef: React.RefObject<number> }) {
  const group = useRef<THREE.Group>(null);
  const { camera, pointer } = useThree();

  useFrame((_, delta) => {
    const progress = scrollRef.current;
    if (group.current) {
      // Прокрутка вращает всю композицию — это и есть «3D-скролл».
      group.current.rotation.y = THREE.MathUtils.damp(
        group.current.rotation.y,
        progress * 0.85 + pointer.x * 0.12,
        3,
        delta,
      );
      group.current.rotation.x = THREE.MathUtils.damp(
        group.current.rotation.x,
        -pointer.y * 0.08,
        3,
        delta,
      );
      group.current.position.y = THREE.MathUtils.damp(group.current.position.y, progress * 1.4, 3, delta);
    }
    camera.position.z = THREE.MathUtils.damp(camera.position.z, 7 + progress * 2.5, 3, delta);
    camera.lookAt(0, 0, 0);
  });

  return (
    <group ref={group}>
      <Arch />
      <Panel position={[-2.85, 0.15, 0.4]} rotation={[0, 0.42, -0.06]} tone="dark" scale={1.05} />
      <Panel position={[2.85, -0.15, 0.4]} rotation={[0, -0.42, 0.06]} tone="dark" scale={1.05} />
      <Panel position={[-1.35, -0.55, 1.5]} rotation={[0, 0.22, 0.04]} tone="wine" scale={0.7} />
      <Panel position={[1.5, 0.6, 1.7]} rotation={[0, -0.26, -0.05]} tone="sand" scale={0.62} />
      <Dust />
    </group>
  );
}

export default function HeroScene() {
  const scrollRef = useRef(0);

  useEffect(() => {
    const onScroll = () => {
      scrollRef.current = Math.min(1, window.scrollY / (window.innerHeight || 1));
    };
    onScroll();
    window.addEventListener("scroll", onScroll, { passive: true });
    return () => window.removeEventListener("scroll", onScroll);
  }, []);

  return (
    <Canvas
      className="absolute inset-0"
      dpr={[1, 1.75]}
      camera={{ position: [0, 0, 7], fov: 42 }}
      gl={{ antialias: true, alpha: true, powerPreference: "high-performance" }}
      style={{ pointerEvents: "none" }}
    >
      <ambientLight intensity={0.35} />
      <directionalLight position={[4, 6, 5]} intensity={1.1} color="#fff3e2" />
      <pointLight position={[-5, -2, 3]} intensity={38} color={WINE} distance={16} decay={2} />
      <pointLight position={[5, 3, -2]} intensity={26} color={SAND} distance={18} decay={2} />
      <Rig scrollRef={scrollRef} />
      {/* Цвет тумана обязан совпадать с --color-ink-950, иначе на границе
          сцены и страницы видно стык */}
      <fog attach="fog" args={["#1a1417", 8, 17]} />
    </Canvas>
  );
}
