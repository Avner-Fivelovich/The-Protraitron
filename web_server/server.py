import os
import socket
from flask import Flask, render_template, request, jsonify, send_from_directory
from PIL import Image, ImageFilter, ImageOps, ImageMath
import qrcode

app = Flask(__name__)

# Folder configurations
UPLOAD_FOLDER = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'uploads')
STATIC_FOLDER = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'static')
os.makedirs(UPLOAD_FOLDER, exist_ok=True)
os.makedirs(STATIC_FOLDER, exist_ok=True)

app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
# Set max file size to 16MB
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024

def get_local_ip():
    """Get the local IP address of the machine on the network."""
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        # Doesn't need to be reachable, just triggers OS network routing info
        s.connect(('10.255.255.255', 1))
        IP = s.getsockname()[0]
    except Exception:
        IP = '127.0.0.1'
    finally:
        s.close()
    return IP

def generate_sketch(input_path, output_path):
    """Processes an image to look like a hand-drawn pencil sketch."""
    try:
        # Open and orient image correctly if EXIF data is present
        img = Image.open(input_path)
        img = ImageOps.exif_transpose(img)
        
        # Convert to grayscale
        gray_img = ImageOps.grayscale(img)
        
        # Invert the grayscale image
        inverted_img = ImageOps.invert(gray_img)
        
        # Apply Gaussian Blur to the inverted image
        blurred_img = inverted_img.filter(ImageFilter.GaussianBlur(radius=15))
        
        # Perform Color Dodge blend using ImageMath
        sketch_img = ImageMath.unsafe_eval(
            "convert(a * 256 / (255 - b + 1), 'L')",
            a=gray_img,
            b=blurred_img
        )
        
        # Save the raster result
        sketch_img.convert('RGB').save(output_path, 'JPEG', quality=90)
        return sketch_img
    except Exception as e:
        print(f"Error generating sketch: {e}")
        return None

def run_custom_vector_tracer(image_obj, svg_path):
    """
    Traces lines from a black-and-white sketch image and saves them in SVG vector path format.
    This simulates the vector stroke output of SwiftSketch.
    """
    try:
        # Convert image to binary black/white (threshold)
        binary = image_obj.point(lambda p: 0 if p < 200 else 255).convert('1')
        width, height = binary.size
        pixels = binary.load()
        
        visited = set()
        paths = []
        step = 2 # trace every 2 pixels to keep it fast
        
        for y in range(0, height, step):
            for x in range(0, width, step):
                if pixels[x, y] == 0 and (x, y) not in visited:
                    # Start tracing a path
                    current_path = []
                    curr_x, curr_y = x, y
                    current_path.append((curr_x, curr_y))
                    visited.add((curr_x, curr_y))
                    
                    # 8-way neighbor search tracing loop
                    while True:
                        found_next = False
                        for dx in [-step, 0, step]:
                            for dy in [-step, 0, step]:
                                if dx == 0 and dy == 0:
                                    continue
                                nx, ny = curr_x + dx, curr_y + dy
                                if 0 <= nx < width and 0 <= ny < height:
                                    if pixels[nx, ny] == 0 and (nx, ny) not in visited:
                                        curr_x, curr_y = nx, ny
                                        current_path.append((curr_x, curr_y))
                                        visited.add((curr_x, curr_y))
                                        found_next = True
                                        break
                            if found_next:
                                break
                        if not found_next:
                            break
                    
                    # Store path if it's long enough to filter random noise
                    if len(current_path) > 3:
                        paths.append(current_path)
                        
        # Generate SVG string
        svg_lines = [
            f'<svg viewBox="0 0 {width} {height}" xmlns="http://www.w3.org/2000/svg">',
            '  <rect width="100%" height="100%" fill="white" />'
        ]
        for path in paths:
            d = []
            d.append(f"M {path[0][0]} {path[0][1]}")
            for pt in path[1:]:
                d.append(f"L {pt[0]} {pt[1]}")
            path_str = " ".join(d)
            svg_lines.append(f'  <path d="{path_str}" stroke="black" stroke-width="1.5" fill="none" stroke-linecap="round" stroke-linejoin="round" />')
        svg_lines.append('</svg>')
        
        with open(svg_path, 'w') as f:
            f.write("\n".join(svg_lines))
        return True
    except Exception as e:
        print(f"Error tracing SVG: {e}")
        return False

import subprocess
import shutil

