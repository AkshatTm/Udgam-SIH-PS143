"use client";

// The one primary action per screen (docs/team/harshita-frontend.md Part C, C2): always
// bottom-right of the work area, always the same shape and colour. Only the label and target
// change between screens, so a judge learns the button once and then only reads the verb.
//
// It is the brightest thing on the screen by design — on a dark map, the eye should land on
// "what do I press next" without being told.

export default function PrimaryAction({
  label,
  onClick,
  disabled = false,
}: {
  label: string;
  onClick: () => void;
  disabled?: boolean;
}) {
  return (
    <button
      type="button"
      onClick={onClick}
      disabled={disabled}
      className="group absolute bottom-6 right-6 z-10 rounded-full bg-drift px-6 py-3 text-[15px] font-semibold text-abyss shadow-[0_8px_30px_rgba(249,115,22,0.35)] transition-all duration-200 ease-out enabled:hover:scale-[1.03] enabled:hover:shadow-[0_10px_38px_rgba(249,115,22,0.5)] enabled:active:scale-[0.99] disabled:cursor-wait disabled:bg-drift/40 disabled:text-abyss/60 disabled:shadow-none"
    >
      {label}
    </button>
  );
}
