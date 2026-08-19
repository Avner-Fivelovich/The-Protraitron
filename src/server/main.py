import os
import sys
import uuid
import time
import socket
import threading
from typing import Optional
import uvicorn
import qrcode
from fastapi import FastAPI, UploadFile, File, Form, HTTPException, Request, Depends
from fastapi.staticfiles import StaticFiles
from fastapi.responses import JSONResponse, FileResponse
from pydantic import BaseModel

# Add project root to sys.path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..")))

from src.common.logger import get_logger
from src.robot.controller import UR5eController
from src.robot.swiftsketch_integration import run_swiftsketch_inference, preprocess_image_to_square
from src.robot.svg_drawing import load_svg_file, normalize_svg_strokes
from src.robot.path_optimization import optimize_strokes_tsp, merge_close_strokes
from src.robot.mask_filtering import load_binary_mask, filter_strokes_with_mask
from src.robot.paper_handler import PaperHandler

logger = get_logger("FastAPIServer")

app = FastAPI(title="Portraitron 3000 Server")

import yaml

# Constants
PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
STATIC_DIR = os.path.join(os.path.dirname(__file__), "static")
# Load File Paths Config
FILES_PATHES_CONFIG = os.path.join(PROJECT_ROOT, "config", "files_pathes.yaml")
paths_cfg = {}
if os.path.exists(FILES_PATHES_CONFIG):
    with open(FILES_PATHES_CONFIG, "r") as f:
        paths_cfg = yaml.safe_load(f)

CALIBRATION_PATH = os.path.join(PROJECT_ROOT, paths_cfg.get("paths", {}).get("calibration_config", "config/calibration.yaml"))
MARKER_CONFIG_PATH = os.path.join(PROJECT_ROOT, paths_cfg.get("paths", {}).get("marker_config", "config/marker.yaml"))
SERVER_CONFIG_PATH = os.path.join(PROJECT_ROOT, paths_cfg.get("paths", {}).get("server_config", "config/server.yaml"))

server_cfg = {}
if os.path.exists(SERVER_CONFIG_PATH):
    with open(SERVER_CONFIG_PATH, "r") as f:
        server_cfg = yaml.safe_load(f)

# Configurable Paths & Settings
UPLOAD_DIR = os.path.join(PROJECT_ROOT, server_cfg.get("directories", {}).get("upload_dir", "plots/uploads"))
SKETCH_DIR = os.path.join(PROJECT_ROOT, server_cfg.get("directories", {}).get("sketch_dir", "plots/generated_sketches"))
ROBOT_IP = server_cfg.get("hardware", {}).get("robot_ip", "192.168.57.101")
SECRET_HANDSHAKE = server_cfg.get("server", {}).get("secret_handshake", "portraitron")

robot_logic_path = paths_cfg.get("paths", {}).get("robot_logic_config", "config/robot_logic.yaml")
robot_logic_cfg = {}
if os.path.exists(os.path.join(PROJECT_ROOT, robot_logic_path)):
    with open(os.path.join(PROJECT_ROOT, robot_logic_path), "r") as f:
        robot_logic_cfg = yaml.safe_load(f)
proc_cfg = robot_logic_cfg.get("processing", {})
hw_cfg = robot_logic_cfg.get("hardware", {})

# Ensure directories exist
os.makedirs(STATIC_DIR, exist_ok=True)
os.makedirs(UPLOAD_DIR, exist_ok=True)
os.makedirs(SKETCH_DIR, exist_ok=True)

# Active Drawing Queue
drawing_queue = []
active_job = None
queue_lock = threading.Lock()

class DrawingJob(BaseModel):
    id: str
    status: str  # "queued", "processing", "completed", "failed", "cancelled"
    original_name: str
    image_path: str
    svg_path: str
    mask_path: Optional[str] = None
    created_at: float
    started_at: Optional[float] = None
    completed_at: Optional[float] = None
    progress: int = 0  # percentage
    total_strokes: int = 0
    current_stroke: int = 0
    error: Optional[str] = None

