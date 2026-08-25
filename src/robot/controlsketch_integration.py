import os
import sys
import time
import subprocess
import shutil
from src.common.logger import get_logger

logger = get_logger("ControlSketchIntegration")

def run_remote_controlsketch(
    input_image_path: str,
    output_svg_path: str,
    config: dict,
    num_strokes: int = 96,
    num_iter: int = 300,
    timeout_seconds: int = 1800
) -> bool:
    """
    Automates the high-quality ControlSketch optimization on the TAU Slurm GPU cluster:
    1. Uploads the preprocessed portrait image to the cluster via SCP.
    2. Submits/executes ControlSketch on the cluster GPU (300-500 iterations, approx. 3 mins).
    3. Downloads the resulting high-quality SVG vector sketch and PNG preview.
    
    :param input_image_path: Path to the input portrait photo (PNG/JPG).
    :param output_svg_path: Destination path for the generated vector SVG.
    :param config: Configuration dict containing cluster credentials & settings.
    :param num_strokes: Number of strokes (default: 96).
    :param num_iter: Number of optimization iterations (default: 300).
    :param timeout_seconds: Maximum time to wait for optimization (default: 30 mins).
    :return: True if generation succeeded and SVG is downloaded, False otherwise.
    """
    cluster_cfg = config.get("cluster", {})
    cluster_user = cluster_cfg.get("username", "regevshabath")
    cluster_host = cluster_cfg.get("hostname", "slurm-client.cs.tau.ac.il")
    remote_base = cluster_cfg.get("remote_repo_path", "/vol/joberant_nobck/data/NLP_368307701_2526a/avnerf/SwiftSketch-Protraitron")
    remote_cs_dir = f"{remote_base}/outputs/code_override"
    remote_conda_env = cluster_cfg.get("conda_env", "swiftsketch_env")
    remote_conda_path = cluster_cfg.get("conda_activate_path", "/vol/joberant_nobck/data/NLP_368307701_2526a/avnerf/anaconda3/bin/activate")
    
    if not os.path.exists(input_image_path):
        logger.error(f"Input image not found: {input_image_path}")
        return False
        
    job_tag = f"cs_live_{int(time.time())}"
    remote_data_dir = f"{remote_base}/ControlSketch/data"
    remote_out_dir = f"{remote_base}/outputs/{job_tag}"
    remote_image_name = f"{job_tag}.jpg"
    remote_image_path = f"{remote_data_dir}/{remote_image_name}"
    
    ssh_opts = [
        "-o", "StrictHostKeyChecking=no",
        "-o", "UserKnownHostsFile=/dev/null",
        "-o", "BatchMode=yes",
        "-o", "ConnectTimeout=10"
    ]
    
    logger.info(f"Starting High-Quality ControlSketch optimization ({num_strokes} strokes, {num_iter} iterations)...")
    logger.info(f"Connecting to TAU Cluster ({cluster_user}@{cluster_host})...")
    
    try:
        # 1. Upload the image to the cluster
        logger.info(f"Uploading image to cluster: {remote_image_path}...")
        upload_cmd = ["scp"] + ssh_opts + [
            os.path.abspath(input_image_path),
            f"{cluster_user}@{cluster_host}:{remote_image_path}"
        ]
        res = subprocess.run(upload_cmd, capture_output=True, text=True)
        if res.returncode != 0:
            logger.error(f"SCP Upload failed: {res.stderr}")
            logger.warning("Ensure SSH key authentication is configured on the cluster.")
            return False
            
        logger.success("Image uploaded to cluster successfully.")
        
        # 2. Execute ControlSketch on the cluster GPU
        logger.info(f"Executing ControlSketch {num_iter}-step optimization on cluster GPU (NVIDIA TITAN Xp)...")
        remote_python = "/vol/joberant_nobck/data/NLP_368307701_2526a/avnerf/anaconda3/envs/swiftsketch_env/bin/python"
        remote_cmd_inner = (
            f"export CUDA_VISIBLE_DEVICES=0 && "
            f"export HF_HOME=/tmp/regevshabath_hf_cache && "
            f"export TRANSFORMERS_CACHE=/tmp/regevshabath_hf_cache && "
            f"export CLIP_CACHE_DIR=/vol/joberant_nobck/data/NLP_368307701_2526a/avnerf/clip_cache && "
            f"export PYTORCH_CUDA_ALLOC_CONF=expandable_segments:True && "
            f"mkdir -p /tmp/regevshabath_hf_cache && "
            f"cd {remote_cs_dir} && "
            f"{remote_python} object_sketching.py "
            f"--target {remote_image_path} "
            f"--num_strokes {num_strokes} "
            f"--num_iter {num_iter} "
            f"--save_interval 50 "
            f"--output_dir {remote_out_dir} "
            f"--fix_scale 1"
        )
        remote_script = f"bash -lc '{remote_cmd_inner}'"
        
        ssh_cmd = ["ssh"] + ssh_opts + [
            f"{cluster_user}@{cluster_host}",
            remote_script
        ]
        
        start_t = time.time()
        res = subprocess.run(
            ssh_cmd, 
            capture_output=True, 
            text=True, 
            encoding="utf-8", 
            errors="replace", 
            timeout=timeout_seconds
        )
        elapsed = time.time() - start_t
        
        if res.returncode != 0:
            logger.error(f"Remote ControlSketch execution failed with code {res.returncode}:\nSTDERR: {res.stderr}\nSTDOUT: {res.stdout}")
            return False
            
        logger.success(f"Cluster GPU optimization completed successfully in {elapsed:.1f} seconds.")
        
        # 3. Dynamically find and download the generated SVG and PNG
        find_cmd = ["ssh"] + ssh_opts + [
            f"{cluster_user}@{cluster_host}",
            f"bash -lc 'find {remote_out_dir} -name \"final_svg.svg\" -o -name \"*.svg\" | head -n 1'"
        ]
        res_find = subprocess.run(find_cmd, capture_output=True, text=True, encoding="utf-8", errors="replace")
        remote_svg_path = res_find.stdout.strip()
        
        if not remote_svg_path:
            logger.error(f"No generated SVG found in remote directory: {remote_out_dir}")
            return False
            
        logger.info(f"Found remote generated SVG: {remote_svg_path}")
        os.makedirs(os.path.dirname(os.path.abspath(output_svg_path)), exist_ok=True)
        
        download_svg_cmd = ["scp"] + ssh_opts + [
            f"{cluster_user}@{cluster_host}:{remote_svg_path}",
            os.path.abspath(output_svg_path)
        ]
        subprocess.run(download_svg_cmd, capture_output=True, text=True)
        
        if not os.path.exists(output_svg_path):
            logger.error("Failed to download generated SVG from cluster.")
            return False
            
        # Also find and download PNG preview
        find_png_cmd = ["ssh"] + ssh_opts + [
            f"{cluster_user}@{cluster_host}",
            f"bash -lc 'find {remote_out_dir} -name \"final_sketch.png\" -o -name \"*.png\" | head -n 1'"
        ]
        res_find_png = subprocess.run(find_png_cmd, capture_output=True, text=True)
        remote_png_path = res_find_png.stdout.strip()
        if remote_png_path:
            output_png_path = os.path.splitext(output_svg_path)[0] + "_preview.png"
            download_png_cmd = ["scp"] + ssh_opts + [
                f"{cluster_user}@{cluster_host}:{remote_png_path}",
                os.path.abspath(output_png_path)
            ]
            subprocess.run(download_png_cmd, capture_output=True, text=True)
        
        logger.success(f"High-quality 96-stroke vector sketch downloaded to: {output_svg_path}")
        return True
        
    except subprocess.TimeoutExpired:
        logger.error(f"Cluster optimization timed out after {timeout_seconds} seconds.")
        return False
    except Exception as e:
        logger.error(f"Error during remote ControlSketch execution: {e}")
        return False
