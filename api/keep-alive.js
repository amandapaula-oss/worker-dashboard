const BACKEND_URL = process.env.REACT_APP_API_URL || "https://worker-dashboard-api.onrender.com";

export default async function handler(req, res) {
  try {
    const response = await fetch(`${BACKEND_URL}/health`, { signal: AbortSignal.timeout(10000) });
    res.status(200).json({ ok: true, status: response.status });
  } catch (err) {
    res.status(200).json({ ok: false, error: err.message });
  }
}