# Background Worker for Robot drawing
def queue_worker():
    global active_job
    
    # Initialize UR5e Controller
    logger.info("Initializing UR5e Controller for background worker...")
    controller = UR5eController(
        ROBOT_IP, 
        calibration_path=CALIBRATION_PATH, 
        marker_config_path=MARKER_CONFIG_PATH
    )
    # Check if we should run in dryrun mode
    # Default to True if calibration file doesn't exist, to prevent hard crashes
    controller.dryrun = not os.path.exists(CALIBRATION_PATH)
    if controller.dryrun:
        logger.warning("Calibration file missing. Background worker running in DRY RUN mode.")
    
    while True:
        # Fetch next job
        job_to_run = None
        with queue_lock:
            # Find first queued job
            for j in drawing_queue:
                if j.status == "queued":
                    job_to_run = j
                    j.status = "processing"
                    j.started_at = time.time()
                    active_job = j
                    break
        
        if not job_to_run:
            time.sleep(1.0)
            continue
            
        logger.info(f"Processing job {job_to_run.id} ({job_to_run.original_name})...")
        
        try:
            # 1. Connect to robot
            if not controller.connect():
                raise Exception("Failed to connect to the UR5e robot.")
                
            # 2. Parse and normalize SVG paths
            raw_strokes = load_svg_file(job_to_run.svg_path)
            normalized_strokes = normalize_svg_strokes(
                raw_strokes,
                canvas_width=controller.width,
                canvas_height=controller.height
            )
            
            if not normalized_strokes:
                raise Exception("Generated SVG contains no valid stroke lines.")
                
            # Optional: Mask filtering
            if job_to_run.mask_path and os.path.exists(job_to_run.mask_path):
                mask_img = load_binary_mask(job_to_run.mask_path)
                if mask_img is not None:
                    keep_ratio = proc_cfg.get('mask_keep_ratio', 0.7)
                    normalized_strokes = filter_strokes_with_mask(
                        normalized_strokes, mask_img,
                        canvas_width=controller.width, canvas_height=controller.height,
                        keep_ratio=keep_ratio
                    )
            
            # Optional: Merging close strokes
            merge_threshold = proc_cfg.get('merge_threshold', 0.002)
            if merge_threshold > 0.0:
                normalized_strokes = merge_close_strokes(normalized_strokes, merge_threshold)
                
            # Optional: Optimize order
            optimize = proc_cfg.get('optimize_strokes', True)
            if optimize:
                logger.info("Optimizing stroke path order via TSP...")
                opt_strokes = optimize_strokes_tsp(normalized_strokes)
            else:
                opt_strokes = normalized_strokes
                
            job_to_run.total_strokes = len(opt_strokes)
            
            # 4. Home robot
            controller.home()
            time.sleep(1.0)
            
            # 5. Execute drawing paths with custom progression hooks
            speed = controller.cfg.get('slide_speed', 0.04)
            accel = controller.cfg.get('slide_acceleration', 0.08)
            blend_radius = controller.cfg.get('blend_radius', 0.002)
            draw_depth_offset = controller.cfg.get('draw_depth_offset', 0.0)
            
            # Progress callback to update active job status
            def update_progress(curr, total):
                with queue_lock:
                    if job_to_run.status == "cancelled":
                        return False
                    job_to_run.current_stroke = curr
                    job_to_run.progress = int((curr / total) * 100)
                    return True
            
            controller.execute_drawing_path(
                opt_strokes,
                speed=speed,
                accel=accel,
                blend_radius=blend_radius,
                draw_depth_offset=draw_depth_offset,
                progress_callback=update_progress
            )
            
            with queue_lock:
                if job_to_run.status == "cancelled":
                    logger.warning(f"Job {job_to_run.id} was cancelled during drawing.")
                else:
                    job_to_run.status = "completed"
                    job_to_run.completed_at = time.time()
                    job_to_run.progress = 100
                    logger.success(f"Job {job_to_run.id} completed successfully.")
                    
                    # 6. Optional: Paper swap
                    if hw_cfg.get('paper_swap', False) and not controller.dryrun:
                        logger.info("Executing automatic paper swap sequence...")
                        paper_handler = PaperHandler(controller.rtde_c, controller.rtde_r)
                        success = paper_handler.execute_paper_swap()
                        if not success:
                            logger.error("Paper swap failed.")
                        paper_handler.disconnect()
            
            # Park robot when done
            controller.home()
            controller.disconnect()
                    
        except Exception as e:
            logger.error(f"Error executing drawing job {job_to_run.id}: {e}")
            with queue_lock:
                job_to_run.status = "failed"
                job_to_run.error = str(e)
        finally:
            controller.disconnect()
            with queue_lock:
                active_job = None

