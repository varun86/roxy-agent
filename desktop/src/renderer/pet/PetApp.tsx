import { useEffect, useState } from "react";
import idleSvg from "../../../assets/roxy/roxy-idle.svg";

export default function PetApp() {
  const [svgPath, setSvgPath] = useState(idleSvg);

  useEffect(() => {
    window.electronAPI.onStateChange((_state, nextSvgPath) => {
      if (nextSvgPath) {
        setSvgPath(nextSvgPath);
      }
    });
  }, []);

  useEffect(() => {
    const preventContextMenu = (event: MouseEvent) => {
      event.preventDefault();
    };

    document.addEventListener("contextmenu", preventContextMenu);
    return () => document.removeEventListener("contextmenu", preventContextMenu);
  }, []);

  return (
    <div id="pet-container">
      <object
        id="pet-svg"
        className="pet-svg"
        data={svgPath}
        type="image/svg+xml"
        aria-label="Roxy pet"
      />
    </div>
  );
}
