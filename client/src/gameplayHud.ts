/** Minimal onboarding shown while the mouse is not captured. */
export function addGameplayHud(canvas: HTMLCanvasElement): void {
  const hint = document.createElement("div");
  hint.id = "controls-hint";
  hint.innerHTML = `
    <strong>CLICK TO DEPLOY</strong>
    <span><kbd>WASD</kbd> MOVE <i></i> <kbd>SHIFT</kbd> SPRINT <i></i> <kbd>SPACE</kbd> JUMP</span>
    <span><kbd>E</kbd> OPEN DOORS <i></i> <kbd>ESC</kbd> RELEASE MOUSE</span>
  `;
  hint.style.cssText =
    "position:fixed;left:50%;bottom:28px;transform:translateX(-50%);" +
    "display:flex;flex-direction:column;align-items:center;gap:7px;padding:12px 18px;" +
    "border:1px solid rgba(205,220,225,.22);border-radius:3px;" +
    "background:linear-gradient(180deg,rgba(13,18,20,.88),rgba(5,7,8,.9));" +
    "box-shadow:0 8px 30px rgba(0,0,0,.38);color:#acb9bd;" +
    "font:600 10px/1.2 ui-monospace,SFMono-Regular,Menlo,monospace;" +
    "letter-spacing:.12em;text-shadow:0 1px 2px #000;pointer-events:none;" +
    "z-index:15;transition:opacity .18s ease,transform .18s ease";
  hint.querySelector("strong")!.setAttribute(
    "style",
    "color:#edf3f4;font-size:13px;letter-spacing:.2em;margin-bottom:2px",
  );
  hint.querySelectorAll("kbd").forEach((key) => {
    key.setAttribute(
      "style",
      "display:inline-block;padding:2px 5px;margin:0 2px;border:1px solid #69777b;" +
        "border-bottom-color:#3e484b;border-radius:2px;background:#20282b;color:#edf3f4;" +
        "font:700 9px ui-monospace,SFMono-Regular,Menlo,monospace;letter-spacing:.04em",
    );
  });
  hint.querySelectorAll("i").forEach((divider) => {
    divider.setAttribute(
      "style",
      "display:inline-block;width:2px;height:2px;margin:0 6px;border-radius:50%;background:#718085;vertical-align:middle",
    );
  });
  document.body.appendChild(hint);

  const sync = (): void => {
    const playing = document.pointerLockElement === canvas;
    hint.style.opacity = playing ? "0" : "1";
    hint.style.transform = playing ? "translate(-50%,8px)" : "translate(-50%,0)";
  };
  document.addEventListener("pointerlockchange", sync);
  sync();
}
