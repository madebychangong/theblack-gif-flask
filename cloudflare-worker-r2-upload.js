export default {
  async fetch(request, env) {
    const corsHeaders = createCorsHeaders(request, env);

    if (request.method === 'OPTIONS') {
      return new Response(null, {
        status: 204,
        headers: corsHeaders,
      });
    }

    const origin = request.headers.get('Origin');
    if (origin && !isOriginAllowed(origin, env.ALLOWED_ORIGIN)) {
      return json({ success: false, error: 'Origin not allowed' }, 403, corsHeaders);
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

    if (!env.PUBLIC_BASE_URL) {
      return json({ success: false, error: 'PUBLIC_BASE_URL is missing' }, 500, corsHeaders);
    }

    if (env.UPLOAD_TOKEN && request.headers.get('X-Upload-Token') !== env.UPLOAD_TOKEN) {
      return json({ success: false, error: 'Upload token required' }, 401, corsHeaders);
    }

    try {
      const filename = safeFilename(request.headers.get('X-Filename') || 'theblack_animated.webp');
      const contentType = request.headers.get('Content-Type') || '';
      const maxUploadBytes = Number(env.MAX_UPLOAD_BYTES || 5 * 1024 * 1024);
      const contentLength = Number(request.headers.get('Content-Length') || 0);

      if (!contentType.toLowerCase().startsWith('image/webp')) {
        return json({ success: false, error: 'Only image/webp uploads are allowed' }, 415, corsHeaders);
      }

      if (contentLength > maxUploadBytes) {
        return json({ success: false, error: `Upload is too large. Max ${maxUploadBytes} bytes` }, 413, corsHeaders);
      }

      const cacheControl = request.headers.get('Cache-Control') || 'public, no-cache';
      const body = await request.arrayBuffer();

      if (!body.byteLength) {
        return json({ success: false, error: 'Empty upload body' }, 400, corsHeaders);
      }

      if (body.byteLength > maxUploadBytes) {
        return json({ success: false, error: `Upload is too large. Max ${maxUploadBytes} bytes` }, 413, corsHeaders);
      }

      await env.R2_BUCKET.put(filename, body, {
        httpMetadata: {
          contentType,
          cacheControl,
        },
      });

      const publicBaseUrl = env.PUBLIC_BASE_URL.replace(/\/+$/, '');

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

function createCorsHeaders(request, env) {
  const origin = request.headers.get('Origin');
  const allowedOrigin = resolveAllowedOrigin(origin, env.ALLOWED_ORIGIN);

  return {
    'Access-Control-Allow-Origin': allowedOrigin,
    'Access-Control-Allow-Methods': 'POST, OPTIONS',
    'Access-Control-Allow-Headers': 'Content-Type, Cache-Control, X-Filename, X-Upload-Token',
  };
}

function resolveAllowedOrigin(origin, allowedOriginConfig) {
  if (!allowedOriginConfig || allowedOriginConfig === '*') {
    return '*';
  }

  const allowedOrigins = allowedOriginConfig.split(',').map(value => value.trim()).filter(Boolean);

  if (origin && allowedOrigins.includes(origin)) {
    return origin;
  }

  return allowedOrigins[0] || '*';
}

function isOriginAllowed(origin, allowedOriginConfig) {
  if (!allowedOriginConfig || allowedOriginConfig === '*') {
    return true;
  }

  return allowedOriginConfig.split(',').map(value => value.trim()).includes(origin);
}

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
