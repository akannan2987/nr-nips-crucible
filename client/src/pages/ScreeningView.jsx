import { useState, useEffect, useMemo, useCallback } from 'react'
import { Link, useSearchParams } from 'react-router-dom'
import {
  MagnifyingGlassIcon,
  PlusIcon,
  TrashIcon,
  EyeIcon,
  BeakerIcon,
  TableCellsIcon,
  AdjustmentsHorizontalIcon,
  ArrowDownTrayIcon,
  XMarkIcon,
} from '@heroicons/react/24/outline'
import toast from 'react-hot-toast'
import {
  getScreening,
  deleteScreening,
  getScreeningColumns,
  getDuplicatesSummary,
  screeningExportUrl,
} from '../services/api'

/**
 * Screening data table.
 *
 * Records loaded from different laboratory templates share almost no field
 * names, so the columns are read from the data itself (`/api/screening/columns`)
 * rather than hard-coded. Two view modes:
 *
 *   Raw         — every column, in the order the source file had them, the way
 *                 the spreadsheet looks.
 *   Customised  — the user picks which columns to show.
 *
 * Filtering is per column plus a free-text search across all fields, and
 * whatever is filtered can be exported in full.
 */

const PAGE_SIZES = [25, 50, 100, 250]

// Columns worth showing first when there are too many to fit. Anything else
// still appears — this only decides what the customised view starts with.
const DEFAULT_VISIBLE = 12

