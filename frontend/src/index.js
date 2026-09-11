import React from "react";
import ReactDOM from "react-dom/client";
import "./index.css";
import App from "./App";

// recharts 2.x still declares defaultProps on XAxis/YAxis; React 18 warns on that
// pattern for function components. Fix is recharts v3 (breaking API rewrite), so
// silence just this known, harmless warning instead of the whole console. React
// logs this via console.error(fmt, ...args) with the component name as a
// separate arg, not embedded in args[0] — check all args, not just the first.
if (process.env.NODE_ENV === "development") {
  const origError = console.error;
  console.error = (...args) => {
    const joined = args.map((a) => (typeof a === "string" ? a : "")).join(" ");
    if (joined.includes("Support for defaultProps will be removed") && /\bXAxis\b|\bYAxis\b/.test(joined)) {
      return;
    }
    origError(...args);
  };
}

// html5-qrcode's camera surface calls `videoElement.play()` without awaiting
// or catching it (node_modules/html5-qrcode/esm/camera/core-impl.js). If the
// scanner's DOM node is removed (route change away from the scan screen)
// before that play() settles, it rejects with AbortError as an unhandled
// promise rejection from inside the library — nothing in QrScanner.jsx's own
// start/stop code can catch it. Benign race, known issue, not fixable from
// our side without patching the dependency; suppress just this one.
window.addEventListener("unhandledrejection", (event) => {
  const msg = String(event.reason?.message || event.reason || "");
  if (msg.includes("play() request was interrupted because the media was removed")) {
    event.preventDefault();
  }
});

const root = ReactDOM.createRoot(document.getElementById("root"));
root.render(<App />);
