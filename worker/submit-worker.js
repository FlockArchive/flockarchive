export default {
  async fetch(request, env) {
    if (request.method === 'OPTIONS') {
      return new Response(null, {
        headers: {
          'Access-Control-Allow-Origin': '*',
          'Access-Control-Allow-Methods': 'POST, OPTIONS',
          'Access-Control-Allow-Headers': 'Content-Type',
        },
      });
    }

    if (request.method !== 'POST') {
      return new Response('Method not allowed', { status: 405 });
    }

    let body;
    try {
      body = await request.json();
    } catch {
      return new Response(JSON.stringify({ error: 'Invalid JSON' }), {
        status: 400,
        headers: { 'Content-Type': 'application/json', 'Access-Control-Allow-Origin': '*' },
      });
    }

    let url = (body.url || '').trim();
    if (!url.startsWith('http')) url = 'https://' + url;
    let hostname;
    try { hostname = new URL(url).hostname; } catch { hostname = ''; }
    if (!hostname.endsWith('flocksafety.com')) {
      return new Response(JSON.stringify({ error: 'Only flocksafety.com URLs are accepted' }), {
        status: 400,
        headers: { 'Content-Type': 'application/json', 'Access-Control-Allow-Origin': '*' },
      });
    }

    const resp = await fetch('https://api.github.com/repos/FlockArchive/flockarchive/dispatches', {
      method: 'POST',
      headers: {
        'Authorization': `Bearer ${env.GITHUB_PAT}`,
        'Accept': 'application/vnd.github.v3+json',
        'Content-Type': 'application/json',
        'User-Agent': 'FlockArchive-Worker',
      },
      body: JSON.stringify({
        event_type: 'submit-url',
        client_payload: { url },
      }),
    });

    if (resp.status === 204) {
      return new Response(JSON.stringify({ ok: true }), {
        headers: { 'Content-Type': 'application/json', 'Access-Control-Allow-Origin': '*' },
      });
    }

    return new Response(JSON.stringify({ error: 'GitHub API error', status: resp.status }), {
      status: 502,
      headers: { 'Content-Type': 'application/json', 'Access-Control-Allow-Origin': '*' },
    });
  },
};
