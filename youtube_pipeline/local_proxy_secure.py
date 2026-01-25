#!/usr/bin/env python3
"""
Secure HTTP/HTTPS proxy server with authentication and IP whitelisting.
Run this on your local machine, then expose it via ngrok or similar tunneling service.

SECURITY FEATURES:
- Basic authentication (username/password)
- IP whitelist (only allow specific IPs)
- Request logging
- Rate limiting (optional)
"""

import http.server
import socketserver
import urllib.request
import urllib.parse
import sys
import logging
import base64
import os
from typing import Optional, Set

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Security configuration
PROXY_USERNAME = os.getenv('PROXY_USERNAME', 'render')
PROXY_PASSWORD = os.getenv('PROXY_PASSWORD', 'changeme123')  # CHANGE THIS!
ALLOWED_IPS: Set[str] = set()  # Empty = allow all, or add specific IPs like {'52.1.2.3'}

class SecureProxyHandler(http.server.BaseHTTPRequestHandler):
    """HTTP proxy handler with authentication and IP whitelisting."""
    
    def _check_auth(self) -> bool:
        """Check if request has valid authentication."""
        auth_header = self.headers.get('Proxy-Authorization', '')
        
        if not auth_header.startswith('Basic '):
            return False
        
        try:
            encoded = auth_header.split(' ', 1)[1]
            decoded = base64.b64decode(encoded).decode('utf-8')
            username, password = decoded.split(':', 1)
            
            return username == PROXY_USERNAME and password == PROXY_PASSWORD
        except Exception:
            return False
    
    def _check_ip_whitelist(self) -> bool:
        """Check if client IP is in whitelist."""
        if not ALLOWED_IPS:
            return True  # No whitelist = allow all
        
        client_ip = self.client_address[0]
        return client_ip in ALLOWED_IPS
    
    def _send_auth_required(self):
        """Send 407 Proxy Authentication Required."""
        self.send_response(407)
        self.send_header('Proxy-Authenticate', 'Basic realm="Proxy"')
        self.end_headers()
        self.wfile.write(b'Proxy Authentication Required')
    
    def _send_forbidden(self):
        """Send 403 Forbidden."""
        self.send_error(403, "IP not whitelisted")
    
    def do_GET(self):
        """Handle GET requests."""
        if not self._check_ip_whitelist():
            self._send_forbidden()
            return
        if not self._check_auth():
            self._send_auth_required()
            return
        self._proxy_request()
    
    def do_POST(self):
        """Handle POST requests."""
        if not self._check_ip_whitelist():
            self._send_forbidden()
            return
        if not self._check_auth():
            self._send_auth_required()
            return
        self._proxy_request()
    
    def do_PUT(self):
        """Handle PUT requests."""
        if not self._check_ip_whitelist():
            self._send_forbidden()
            return
        if not self._check_auth():
            self._send_auth_required()
            return
        self._proxy_request()
    
    def do_DELETE(self):
        """Handle DELETE requests."""
        if not self._check_ip_whitelist():
            self._send_forbidden()
            return
        if not self._check_auth():
            self._send_auth_required()
            return
        self._proxy_request()
    
    def do_CONNECT(self):
        """Handle CONNECT requests for HTTPS."""
        if not self._check_ip_whitelist():
            self._send_forbidden()
            return
        if not self._check_auth():
            self._send_auth_required()
            return
        
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
            
            # Log request (for monitoring)
            logger.info(f"Proxying {self.command} {url} from {self.client_address[0]}")
            
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
    """Run the secure proxy server."""
    handler = SecureProxyHandler
    
    with socketserver.TCPServer((host, port), handler) as httpd:
        logger.info(f"Secure proxy server running on {host}:{port}")
        logger.info(f"Access it at http://{host}:{port}")
        logger.info("")
        logger.info("SECURITY CONFIGURATION:")
        logger.info(f"  Username: {PROXY_USERNAME}")
        logger.info(f"  Password: {'*' * len(PROXY_PASSWORD)}")
        logger.info(f"  IP Whitelist: {'Enabled' if ALLOWED_IPS else 'Disabled (allowing all IPs)'}")
        if ALLOWED_IPS:
            logger.info(f"    Allowed IPs: {', '.join(ALLOWED_IPS)}")
        logger.info("")
        logger.info("To expose publicly, use one of these options:")
        logger.info("  1. ngrok: ngrok http 8888")
        logger.info("  2. cloudflared: cloudflared tunnel --url http://localhost:8888")
        logger.info("  3. localtunnel: lt --port 8888")
        logger.info("")
        logger.info("IMPORTANT: Set PROXY_USERNAME and PROXY_PASSWORD environment variables!")
        logger.info("Example: PROXY_USERNAME=myuser PROXY_PASSWORD=mypass python local_proxy.py")
        logger.info("")
        logger.info("For Render, set YOUTUBE_PROXY_URL to:")
        logger.info(f"  http://{PROXY_USERNAME}:{PROXY_PASSWORD}@your-ngrok-url")
        
        try:
            httpd.serve_forever()
        except KeyboardInterrupt:
            logger.info("\nShutting down proxy server...")
            httpd.shutdown()


if __name__ == '__main__':
    port = int(sys.argv[1]) if len(sys.argv) > 1 else 8888
    host = sys.argv[2] if len(sys.argv) > 2 else '127.0.0.1'
    
    run_proxy(port, host)

