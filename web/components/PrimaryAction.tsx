"use client";

// The one primary action per screen (docs/04 Part C, C2): always bottom-right of the work
// area, always the same shape and colour. Only the label and target change between screens.

export default function PrimaryAction({
  label,
  onClick,
}: {
  label: string;
  onClick: () => void;
}) {
  return (
    <button
      type="button"
      onClick={onClick}
      className="absolute bottom-4 right-4 z-10 flex items-center gap-2 rounded bg-[#f97316] px-4 py-2 text-[12px] font-semibold text-[#0b0f14] shadow-lg transition-colors hover:bg-[#fb923c]"
    >
      {label}
      <span aria-hidden>→</span>
    </button>
  );
}
