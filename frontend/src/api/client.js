const getBaseUrl = () => import.meta.env.VITE_API_URL || 'http://localhost:8000';

export async function fetchEnterprise(id) {
  const base = getBaseUrl();
  const res = await fetch(`${base}/enterprise/${id}`);
  if (!res.ok) {
    throw new Error(`API error: ${res.status}`);
  }
  return res.json();
}
