import {ThreeCanvas} from "@remotion/three";
import {useCurrentFrame, useVideoConfig} from "remotion";

const statePoints = Array.from({length: 22}, (_, index) => {
  const angle = index * 2.399963;
  const radius = 1.65 + (index % 4) * .25;
  return {
    position: [Math.cos(angle) * radius, Math.sin(angle * 1.3) * 1.45, Math.sin(angle) * radius] as [number, number, number],
    color: index % 7 === 0 ? "#CFFF3D" : index % 5 === 0 ? "#6ADFF4" : "#7E807B",
    size: .05 + (index % 3) * .018,
  };
});

export const StateCore3D: React.FC = () => {
  const frame = useCurrentFrame();
  const {width, height} = useVideoConfig();
  return (
    <ThreeCanvas width={width} height={height} camera={{position: [0, 0, 9.5], fov: 39}}>
      <ambientLight intensity={1.7} />
      <directionalLight position={[4, 5, 7]} intensity={2.4} color="#ffffff" />
      <pointLight position={[-4, -1, 3]} intensity={12} color="#6ADFF4" />
      <group position={[0, .2, 0]} rotation={[frame * .0025, frame * .005, 0]} scale={.9}>
        <mesh>
          <icosahedronGeometry args={[1.75, 2]} />
          <meshStandardMaterial color="#DCDDDA" roughness={.55} metalness={.2} transparent opacity={.72} />
        </mesh>
        <mesh scale={1.02}>
          <icosahedronGeometry args={[1.75, 2]} />
          <meshBasicMaterial color="#595B57" wireframe transparent opacity={.34} />
        </mesh>
        {statePoints.map((point, index) => (
          <mesh key={index} position={point.position} scale={point.size * (1 + Math.sin(frame / 11 + index) * .12)}>
            <sphereGeometry args={[1, 14, 14]} />
            <meshBasicMaterial color={point.color} />
          </mesh>
        ))}
      </group>
    </ThreeCanvas>
  );
};