# Start queue thread
worker_thread = threading.Thread(target=queue_worker, daemon=True)
worker_thread.start()

# API Endpoints
@app.post("/api/upload")
async def upload_image(file: UploadFile = File(...)):
    """
    Uploads a portrait image, runs the SwiftSketch model to vectorize it,
    and returns the preview SVG.
    """
    raw_path = None
    preprocessed_path = None
    try:
        # Save original file
        job_id = str(uuid.uuid4())
        file_ext = os.path.splitext(file.filename)[1]
        raw_filename = f"{job_id}{file_ext}"
        raw_path = os.path.join(UPLOAD_DIR, raw_filename)
        
        with open(raw_path, "wb") as buffer:
            contents = await file.read()
            buffer.write(contents)
            
        # Preprocess to square (1024x1024)
        preprocessed_filename = f"{job_id}_square.png"
        preprocessed_path = os.path.join(UPLOAD_DIR, preprocessed_filename)
        
        logger.info(f"Preprocessing uploaded image: {file.filename} -> {preprocessed_path}")
        preprocess_image_to_square(raw_path, preprocessed_path)
        
        return JSONResponse(content={
            "jobId": job_id,
            "filename": file.filename,
            "rawUrl": f"/api/raw/{raw_filename}"
        })
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error handling upload: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/generate/{strokes}")
def generate_sketch(strokes: int, job_id: str = Form(...)):
    """
    Generates an SVG for the given job_id and stroke configuration.
    """
    try:
        preprocessed_filename = f"{job_id}_square.png"
        preprocessed_path = os.path.join(UPLOAD_DIR, preprocessed_filename)
        
        if not os.path.exists(preprocessed_path):
            raise HTTPException(status_code=404, detail="Uploaded image not found. Please re-upload.")
            
        # Load calibration/parameters
        controller = UR5eController(ROBOT_IP, calibration_path=CALIBRATION_PATH, marker_config_path=MARKER_CONFIG_PATH)
        
        if strokes == 32:
            model_override = None
            svg_filename = f"{job_id}_sketch.svg"
            logger.info(f"Generating 32-stroke sketch for {job_id} using SwiftSketch...")
        elif strokes == 96:
            model_override = controller.cfg.get("swiftsketch", {}).get("model_96_path", "models/model000040000.pt")
            svg_filename = f"{job_id}_sketch_96.svg"
            logger.info(f"Generating 96-stroke sketch for {job_id} using SwiftSketch...")
        else:
            raise HTTPException(status_code=400, detail="Unsupported stroke count")
            
        svg_path = os.path.join(SKETCH_DIR, svg_filename)
        
        success = run_swiftsketch_inference(
            preprocessed_path, 
            svg_path, 
            controller.cfg, 
            override_model_path=model_override
        )
        
        if not success:
            raise HTTPException(status_code=500, detail="SwiftSketch generative model failed to vectorize image.")
            
        return JSONResponse(content={
            "svgUrl": f"/api/svg/{svg_filename}"
        })
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error generating {strokes} strokes: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/config")
def get_config():
    """
    Returns public frontend configuration values from server.yaml.
    """
    return {
        "camera_width": server_cfg.get("frontend", {}).get("camera_width", 1024),
        "camera_height": server_cfg.get("frontend", {}).get("camera_height", 768),
        "default_facing_mode": server_cfg.get("frontend", {}).get("default_facing_mode", "environment")
    }

@app.get("/api/raw/{filename}")
async def get_raw_file(filename: str):
    """
    Returns the uploaded raw image file.
    """
    safe_filename = os.path.basename(filename)
    file_path = os.path.join(UPLOAD_DIR, safe_filename)
    if not os.path.exists(file_path):
        raise HTTPException(status_code=404, detail="Raw image file not found.")
    return FileResponse(file_path)

