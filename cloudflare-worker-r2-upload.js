export default {
  async fetch(request, env) {
    const corsHeaders = {
      'Access-Control-Allow-Origin': env.ALLOWED_ORIGIN || '*',
      'Access-Control-Allow-Methods': 'POST, OPTIONS',
      'Access-Control-Allow-Headers': 'Content-Type, Cache-Control, X-Filename, X-Upload-Token',
    };

    if (request.method === 'OPTIONS') {
      return new Response(null, {
        status: 204,
        headers: corsHeaders,
      });
    }

    const url = new URL(request.url);
    if (url.pathname !== '/upload') {
      return json({ success: false, error: 'Not found' }, 404, corsHeaders);
    }

    if (request.method !== 'POST') {
      return json({ success: false, error: 'Method not allowed' }, 405, corsHeaders);
    }

    if (!env.R2_BUCKET) {
      return json({ success: false, error: 'R2_BUCKET binding is missing' }, 500, corsHeaders);
    }

    if (env.UPLOAD_TOKEN && request.headers.get('X-Upload-Token') !== env.UPLOAD_TOKEN) {
      return json({ success: false, error: 'Upload token required' }, 401, corsHeaders);
    }

    try {
      const filename = safeFilename(request.headers.get('X-Filename') || 'theblack_animated.webp');
      const contentType = request.headers.get('Content-Type') || 'image/webp';
      const cacheControl = request.headers.get('Cache-Control') || 'public, max-age=31536000, immutable';
      const body = await request.arrayBuffer();

      if (!body.byteLength) {
        return json({ success: false, error: 'Empty upload body' }, 400, corsHeaders);
      }

      await env.R2_BUCKET.put(filename, body, {
        httpMetadata: {
          contentType,
          cacheControl,
        },
      });

      const publicBaseUrl = (env.PUBLIC_BASE_URL || url.origin).replace(/\/+$/, '');

      return json({
        success: true,
        publicUrl: `${publicBaseUrl}/${encodePath(filename)}`,
        size: body.byteLength,
      }, 200, corsHeaders);
    } catch (error) {
      return json({
        success: false,
        error: error.message || 'Upload failed',
      }, 400, corsHeaders);
    }
  },
};

function json(data, status, headers) {
  return new Response(JSON.stringify(data), {
    status,
    headers: {
      ...headers,
      'Content-Type': 'application/json; charset=utf-8',
    },
  });
}

function safeFilename(filename) {
  const value = String(filename).replace(/^\/+/, '');

  if (!value || value.includes('..') || value.includes('\\')) {
    throw new Error('Invalid filename');
  }

  return value;
}

function encodePath(path) {
  return path.split('/').map(encodeURIComponent).join('/');
}
