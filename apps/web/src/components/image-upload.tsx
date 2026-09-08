"use client";

import { useRef, useState } from "react";
import { Button } from "@/components/ui/button";
import { ImagePlus, Loader2 } from "lucide-react";
import { shoppingImage } from "@/lib/api";
import { ApiError } from "@/lib/api";
import type { ShoppingAgentResponse } from "@/lib/types";

const ACCEPTED = ["image/jpeg", "image/png", "image/webp"];
const MAX_BYTES = 5 * 1024 * 1024;

/**
 * Image shopping upload. Validates type+size client-side BEFORE sending,
 * and surface honest "vision not configured" states from the backend.
 */
export function ImageUpload({ onResult }: { onResult: (data: ShoppingAgentResponse) => void }) {
  const inputRef = useRef<HTMLInputElement>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [previewUrl, setPreviewUrl] = useState<string | null>(null);

  async function onFile(file: File | undefined) {
    if (!file) return;
    if (!ACCEPTED.includes(file.type)) {
      setError("Unsupported image type — please upload JPEG, PNG, or WebP.");
      return;
    }
    if (file.size > MAX_BYTES) {
      setError("Image exceeds the 5 MB limit.");
      return;
    }
    setError(null);
    setBusy(true);
    setPreviewUrl(URL.createObjectURL(file));
    try {
      const data = await shoppingImage(file);
      onResult(data);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Image identification failed.");
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="flex items-center gap-3">
      <input
        ref={inputRef}
        type="file"
        accept="image/jpeg,image/png,image/webp"
        className="hidden"
        onChange={(e) => onFile(e.target.files?.[0])}
      />
      <Button type="button" variant="outline" size="sm" onClick={() => inputRef.current?.click()} disabled={busy}>
        {busy ? <Loader2 className="h-4 w-4 animate-spin" /> : <ImagePlus className="h-4 w-4" />}
        Upload image
      </Button>
      {/* eslint-disable-next-line @next/next/no-img-element -- local blob preview, not remote */}
      {previewUrl ? <img src={previewUrl} alt="upload preview" className="h-10 w-10 rounded object-cover" /> : null}
      {error ? <p className="text-xs text-destructive">{error}</p> : null}
    </div>
  );
}