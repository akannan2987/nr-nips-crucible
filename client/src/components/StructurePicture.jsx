import { useState } from 'react'

/**
 * CR-12 step B: the picture of an entry's derived structure, drawn by the
 * server at GET /api/chemicals/{id}/structure.svg. The browser shows an
 * image; it holds no chemistry library. `version` is the structure's
 * derived_at: it goes into the address so that a re-derived entry gets a
 * fresh picture instead of the one the browser cached (the server also
 * answers 304 to a browser that already has the current one).
 *
 * The parent decides whether there is anything to draw (row.structure.source);
 * this component only draws, and says so quietly if the server refuses.
 */
export default function StructurePicture({ id, version, width = 96, height = 72, className = '', title }) {
  const [failed, setFailed] = useState(false)
  const src = `/api/chemicals/${encodeURIComponent(id)}/structure.svg?w=${width}&h=${height}&v=${encodeURIComponent(version || '')}`
  if (failed) {
    return (
      <div
        className={`flex items-center justify-center text-[10px] text-gray-400 border border-dashed border-gray-200 rounded ${className}`}
        style={{ width, height }}
        title="The picture could not be drawn"
        data-testid="structure-picture-missing"
      >
        no picture
      </div>
    )
  }
  return (
    <img
      src={src}
      width={width}
      height={height}
      alt={`Structure of ${id}`}
      title={title || `${id}: the derived structure, drawn by the server`}
      loading="lazy"
      onError={() => setFailed(true)}
      className={`inline-block bg-white rounded ${className}`}
      data-testid="structure-picture"
    />
  )
}
