import os
import sys
import json
import urllib.parse
import subprocess
import socketserver
from http.server import HTTPServer, BaseHTTPRequestHandler

PORT = 8080
active_process = None

class ThreadingHTTPServer(socketserver.ThreadingMixIn, HTTPServer):
    """
    Multi-threaded HTTP server using standard Python libraries.
    This allows handling concurrent requests, e.g. aborting a process
    while the terminal output is streaming.
    """
    daemon_threads = True

class CommandGeneratorHandler(BaseHTTPRequestHandler):
    def log_message(self, format, *args):
        # Silence default server logging to keep terminal output clean
        pass

    def do_GET(self):
        global active_process
        
        parsed_url = urllib.parse.urlparse(self.path)
        path = parsed_url.path
        
        if path == '/' or path == '/index.html':
            self.serve_html()
            
        elif path == '/api/run':
            self.handle_run_stream(parsed_url.query)
            
        else:
            self.send_error(404, "File not found")

    def do_POST(self):
        global active_process
        
        parsed_url = urllib.parse.urlparse(self.path)
        path = parsed_url.path
        
        if path == '/api/abort':
            self.handle_abort()
        else:
            self.send_error(404, "Endpoint not found")

    def serve_html(self):
        try:
            with open('command_generator.html', 'r', encoding='utf-8') as f:
                content = f.read()
            self.send_response(200)
            self.send_header('Content-Type', 'text/html; charset=utf-8')
            self.send_header('Content-Length', str(len(content.encode('utf-8'))))
            self.end_headers()
            self.wfile.write(content.encode('utf-8'))
        except Exception as e:
            self.send_error(500, f"Error serving HTML: {e}")

    def handle_run_stream(self, query_string):
        global active_process
        
        params = urllib.parse.parse_qs(query_string)
        cmd_list = params.get('cmd')
        if not cmd_list:
            self.send_error(400, "Missing cmd parameter")
            return
            
        cmd = cmd_list[0]
        print(f"[SERVER] Launching CLI command: {cmd}")
        
        # Send SSE (Server-Sent Events) headers
        self.send_response(200)
        self.send_header('Content-Type', 'text/event-stream')
        self.send_header('Cache-Control', 'no-cache')
        self.send_header('Connection', 'keep-alive')
        self.end_headers()
        
        try:
            # Run the command with PAGER=cat so we don't block on long outputs
            env = os.environ.copy()
            env["PAGER"] = "cat"
            
            # Start the child process
            active_process = subprocess.Popen(
                cmd,
                shell=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                env=env,
                bufsize=1
            )
            
            # Stream stdout line-by-line in real-time
            for line in active_process.stdout:
                clean_line = line.rstrip('\r\n')
                # Escape SSE format: prefix with 'data: ' and end with '\n\n'
                self.wfile.write(f"data: {clean_line}\n\n".encode('utf-8'))
                self.wfile.flush()
                
            active_process.wait()
            exit_code = active_process.returncode
            
            if exit_code == 0:
                self.wfile.write(b"data: [PROCESS_COMPLETED]\n\n")
            else:
                self.wfile.write(f"data: [PROCESS_FAILED]: {exit_code}\n\n".encode('utf-8'))
            self.wfile.flush()
            
        except Exception as e:
            err_msg = f"[SERVER ERROR] Execution failed: {e}"
            self.wfile.write(f"data: {err_msg}\n\n".encode('utf-8'))
            self.wfile.write(b"data: [PROCESS_FAILED]: -1\n\n")
            self.wfile.flush()
        finally:
            active_process = None

    def handle_abort(self):
        global active_process
        
        if active_process:
            print("[SERVER] Terminating active drawing process...")
            try:
                active_process.terminate()
                active_process.wait(timeout=3)
            except subprocess.TimeoutExpired:
                active_process.kill()
            active_process = None
            
        self.send_response(200)
        self.send_header('Content-Type', 'application/json')
        self.end_headers()
        self.wfile.write(json.dumps({"status": "aborted"}).encode('utf-8'))

def main():
    print("=" * 60)
    print("      PORTRAITRON 3000 COMMAND CONTROL PANEL SERVER")
    print("=" * 60)
    print(f"Starting server locally at http://localhost:{PORT}")
    print("Open http://localhost:8080 in your web browser to configure parameters.")
    print("Press Ctrl+C to terminate server.")
    print("=" * 60)
    
    server = ThreadingHTTPServer(('0.0.0.0', PORT), CommandGeneratorHandler)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nShutting down server cleanly...")
        server.server_close()

if __name__ == '__main__':
    main()
