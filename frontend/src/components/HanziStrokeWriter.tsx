"use client";

import { useEffect, useMemo, useRef, useState } from "react";
import HanziWriter from "hanzi-writer";
import { Loader2, Play } from "lucide-react";

interface Props {
  text: string;
  compact?: boolean;
}

type Writer = ReturnType<typeof HanziWriter.create>;

const HANZI_PATTERN = /\p{Script=Han}/u;

export function HanziStrokeWriter({ text, compact = false }: Props) {
  const characters = useMemo(() => Array.from(text).filter((char) => HANZI_PATTERN.test(char)), [text]);
  const [activeIndex, setActiveIndex] = useState(0);
  const [loading, setLoading] = useState(false);
  const targetRef = useRef<HTMLDivElement | null>(null);
  const writerRef = useRef<Writer | null>(null);
  const activeCharacter = characters[activeIndex] ?? "";

  useEffect(() => {
    const target = targetRef.current;
    if (!target || !activeCharacter) return;

    target.innerHTML = "";
    const size = compact ? 112 : 156;
    setLoading(true);
    const writer = HanziWriter.create(target, activeCharacter, {
      width: size,
      height: size,
      padding: compact ? 6 : 8,
      showOutline: true,
      showCharacter: false,
      strokeColor: "#263028",
      radicalColor: "#3d6346",
      outlineColor: "#d8d0be",
      highlightColor: "#b95f27",
      strokeAnimationSpeed: 1.15,
      delayBetweenStrokes: 120,
    });
    writerRef.current = writer;
    writer
      .animateCharacter()
      .catch(() => undefined)
      .finally(() => setLoading(false));

    return () => {
      writerRef.current = null;
      target.innerHTML = "";
    };
  }, [activeCharacter, compact]);

  if (characters.length === 0) {
    return null;
  }

  function replay() {
    setLoading(true);
    writerRef.current
      ?.animateCharacter()
      .catch(() => undefined)
      .finally(() => setLoading(false));
  }

  return (
    <section className={compact ? "min-w-[112px]" : "rounded-lg border border-cream-200 bg-cream-100/50 p-3"}>
      <div className={compact ? "mb-2 flex items-center justify-between gap-2" : "mb-3 flex items-center justify-between gap-3"}>
        <p className="text-xs font-semibold uppercase text-slate-500">Cách viết</p>
        <button
          className="inline-flex h-8 items-center gap-1.5 rounded-md border border-cream-300 bg-cream-50 px-2 text-xs font-semibold text-slate-700 hover:bg-cream-200 disabled:opacity-60"
          disabled={loading}
          onClick={replay}
          type="button"
        >
          {loading ? <Loader2 className="animate-spin" size={14} /> : <Play size={14} />}
          Viết lại
        </button>
      </div>

      <div className="flex flex-col items-center gap-3">
        <div className={compact ? "h-28 w-28 rounded-lg border border-cream-200 bg-cream-50" : "h-[156px] w-[156px] rounded-lg border border-cream-200 bg-white"} ref={targetRef} />
        {characters.length > 1 ? (
          <div className="flex max-w-full flex-wrap justify-center gap-1.5">
            {characters.map((character, index) => (
              <button
                className={`flex h-8 min-w-8 items-center justify-center rounded-md border px-2 font-serif text-base font-semibold ${
                  index === activeIndex ? "border-brand-300 bg-brand-100 text-brand-900" : "border-cream-300 bg-cream-50 text-slate-700 hover:bg-cream-200"
                }`}
                key={`${character}-${index}`}
                onClick={() => setActiveIndex(index)}
                type="button"
              >
                {character}
              </button>
            ))}
          </div>
        ) : null}
      </div>
    </section>
  );
}
