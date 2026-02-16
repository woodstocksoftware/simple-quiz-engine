/**
 * Format seconds into a mm:ss string. Clamps to zero.
 */
export function formatTime(seconds) {
  const safe = Math.max(0, seconds)
  const mins = Math.floor(safe / 60)
  const secs = safe % 60
  return `${mins}:${secs.toString().padStart(2, '0')}`
}
