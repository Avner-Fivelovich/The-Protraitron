import os
import sys
import json
import urllib.parse
import subprocess
import socketserver
import glob
import yaml
from http.server import HTTPServer, BaseHTTPRequestHandler

# Resolve project root directory
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.abspath(os.path.join(SCRIPT_DIR, '..', '..'))

# Load config
CONFIG_PATH = os.path.join(PROJECT_ROOT, 'config', 'server.yaml')
try:
    with open(CONFIG_PATH, 'r', encoding='utf-8') as f:
        config = yaml.safe_load(f)
        cg_config = config.get('command_generator', {}) if config else {}
except Exception as e:
    print(f"Warning: Failed to load config from {CONFIG_PATH}: {e}")
    cg_config = {}

PORT = cg_config.get('port', 8080)
HOST = cg_config.get('host', '0.0.0.0')
MODELS_DIR_REL = cg_config.get('models_dir', 'SwiftSketch-Protraitron/models')

# Resolve HTML file: check local directory first, then fallback to project root
HTML_FILE_NAME = cg_config.get('html_file', 'command_generator.html')
LOCAL_HTML_PATH = os.path.join(SCRIPT_DIR, 'command_generator.html')
ROOT_HTML_PATH = os.path.join(PROJECT_ROOT, HTML_FILE_NAME)
HTML_FILE = LOCAL_HTML_PATH if os.path.exists(LOCAL_HTML_PATH) else ROOT_HTML_PATH

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
            
        elif path == '/api/models':
            self.handle_models()
            
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
            target_html = HTML_FILE if os.path.exists(HTML_FILE) else LOCAL_HTML_PATH
            with open(target_html, 'r', encoding='utf-8') as f:
                content = f.read()
            self.send_response(200)
            self.send_header('Content-Type', 'text/html; charset=utf-8')
            self.send_header('Content-Length', str(len(content.encode('utf-8'))))
            self.end_headers()
            self.wfile.write(content.encode('utf-8'))
        except Exception as e:
            self.send_error(500, f"Error serving HTML: {e}")

    def handle_models(self):
        try:
            # Look for .pt files in MODELS_DIR_REL relative to project root
            models_dir = os.path.join(PROJECT_ROOT, MODELS_DIR_REL)
            pt_files = glob.glob(os.path.join(models_dir, '*.pt'))
            
            # Also check root models directory
            root_models_dir = os.path.join(PROJECT_ROOT, 'models')
            if os.path.exists(root_models_dir):
                pt_files.extend(glob.glob(os.path.join(root_models_dir, '*.pt')))
                
            model_names = list(set([os.path.basename(f) for f in pt_files]))
            model_names.sort(reverse=True)
            
            self.send_response(200)
            self.send_header('Content-Type', 'application/json')
            self.end_headers()
            self.wfile.write(json.dumps({"models": model_names}).encode('utf-8'))
        except Exception as e:
            self.send_error(500, f"Error loading models: {e}")

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
            
            # Start the child process with cwd set to PROJECT_ROOT
            active_process = subprocess.Popen(
                cmd,
                shell=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                env=env,
                bufsize=1,
                cwd=PROJECT_ROOT
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
    print(f"Starting server locally at http://{HOST}:{PORT}")
    print(f"Open http://{HOST}:{PORT} in your web browser to configure parameters.")
    print("Press Ctrl+C to terminate server.")
    print("=" * 60)
    
    server = ThreadingHTTPServer((HOST, PORT), CommandGeneratorHandler)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nShutting down server cleanly...")
        server.server_close()

if __name__ == '__main__':
    main()