@app.get("/api/svg/{filename}")
async def get_svg_file(filename: str):
    """
    Returns the generated SVG file.
    """
    safe_filename = os.path.basename(filename)
    file_path = os.path.join(SKETCH_DIR, safe_filename)
    if not os.path.exists(file_path):
        raise HTTPException(status_code=404, detail="SVG file not found.")
    return FileResponse(file_path, media_type="image/svg+xml")

@app.post("/api/draw")
async def trigger_drawing(
    job_id: str = Form(...),
    svg_filename: str = Form(...),
    original_name: str = Form(...),
    passcode: str = Form(...),
    mask_filename: Optional[str] = Form(None)
):
    """
    Adds a drawing task to the active robot execution queue.
    Requires a valid security passcode.
    """
    # Load configuration to verify handshake passcode
    controller = UR5eController(ROBOT_IP, calibration_path=CALIBRATION_PATH, marker_config_path=MARKER_CONFIG_PATH)
    required_passcode = controller.cfg.get("secret_handshake", "portraitron")
    
    if passcode != required_passcode:
        raise HTTPException(status_code=403, detail="Invalid security handshake passcode.")
        
    safe_svg = os.path.basename(svg_filename)
    svg_path = os.path.join(SKETCH_DIR, safe_svg)
    if not os.path.exists(svg_path):
        raise HTTPException(status_code=404, detail="SVG file not found.")
        
    mask_path = None
    if mask_filename:
        safe_mask = os.path.basename(mask_filename)
        mask_path = os.path.join(UPLOAD_DIR, safe_mask)
        if not os.path.exists(mask_path):
            raise HTTPException(status_code=404, detail="Mask file not found.")
        
    # Check if job is already in queue
    with queue_lock:
        for job in drawing_queue:
            if job.id == job_id and job.status in ("queued", "processing"):
                return JSONResponse(content={"status": "already_queued", "jobId": job_id})
                
        # Create new job
        new_job = DrawingJob(
            id=job_id,
            status="queued",
            original_name=original_name,
            image_path="",  # Optional
            svg_path=svg_path,
            mask_path=mask_path,
            created_at=time.time()
        )
        drawing_queue.append(new_job)
        
        # Calculate queue position
        position = len([j for j in drawing_queue if j.status == "queued"])
        
    logger.info(f"Job {job_id} successfully queued at position {position}.")
    return JSONResponse(content={
        "status": "queued",
        "jobId": job_id,
        "position": position
    })

@app.get("/api/queue")
async def get_queue_status():
    """
    Returns the current status of the queue and active job.
    """
    with queue_lock:
        active_list = [j.dict() for j in drawing_queue if j.status in ("queued", "processing")]
        history_list = [j.dict() for j in drawing_queue if j.status in ("completed", "failed", "cancelled")][-5:]
        
    return JSONResponse(content={
        "queue": active_list,
        "history": history_list,
        "activeJob": active_job.dict() if active_job else None
    })

@app.post("/api/cancel")
async def cancel_job(job_id: str = Form(...)):
    """
    Cancels a job in the queue. If it is currently drawing, it stops the robot.
    """
    with queue_lock:
        for job in drawing_queue:
            if job.id == job_id:
                if job.status == "queued":
                    job.status = "cancelled"
                    logger.info(f"Cancelled queued job {job_id}")
                    return JSONResponse(content={"status": "cancelled", "jobId": job_id})
                elif job.status == "processing":
                    job.status = "cancelled"
                    # The queue_worker checks for this status and stops servo Stop
                    logger.info(f"Requested cancellation for active drawing job {job_id}")
                    return JSONResponse(content={"status": "cancelling", "jobId": job_id})
                    
    raise HTTPException(status_code=404, detail="Job not found in queue.")

def get_local_ip():
    """Get the local IP address of the machine on the network."""
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        s.connect(('10.255.255.255', 1))
        IP = s.getsockname()[0]
    except Exception:
        IP = '127.0.0.1'
    finally:
        s.close()
    return IP

def generate_startup_qr(ip_address, port=8000):
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
    qr_img.save(os.path.join(STATIC_DIR, 'qr.png'))
    
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

