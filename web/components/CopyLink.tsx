"use client";

import { useEffect, useState } from "react";

export default function CopyLink({ path }: { path: string }) {
  const [url, setUrl] = useState(path);
  const [copied, setCopied] = useState(false);

  useEffect(() => {
    setUrl(window.location.origin + path);
  }, [path]);

  async function copy() {
    try {
      await navigator.clipboard.writeText(url);
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    } catch {
      // clipboard may be unavailable; the field is selectable
    }
  }

  return (
    <div className="invite">
      <input readOnly value={url} onFocus={(e) => e.target.select()} />
      <button type="button" className="button" onClick={copy}>{copied ? "Скопировано" : "Копировать"}</button>
    </div>
  );
}
