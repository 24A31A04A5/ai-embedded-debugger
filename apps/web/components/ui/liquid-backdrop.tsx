import * as React from "react";

/** Fixed colour field that Liquid Glass surfaces blur and refract. */
export function LiquidBackdrop() {
  return <div aria-hidden="true" className="lg-wallpaper pointer-events-none fixed inset-0 -z-10" />;
}
