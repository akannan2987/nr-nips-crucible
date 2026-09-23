import { useState, useEffect, useCallback } from 'react'
import { Link, useLocation } from 'react-router-dom'
import { CheckCircleIcon, ArrowPathIcon, XMarkIcon, ArrowTopRightOnSquareIcon, BeakerIcon } from '@heroicons/react/24/outline'
import toast from 'react-hot-toast'
import {
  getRegistryAudit,
  reviewAuditItems,
  mergeChemicals,
  setChemicalIdentifier,
  deleteChemical,
  deriveStructures,
} from '../services/api'
import StructurePicture from '../components/StructurePicture'

/**
 * CR-10 — the attention page.
 *
 * Everything the registry wants a person to look at, in one place, with the
 * buttons to act: shared identifiers side by side with the other holder
 * (merge, or keep both), batch conflicts with each batch's value (mark
 * reviewed), pending identifiers (set it), and the formula findings (mark
 * reviewed, or delete), and since CR-12 the structure findings (a derived
 * structure that disagrees with the formula, weight or InChI the source
 * recorded; mark reviewed) with the button that derives them. The list comes
 * from GET /api/chemicals/audit — the same call the terminal audit script
 * makes — so the browser and the terminal never disagree about what is flagged.
 *
 * A "reviewed" item stays listed, greyed, and stops counting on the banner;
 * the mark is data on the entry (`reviewed: {key: timestamp}`), so it is
 * visible from every route and can be lifted.
 */

const KIND_LABEL = { cas: 'CAS number', dtxsid: 'DTXSID', pubchem: 'PubChem compound' }

const fmt = (v) => (v === null || v === undefined || v === '' ? '—' : String(v))

