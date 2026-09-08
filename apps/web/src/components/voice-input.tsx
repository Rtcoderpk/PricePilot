"use client";

import { useState } from "react";
import { Button } from "@/components/ui/button";
import { Mic } from "lucide-react";

/**
 * Voice shopping input using the browser Web Speech API.
 * Honest fallback: if the browser doesn't support SpeechRecognition the mic
 * button is hidden and a muted note explains why.
 */
export function VoiceInput({ onTranscript }: { onTranscript: (text: string) => void }) {
  // Client-only capability check computed lazily once (avoids setState-in-effect).
  const [supported] = useState<boolean>(() => {
    if (typeof window === "undefined") return false;
    return "webkitSpeechRecognition" in window || "SpeechRecognition" in window;
  });
  const [listening, setListening] = useState(false);

  function start() {
    if (!supported) return;
    const Recognition =
      (window as any).SpeechRecognition || (window as any).webkitSpeechRecognition;
    if (!Recognition) return;
    const rec = new Recognition();
    rec.lang = "en-US";
    rec.interimResults = false;
    rec.maxAlternatives = 1;
    rec.onstart = () => setListening(true);
    rec.onend = () => setListening(false);
    rec.onresult = (e: any) => {
      const text = e.results?.[0]?.[0]?.transcript ?? "";
      if (text) onTranscript(text);
    };
    rec.onerror = () => setListening(false);
    try {
      rec.start();
    } catch {
      setListening(false);
    }
  }

  if (!supported) {
    return (
      <p className="text-xs text-muted-foreground">
        Voice input is not supported in this browser (Web Speech API unavailable).
      </p>
    );
  }

  return (
    <Button
      type="button"
      variant="outline"
      size="icon"
      onClick={start}
      disabled={listening}
      title="Speak your search"
      aria-label="Voice search"
    >
      <Mic className={`h-4 w-4 ${listening ? "animate-pulse text-primary" : ""}`} />
    </Button>
  );
}