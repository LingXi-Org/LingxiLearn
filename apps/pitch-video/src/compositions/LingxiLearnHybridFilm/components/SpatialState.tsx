import {ThreeCanvas} from "@remotion/three";
import {useCurrentFrame, useVideoConfig} from "remotion";

const nodes = Array.from({length: 34}, (_, index) => {
  const angle = index * 2.399963;
  const radius = 1.65 + (index % 6) * .34;
  return {
    position: [Math.cos(angle) * radius, Math.sin(angle * 1.37) * 1.7, Math.sin(angle) * radius] as [number, number, number],
    scale: .045 + (index % 4) * .018,
    color: index % 7 === 0 ? "#C8FF45" : index % 5 === 0 ? "#65E6FF" : "#FFFFFF",
  };
});

export const SpatialState: React.FC = () => {
  const frame = useCurrentFrame();
  const {width, height} = useVideoConfig();
  const rotation = frame * .006;
  return (
    <ThreeCanvas width={width} height={height} camera={{position: [0, 0, 9], fov: 42}}>
      <ambientLight intensity={.55} />
      <directionalLight position={[4, 5, 6]} intensity={2.2} color="#ffffff" />
      <pointLight position={[-4, -2, 3]} intensity={35} color="#65E6FF" />
      <pointLight position={[4, 2, 2]} intensity={30} color="#C8FF45" />
      <group rotation={[rotation * .55, rotation, rotation * .18]}>
        <mesh scale={1 + Math.sin(frame / 22) * .025}>
          <icosahedronGeometry args={[2.05, 2]} />
          <meshStandardMaterial color="#161A20" roughness={.28} metalness={.72} wireframe />
        </mesh>
        <mesh scale={.93}>
          <icosahedronGeometry args={[2.05, 3]} />
          <meshPhysicalMaterial color="#13161A" roughness={.32} metalness={.55} transparent opacity={.72} />
        </mesh>
        {nodes.map((node, index) => (
          <mesh key={index} position={node.position} scale={node.scale * (1 + Math.sin(frame / 9 + index) * .18)}>
            <sphereGeometry args={[1, 18, 18]} />
            <meshBasicMaterial color={node.color} />
          </mesh>
        ))}
      </group>
    </ThreeCanvas>
  );
};