def run_swiftsketch_pipeline(input_path, output_svg_path, sketch_img_obj):
    """
    PIPELINE HOOK FOR SWIFTSKETCH INTEGRATION
    Runs the deep learning model to generate a professional vector SVG.
    Falls back to custom line tracer if it fails or is not available.
    """
    try:
        # Define paths
        model_script = r"C:\tau_university\2026B\Robotics\web_server\swiftsketch_model\SwiftSketch\generate.py"
        model_path = r"C:\tau_university\2026B\Robotics\web_server\swiftsketch_model\SwiftSketch\save\sketch-diffusion\model000450000.pt"
        refine_model_path = r"C:\tau_university\2026B\Robotics\web_server\swiftsketch_model\SwiftSketch\save\refinement-network\model000430000.pt"
        cwd = r"C:\tau_university\2026B\Robotics\web_server\swiftsketch_model\SwiftSketch"
        
        # We need a temp directory for the output SVG
        temp_out_dir = os.path.join(app.config['UPLOAD_FOLDER'], f"temp_ss_{os.urandom(4).hex()}")
        os.makedirs(temp_out_dir, exist_ok=True)
        
        # Construct command
        cmd = [
            sys.executable,
            model_script,
            "--model_path", model_path,
            "--refine_model_path", refine_model_path,
            "--input_data", os.path.abspath(input_path),
            "--output_dir", os.path.abspath(temp_out_dir),
            "--save_svg", "1",
            "--use_refine", "1"
        ]
        
        print(f"Running SwiftSketch: {' '.join(cmd)}")
        result = subprocess.run(cmd, cwd=cwd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, timeout=120)
        
        # Check if run succeeded
        if result.returncode == 0:
            input_basename = os.path.splitext(os.path.basename(input_path))[0]
            generated_svg = os.path.join(temp_out_dir, f"{input_basename}.svg")
            
            if os.path.exists(generated_svg):
                shutil.copy(generated_svg, output_svg_path)
                print(f"SwiftSketch successfully generated vector SVG: {output_svg_path}")
                
                # Cleanup temp directory
                try:
                    shutil.rmtree(temp_out_dir)
                except Exception:
                    pass
                return True
            else:
                print("SwiftSketch succeeded but output SVG file was not found. Falling back...")
        else:
            error_msg = f"SwiftSketch execution failed with code {result.returncode}.\nStderr: {result.stderr}\nStdout: {result.stdout}"
            print(error_msg)
            with open("pipeline_error.log", "w", encoding="utf-8") as err_f:
                err_f.write(error_msg)
            
        # Cleanup temp directory on failure
        try:
            shutil.rmtree(temp_out_dir)
        except Exception:
            pass
            
    except Exception as e:
        error_msg = f"SwiftSketch pipeline encountered exception: {e}"
        print(error_msg)
        try:
            with open("pipeline_error.log", "w", encoding="utf-8") as err_f:
                err_f.write(error_msg)
        except Exception:
            pass
        
    # Fallback to the fast custom line tracer
    print("Falling back to custom vector line tracer...")
    return run_custom_vector_tracer(sketch_img_obj, output_svg_path)

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/api/qr-data')
def get_qr_data():
    local_ip = get_local_ip()
    current_port = 5000
    if ":" in request.host:
        try:
            current_port = int(request.host.split(":")[-1])
        except ValueError:
            pass
    return jsonify({
        'local_ip_url': f"http://{local_ip}:{current_port}"
    })

@app.route('/upload', methods=['POST'])
def upload_image():
    if 'image' not in request.files:
        return jsonify({'error': 'No image file in the request'}), 400
        
    file = request.files['image']
    if file.filename == '':
        return jsonify({'error': 'No selected file'}), 400
        
    if file:
        # Generate safe filenames
        filename = f"photo_{os.urandom(4).hex()}.jpg"
        raw_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
        
        sketch_filename = f"sketch_{filename}"
        sketch_path = os.path.join(app.config['UPLOAD_FOLDER'], sketch_filename)
        
        svg_filename = f"vector_{os.urandom(4).hex()}.svg"
        svg_path = os.path.join(app.config['UPLOAD_FOLDER'], svg_filename)
        
        # Save raw image
        file.save(raw_path)
        
        # Process sketch to PIL Image object
        sketch_img = generate_sketch(raw_path, sketch_path)
        
        if sketch_img is not None:
            # Run the vectorization pipeline (mocking SwiftSketch SVG output)
            success = run_swiftsketch_pipeline(raw_path, svg_path, sketch_img)
            
            if success:
                return jsonify({
                    'raw_url': f'/uploads/{filename}',
                    'sketch_url': f'/uploads/{svg_filename}'
                })
            else:
                return jsonify({'error': 'Failed to generate vector layout'}), 500
        else:
            return jsonify({'error': 'Failed to process sketch'}), 500

@app.route('/uploads/<filename>')
def serve_upload(filename):
    return send_from_directory(app.config['UPLOAD_FOLDER'], filename)

def generate_startup_qr(ip_address, port=5000):
    """Generates a QR code pointing to the server and saves it to static/qr.png."""
    url = f"http://{ip_address}:{port}"
    qr = qrcode.QRCode(
        version=1,
        error_correction=qrcode.constants.ERROR_CORRECT_L,
        box_size=10,
        border=4,
    )
    qr.add_data(url)
    qr.make(fit=True)

    # Save image to static folder
    qr_img = qr.make_image(fill_color="black", back_color="white")
    qr_img.save(os.path.join(STATIC_FOLDER, 'qr.png'))
    
    # Also print an ASCII QR Code to terminal for instant scanning
    print("\n" + "="*50)
    print(" SCAN THIS QR CODE WITH YOUR PHONE TO OPEN THE CAMERA PAGE:")
    print("="*50)
    try:
        import sys
        if hasattr(sys.stdout, 'reconfigure'):
            sys.stdout.reconfigure(encoding='utf-8')
        qr.print_ascii(invert=True)
    except Exception:
        print("[ASCII QR Code could not be rendered in this console - see static/qr.png or visit the link below]")
    print("="*50)
    print(f" Server URL: {url}")
    print(f" Local URL:  http://localhost:{port}")
    print("="*50 + "\n")

if __name__ == '__main__':
    import sys
    port = 5000
    if len(sys.argv) > 1:
        try:
            port = int(sys.argv[1])
        except ValueError:
            print(f"Invalid port argument. Using default: {port}")
            
    local_ip = get_local_ip()
    generate_startup_qr(local_ip, port=port)
    
    # Run server on all network interfaces
    app.run(host='0.0.0.0', port=port, debug=True)