export default function RegistryAttention() {
  const [audit, setAudit] = useState(null)
  const [loading, setLoading] = useState(true)
  const [showReviewed, setShowReviewed] = useState(false)
  const [busy, setBusy] = useState(false)
  const [mergePlan, setMergePlan] = useState(null) // { group, keep }
  const [deriveReport, setDeriveReport] = useState(null) // CR-12: the report shown before "apply"
  const location = useLocation()

  const load = useCallback(async () => {
    try {
      const { data } = await getRegistryAudit()
      setAudit(data)
    } catch {
      toast.error('The audit could not be read')
      setAudit(null)
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => { load() }, [load])

  // The banner's links land on a section: #shared, #batches, #pending, #formula, #structures.
  useEffect(() => {
    if (!audit || !location.hash) return
    const el = document.getElementById(location.hash.slice(1))
    if (el) el.scrollIntoView({ behavior: 'smooth', block: 'start' })
  }, [audit, location.hash])

  const act = async (fn, okMessage) => {
    setBusy(true)
    try {
      const res = await fn()
      toast.success(okMessage(res?.data))
      await load()
      return true
    } catch (err) {
      toast.error(err?.response?.data?.error || err?.response?.data?.detail || err.message || 'The action failed')
      return false
    } finally {
      setBusy(false)
    }
  }

  const review = (ids, key, reviewed) =>
    act(
      () => reviewAuditItems(ids, key, reviewed),
      () => (reviewed ? 'Marked as reviewed — it no longer counts on the banner' : 'Reopened')
    )

  // CR-12: derive is two clicks on purpose — a report first (nothing written), then apply.
  const previewDerive = async () => {
    setBusy(true)
    try {
      const { data } = await deriveStructures([], false)
      setDeriveReport(data)
    } catch (err) {
      toast.error(err?.response?.data?.error || err.message || 'The structures could not be derived')
    } finally {
      setBusy(false)
    }
  }
  const applyDerive = async () => {
    const ok = await act(
      () => deriveStructures([], true),
      (d) => `${(d?.written || 0).toLocaleString()} structures written, ${(d?.unchanged || 0).toLocaleString()} unchanged; ${(d?.findings?.entries || 0).toLocaleString()} with a finding`
    )
    if (ok) setDeriveReport(null)
  }

  const confirmMerge = async () => {
    const { group, keep } = mergePlan
    const remove = group.entries.map((e) => e.chemical_id).filter((id) => id !== keep)
    const ok = await act(
      () => mergeChemicals(keep, remove),
      (d) => d?.message || 'Merged'
    )
    if (ok) setMergePlan(null)
  }

  if (loading) {
    return <div className="text-center py-12 text-gray-500">Reading the registry…</div>
  }
  if (!audit) {
    return <div className="text-center py-12 text-gray-500">The audit could not be read. Is the application running?</div>
  }

  const c = audit.counts
  const visible = (items) => (showReviewed ? items : items.filter((i) => !i.reviewed))
  const shared = visible(audit.shared)
  const conflicts = visible(audit.batch_conflicts)
  const pending = audit.pending
  const formula = visible(audit.formula)
  const structures = visible(audit.structures || [])
  const ss = audit.structures_summary || { with_source: 0, derived: 0, to_derive: 0, findings: 0 }
  const nothingOpen = c.attention === 0

  return (
    <div className="space-y-6">
      <div className="flex flex-wrap items-start justify-between gap-4">
        <div>
          <h1 className="text-2xl font-bold text-gray-900">Needs attention</h1>
          <p className="text-gray-600 mt-1">
            What the registry wants a person to look at, and the buttons to act on it. Nothing here
            is decided for you: the system points, you choose.
          </p>
        </div>
        <div className="flex items-center gap-3 text-sm">
          <label className="inline-flex items-center gap-2 text-gray-700">
            <input type="checkbox" checked={showReviewed} onChange={(e) => setShowReviewed(e.target.checked)} className="rounded" />
            Show reviewed ({c.reviewed.toLocaleString()})
          </label>
          <button onClick={load} disabled={busy} className="inline-flex items-center px-3 py-1.5 border border-gray-300 rounded-lg hover:bg-gray-50 disabled:opacity-40">
            <ArrowPathIcon className="h-4 w-4 mr-1" /> Refresh
          </button>
          <a href="/api/chemicals/audit" target="_blank" rel="noreferrer" className="inline-flex items-center px-3 py-1.5 border border-gray-300 rounded-lg hover:bg-gray-50" title="The same list as the API answers it">
            JSON <ArrowTopRightOnSquareIcon className="h-4 w-4 ml-1" />
          </a>
        </div>
      </div>

      {/* the five counts, each a link to its section */}
      <div className="grid grid-cols-2 lg:grid-cols-5 gap-3">
        <Tile href="#shared" n={c.shared_groups} label="shared identifiers" sub={`${c.shared_entries.toLocaleString()} entries`} />
        <Tile href="#batches" n={c.batch_conflicts} label="batch conflicts" sub="batches that disagree" />
        <Tile href="#pending" n={c.pending} label="pending identifiers" sub="waiting for screening data" />
        <Tile href="#formula" n={c.formula} label="doubtful formulas" sub={`${audit.checked.toLocaleString()} checked`} />
        <Tile href="#structures" n={c.structure || 0} label="doubtful structures" sub={`${ss.derived.toLocaleString()} derived of ${ss.with_source.toLocaleString()} with a source`} />
      </div>

      {nothingOpen && (
        <div className="bg-green-50 border border-green-200 rounded-lg px-4 py-4 text-sm text-green-900 flex items-start gap-3">
          <CheckCircleIcon className="h-6 w-6 text-green-600 flex-shrink-0" />
          <div>
            <div className="font-semibold">Nothing needs attention.</div>
            <div className="text-green-800">
              Every shared identifier, batch conflict, doubtful formula and doubtful structure has been reviewed or
              resolved, and no identifier is pending. {c.reviewed > 0 && 'Tick "Show reviewed" to see what was decided.'}
              {ss.to_derive > 0 && ` ${ss.to_derive.toLocaleString()} entries carry a structure not yet derived: Derive structures below.`}
            </div>
          </div>
        </div>
      )}

      {/* ---------------------------------------------------- shared identifiers */}
      <Section
        id="shared"
        title="Shared identifiers"
        count={c.shared_groups}
        shown={shared.length}
        blurb="Two or more entries carry the same identifier. They were kept on purpose: the source registered them separately, and only a person can say whether they are one substance (merge them) or two that happen to share a number (keep both). Merging repoints every measurement to the survivor first, then removes the others — nothing is ever left pointing at a missing entry."
      >
        {shared.map((group) => (
          <SharedGroup
            key={group.key}
            group={group}
            busy={busy}
            onMerge={(keep) => setMergePlan({ group, keep })}
            onReview={(reviewed) => review(group.entries.map((e) => e.chemical_id), group.key, reviewed)}
          />
        ))}
      </Section>

      {/* ------------------------------------------------------ batch conflicts */}
      <Section
        id="batches"
        title="Batch conflicts"
        count={c.batch_conflicts}
        shown={conflicts.length}
        blurb="The export has one row per batch of a compound. When the batches disagree on a column that should describe the compound, not the batch, each batch's value was kept and the first batch's promoted to the entry. Look at the values; if the first batch was wrong, edit the entry; either way, mark it reviewed."
      >
        {conflicts.map((item) => (
          <Card key={item.chemical_id} reviewed={item.reviewed}>
            <EntryHeading item={item} />
            <div className="overflow-x-auto mt-3">
              <table className="min-w-full text-sm">
                <thead className="bg-gray-50 text-xs uppercase text-gray-500">
                  <tr>
                    <th className="px-3 py-2 text-left">Column</th>
                    <th className="px-3 py-2 text-left">On the entry</th>
                    {item.columns[0]?.values.map((v) => (
                      <th key={v.batch} className="px-3 py-2 text-left">Batch {v.batch}{v.batch_id ? ` · ${v.batch_id}` : ''}</th>
                    ))}
                  </tr>
                </thead>
                <tbody className="divide-y divide-gray-100">
                  {item.columns.map((col) => (
                    <tr key={col.column}>
                      <td className="px-3 py-2 font-mono text-xs text-gray-700">{col.column}</td>
                      <td className="px-3 py-2 font-medium">{fmt(col.promoted)}</td>
                      {col.values.map((v) => (
                        <td key={v.batch} className={`px-3 py-2 ${String(v.value ?? '') !== String(col.promoted ?? '') ? 'text-amber-800 font-medium' : ''}`}>{fmt(v.value)}</td>
                      ))}
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
            <Actions>
              <OpenEntry id={item.chemical_id} />
              <ReviewButton reviewed={item.reviewed} busy={busy} onClick={() => review([item.chemical_id], item.key, !item.reviewed)} />
            </Actions>
          </Card>
        ))}
      </Section>

      {/* -------------------------------------------------- pending identifiers */}
      <Section
        id="pending"
        title="Pending identifiers"
        count={c.pending}
        shown={pending.length}
        blurb="Entries from the limited list whose identifier column said it would come from the screening data. The screening-data phase fills them in when that data is loaded; if you already know the identifier, set it here."
      >
        {pending.length > 0 && (
          <div className="bg-white rounded-lg border border-gray-200 overflow-x-auto">
            <table className="min-w-full text-sm">
              <thead className="bg-gray-50 text-xs uppercase text-gray-500">
                <tr>
                  <th className="px-3 py-2 text-left">Identifier</th>
                  <th className="px-3 py-2 text-left">Name</th>
                  <th className="px-3 py-2 text-left">CAS</th>
                  <th className="px-3 py-2 text-left">Supplier ref.</th>
                  <th className="px-3 py-2 text-left">Set the identifier</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-gray-100">
                {pending.map((item) => (
                  <PendingRow key={item.chemical_id} item={item} busy={busy} onSet={(value) => act(() => setChemicalIdentifier(item.chemical_id, value), () => `Identifier set on ${item.chemical_id}`)} />
                ))}
              </tbody>
            </table>
          </div>
        )}
      </Section>

      {/* ------------------------------------------------------ formula findings */}
      <Section
        id="formula"
        title="Doubtful formulas"
        count={c.formula}
        shown={formula.length}
        blurb="A check, not a verdict: the name claims a carbon chain the formula cannot hold, or the formula contains an element nothing in the name accounts for. Trivial names (Caffeine, DDT) carry no structural hint, so they are listed when no PubChem name confirms them — read the pair and decide. An entry that is wrong can be deleted here; one that is fine is marked reviewed."
      >
        {formula.map((item) => (
          <FormulaCard key={item.chemical_id} item={item} busy={busy} onReview={(r) => review([item.chemical_id], item.key, r)} onDelete={() => act(() => deleteChemical(item.chemical_id), () => `${item.chemical_id} deleted`)} />
        ))}
      </Section>

      {/* ---------------------------------------------------- structure findings */}
      <section id="structures" className="scroll-mt-20 space-y-3">
        <div>
          <h2 className="text-lg font-bold text-gray-900">
            Doubtful structures <span className="text-gray-400 font-normal">· {(c.structure || 0).toLocaleString()} open</span>
          </h2>
          <p className="text-sm text-gray-600 mt-1 max-w-4xl">
            A structure is the one fact about a compound that can be checked. From the MOL block, SMILES or InChI a source gave,
            the server derives one structure with RDKit and computes its formula, weight and InChIKey; where the source's own
            formula, weight or InChI disagrees with its own structure, the entry is listed here with the two values side by side.
            A check, not a verdict: a salt recorded by its parent's formula passes (every fragment is tried), a weight passes as an
            average or an exact mass. Read the pair; <em>It is fine — mark reviewed</em> when the source is right as it stands.
          </p>
        </div>
        <DerivePanel summary={ss} report={deriveReport} busy={busy} onPreview={previewDerive} onApply={applyDerive} onDismiss={() => setDeriveReport(null)} />
        {structures.length === 0 ? (
          <p className="text-sm text-gray-500 italic">Nothing open here{(c.structure || 0) === 0 ? '' : ' — tick "Show reviewed" to see the decided ones'}.</p>
        ) : (
          structures.map((item) => (
            <StructureCard key={item.chemical_id} item={item} busy={busy} onReview={(r) => review([item.chemical_id], item.key, r)} />
          ))
        )}
      </section>

      {mergePlan && <MergeConfirm plan={mergePlan} busy={busy} onConfirm={confirmMerge} onClose={() => setMergePlan(null)} />}
    </div>
  )
}

// ------------------------------------------------------------------ pieces --

function Tile({ href, n, label, sub }) {
  const open = n > 0
  return (
    <a href={href} className={`block rounded-lg border px-4 py-3 ${open ? 'bg-amber-50 border-amber-200' : 'bg-white border-gray-200'}`}>
      <div className={`text-2xl font-bold ${open ? 'text-amber-800' : 'text-gray-400'}`}>{n.toLocaleString()}</div>
      <div className="text-sm font-medium text-gray-800">{label}</div>
      <div className="text-xs text-gray-500">{sub}</div>
    </a>
  )
}

function Section({ id, title, count, shown, blurb, children }) {
  return (
    <section id={id} className="scroll-mt-20 space-y-3">
      <div>
        <h2 className="text-lg font-bold text-gray-900">
          {title} <span className="text-gray-400 font-normal">· {count.toLocaleString()} open</span>
        </h2>
        <p className="text-sm text-gray-600 mt-1 max-w-4xl">{blurb}</p>
      </div>
      {shown === 0 ? (
        <p className="text-sm text-gray-500 italic">Nothing open here{count === 0 ? '' : ' — tick "Show reviewed" to see the decided ones'}.</p>
      ) : (
        children
      )}
    </section>
  )
}

function Card({ reviewed, children }) {
  return (
    <div className={`bg-white rounded-lg border p-4 ${reviewed ? 'border-gray-200 opacity-60' : 'border-amber-200'}`}>
      {children}
    </div>
  )
}

function Actions({ children }) {
  return <div className="flex flex-wrap items-center gap-2 mt-3">{children}</div>
}

function OpenEntry({ id }) {
  return (
    <Link to={`/chemicals?search=${encodeURIComponent(id)}`} className="px-3 py-1.5 text-sm border border-gray-300 rounded-lg hover:bg-gray-50">
      Open the entry
    </Link>
  )
}

function ReviewButton({ reviewed, busy, onClick, label = 'Mark reviewed' }) {
  return (
    <button onClick={onClick} disabled={busy} className={`px-3 py-1.5 text-sm rounded-lg disabled:opacity-40 ${reviewed ? 'border border-gray-300 hover:bg-gray-50' : 'bg-gray-800 text-white hover:bg-gray-900'}`}>
      {reviewed ? 'Reopen' : label}
    </button>
  )
}

function EntryHeading({ item }) {
  return (
    <div className="flex flex-wrap items-baseline gap-x-3 gap-y-1">
      <span className="font-mono text-sm text-gray-500">{item.chemical_id}</span>
      <span className="font-semibold text-gray-900">{fmt(item.name)}</span>
      <span className="text-sm text-gray-500">CAS {fmt(item.cas_number)}</span>
      {item.reviewed && <span className="text-xs bg-gray-100 text-gray-600 rounded-full px-2 py-0.5">reviewed</span>}
    </div>
  )
}

function SharedGroup({ group, busy, onMerge, onReview }) {
  // The survivor defaults to the oldest entry (the lowest identifier), as the
  // terminal script has always chosen; the radio lets a person choose otherwise.
  const [keep, setKeep] = useState(group.entries[0]?.chemical_id)
  return (
    <Card reviewed={group.reviewed}>
      <div className="flex flex-wrap items-baseline gap-x-3">
        <span className="font-semibold text-gray-900">{KIND_LABEL[group.kind] || group.kind} <span className="font-mono">{group.value}</span></span>
        <span className="text-sm text-gray-500">shared by {group.entries.length} entries</span>
        {group.reviewed && <span className="text-xs bg-gray-100 text-gray-600 rounded-full px-2 py-0.5">reviewed · kept both</span>}
      </div>
      <div className="overflow-x-auto mt-3">
        <table className="min-w-full text-sm">
          <thead className="bg-gray-50 text-xs uppercase text-gray-500">
            <tr>
              <th className="px-3 py-2 text-left">Keep</th>
              <th className="px-3 py-2 text-left">Identifier</th>
              <th className="px-3 py-2 text-left" title="The derived structure, drawn by the server (CR-12)">Structure</th>
              <th className="px-3 py-2 text-left">Name</th>
              <th className="px-3 py-2 text-left">CAS</th>
              <th className="px-3 py-2 text-left">DTXSID</th>
              <th className="px-3 py-2 text-left">PubChem</th>
              <th className="px-3 py-2 text-left">Formula</th>
              <th className="px-3 py-2 text-left">Source</th>
              <th className="px-3 py-2 text-right">Batches</th>
              <th className="px-3 py-2 text-right">Linked rows</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-gray-100">
            {group.entries.map((e) => (
              <tr key={e.chemical_id} className={e.chemical_id === keep ? 'bg-pandora-50' : ''}>
                <td className="px-3 py-2"><input type="radio" name={`keep-${group.key}`} checked={keep === e.chemical_id} onChange={() => setKeep(e.chemical_id)} disabled={group.reviewed} /></td>
                <td className="px-3 py-2 font-mono text-xs">{e.chemical_id}</td>
                <td className="px-3 py-2">{e.structure_source ? <StructurePicture id={e.chemical_id} version={e.structure_version} /> : <span className="text-gray-300">—</span>}</td>
                <td className="px-3 py-2 font-medium text-gray-900">{fmt(e.name)}</td>
                <td className="px-3 py-2 font-mono text-xs">{fmt(e.cas_number)}</td>
                <td className="px-3 py-2 font-mono text-xs">{fmt(e.dtx_id)}</td>
                <td className="px-3 py-2 font-mono text-xs">{fmt(e.pubchem_cid)}</td>
                <td className="px-3 py-2 font-mono text-xs">{fmt(e.molecular_formula)}</td>
                <td className="px-3 py-2 text-xs text-gray-600">{fmt(e.source_template)}{e.merged_from?.length ? ` + ${e.merged_from.join(', ')}` : ''}</td>
                <td className="px-3 py-2 text-right">{e.batches}</td>
                <td className="px-3 py-2 text-right">{(e.linked_rows || 0).toLocaleString()}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      <Actions>
        {!group.reviewed && (
          <button onClick={() => onMerge(keep)} disabled={busy || !keep} className="px-3 py-1.5 text-sm bg-pandora-600 text-white rounded-lg hover:bg-pandora-700 disabled:opacity-40">
            Merge the others into {keep}…
          </button>
        )}
        <ReviewButton reviewed={group.reviewed} busy={busy} onClick={() => onReview(!group.reviewed)} label="Keep both — mark reviewed" />
        {group.entries.map((e) => <OpenEntry key={e.chemical_id} id={e.chemical_id} />)}
      </Actions>
    </Card>
  )
}

function PendingRow({ item, busy, onSet }) {
  const [value, setValue] = useState('')
  return (
    <tr>
      <td className="px-3 py-2 font-mono text-xs">{item.chemical_id}</td>
      <td className="px-3 py-2 font-medium">{fmt(item.name)}</td>
      <td className="px-3 py-2 font-mono text-xs">{fmt(item.cas_number)}</td>
      <td className="px-3 py-2 text-xs">{fmt(item.supplier)}</td>
      <td className="px-3 py-2">
        <form className="flex gap-2" onSubmit={(e) => { e.preventDefault(); if (value.trim()) onSet(value.trim()) }}>
          <input value={value} onChange={(e) => setValue(e.target.value)} placeholder="the identifier…" className="px-2 py-1 border border-gray-300 rounded-md text-sm w-40" />
          <button type="submit" disabled={busy || !value.trim()} className="px-3 py-1 text-sm bg-gray-800 text-white rounded-md disabled:opacity-40">Set</button>
        </form>
      </td>
    </tr>
  )
}

function FormulaCard({ item, busy, onReview, onDelete }) {
  const [confirming, setConfirming] = useState(false)
  return (
    <Card reviewed={item.reviewed}>
      <EntryHeading item={item} />
      <dl className="grid grid-cols-1 sm:grid-cols-2 gap-x-6 gap-y-1 text-sm mt-2">
        <div className="flex gap-2"><dt className="w-28 text-gray-500">Your name</dt><dd className="text-gray-900">{fmt(item.name)}</dd></div>
        <div className="flex gap-2"><dt className="w-28 text-gray-500">PubChem name</dt><dd className="text-gray-900">{item.pubchem_name || '(none recorded)'}</dd></div>
        <div className="flex gap-2"><dt className="w-28 text-gray-500">Formula</dt><dd className="font-mono">{fmt(item.molecular_formula)}</dd></div>
        <div className="flex gap-2"><dt className="w-28 text-gray-500">Weight</dt><dd className="font-mono">{fmt(item.molecular_weight)}</dd></div>
      </dl>
      <ul className="mt-2 text-sm text-amber-800 list-disc list-inside">
        {item.reasons.map((r) => <li key={r}>{r}</li>)}
      </ul>
      <Actions>
        <OpenEntry id={item.chemical_id} />
        <ReviewButton reviewed={item.reviewed} busy={busy} onClick={() => onReview(!item.reviewed)} label="It is fine — mark reviewed" />
        {confirming ? (
          <>
            <span className="text-sm text-red-700">Delete {item.chemical_id}? Its linked rows, if any, must be unlinked first.</span>
            <button onClick={() => { setConfirming(false); onDelete() }} disabled={busy} className="px-3 py-1.5 text-sm bg-red-600 text-white rounded-lg hover:bg-red-700 disabled:opacity-40">Yes, delete</button>
            <button onClick={() => setConfirming(false)} className="px-3 py-1.5 text-sm border border-gray-300 rounded-lg">Cancel</button>
          </>
        ) : (
          <button onClick={() => setConfirming(true)} disabled={busy} className="px-3 py-1.5 text-sm border border-red-300 text-red-700 rounded-lg hover:bg-red-50 disabled:opacity-40">Delete…</button>
        )}
      </Actions>
    </Card>
  )
}

// CR-12: the derive panel — where the registry stands, and the two-click derive
function DerivePanel({ summary, report, busy, onPreview, onApply, onDismiss }) {
  return (
    <div className="bg-white rounded-lg border border-gray-200 p-4 space-y-3" data-testid="derive-panel">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div className="text-sm text-gray-700">
          <span className="font-semibold">{summary.with_source.toLocaleString()}</span> entries carry a structure source ·{' '}
          <span className="font-semibold">{summary.derived.toLocaleString()}</span> derived ·{' '}
          <span className={`font-semibold ${summary.to_derive > 0 ? 'text-amber-800' : ''}`}>{summary.to_derive.toLocaleString()}</span> still to derive ·{' '}
          <span className="font-semibold">{summary.findings.toLocaleString()}</span> with a finding
        </div>
        {!report && (
          <button onClick={onPreview} disabled={busy} className="inline-flex items-center px-3 py-1.5 text-sm bg-pandora-600 text-white rounded-lg hover:bg-pandora-700 disabled:opacity-40" data-testid="derive-preview">
            <BeakerIcon className="h-4 w-4 mr-1" /> {busy ? 'Deriving…' : 'Derive structures…'}
          </button>
        )}
      </div>
      {report && (
        <div className="border border-amber-200 bg-amber-50 rounded-lg p-3 text-sm text-amber-900 space-y-2" data-testid="derive-report">
          <div className="font-semibold">Report — nothing written yet ({report.seconds} s)</div>
          <div>
            {report.with_source.toLocaleString()} of {report.entries.toLocaleString()} entries carry a source. Derived {report.derived.toLocaleString()}:{' '}
            {report.from.mol_block.toLocaleString()} from a MOL block, {report.from.smiles.toLocaleString()} from a SMILES
            {report.repaired > 0 && ` (${report.repaired.toLocaleString()} read after removing the outer brackets the source added)`},{' '}
            {report.from.inchi.toLocaleString()} from an InChI; {report.unreadable.toLocaleString()} could not be read.
          </div>
          <div>
            Findings on {report.findings.entries.toLocaleString()} entries: formula {report.findings.formula.toLocaleString()}, weight{' '}
            {report.findings.weight.toLocaleString()}, InChI {report.findings.inchi.toLocaleString()}, unreadable {report.findings.unreadable.toLocaleString()}.
          </div>
          <div className="text-xs">Applying stores the structure beside each entry's own fields (never over them) and lists the findings here; a later run rewrites only what changed.</div>
          <div className="flex gap-2">
            <button onClick={onApply} disabled={busy} className="px-3 py-1.5 text-sm bg-pandora-600 text-white rounded-lg hover:bg-pandora-700 disabled:opacity-40" data-testid="derive-apply">
              {busy ? 'Writing…' : `Apply: store the result on ${report.with_source.toLocaleString()} entries`}
            </button>
            <button onClick={onDismiss} disabled={busy} className="px-3 py-1.5 text-sm border border-gray-300 rounded-lg bg-white">Cancel</button>
          </div>
        </div>
      )}
    </div>
  )
}

const CHECK_LABEL = { agrees: '✓ agrees', differs: '✗ differs', none: 'no value to compare', 'same source': 'derived from it', unreadable: 'unreadable', 'not computable': 'not computable' }

function StructureCard({ item, busy, onReview }) {
  const s = item.structure || {}
  const checks = s.checks || {}
  const cell = (k) => <span className={['differs', 'unreadable', 'not computable'].includes(checks[k]) ? 'text-amber-800 font-medium' : 'text-gray-500'}>{CHECK_LABEL[checks[k]] || '—'}</span>
  return (
    <Card reviewed={item.reviewed}>
      <EntryHeading item={item} />
      <div className="flex flex-col md:flex-row gap-4 mt-3">
      {s.source && (
        <div className="flex-shrink-0">
          <StructurePicture id={item.chemical_id} version={s.derived_at} width={180} height={135} className="border border-gray-200" title="The derived structure, drawn by the server" />
        </div>
      )}
      <div className="overflow-x-auto flex-1">
        <table className="min-w-full text-sm">
          <thead className="bg-gray-50 text-xs uppercase text-gray-500">
            <tr>
              <th className="px-3 py-2 text-left">Fact</th>
              <th className="px-3 py-2 text-left">The source says</th>
              <th className="px-3 py-2 text-left">Its own structure is</th>
              <th className="px-3 py-2 text-left">Check</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-gray-100">
            <tr>
              <td className="px-3 py-2 text-gray-500">Structure from</td>
              <td className="px-3 py-2 font-mono text-xs">{s.source ? `${s.source}${s.repaired ? ` (${s.repaired})` : ''}` : `unreadable: ${(s.unreadable || []).join(', ')}`}</td>
              <td className="px-3 py-2 font-mono text-xs break-all">{s.smiles ? <span title={s.smiles}>{s.smiles.length > 60 ? s.smiles.slice(0, 60) + '…' : s.smiles}</span> : '—'}</td>
              <td className="px-3 py-2 text-xs text-gray-500">{s.fragments > 1 ? `${s.fragments} fragments` : ''}</td>
            </tr>
            <tr>
              <td className="px-3 py-2 text-gray-500">Formula</td>
              <td className="px-3 py-2 font-mono text-xs">{fmt(item.molecular_formula)}</td>
              <td className="px-3 py-2 font-mono text-xs">{fmt(s.formula)}{s.largest_fragment ? ` (largest fragment ${s.largest_fragment.formula})` : ''}</td>
              <td className="px-3 py-2 text-xs">{cell('formula')}</td>
            </tr>
            <tr>
              <td className="px-3 py-2 text-gray-500">Weight</td>
              <td className="px-3 py-2 font-mono text-xs">{fmt(item.molecular_weight)}</td>
              <td className="px-3 py-2 font-mono text-xs">{s.weight !== undefined && s.weight !== null ? `${s.weight} average · ${s.exact_mass} exact` : '—'}</td>
              <td className="px-3 py-2 text-xs">{cell('weight')}</td>
            </tr>
            <tr>
              <td className="px-3 py-2 text-gray-500">InChIKey</td>
              <td className="px-3 py-2 text-xs text-gray-500">{checks.inchi === 'none' ? 'no InChI on the entry' : 'the InChI the source carries'}</td>
              <td className="px-3 py-2 font-mono text-xs">{fmt(s.inchikey)}</td>
              <td className="px-3 py-2 text-xs">{cell('inchi')}</td>
            </tr>
          </tbody>
        </table>
      </div>
      </div>
      <ul className="mt-2 text-sm text-amber-800 list-disc list-inside">
        {item.reasons.map((r) => <li key={r}>{r}</li>)}
      </ul>
      <Actions>
        <OpenEntry id={item.chemical_id} />
        <ReviewButton reviewed={item.reviewed} busy={busy} onClick={() => onReview(!item.reviewed)} label="It is fine — mark reviewed" />
      </Actions>
    </Card>
  )
}

function MergeConfirm({ plan, busy, onConfirm, onClose }) {
  const { group, keep } = plan
  const survivor = group.entries.find((e) => e.chemical_id === keep)
  const removed = group.entries.filter((e) => e.chemical_id !== keep)
  const rows = removed.reduce((n, e) => n + (e.linked_rows || 0), 0)
  return (
    <div className="fixed inset-0 bg-black/40 flex items-center justify-center p-4 z-50" onClick={onClose}>
      <div className="bg-white rounded-xl max-w-lg w-full p-5 space-y-4" onClick={(e) => e.stopPropagation()}>
        <div className="flex items-start justify-between">
          <h2 className="text-lg font-bold text-gray-900">Merge {removed.length} entr{removed.length === 1 ? 'y' : 'ies'} into {keep}?</h2>
          <button onClick={onClose} className="text-gray-400 hover:text-gray-600"><XMarkIcon className="h-6 w-6" /></button>
        </div>
        <dl className="text-sm border border-gray-200 rounded-lg divide-y divide-gray-100">
          <div className="flex gap-3 px-3 py-2 items-center"><dt className="w-24 text-gray-500">Survivor</dt><dd className="flex items-center gap-3">{survivor?.structure_source && <StructurePicture id={survivor.chemical_id} version={survivor.structure_version} width={72} height={54} />}<span><span className="font-mono text-xs">{survivor?.chemical_id}</span> <span className="font-medium">{fmt(survivor?.name)}</span></span></dd></div>
          {removed.map((e) => (
            <div key={e.chemical_id} className="flex gap-3 px-3 py-2 items-center"><dt className="w-24 text-gray-500">Removed</dt><dd className="flex items-center gap-3">{e.structure_source && <StructurePicture id={e.chemical_id} version={e.structure_version} width={72} height={54} />}<span><span className="font-mono text-xs">{e.chemical_id}</span> <span className="font-medium">{fmt(e.name)}</span> <span className="text-gray-500">· {(e.linked_rows || 0).toLocaleString()} linked row{e.linked_rows === 1 ? '' : 's'}</span></span></dd></div>
          ))}
        </dl>
        <ol className="text-sm text-gray-700 list-decimal list-inside space-y-1">
          <li>Any field the survivor lacks is copied from the removed entr{removed.length === 1 ? 'y' : 'ies'}.</li>
          <li><span className="font-semibold">{rows.toLocaleString()}</span> linked row{rows === 1 ? '' : 's'} {rows === 1 ? 'is' : 'are'} repointed at the survivor first.</li>
          <li>Only then {removed.length === 1 ? 'is the entry' : 'are the entries'} removed. Nothing is left pointing at a missing entry.</li>
        </ol>
        <p className="text-xs text-gray-500">This cannot be undone from the browser. The survivor records what was merged into it.</p>
        <div className="flex justify-end gap-2">
          <button onClick={onClose} className="px-3 py-1.5 text-sm border border-gray-300 rounded-lg">Cancel</button>
          <button onClick={onConfirm} disabled={busy} className="px-3 py-1.5 text-sm bg-pandora-600 text-white rounded-lg hover:bg-pandora-700 disabled:opacity-40">
            Yes, merge into {keep}
          </button>
        </div>
      </div>
    </div>
  )
}
