#!/usr/bin/env python3
"""
Simple HTTP/HTTPS proxy server for routing YouTube requests through your residential IP.
Run this on your local machine, then expose it via ngrok or similar tunneling service.
"""

import http.server
import socketserver
import urllib.request
import urllib.parse
import sys
import logging
from typing import Optional

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

class ProxyHandler(http.server.BaseHTTPRequestHandler):
    """HTTP proxy handler that forwards requests."""
    
    def do_GET(self):
        """Handle GET requests."""
        self._proxy_request()
    
    def do_POST(self):
        """Handle POST requests."""
        self._proxy_request()
    
    def do_PUT(self):
        """Handle PUT requests."""
        self._proxy_request()
    
    def do_DELETE(self):
        """Handle DELETE requests."""
        self._proxy_request()
    
    def do_CONNECT(self):
        """Handle CONNECT requests for HTTPS."""
        # Extract host and port
        host, port = self.path.split(':', 1)
        port = int(port) if port else 443
        
        try:
            # Connect to target
            import socket
            target = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            target.connect((host, port))
            
            # Send 200 Connection established
            self.wfile.write(b'HTTP/1.1 200 Connection established\r\n\r\n')
            
            # Relay data
            self._relay_connection(target)
            
        except Exception as e:
            logger.error(f"CONNECT failed: {e}")
            self.send_error(502, f"Proxy error: {e}")
        finally:
            if 'target' in locals():
                target.close()
    
    def _relay_connection(self, target):
        """Relay data between client and target."""
        import select
        import socket
        
        client_sock = self.connection
        while True:
            try:
                readable, _, _ = select.select([client_sock, target], [], [], 1)
                if not readable:
                    continue
                
                for sock in readable:
                    data = sock.recv(8192)
                    if not data:
                        return
                    
                    if sock is client_sock:
                        target.sendall(data)
                    else:
                        client_sock.sendall(data)
            except Exception as e:
                logger.error(f"Relay error: {e}")
                return
    
    def _proxy_request(self):
        """Proxy HTTP request to target server."""
        try:
            # Parse the request URL
            url = self.path
            if not url.startswith('http'):
                # Extract host from headers
                host = self.headers.get('Host', '')
                if not host:
                    self.send_error(400, "Missing Host header")
                    return
                url = f"{'https' if self.command == 'CONNECT' else 'http'}://{host}{url}"
            
            logger.info(f"Proxying {self.command} {url}")
            
            # Create request
            req = urllib.request.Request(url, method=self.command)
            
            # Copy headers (except hop-by-hop headers)
            hop_by_hop = {'connection', 'keep-alive', 'proxy-authenticate', 
                          'proxy-authorization', 'te', 'trailers', 'transfer-encoding', 'upgrade'}
            
            for header, value in self.headers.items():
                if header.lower() not in hop_by_hop:
                    req.add_header(header, value)
            
            # Copy body for POST/PUT
            if self.command in ('POST', 'PUT'):
                content_length = int(self.headers.get('Content-Length', 0))
                if content_length > 0:
                    req.data = self.rfile.read(content_length)
            
            # Make request
            try:
                with urllib.request.urlopen(req, timeout=30) as response:
                    # Send response headers
                    self.send_response(response.getcode())
                    
                    # Copy response headers
                    for header, value in response.headers.items():
                        if header.lower() not in hop_by_hop:
                            self.send_header(header, value)
                    
                    self.end_headers()
                    
                    # Copy response body
                    self.wfile.write(response.read())
                    
            except urllib.error.HTTPError as e:
                logger.error(f"HTTP error: {e.code} {e.reason}")
                self.send_response(e.code)
                self.end_headers()
                self.wfile.write(e.read())
            except Exception as e:
                logger.error(f"Request failed: {e}")
                self.send_error(502, f"Proxy error: {e}")
                
        except Exception as e:
            logger.error(f"Proxy error: {e}")
            self.send_error(500, f"Internal proxy error: {e}")
    
    def log_message(self, format, *args):
        """Override to use our logger."""
        logger.info(f"{self.address_string()} - {format % args}")


def run_proxy(port: int = 8888, host: str = '127.0.0.1'):
    """Run the proxy server."""
    handler = ProxyHandler
    
    with socketserver.TCPServer((host, port), handler) as httpd:
        logger.info(f"Proxy server running on {host}:{port}")
        logger.info(f"Access it at http://{host}:{port}")
        logger.info("")
        logger.info("To expose publicly, use one of these options:")
        logger.info("  1. ngrok: ngrok http 8888")
        logger.info("  2. cloudflared: cloudflared tunnel --url http://localhost:8888")
        logger.info("  3. localtunnel: lt --port 8888")
        logger.info("")
        logger.info("Then set PROXY_URL environment variable on Render to the public URL")
        
        try:
            httpd.serve_forever()
        except KeyboardInterrupt:
            logger.info("\nShutting down proxy server...")
            httpd.shutdown()


if __name__ == '__main__':
    port = int(sys.argv[1]) if len(sys.argv) > 1 else 8888
    host = sys.argv[2] if len(sys.argv) > 2 else '127.0.0.1'
    
    run_proxy(port, host)

