import axios from 'axios';
import toast from 'react-hot-toast';

const API_BASE = '/api';

const api = axios.create({
  baseURL: API_BASE,
  headers: {
    'Content-Type': 'application/json',
  },
});

// Statistics
export const getStats = () => api.get('/stats');
// SH-13: which instance is answering (name, label, port, https); open, no data
export const getInstance = () => api.get('/instance');
// SH-3a and SH-3b: the login (docs/13-authentication.md). /auth/me is open
// and says which mode is on and whether this browser is signed in; login
// posts the credential once ({token} on the token rung, {username, password}
// on the local rung) and the server answers with a cookie the browser then
// sends on every request (downloads included, which a header could not
// cover); logout clears it; password lets a signed-in person change theirs.
export const getAuthMe = () => api.get('/auth/me');
export const login = (credentials) => api.post('/auth/login', credentials);
export const logout = () => api.post('/auth/logout');
export const changePassword = (current, next) => api.post('/auth/password', { current, new: next });

// Chemicals
// `config` may carry an AbortController signal so a superseded list request is cancelled (v2.18.2).
export const getChemicals = (params, config = {}) => api.get('/chemicals', { params, ...config });
export const getChemical = (id) => api.get(`/chemicals/${id}`);
export const createChemical = (data) => api.post('/chemicals', data);
export const updateChemical = (id, data) => api.put(`/chemicals/${id}`, data);
export const deleteChemical = (id) => api.delete(`/chemicals/${id}`);
export const uploadChemicalsSDF = (formData) => 
  api.post('/chemicals/upload/sdf', formData, {
    headers: { 'Content-Type': 'multipart/form-data' },
  });
export const uploadChemicalsExcel = (formData) =>
  api.post('/chemicals/upload/excel', formData, {
    headers: { 'Content-Type': 'multipart/form-data' },
  });
export const getChemicalsDropdown = () => api.get('/chemicals/list/dropdown');
export const getChemicalNotices = () => api.get('/chemicals/notices/summary');
// CR-10: the attention page — every flagged entry, and the marks a person leaves.
export const getRegistryAudit = () => api.get('/chemicals/audit');
export const reviewAuditItems = (chemical_ids, key, reviewed = true) =>
  api.post('/chemicals/audit/review', { chemical_ids, key, reviewed });
export const mergeChemicals = (keep, remove) => api.post('/chemicals/merge', { keep, remove });
export const setChemicalIdentifier = (chemicalId, nestle_id) =>
  api.post(`/chemicals/${chemicalId}/identifier`, { nestle_id });
export const getChemicalColumns = () => api.get('/chemicals/columns');
// CR-11: the counts above the registry table — compounds, batches, entries per source tag.
export const getChemicalSummary = () => api.get('/chemicals/summary');
export const bulkDeleteChemicals = (chemical_ids) => api.post('/chemicals/bulk/delete', { chemical_ids });
export const bulkUpdateChemicals = (chemical_ids, updates) => api.post('/chemicals/bulk/update', { chemical_ids, updates });
export const clearAllChemicals = () => api.delete('/chemicals/all/clear');
export const uploadChemicalsJSON = (formData) =>
  api.post('/chemicals/upload/json', formData, {
    headers: { 'Content-Type': 'multipart/form-data' },
  });

// Samples
export const getSamples = (params) => api.get('/samples', { params });
export const getSample = (id) => api.get(`/samples/${id}`);
export const createSample = (data) => api.post('/samples', data);
export const updateSample = (id, data) => api.put(`/samples/${id}`, data);
export const deleteSample = (id) => api.delete(`/samples/${id}`);
export const uploadSamplesExcel = (formData) =>
  api.post('/samples/upload/excel', formData, {
    headers: { 'Content-Type': 'multipart/form-data' },
  });
export const linkSampleChemicals = (sampleId, chemical_ids) =>
  api.put(`/samples/${sampleId}/chemicals`, { chemical_ids });
