import { useMemo, useState } from "react";
import type { WindowParams } from "../api/types";
import { defaultWindowInputs, windowParamsFromInputs } from "../lib/window";

export function useQueryWindow(): {
  fromInput: string;
  toInput: string;
  setFromInput: (value: string) => void;
  setToInput: (value: string) => void;
  window: WindowParams | null;
  windowError: string | null;
} {
  const defaults = defaultWindowInputs();
  const [fromInput, setFromInput] = useState(defaults.from);
  const [toInput, setToInput] = useState(defaults.to);

  const parsed = useMemo(() => {
    try {
      return {
        window: windowParamsFromInputs(fromInput, toInput),
        windowError: null,
      };
    } catch (error) {
      return {
        window: null,
        windowError:
          error instanceof Error ? error.message : "Invalid date window",
      };
    }
  }, [fromInput, toInput]);

  return {
    fromInput,
    toInput,
    setFromInput,
    setToInput,
    window: parsed.window,
    windowError: parsed.windowError,
  };
}
