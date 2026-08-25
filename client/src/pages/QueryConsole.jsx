import { useState, useEffect } from 'react'
import { PlayIcon, TableCellsIcon, ArrowDownTrayIcon } from '@heroicons/react/24/outline'
import toast from 'react-hot-toast'
import { runQuery, getQuerySchema } from '../services/api'

/**
 * Read-only SQL console.
 *
 * The tables store each record whole, as JSON in a `doc` column, so most real
 * questions need `json_extract(doc, '$.field')` rather than a plain column
 * name. The examples below are written to teach that shape, because it is the
 * one thing that is not guessable from the table definitions.
 */

const EXAMPLES = [
  {
    title: 'Count the screening rows by simulant',
    why: 'The simplest useful shape: pull one field out of the document and group by it.',
    sql: `SELECT json_extract(doc, '$.simulant') AS simulant,
       COUNT(*) AS rows
FROM screening
GROUP BY simulant
ORDER BY rows DESC;`,
  },
  {
    title: 'Highest migration into food, by compound',
    why: 'CAST is needed because numbers come out of JSON as text, and would otherwise sort 100 before 20.',
    sql: `SELECT json_extract(doc, '$.compound_name')          AS compound,
       json_extract(doc, '$.cas')                    AS cas,
       MAX(CAST(json_extract(doc, '$.mg_per_kg_food') AS REAL)) AS max_mg_per_kg
FROM screening
WHERE json_extract(doc, '$.mg_per_kg_food') IS NOT NULL
GROUP BY compound, cas
ORDER BY max_mg_per_kg DESC
LIMIT 25;`,
  },
  {
    title: 'Samples where nothing was detected',
    why: 'Uses the below_detection_limit flag — a clean sample is a result, not missing data.',
    sql: `SELECT json_extract(doc, '$.lims_id')   AS lims,
       json_extract(doc, '$.factory')   AS factory,
       COUNT(*)                         AS rows
FROM screening
WHERE json_extract(doc, '$.below_detection_limit') = 1
GROUP BY lims, factory
ORDER BY rows DESC;`,
  },
  {
    title: 'Compounds that are still unidentified',
    why: 'Rows with no chemical link — PubChem could not confirm the name and CAS together.',
    sql: `SELECT json_extract(doc, '$.compound_name') AS compound,
       json_extract(doc, '$.cas')           AS cas,
       COUNT(*)                             AS rows
FROM screening
WHERE chemical_id IS NULL
GROUP BY compound, cas
ORDER BY rows DESC
LIMIT 50;`,
  },
  {
    title: 'Screening joined to the chemical registry',
    why: 'chemical_id is a real indexed column on both tables, so this join is cheap.',
    sql: `SELECT json_extract(c.doc, '$.name')              AS chemical,
       json_extract(c.doc, '$.molecular_formula')  AS formula,
       COUNT(s.id)                                 AS screening_rows
FROM chemicals c
JOIN screening s ON s.chemical_id = c.chemical_id
GROUP BY chemical, formula
ORDER BY screening_rows DESC
LIMIT 25;`,
  },
  {
    title: 'Exact duplicate rows',
    why: 'The same row present twice, as opposed to a repeat measurement.',
    sql: `SELECT json_extract(doc, '$.lims_id')       AS lims,
       json_extract(doc, '$.compound_name') AS compound,
       COUNT(*)                             AS copies
FROM screening
WHERE json_extract(doc, '$.duplicate_kind') = 'identical'
GROUP BY json_extract(doc, '$.duplicate_group')
ORDER BY copies DESC;`,
  },
  {
    title: 'Migration by temperature and time',
    why: 'Two grouping keys and an average — the shape most reporting questions take.',
    sql: `SELECT json_extract(doc, '$.migration_temperature_c') AS temp_c,
       json_extract(doc, '$.migration_time_h')         AS hours,
       ROUND(AVG(CAST(json_extract(doc, '$.mg_per_dm2_material') AS REAL)), 4) AS avg_mg_dm2,
       COUNT(*) AS rows
FROM screening
GROUP BY temp_c, hours
ORDER BY rows DESC;`,
  },
]

