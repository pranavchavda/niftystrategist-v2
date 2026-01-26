// Simple static file server for testing the production build
import { createServer } from 'http';
import { readFileSync, existsSync } from 'fs';
import { join, extname } from 'path';

const PORT = 3000;
const BUILD_DIR = './build/client';

const mimeTypes = {
  '.html': 'text/html',
  '.js': 'application/javascript',
  '.css': 'text/css',
  '.json': 'application/json',
  '.png': 'image/png',
  '.jpg': 'image/jpeg',
  '.svg': 'image/svg+xml',
};

createServer((req, res) => {
  // Proxy API requests to backend
  if (req.url.startsWith('/api/')) {
    res.writeHead(307, { Location: `http://localhost:8000${req.url}` });
    res.end();
    return;
  }

  // Serve static files, fallback to index.html for client-side routing
  let filePath = join(BUILD_DIR, req.url === '/' ? 'index.html' : req.url);
  
  if (!existsSync(filePath)) {
    filePath = join(BUILD_DIR, 'index.html'); // SPA fallback
  }

  const ext = extname(filePath);
  const contentType = mimeTypes[ext] || 'application/octet-stream';

  try {
    const content = readFileSync(filePath);
    res.writeHead(200, { 'Content-Type': contentType });
    res.end(content);
  } catch (err) {
    res.writeHead(404);
    res.end('404 Not Found');
  }
}).listen(PORT, () => {
  console.log(`\n🚀 Serving production build at http://localhost:${PORT}`);
  console.log(`📡 Proxying /api/* to http://localhost:8000\n`);
  console.log('Make sure backend is running on port 8000!\n');
});
