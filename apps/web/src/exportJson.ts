// Machine-readable export only (master plan §12.5's human-readable
// PDF/Markdown export is a separate, real templating effort -- deferred,
// recorded in docs/decisions/OPEN-QUESTIONS.md, not faked with a
// placeholder file here).
export function downloadJson(filename: string, data: unknown): void {
  const blob = new Blob([JSON.stringify(data, null, 2)], { type: "application/json" });
  const url = URL.createObjectURL(blob);
  const link = document.createElement("a");
  link.href = url;
  link.download = filename;
  document.body.appendChild(link);
  link.click();
  document.body.removeChild(link);
  URL.revokeObjectURL(url);
}