export const bulkDeleteSamples = (sample_ids) => api.post('/samples/bulk/delete', { sample_ids });
export const clearAllSamples = () => api.delete('/samples/all/clear');
// Direct download URL for the SLIMS sample template (used by an <a> tag).
export const SAMPLE_TEMPLATE_URL = `${API_BASE}/samples/template/download`;

// Screening
export const getScreening = (params) => api.get('/screening', { params });
export const getScreeningColumns = () => api.get('/screening/columns');
export const getDuplicatesSummary = () => api.get('/screening/duplicates/summary');
// Export runs server-side so the download is the whole filtered selection,
// not just the rows currently on screen. Returns a URL rather than data so the
// browser downloads it directly instead of buffering 49,000 rows in memory.
export const screeningExportUrl = (params) => {
  const qs = new URLSearchParams(
    Object.entries(params).filter(([, v]) => v !== '' && v != null)
  ).toString();
  return `${API_BASE}/screening/export?${qs}`;
};
export const getScreeningRecord = (id) => api.get(`/screening/${id}`);
// Point rows at a registered chemical, or detach them. `unlinkAllScreening`
// is the registry reset's first step, from the browser.
// `target` is {record_ids: [...]} for ticked rows or {match: {...}} for every
// row matching the table's current filters.
export const linkScreening = (target, chemical_id) =>
  api.post('/screening/link', { ...target, chemical_id });
export const unlinkScreening = (target) => api.post('/screening/unlink', target);
export const unlinkAllScreening = () => api.post('/screening/unlink', { all: true });
export const getScreeningByChemical = (chemicalId) => api.get(`/screening/chemical/${chemicalId}`);
export const createScreening = (data) => api.post('/screening', data);
export const updateScreening = (id, data) => api.put(`/screening/${id}`, data);
export const deleteScreening = (id) => api.delete(`/screening/${id}`);
export const uploadScreeningExcel = (formData) =>
  api.post('/screening/upload/excel', formData, {
    headers: { 'Content-Type': 'multipart/form-data' },
  });

// Query (read-only SQL)
export const runQuery = (sql, limit) => api.post('/query', { sql, limit });
export const getQuerySchema = () => api.get('/query/schema');

// Toxicology
export const getToxicology = (params) => api.get('/toxicology', { params });
export const getToxicologyRecord = (id) => api.get(`/toxicology/${id}`);
export const getToxicologyByChemical = (chemicalId) => api.get(`/toxicology/chemical/${chemicalId}`);
export const createToxicology = (data) => api.post('/toxicology', data);
export const updateToxicology = (id, data) => api.put(`/toxicology/${id}`, data);
export const deleteToxicology = (id) => api.delete(`/toxicology/${id}`);
export const uploadToxicologyExcel = (formData) =>
  api.post('/toxicology/upload/excel', formData, {
    headers: { 'Content-Type': 'multipart/form-data' },
  });

// SH-3a, the 401 handler: an answer of 401 from any call means "not signed
// in". The API layer raises one event; AuthGate listens and shows the
// login page, and the page that asked is mounted again after the login, so
// it asks again. The auth calls themselves are left alone: a wrong token on
// the login page is that page's own business.
// SH-3b: a 403 means "signed in, but your role does not allow this". The
// server names the role needed; one toast says so, and the page's own error
// handling runs as before (the action simply did not happen).
export const UNAUTHENTICATED_EVENT = 'crucible:unauthenticated';
api.interceptors.response.use(
  (response) => response,
  (error) => {
    const status = error?.response?.status;
    const url = error?.config?.url || '';
    if (status === 401 && !url.startsWith('/auth/')) {
      window.dispatchEvent(new Event(UNAUTHENTICATED_EVENT));
    }
    if (status === 403) {
      toast.error(error?.response?.data?.error || 'Your role does not allow this.', { id: 'forbidden' });
    }
    return Promise.reject(error);
  }
);

export default api;
