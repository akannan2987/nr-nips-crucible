"""Pydantic v2 request models.

Design note (important for parity): the legacy (v1) backend performed almost
no request validation — any JSON object is accepted, unknown keys are kept,
and missing keys become null. A strict Pydantic model would reject such
requests with HTTP 422, which the React client (and the documented contract)
does not expect. Therefore every model here:

* makes all fields optional, and
* sets `model_config = ConfigDict(extra="allow")` so unknown keys are kept
  (they end up in the stored record, exactly like the legacy spread operator).

The models still give you typed access, editor autocomplete and OpenAPI docs
(FastAPI serves them at /docs) without changing observable behaviour.

Endpoints whose v1 counterpart merged a *completely arbitrary* body into
the stored record (the PUT update endpoints) accept a plain `dict` instead —
there is genuinely no schema to describe there.
"""

from typing import Any

from pydantic import BaseModel, ConfigDict


class _LenientModel(BaseModel):
    """Base for all request bodies: optional everything, unknown keys kept."""

    model_config = ConfigDict(extra="allow")

    def merged_dict(self) -> dict[str, Any]:
        """Declared fields + any extra keys, as a plain dict (JS spread)."""
        data = self.model_dump()
        if self.model_extra:
            data.update(self.model_extra)
        return data


class ChemicalIn(_LenientModel):
    """Body of POST /api/chemicals (all fields optional, like the v1 API)."""

    chemical_id: str | None = None
    nestle_id: str | None = None
    name: str | None = None
    cas_number: str | None = None
    molecular_formula: str | None = None
    molecular_weight: float | None = None
    smiles: str | None = None
    inchi: str | None = None
    inchi_key: str | None = None
    supplier: str | None = None
    description: str | None = None
    metadata: dict[str, Any] | None = None


class SampleIn(_LenientModel):
    """Body of POST /api/samples — the v1 API spread the whole body into the
    record, so extra keys are preserved via `extra="allow"`."""

    sample_id: str | None = None
    identification: str | None = None
    content_type: str | None = None
    material_type: str | None = None
    project_number: str | None = None
    status: str | None = None


class ScreeningIn(_LenientModel):
    """Body of POST /api/screening."""

    chemical_id: str | None = None
    assay_name: str | None = None
    assay_type: str | None = None
    target: str | None = None
    result: str | None = None
    result_value: Any | None = None
    result_unit: str | None = None
    concentration: Any | None = None
    concentration_unit: str | None = None
    timepoint: Any | None = None
    replicate: Any | None = None
    plate_id: str | None = None
    well_position: str | None = None
    experiment_date: str | None = None
    operator: str | None = None
    notes: str | None = None
    metadata: dict[str, Any] | None = None


class ToxicologyIn(_LenientModel):
    """Body of POST /api/toxicology."""

    chemical_id: str | None = None
    study_type: str | None = None
    species: str | None = None
    strain: str | None = None
    sex: str | None = None
    route_of_administration: str | None = None
    duration: Any | None = None
    duration_unit: str | None = None
    dose: Any | None = None
    dose_unit: str | None = None
    endpoint: str | None = None
    endpoint_value: Any | None = None
    endpoint_unit: str | None = None
    noael: Any | None = None
    loael: Any | None = None
    ld50: Any | None = None
    study_reference: str | None = None
    study_date: str | None = None
    source: str | None = None
    notes: str | None = None
    metadata: dict[str, Any] | None = None


class BulkDeleteChemicals(_LenientModel):
    chemical_ids: Any | None = None  # validated by hand, like the v1 API


class BulkUpdateChemicals(_LenientModel):
    chemical_ids: Any | None = None
    updates: dict[str, Any] | None = None


class BulkDeleteSamples(_LenientModel):
    sample_ids: Any | None = None


class LinkChemicals(_LenientModel):
    chemical_ids: Any | None = None