@app.get("/api/qr-data")
async def get_qr_data(request: Request):
    local_ip = get_local_ip()
    current_port = 8000
    if ":" in request.url.netloc:
        try:
            current_port = int(request.url.netloc.split(":")[-1])
        except ValueError:
            pass
    return JSONResponse(content={
        'local_ip_url': f"http://{local_ip}:{current_port}"
    })

@app.get("/")
async def serve_index():
    return FileResponse(os.path.join(STATIC_DIR, "index.html"))

def verify_localhost(request: Request):
    """
    Dependency that blocks any request not originating from localhost.
    This secures the admin dashboard from being accessed over Wi-Fi.
    """
    client_host = request.client.host
    if client_host not in ("127.0.0.1", "::1", "localhost"):
        logger.warning(f"Blocked unauthorized admin access attempt from {client_host}")
        raise HTTPException(status_code=403, detail="Admin dashboard is restricted to localhost only.")

@app.get("/admin", dependencies=[Depends(verify_localhost)])
async def serve_admin():
    return FileResponse(os.path.join(STATIC_DIR, "admin.html"))

@app.get("/api/admin/queue", dependencies=[Depends(verify_localhost)])
async def admin_get_queue():
    with queue_lock:
        active_list = [j.dict() for j in drawing_queue if j.status in ("queued", "processing")]
        history_list = [j.dict() for j in drawing_queue if j.status in ("completed", "failed", "cancelled")][-20:]
    return JSONResponse(content={
        "queue": active_list,
        "history": history_list,
        "activeJob": active_job.dict() if active_job else None
    })

@app.post("/api/admin/cancel", dependencies=[Depends(verify_localhost)])
async def admin_cancel_job(job_id: str = Form(...)):
    with queue_lock:
        for job in drawing_queue:
            if job.id == job_id:
                if job.status == "queued":
                    job.status = "cancelled"
                    logger.info(f"Admin cancelled queued job {job_id}.")
                    return JSONResponse(content={"status": "cancelled"})
        
        if active_job and active_job.id == job_id:
            active_job.status = "cancelled"
            logger.info(f"Admin cancelled active job {job_id}. Robot will stop.")
            return JSONResponse(content={"status": "cancelling_active"})
            
    raise HTTPException(status_code=404, detail="Job not found or already completed.")

@app.post("/api/admin/clear_queue", dependencies=[Depends(verify_localhost)])
async def admin_clear_queue():
    with queue_lock:
        for job in drawing_queue:
            if job.status == "queued":
                job.status = "cancelled"
        logger.info("Admin cleared all queued jobs.")
    return JSONResponse(content={"status": "cleared"})

@app.post("/api/admin/park", dependencies=[Depends(verify_localhost)])
async def admin_park_robot():
    logger.info("Admin triggered EMERGENCY PARK.")
    controller = UR5eController(ROBOT_IP, calibration_path=CALIBRATION_PATH, marker_config_path=MARKER_CONFIG_PATH)
    if controller.connect():
        controller.home()
        controller.disconnect()
        return JSONResponse(content={"status": "parked"})
    return JSONResponse(content={"status": "error", "detail": "Could not connect to robot."})

@app.post("/api/admin/swap_paper", dependencies=[Depends(verify_localhost)])
async def admin_swap_paper():
    logger.info("Admin triggered manual paper swap.")
    controller = UR5eController(ROBOT_IP, calibration_path=CALIBRATION_PATH, marker_config_path=MARKER_CONFIG_PATH)
    if controller.connect():
        paper_handler = PaperHandler(controller.rtde_c, controller.rtde_r)
        success = paper_handler.execute_paper_swap()
        paper_handler.disconnect()
        controller.disconnect()
        if success:
            return JSONResponse(content={"status": "swapped"})
        return JSONResponse(content={"status": "error", "detail": "Paper swap sequence failed."})
    return JSONResponse(content={"status": "error", "detail": "Could not connect to robot."})

# Serve static files
app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")

def start_server(port=8000):
    """
    Boots the FastAPI web server using uvicorn.
    Generates QR code for LAN access.
    """
    local_ip = get_local_ip()
    generate_startup_qr(local_ip, port=port)
    uvicorn.run("src.server.main:app", host="0.0.0.0", port=port, reload=True)

if __name__ == "__main__":
    start_server()
