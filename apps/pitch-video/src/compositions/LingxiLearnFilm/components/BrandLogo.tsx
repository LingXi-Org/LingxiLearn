import {Img, staticFile} from "remotion";

export const BrandLogo = ({width = 260, dark = true}: {width?: number; dark?: boolean}) => (
  <div style={{display: "flex", alignItems: "center", gap: 17}}>
    <Img src={staticFile(dark ? "brand/icon-on-light.svg" : "brand/icon-on-dark.svg")} style={{width: width * 0.24, height: width * 0.24}} />
    <div style={{fontSize: width * 0.23, fontWeight: 500, letterSpacing: "-.055em", color: dark ? "#0a0a0b" : "white"}}>LingxiLearn</div>
  </div>
);
