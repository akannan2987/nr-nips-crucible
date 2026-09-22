import { Routes, Route } from 'react-router-dom'
import { Toaster } from 'react-hot-toast'
import Layout from './components/Layout'
import AuthGate from './components/AuthGate'
import Dashboard from './pages/Dashboard'
import ChemicalsView from './pages/ChemicalsView'
import ChemicalsUpload from './pages/ChemicalsUpload'
import RegistryAttention from './pages/RegistryAttention'
import SamplesView from './pages/SamplesView'
import SamplesUpload from './pages/SamplesUpload'
import ScreeningView from './pages/ScreeningView'
import QueryConsole from './pages/QueryConsole'
import ScreeningUpload from './pages/ScreeningUpload'
import ToxicologyView from './pages/ToxicologyView'
import ToxicologyUpload from './pages/ToxicologyUpload'

function App() {
  return (
    <>
      <Toaster position="top-right" />
      {/* SH-3a: nothing below renders until the server says no login is needed, or this browser is signed in */}
      <AuthGate>
      <Routes>
        <Route path="/" element={<Layout />}>
          <Route index element={<Dashboard />} />
          {/* Chemicals */}
          <Route path="chemicals" element={<ChemicalsView />} />
          <Route path="chemicals/upload" element={<ChemicalsUpload />} />
          <Route path="chemicals/attention" element={<RegistryAttention />} />
          {/* Samples */}
          <Route path="samples" element={<SamplesView />} />
          <Route path="samples/upload" element={<SamplesUpload />} />
          {/* Screening */}
          <Route path="screening" element={<ScreeningView />} />
          <Route path="query" element={<QueryConsole />} />
          <Route path="screening/upload" element={<ScreeningUpload />} />
          {/* Toxicology */}
          <Route path="toxicology" element={<ToxicologyView />} />
          <Route path="toxicology/upload" element={<ToxicologyUpload />} />
        </Route>
      </Routes>
      </AuthGate>
    </>
  )
}

export default App
