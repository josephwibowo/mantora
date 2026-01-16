/**
 * Robust clipboard helper with fallback for non-secure contexts.
 *
 * Per NIT from plan review: navigator.clipboard requires HTTPS or localhost.
 * This helper falls back to execCommand for HTTP/IP access scenarios.
 */
export async function copyToClipboard(text: string): Promise<void> {
  // Try modern Clipboard API first
  if (navigator.clipboard && window.isSecureContext) {
    try {
      await navigator.clipboard.writeText(text);
      return;
    } catch (err) {
      console.warn("Clipboard API failed, falling back to execCommand:", err);
    }
  }

  // Fallback: use execCommand (deprecated but widely supported)
  const textarea = document.createElement("textarea");
  textarea.value = text;
  textarea.style.position = "fixed";
  textarea.style.opacity = "0";
  document.body.appendChild(textarea);
  textarea.focus();
  textarea.select();

  try {
    const success = document.execCommand("copy");
    if (!success) {
      throw new Error("execCommand copy returned false");
    }
  } finally {
    document.body.removeChild(textarea);
  }
}