export default function QueryConsole() {
  const [sql, setSql] = useState(EXAMPLES[0].sql)
  const [result, setResult] = useState(null)
  const [running, setRunning] = useState(false)
  const [schema, setSchema] = useState(null)
  const [showSchema, setShowSchema] = useState(false)

  useEffect(() => {
    getQuerySchema()
      .then(({ data }) => setSchema(data))
      .catch(() => {})
  }, [])

  const execute = async () => {
    setRunning(true)
    try {
      const { data } = await runQuery(sql)
      setResult(data)
      toast.success(`${data.row_count} row${data.row_count === 1 ? '' : 's'} in ${data.elapsed_ms} ms`)
    } catch (error) {
      const message = error?.response?.data?.error || error?.response?.data?.detail || 'Query failed'
      setResult({ error: String(message) })
      toast.error('Query failed')
    } finally {
      setRunning(false)
    }
  }

  const downloadCsv = () => {
    if (!result?.rows) return
    const escape = (v) => {
      const s = v === null || v === undefined ? '' : String(v)
      return /[",\n]/.test(s) ? `"${s.replace(/"/g, '""')}"` : s
    }
    const csv = [result.columns.join(','), ...result.rows.map((r) => r.map(escape).join(','))].join('\n')
    const url = URL.createObjectURL(new Blob([csv], { type: 'text/csv' }))
    const a = document.createElement('a')
    a.href = url
    a.download = 'query-result.csv'
    a.click()
    URL.revokeObjectURL(url)
  }

  return (
    <div className="space-y-4 fade-in">
      <div>
        <h1 className="text-2xl font-bold text-gray-800">Query</h1>
        <p className="text-gray-500">
          Run a read-only SQL query against the database. Only <code>SELECT</code> is
          permitted — the connection itself is opened read-only, so nothing here can
          change your data.
        </p>
      </div>

      <div className="grid lg:grid-cols-3 gap-4">
        {/* editor + results */}
        <div className="lg:col-span-2 space-y-3">
          <div className="bg-white rounded-xl shadow-sm p-3">
            <textarea
              value={sql}
              onChange={(e) => setSql(e.target.value)}
              spellCheck={false}
              rows={10}
              className="w-full font-mono text-sm p-3 border border-gray-200 rounded-lg focus:ring-2 focus:ring-purple-400 focus:border-transparent"
              placeholder="SELECT …"
            />
            <div className="flex items-center gap-2 mt-2">
              <button
                onClick={execute}
                disabled={running}
                className="inline-flex items-center px-4 py-2 bg-purple-600 text-white rounded-lg hover:bg-purple-700 disabled:opacity-50"
              >
                <PlayIcon className="h-4 w-4 mr-1.5" />
                {running ? 'Running…' : 'Run query'}
              </button>
              <button
                onClick={() => setShowSchema((v) => !v)}
                className="inline-flex items-center px-3 py-2 border border-gray-300 rounded-lg text-sm hover:bg-gray-50"
              >
                <TableCellsIcon className="h-4 w-4 mr-1.5" />
                {showSchema ? 'Hide' : 'Show'} tables &amp; fields
              </button>
              {result?.rows?.length > 0 && (
                <button
                  onClick={downloadCsv}
                  className="inline-flex items-center px-3 py-2 border border-gray-300 rounded-lg text-sm hover:bg-gray-50"
                >
                  <ArrowDownTrayIcon className="h-4 w-4 mr-1.5" />
                  Download CSV
                </button>
              )}
              <span className="ml-auto text-xs text-gray-400">Ctrl/Cmd + Enter to run</span>
            </div>
          </div>

          {showSchema && schema && (
            <div className="bg-white rounded-xl shadow-sm p-4 text-sm">
              <p className="text-xs text-gray-500 mb-3">
                Each table has a few real columns plus <code>doc</code>, which holds the
                whole record as JSON. Reach inside it with{' '}
                <code>json_extract(doc, '$.field')</code>.
              </p>
              {schema.tables.map((t) => (
                <div key={t.table} className="mb-3">
                  <p className="font-medium text-gray-800">
                    {t.table}{' '}
                    <span className="text-gray-400 font-normal">
                      ({t.rows.toLocaleString()} rows)
                    </span>
                  </p>
                  <p className="text-xs text-gray-500 mt-0.5">
                    columns: {t.columns.map((c) => c.name).join(', ') || '—'}
                  </p>
                  {t.doc_keys.length > 0 && (
                    <p className="text-xs text-gray-500 mt-0.5">
                      <span className="text-gray-400">doc fields:</span>{' '}
                      {t.doc_keys.join(', ')}
                    </p>
                  )}
                </div>
              ))}
            </div>
          )}

          {result && (
            <div className="bg-white rounded-xl shadow-sm overflow-hidden">
              {result.error ? (
                <div className="p-4 text-red-700 bg-red-50 font-mono text-sm">{result.error}</div>
              ) : (
                <>
                  <div className="px-4 py-2 border-b border-gray-100 text-xs text-gray-500">
                    {result.row_count.toLocaleString()} rows · {result.elapsed_ms} ms
                    {result.truncated && (
                      <span className="ml-2 text-amber-600">
                        truncated at {result.limit.toLocaleString()} — add a LIMIT or narrow
                        the query
                      </span>
                    )}
                  </div>
                  <div className="overflow-x-auto max-h-[28rem]">
                    <table className="min-w-full text-sm">
                      <thead className="bg-gray-50 sticky top-0">
                        <tr>
                          {result.columns.map((c) => (
                            <th
                              key={c}
                              className="px-3 py-2 text-left font-semibold text-gray-700 whitespace-nowrap border-b"
                            >
                              {c}
                            </th>
                          ))}
                        </tr>
                      </thead>
                      <tbody>
                        {result.rows.map((row, i) => (
                          <tr key={i} className="border-b border-gray-50 hover:bg-purple-50/40">
                            {row.map((cell, j) => (
                              <td key={j} className="px-3 py-1.5 text-gray-800 max-w-md truncate">
                                {cell === null ? (
                                  <span className="text-gray-300">null</span>
                                ) : (
                                  String(cell)
                                )}
                              </td>
                            ))}
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                </>
              )}
            </div>
          )}
        </div>

        {/* examples */}
        <div className="bg-white rounded-xl shadow-sm p-4 space-y-3 h-fit">
          <h2 className="font-semibold text-gray-800">Examples</h2>
          <p className="text-xs text-gray-500">
            Click one to load it, then edit freely.
          </p>
          {EXAMPLES.map((ex) => (
            <button
              key={ex.title}
              onClick={() => setSql(ex.sql)}
              className="block w-full text-left p-2.5 rounded-lg border border-gray-200 hover:border-purple-300 hover:bg-purple-50/40"
            >
              <span className="block text-sm font-medium text-gray-800">{ex.title}</span>
              <span className="block text-xs text-gray-500 mt-0.5">{ex.why}</span>
            </button>
          ))}
        </div>
      </div>
    </div>
  )
}
