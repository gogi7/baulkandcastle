import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom'
import Layout from './components/layout/Layout'
import DashboardPage from './pages/DashboardPage'
import PropertiesPage from './pages/PropertiesPage'
import SoldPage from './pages/SoldPage'
import PredictorPage from './pages/PredictorPage'
import ToolsPage from './pages/ToolsPage'
import DatabasePage from './pages/DatabasePage'

function App() {
  return (
    <BrowserRouter>
      <Routes>
        <Route path="/" element={<Layout />}>
          <Route index element={<DashboardPage />} />
          <Route path="properties" element={<PropertiesPage />} />
          <Route path="sold" element={<SoldPage />} />
          <Route path="predict" element={<PredictorPage />} />
          <Route path="tools" element={<ToolsPage />} />
          <Route path="database" element={<DatabasePage />} />
          <Route path="*" element={<Navigate to="/" replace />} />
        </Route>
      </Routes>
    </BrowserRouter>
  )
}

export default App
