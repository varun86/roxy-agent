import { useEffect, useRef, useState } from "react";
import idleSvg from "../../../assets/roxy/roxy-idle.svg";

export default function PetApp() {
  const [svgPath, setSvgPath] = useState(idleSvg);
  const audioRef = useRef<HTMLAudioElement | null>(null);

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

  useEffect(() => {
    const stopCurrentAudio = () => {
      if (audioRef.current) {
        audioRef.current.pause();
        audioRef.current.currentTime = 0;
        audioRef.current = null;
      }
    };

    const unsubscribe = window.electronAPI.onPlayVoiceAsset((payload) => {
      if (!payload?.assetUrl) {
        return;
      }
      console.info("Pet renderer received voice asset", payload.voiceKey);
      stopCurrentAudio();
      const audio = new Audio(payload.assetUrl);
      audioRef.current = audio;
      void audio.play().catch((error) => {
        console.error("Failed to play voice asset:", error);
      });
      audio.addEventListener("ended", () => {
        console.info("Pet renderer finished voice playback", payload.voiceKey);
      }, { once: true });
    });

    return () => {
      unsubscribe();
      stopCurrentAudio();
    };
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
