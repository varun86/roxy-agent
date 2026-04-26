import { createRoot } from "react-dom/client";
import DialogApp from "./DialogApp";
import "./dialog.css";

const container = document.getElementById("root");

if (!container) {
  throw new Error("Dialog root container not found");
}

createRoot(container).render(<DialogApp />);
