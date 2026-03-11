import { useState } from 'react'
import { fetchEnterprise } from './api/client'
import './App.css'

function App() {
  const [enterpriseId, setEnterpriseId] = useState('1')
  const [enterprise, setEnterprise] = useState(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState(null)

  const handleFetch = async () => {
    setError(null)
    setEnterprise(null)
    setLoading(true)
    try {
      const id = Number(enterpriseId)
      if (Number.isNaN(id) || id < 1) {
        setError('Please enter a valid ID (positive number)')
        return
      }
      const data = await fetchEnterprise(id)
      setEnterprise(data ?? null)
    } catch (e) {
      setError(e.message || 'Failed to fetch enterprise')
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="app">
      <h1>Enterprise AI Knowledge Assistant</h1>
      <div className="card">
        <label htmlFor="enterprise-id">Enterprise ID</label>
        <input
          id="enterprise-id"
          type="number"
          min="1"
          value={enterpriseId}
          onChange={(e) => setEnterpriseId(e.target.value)}
        />
        <button onClick={handleFetch} disabled={loading}>
          {loading ? 'Loading…' : 'Fetch enterprise'}
        </button>
      </div>
      {error && <p className="error">{error}</p>}
      {enterprise !== null && enterprise !== undefined && (
        <div className="result">
          <h2>Enterprise</h2>
          {enterprise ? (
            <pre>{JSON.stringify(enterprise, null, 2)}</pre>
          ) : (
            <p>No enterprise found for this ID.</p>
          )}
        </div>
      )}
    </div>
  )
}

export default App
