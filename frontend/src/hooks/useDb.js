import { useState, useEffect, useRef } from "react";
import { subscribe, getState } from "../services/db";

// Reactive selector into the in-memory store. Re-renders on every emit()
// (which is rAF-batched). Used for smooth live maps + notification feeds.
export function useLive(selector) {
  const sel = useRef(selector);
  sel.current = selector;
  const [val, setVal] = useState(() => sel.current(getState()));
  useEffect(() => {
    const compute = () => setVal(() => sel.current(getState()));
    compute();
    return subscribe(compute);
  }, []);
  return val;
}