export default function ScreeningView() {
  const [searchParams] = useSearchParams()

  const [rows, setRows] = useState([])
  const [columns, setColumns] = useState([])
  const [tags, setTags] = useState([])
  const [loading, setLoading] = useState(true)

  const [viewMode, setViewMode] = useState('raw') // 'raw' | 'custom'
  const [visible, setVisible] = useState([])      // column keys, customised view
  const [showPicker, setShowPicker] = useState(false)
  const [showLegend, setShowLegend] = useState(false)
  const [duplicates, setDuplicates] = useState('all')
  const [dupSummary, setDupSummary] = useState(null)
  const [showDupHelp, setShowDupHelp] = useState(false)

  const [search, setSearch] = useState('')
  const [searchInput, setSearchInput] = useState('')
  const [colFilters, setColFilters] = useState({})
  const [tag, setTag] = useState('')
  // Set from the URL when arriving via "see screening for this chemical".
  const chemicalFilter = searchParams.get('chemical_id') || ''

  const [sort, setSort] = useState({ key: null, dir: 'asc', numeric: false })
  const [pagination, setPagination] = useState({ page: 1, limit: 50, total: 0, totalPages: 0 })
  const [selectedRecord, setSelectedRecord] = useState(null)

  // ---- column metadata -------------------------------------------------
  useEffect(() => {
    getScreeningColumns()
      .then(({ data }) => {
        setColumns(data.columns)
        setTags(data.tags || [])
        // Start the customised view with the best-populated columns, so it is
        // useful before the user has chosen anything.
        const ranked = [...data.columns].sort((a, b) => b.filled - a.filled)
        setVisible(ranked.slice(0, DEFAULT_VISIBLE).map((c) => c.key))
      })
      .catch(() => toast.error('Could not read the column list'))
    getDuplicatesSummary()
      .then(({ data }) => setDupSummary(data))
      .catch(() => {})
  }, [])

  // ---- data ------------------------------------------------------------
  const queryParams = useMemo(() => {
    const params = {
      page: pagination.page,
      limit: pagination.limit,
      search,
      chemical_id: chemicalFilter,
      tag,
      sort: sort.key || '',
      dir: sort.dir,
      sort_numeric: sort.numeric ? 'true' : '',
      duplicates,
    }
    Object.entries(colFilters).forEach(([key, value]) => {
      if (value) params[`f.${key}`] = value
    })
    return params
  }, [pagination.page, pagination.limit, search, chemicalFilter, tag, colFilters, sort, duplicates])

  const loadScreening = useCallback(async () => {
    setLoading(true)
    try {
      const response = await getScreening(queryParams)
      setRows(response.data.data)
      setPagination((prev) => ({ ...prev, ...response.data.pagination }))
    } catch (error) {
      toast.error('Failed to load screening data')
      console.error(error)
    } finally {
      setLoading(false)
    }
  }, [queryParams])

  useEffect(() => {
    loadScreening()
  }, [loadScreening])

  // ---- which columns are on screen ------------------------------------
  // Coverage stats take a moment to compute on a large table, so until they
  // arrive the columns are derived from the rows themselves. The table is
  // therefore usable immediately rather than waiting on metadata.
  const effectiveColumns = useMemo(() => {
    if (columns.length > 0) return columns
    const keys = []
    rows.forEach((row) => {
      Object.keys(row).forEach((k) => {
        if (!['id', 'raw', 'source', 'updated_at', 'chemical_name'].includes(k) && !keys.includes(k))
          keys.push(k)
      })
    })
    return keys.map((k) => ({ key: k, label: humanise(k), filled: 0, coverage: 0 }))
  }, [columns, rows])

  const shownColumns = useMemo(() => {
    if (viewMode === 'raw') return effectiveColumns
    return effectiveColumns.filter((c) => visible.includes(c.key))
  }, [viewMode, effectiveColumns, visible])

  // Columns this application added rather than ones from the uploaded file.
  const derivedColumns = useMemo(
    () => effectiveColumns.filter((c) => c.derived && c.description),
    [effectiveColumns]
  )

  const activeFilterCount =
    Object.values(colFilters).filter(Boolean).length + (search ? 1 : 0) + (tag ? 1 : 0)

  const handleSearch = (e) => {
    e.preventDefault()
    setSearch(searchInput)
    setPagination((p) => ({ ...p, page: 1 }))
  }

  // Filter boxes update as you type, but a filtered query has to scan every
  // record, so the request is held back until typing pauses. Without this,
  // every keystroke would queue a multi-second scan.
  const [filterDraft, setFilterDraft] = useState({})
  useEffect(() => {
    const timer = setTimeout(() => {
      setColFilters(filterDraft)
      setPagination((p) => ({ ...p, page: 1 }))
    }, 400)
    return () => clearTimeout(timer)
  }, [filterDraft])

  // Click a heading to sort by it; click again to reverse; a third time clears
  // the sort and returns to import order.
  const toggleSort = (col) => {
    setSort((prev) => {
      if (prev.key !== col.key) return { key: col.key, dir: 'asc', numeric: col.type === 'number' }
      if (prev.dir === 'asc') return { key: col.key, dir: 'desc', numeric: col.type === 'number' }
      return { key: null, dir: 'asc', numeric: false }
    })
    setPagination((p) => ({ ...p, page: 1 }))
  }

  const setFilter = (key, value) => {
    setFilterDraft((prev) => ({ ...prev, [key]: value }))
  }

  const clearFilters = () => {
    setColFilters({})
    setFilterDraft({})
    setSearch('')
    setSearchInput('')
    setTag('')
    setPagination((p) => ({ ...p, page: 1 }))
  }

  const handleDelete = async (id) => {
    if (!window.confirm('Delete this screening record?')) return
    try {
      await deleteScreening(id)
      toast.success('Record deleted')
      loadScreening()
    } catch {
      toast.error('Could not delete the record')
    }
  }

  const exportHref = (format, raw = false) =>
    screeningExportUrl({
      format,
      raw: raw ? 'true' : '',
      search,
      tag,
      chemical_id: chemicalFilter,
      // In the customised view export exactly what is on screen; in raw view
      // export everything.
      columns: viewMode === 'custom' ? visible.join(',') : '',
      duplicates,
      ...Object.fromEntries(
        Object.entries(colFilters)
          .filter(([, v]) => v)
          .map(([k, v]) => [`f.${k}`, v])
      ),
    })

  return (
    <div className="space-y-4">
      {/* ---- header -------------------------------------------------- */}
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <h1 className="text-2xl font-bold text-gray-900">Screening Data</h1>
          <p className="text-sm text-gray-500">
            {pagination.total.toLocaleString()} records
            {activeFilterCount > 0 && ' matching your filters'}
            {effectiveColumns.length > 0 && ` · ${effectiveColumns.length} columns`}
          </p>
        </div>
        <Link
          to="/screening/upload"
          className="inline-flex items-center px-4 py-2 bg-purple-600 text-white rounded-lg hover:bg-purple-700"
        >
          <PlusIcon className="h-5 w-5 mr-2" />
          Upload
        </Link>
      </div>

      {/* ---- toolbar ------------------------------------------------- */}
      <div className="bg-white rounded-xl shadow-sm p-4 space-y-3">
        <div className="flex flex-wrap items-center gap-3">
          <form onSubmit={handleSearch} className="flex-1 min-w-[240px] relative">
            <MagnifyingGlassIcon className="h-5 w-5 text-gray-400 absolute left-3 top-2.5" />
            <input
              value={searchInput}
              onChange={(e) => setSearchInput(e.target.value)}
              placeholder="Search every column…"
              className="w-full pl-10 pr-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-purple-500 focus:border-transparent"
            />
          </form>

          {/* view mode */}
          <div className="inline-flex rounded-lg border border-gray-300 overflow-hidden">
            <button
              onClick={() => setViewMode('raw')}
              className={`px-3 py-2 text-sm inline-flex items-center gap-1.5 ${
                viewMode === 'raw' ? 'bg-purple-600 text-white' : 'bg-white text-gray-700'
              }`}
            >
              <TableCellsIcon className="h-4 w-4" />
              Raw view
            </button>
            <button
              onClick={() => setViewMode('custom')}
              className={`px-3 py-2 text-sm inline-flex items-center gap-1.5 ${
                viewMode === 'custom' ? 'bg-purple-600 text-white' : 'bg-white text-gray-700'
              }`}
            >
              <AdjustmentsHorizontalIcon className="h-4 w-4" />
              Choose columns
              {viewMode === 'custom' && (
                <span className="ml-1 text-xs opacity-80">({visible.length})</span>
              )}
            </button>
          </div>

          {tags.length > 0 && (
            <select
              value={tag}
              onChange={(e) => {
                setTag(e.target.value)
                setPagination((p) => ({ ...p, page: 1 }))
              }}
              className="px-3 py-2 border border-gray-300 rounded-lg text-sm"
            >
              <option value="">All sources</option>
              {tags.map((t) => (
                <option key={t} value={t}>
                  {t}
                </option>
              ))}
            </select>
          )}

          {/* Which rows to show, by duplicate state. A single toggle could
              only ever express "all" or "unique"; these are four distinct
              questions someone actually asks of this data. */}
          <select
            value={duplicates}
            onChange={(e) => {
              setDuplicates(e.target.value)
              setPagination((p) => ({ ...p, page: 1 }))
            }}
            className={`px-3 py-2 border rounded-lg text-sm ${
              duplicates === 'all'
                ? 'border-gray-300 bg-white text-gray-700'
                : 'border-purple-400 bg-purple-50 text-purple-700 font-medium'
            }`}
          >
            <option value="all">
              All rows{dupSummary ? ` (${dupSummary.total.toLocaleString()})` : ''}
            </option>
            <option value="unique">
              Unique rows — hide exact copies
              {dupSummary ? ` (${dupSummary.unique.toLocaleString()})` : ''}
            </option>
            <option value="identical">
              Only exact copies (amber)
              {dupSummary ? ` (${dupSummary.identical.toLocaleString()})` : ''}
            </option>
            <option value="repeat">
              Only repeat measurements (blue)
              {dupSummary ? ` (${dupSummary.repeat_measurement.toLocaleString()})` : ''}
            </option>
            <option value="flagged">
              Anything flagged — amber and blue
              {dupSummary
                ? ` (${(dupSummary.identical + dupSummary.repeat_measurement).toLocaleString()})`
                : ''}
            </option>
          </select>

          <select
            value={pagination.limit}
            onChange={(e) =>
              setPagination((p) => ({ ...p, limit: Number(e.target.value), page: 1 }))
            }
            className="px-3 py-2 border border-gray-300 rounded-lg text-sm"
          >
            {PAGE_SIZES.map((n) => (
              <option key={n} value={n}>
                {n} rows
              </option>
            ))}
          </select>

          {/* export */}
          <div className="relative group">
            <button className="px-3 py-2 border border-gray-300 rounded-lg text-sm inline-flex items-center gap-1.5 hover:bg-gray-50">
              <ArrowDownTrayIcon className="h-4 w-4" />
              Export
            </button>
            <div className="absolute right-0 z-20 mt-1 w-56 bg-white border border-gray-200 rounded-lg shadow-lg opacity-0 invisible group-hover:opacity-100 group-hover:visible transition">
              <p className="px-3 pt-2 pb-1 text-xs text-gray-500">
                Exports all {pagination.total.toLocaleString()} matching rows
              </p>
              {[
                ['csv', 'CSV'],
                ['xlsx', 'Excel (.xlsx)'],
                ['json', 'JSON'],
                ['tsv', 'Tab-separated'],
              ].map(([fmt, label]) => (
                <a
                  key={fmt}
                  href={exportHref(fmt)}
                  className="block px-3 py-2 text-sm text-gray-700 hover:bg-gray-50"
                >
                  {label}
                </a>
              ))}
              <div className="border-t border-gray-100">
                <a
                  href={exportHref('csv', true)}
                  className="block px-3 py-2 text-sm text-gray-700 hover:bg-gray-50"
                >
                  Original values (CSV)
                  <span className="block text-xs text-gray-400">
                    exactly as the source file had them
                  </span>
                </a>
              </div>
            </div>
          </div>

          {activeFilterCount > 0 && (
            <button
              onClick={clearFilters}
              className="px-3 py-2 text-sm text-gray-600 hover:text-gray-900 inline-flex items-center gap-1"
            >
              <XMarkIcon className="h-4 w-4" />
              Clear {activeFilterCount} filter{activeFilterCount > 1 ? 's' : ''}
            </button>
          )}
        </div>

        {/* Shading legend. Colour with no key is decoration, not information —
            and "repeat measurement" needs a worked example to mean anything. */}
        <div className="text-xs text-gray-600 space-y-1.5">
          <div className="flex flex-wrap items-start gap-x-6 gap-y-1.5">
            <span className="flex items-start gap-1.5">
              <span className="inline-block w-4 h-3 mt-0.5 rounded-sm bg-amber-100 border border-amber-200 shrink-0" />
              <span>
                <strong>exact copy</strong> — every column matches another row, the same
                row present twice. Safe to hide.
                {dupSummary && ` ${dupSummary.identical.toLocaleString()} rows.`}
              </span>
            </span>
            <span className="flex items-start gap-1.5">
              <span className="inline-block w-4 h-3 mt-0.5 rounded-sm bg-sky-100 border border-sky-200 shrink-0" />
              <span>
                <strong>repeat measurement</strong> — same sample and compound, but
                different measured values.
                {dupSummary && ` ${dupSummary.repeat_measurement.toLocaleString()} rows.`}
              </span>
            </span>
          </div>
          <button
            onClick={() => setShowDupHelp((v) => !v)}
            className="text-purple-600 hover:text-purple-700"
          >
            {showDupHelp ? 'Hide' : 'What is a repeat measurement?'}
          </button>
          {showDupHelp && (
            <div className="border border-sky-100 bg-sky-50/60 rounded-lg p-3 text-gray-700 space-y-2">
              <p>
                Two rows describe the same sample, the same compound and the same
                conditions — so they look like duplicates — but the numbers differ.
                The substance was measured more than once.
              </p>
              <pre className="bg-white/70 rounded p-2 overflow-x-auto text-[11px] leading-relaxed">
{`lims        822486840        822486840     <- same
name        Hump of hydro…   Hump of hydro…  <- same
simulant    isooctane        isooctane     <- same
mg_dm2_material   0.0496     0.3515        <- DIFFERENT
mg_kg_food        5.9481    42.1798        <- DIFFERENT`}
              </pre>
              <p>
                Both numbers are real results. Hiding one would discard a measurement,
                so <strong>“Unique rows” keeps them</strong> and removes only exact
                copies. Use <em>Only repeat measurements</em> to review them and decide
                for yourself.
              </p>
            </div>
          )}
        </div>

        {/* What the extra columns are. Shown in the page rather than only in a
            tooltip: a column nobody can explain is a column nobody trusts. */}
        {derivedColumns.length > 0 && (
          <div>
            <button
              onClick={() => setShowLegend((s) => !s)}
              className="text-sm text-purple-600 hover:text-purple-700"
            >
              {showLegend ? 'Hide' : 'What are the'} {derivedColumns.length} columns marked{' '}
              <span className="text-[10px] border border-purple-200 rounded px-1">+</span>?
            </button>
            {showLegend && (
              <div className="mt-2 border border-purple-100 bg-purple-50/50 rounded-lg p-3 space-y-2">
                <p className="text-xs text-gray-600">
                  Every other column is your file's own, shown under its original heading.
                  These were added during import — each one exists because cleaning found
                  something that would otherwise have been lost silently.
                </p>
                {derivedColumns.map((col) => (
                  <div key={col.key} className="text-sm">
                    <span className="font-medium text-gray-800">{col.label}</span>
                    <span className="ml-2 text-xs text-gray-400">
                      {(col.filled || 0).toLocaleString()} rows
                    </span>
                    <p className="text-gray-600 text-xs mt-0.5">{col.description}</p>
                  </div>
                ))}
              </div>
            )}
          </div>
        )}

        {/* column picker */}
        {viewMode === 'custom' && (
          <div>
            <button
              onClick={() => setShowPicker((s) => !s)}
              className="text-sm text-purple-600 hover:text-purple-700"
            >
              {showPicker ? 'Hide' : 'Show'} column list
            </button>
            {showPicker && (
              <div className="mt-2 border border-gray-200 rounded-lg p-3">
                <div className="flex gap-3 mb-2 text-xs">
                  <button
                    onClick={() => setVisible(effectiveColumns.map((c) => c.key))}
                    className="text-purple-600 hover:underline"
                  >
                    Select all
                  </button>
                  <button
                    onClick={() => setVisible([])}
                    className="text-purple-600 hover:underline"
                  >
                    Clear all
                  </button>
                </div>
                <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-4 gap-x-4 gap-y-1 max-h-64 overflow-y-auto">
                  {effectiveColumns.map((col) => (
                    <label
                      key={col.key}
                      className="flex items-center gap-2 text-sm text-gray-700 cursor-pointer"
                    >
                      <input
                        type="checkbox"
                        checked={visible.includes(col.key)}
                        onChange={(e) =>
                          setVisible((prev) =>
                            e.target.checked
                              ? [...prev, col.key]
                              : prev.filter((k) => k !== col.key)
                          )
                        }
                        className="rounded border-gray-300 text-purple-600"
                      />
                      <span className="truncate">
                        {col.label}
                        {col.derived && <span className="ml-1 text-purple-500">+</span>}
                      </span>
                      <span className="ml-auto text-xs text-gray-400">
                        {Math.round(col.coverage * 100)}%
                      </span>
                    </label>
                  ))}
                </div>
              </div>
            )}
          </div>
        )}
      </div>

      {/* ---- table --------------------------------------------------- */}
      <div className="bg-white rounded-xl shadow-sm overflow-hidden">
        {loading ? (
          <div className="p-12 text-center text-gray-500">Loading…</div>
        ) : rows.length === 0 ? (
          <div className="p-12 text-center">
            <BeakerIcon className="h-10 w-10 text-gray-300 mx-auto mb-3" />
            <p className="text-gray-500">No screening records match.</p>
          </div>
        ) : (
          <div className="overflow-x-auto">
            <table className="min-w-full text-sm border-collapse">
              <thead className="bg-gray-50 sticky top-0">
                <tr>
                  <th className="px-3 py-2 text-left font-semibold text-gray-700 whitespace-nowrap border-b border-gray-200">
                    Chemical
                  </th>
                  {shownColumns.map((col) => (
                    <th
                      key={col.key}
                      onClick={() => toggleSort(col)}
                      className="px-3 py-2 text-left font-semibold text-gray-700 whitespace-nowrap border-b border-gray-200 cursor-pointer select-none hover:bg-gray-100"
                      title={
                        (col.derived
                          ? `Added by Crucible — not a column in your file.\n\n${col.description || ''}\n\n`
                          : `Column "${col.source_column}" from your file.\n\n`) +
                        `${(col.filled || 0).toLocaleString()} rows have a value.\nClick to sort.`
                      }
                    >
                      <span className="inline-flex items-center gap-1">
                        {col.label}
                        {/* Marks a column this application added rather than one
                            that came from the uploaded file. */}
                        {col.derived && (
                          <span
                            className="text-[10px] font-normal text-purple-500 border border-purple-200 rounded px-1"
                            aria-label="added by Crucible"
                          >
                            +
                          </span>
                        )}
                        {sort.key === col.key && (
                          <span className="text-purple-600">{sort.dir === 'asc' ? '▲' : '▼'}</span>
                        )}
                      </span>
                    </th>
                  ))}
                  <th className="px-3 py-2 border-b border-gray-200" />
                </tr>
                {/* per-column filter row, the way a spreadsheet filters */}
                <tr>
                  <th className="px-2 py-1 border-b border-gray-200 bg-white" />
                  {shownColumns.map((col) => (
                    <th key={col.key} className="px-2 py-1 border-b border-gray-200 bg-white">
                      <input
                        value={filterDraft[col.key] || ''}
                        onChange={(e) => setFilter(col.key, e.target.value)}
                        placeholder="filter…"
                        className="w-full min-w-[90px] px-2 py-1 text-xs font-normal border border-gray-200 rounded focus:ring-1 focus:ring-purple-400"
                      />
                    </th>
                  ))}
                  <th className="border-b border-gray-200 bg-white" />
                </tr>
              </thead>
              <tbody>
                {rows.map((record) => (
                  <tr
                    key={record.id}
                    className={`border-b border-gray-100 ${duplicateShade(record)}`}
                    title={duplicateTitle(record)}
                  >
                    <td className="px-3 py-1.5 whitespace-nowrap">
                      {/* A compound identified in PubChem (its name and CAS
                          number agreeing) is registered in the Chemicals
                          module, so it links there. Anything else shows the
                          name exactly as the source file gave it — the
                          observation is real even when the identity is not
                          established. */}
                      {record.chemical_id ? (
                        <Link
                          to={`/chemicals?search=${encodeURIComponent(record.cas || record.compound_name || '')}`}
                          className="text-purple-600 hover:underline"
                          title="Identified via PubChem — open in Chemicals"
                        >
                          {record.chemical_name || record.compound_name}
                        </Link>
                      ) : (
                        <span
                          className="text-gray-700"
                          title="Not identified — shown as the source file recorded it"
                        >
                          {record.compound_name || '—'}
                        </span>
                      )}
                    </td>
                    {shownColumns.map((col) => (
                      <td
                        key={col.key}
                        className="px-3 py-1.5 text-gray-800 max-w-xs truncate"
                        title={formatCell(record[col.key])}
                      >
                        {formatCell(record[col.key])}
                      </td>
                    ))}
                    <td className="px-3 py-1.5 whitespace-nowrap">
                      <div className="flex gap-2">
                        <button
                          onClick={() => setSelectedRecord(record)}
                          className="text-gray-400 hover:text-purple-600"
                          title="View full record"
                        >
                          <EyeIcon className="h-4 w-4" />
                        </button>
                        <button
                          onClick={() => handleDelete(record.id)}
                          className="text-gray-400 hover:text-red-600"
                          title="Delete"
                        >
                          <TrashIcon className="h-4 w-4" />
                        </button>
                      </div>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}

        {/* ---- pagination -------------------------------------------- */}
        {pagination.totalPages > 1 && (
          <div className="flex items-center justify-between px-4 py-3 border-t border-gray-200">
            <p className="text-sm text-gray-600">
              Page {pagination.page} of {pagination.totalPages.toLocaleString()} ·{' '}
              {pagination.total.toLocaleString()} records
            </p>
            <div className="flex gap-2">
              <button
                onClick={() => setPagination((p) => ({ ...p, page: Math.max(1, p.page - 1) }))}
                disabled={pagination.page === 1}
                className="px-3 py-1.5 text-sm border border-gray-300 rounded-lg disabled:opacity-40"
              >
                Previous
              </button>
              <button
                onClick={() =>
                  setPagination((p) => ({
                    ...p,
                    page: Math.min(p.totalPages, p.page + 1),
                  }))
                }
                disabled={pagination.page >= pagination.totalPages}
                className="px-3 py-1.5 text-sm border border-gray-300 rounded-lg disabled:opacity-40"
              >
                Next
              </button>
            </div>
          </div>
        )}
      </div>

      {/* ---- record detail ------------------------------------------- */}
      {selectedRecord && (
        <RecordDetail record={selectedRecord} onClose={() => setSelectedRecord(null)} />
      )}
    </div>
  )
}

/**
 * Shading for rows that share an identity with another row.
 *
 * Two different situations, deliberately given different colours:
 *   amber — every column matches another row: the same row present twice.
 *   blue  — same sample and compound, but different measured values: a repeat
 *           measurement, which is real data and must not be mistaken for noise.
 */
function duplicateShade(record) {
  if (record.duplicate_kind === 'identical') return 'bg-amber-50 hover:bg-amber-100'
  if (record.duplicate_kind === 'repeat_measurement') return 'bg-sky-50 hover:bg-sky-100'
  return 'hover:bg-purple-50/40'
}

function duplicateTitle(record) {
  if (record.duplicate_kind === 'identical')
    return 'Identical to another row in every column — an exact copy. "Unique rows only" hides the extra copies.'
  if (record.duplicate_kind === 'repeat_measurement')
    return 'Same sample, compound and conditions as another row, but different measured values — a repeat measurement. Kept even under "Unique rows only".'
  return undefined
}

/** `mg_per_kg_food` → `Mg Per Kg Food`, matching the server's column labels. */
function humanise(key) {
  return key
    .replace(/_/g, ' ')
    .trim()
    .replace(/\b\w/g, (c) => c.toUpperCase())
}

/** Render any stored value as table text. */
function formatCell(value) {
  if (value === null || value === undefined || value === '') return ''
  if (typeof value === 'boolean') return value ? 'Yes' : 'No'
  if (Array.isArray(value)) return value.join('; ')
  if (typeof value === 'object') return JSON.stringify(value)
  return String(value)
}

/**
 * The full record, cleaned values beside the untouched original.
 * Showing both is the point: you can always see what the source actually said.
 */
function RecordDetail({ record, onClose }) {
  const raw = record.raw || {}
  const source = record.source || {}
  const cleaned = Object.entries(record).filter(
    ([key]) => !['raw', 'source', 'id', 'updated_at'].includes(key)
  )

  return (
    <div
      className="fixed inset-0 bg-black/40 flex items-center justify-center p-4 z-50"
      onClick={onClose}
    >
      <div
        className="bg-white rounded-xl max-w-5xl w-full max-h-[85vh] overflow-y-auto"
        onClick={(e) => e.stopPropagation()}
      >
        <div className="flex items-start justify-between p-5 border-b border-gray-200">
          <div>
            <h2 className="text-lg font-bold text-gray-900">
              {record.compound_name || record.chemical_name || 'Screening record'}
            </h2>
            {source.tag && (
              <p className="text-sm text-gray-500 mt-0.5">
                <span className="inline-block px-2 py-0.5 rounded bg-purple-100 text-purple-700 text-xs font-medium">
                  {source.tag}
                </span>
                {source.row_number && ` · row ${source.row_number} of the source file`}
              </p>
            )}
          </div>
          <button onClick={onClose} className="text-gray-400 hover:text-gray-600">
            <XMarkIcon className="h-6 w-6" />
          </button>
        </div>

        <div className="grid md:grid-cols-2 gap-6 p-5">
          <div>
            <h3 className="text-sm font-semibold text-gray-700 mb-2">Cleaned values</h3>
            <dl className="space-y-1">
              {cleaned.map(([key, value]) => (
                <div key={key} className="flex gap-3 text-sm border-b border-gray-50 py-1">
                  <dt className="w-44 shrink-0 text-gray-500">{key.replace(/_/g, ' ')}</dt>
                  <dd className="text-gray-900 break-words">{formatCell(value) || '—'}</dd>
                </div>
              ))}
            </dl>
          </div>
          <div>
            <h3 className="text-sm font-semibold text-gray-700 mb-2">
              Original row
              <span className="ml-2 font-normal text-xs text-gray-400">
                exactly as the file had it
              </span>
            </h3>
            <dl className="space-y-1">
              {Object.entries(raw).map(([key, value]) => (
                <div key={key} className="flex gap-3 text-sm border-b border-gray-50 py-1">
                  <dt className="w-44 shrink-0 text-gray-500">{key.replace(/\n/g, ' ')}</dt>
                  <dd className="text-gray-900 break-words font-mono text-xs">{value}</dd>
                </div>
              ))}
            </dl>
          </div>
        </div>
      </div>
    </div>
  )
}
