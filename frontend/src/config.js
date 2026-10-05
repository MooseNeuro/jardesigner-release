// Base URL of the Flask backend.
//
// An empty string means "same origin as the page". That is the normal case:
// the packaged app (`jardesigner` command) serves the built frontend from the
// same Flask process, on whatever --port it was started with.
//
// The Vite dev server runs on its own port, so in dev mode the backend is
// assumed to be on port 5000 of the same host. Set VITE_API_BASE_URL to
// override either default.
export const API_BASE_URL =
    import.meta.env.VITE_API_BASE_URL ??
    (import.meta.env.DEV ? `http://${window.location.hostname}:5000` : '');
