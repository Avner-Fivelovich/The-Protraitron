import os
import subprocess
import shutil
from PIL import Image
from src.common.logger import get_logger

logger = get_logger("SwiftSketchIntegration")

def preprocess_image_to_square(input_path: str, output_path: str, size: int = 1024):
    """
    Resizes the input image so its maximum dimension is size, 
    and pads it with white pixels to form a square (size x size) image.
    This preserves the original aspect ratio without smearing/stretching.
    """
    with Image.open(input_path) as img:
        # Handle alpha channel (convert RGBA/LA to RGB with white background)
        if img.mode in ('RGBA', 'LA') or (img.mode == 'P' and 'transparency' in img.info):
            bg = Image.new("RGB", img.size, (255, 255, 255))
            if img.mode == 'RGBA':
                bg.paste(img, (0, 0), img)
            else:
                bg.paste(img.convert('RGBA'), (0, 0), img.convert('RGBA'))
            img = bg
        else:
            img = img.convert("RGB")

        width, height = img.size
        max_dim = max(width, height)
        scale = size / max_dim
        new_w = int(width * scale)
        new_h = int(height * scale)

        # Resize image
        img_resized = img.resize((new_w, new_h), Image.Resampling.LANCZOS if hasattr(Image, 'Resampling') else Image.ANTIALIAS)

        # Create white background canvas
        new_img = Image.new("RGB", (size, size), (255, 255, 255))

        # Center resized image on canvas
        x = (size - new_w) // 2
        y = (size - new_h) // 2
        new_img.paste(img_resized, (x, y))

        new_img.save(output_path)

def run_swiftsketch_inference(input_image_path: str, output_svg_path: str, config: dict, override_model_path: str = None) -> bool:
    """
    Runs SwiftSketch inference on the input image using the conda environment
    and saves the resulting SVG to output_svg_path.
    
    :param input_image_path: Path to the input portrait image (JPEG/PNG).
    :param output_svg_path: Path where the output SVG should be copied/saved.
    :param config: Configuration dictionary (typically loaded from marker.yaml).
    :param override_model_path: Optional relative path to override the default model.
    :return: True if successful, False otherwise.
    """
    # 1. Load parameters from config
    swiftsketch_cfg = config.get("swiftsketch", {})
    conda_env = swiftsketch_cfg.get("conda_env", "swiftsketch_env")
    repo_rel_path = swiftsketch_cfg.get("repo_path", "../swiftsketch")
    model_rel_path = override_model_path or swiftsketch_cfg.get("model_path", "SwiftSketch/save/sketch-diffusion/model000450000.pt")
    refine_model_rel_path = swiftsketch_cfg.get("refine_model_path", "SwiftSketch/save/refinement-network/model000430000.pt")
    guidance_param = swiftsketch_cfg.get("guidance_param", 2.5)
    use_refine = swiftsketch_cfg.get("use_refine", 1)
    use_residual = swiftsketch_cfg.get("use_residual", False)

    # 2. Get absolute paths
    # Resolve relative paths with respect to this project's root folder
    project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
    swiftsketch_dir = os.path.abspath(os.path.join(project_root, repo_rel_path))
    
    # Path to the SwiftSketch subdirectory containing generate.py
    swiftsketch_src_dir = os.path.join(swiftsketch_dir, "SwiftSketch")
    
    model_path = os.path.abspath(os.path.join(swiftsketch_dir, model_rel_path))
    refine_model_path = os.path.abspath(os.path.join(swiftsketch_dir, refine_model_rel_path))
    abs_input_image = os.path.abspath(input_image_path)
    
    if not os.path.exists(abs_input_image):
        logger.error(f"Input image path does not exist: {abs_input_image}")
        return False
        
    if not os.path.exists(swiftsketch_dir):
        logger.error(f"SwiftSketch repository not found at: {swiftsketch_dir}")
        return False
        
    if not os.path.exists(model_path):
        logger.error(f"Model checkpoint not found at: {model_path}")
        return False

    # 3. Create a temporary output folder inside our workspace
    temp_output_dir = os.path.abspath(os.path.join(project_root, "plots", "swiftsketch_temp"))
    os.makedirs(temp_output_dir, exist_ok=True)

    try:
        # Preprocess image to a square 1024x1024 with white padding to prevent shape mismatches
        preprocessed_image_path = os.path.join(temp_output_dir, "preprocessed_input.png")
        try:
            logger.info(f"Preprocessing input image to square (1024x1024) with white padding...")
            preprocess_image_to_square(abs_input_image, preprocessed_image_path)
            abs_input_image = preprocessed_image_path
        except Exception as e:
            logger.error(f"Failed to preprocess image: {e}. Proceeding with original image.")

        # 4. Prepare command
        module_to_run = "residual_generate" if use_residual else "generate"
        cmd = [
            "conda", "run", "-n", conda_env,
            "python", "-m", module_to_run,
            "--model_path", model_path,
            "--refine_model_path", refine_model_path,
            "--input_data", abs_input_image,
            "--output_dir", temp_output_dir,
            "--use_refine", str(use_refine),
            "--guidance_param", str(guidance_param)
        ]

        logger.info(f"Running SwiftSketch inference command in conda environment '{conda_env}'...")
        logger.info(f"Command: {' '.join(cmd)}")

        # Run command inside SwiftSketch source directory so imports resolve correctly
        # Pass the parent directory in PYTHONPATH so 'SwiftSketch' module imports work
        env = os.environ.copy()
        env["PYTHONPATH"] = swiftsketch_dir
        
        result = subprocess.run(
            cmd,
            cwd=swiftsketch_src_dir,
            env=env,
            capture_output=True,
            text=True,
            check=True
        )
        logger.info("SwiftSketch inference completed successfully.")
        
        # 5. Extract the generated SVG file
        image_filename = os.path.basename(abs_input_image)
        base_name = os.path.splitext(image_filename)[0]
        expected_svg = os.path.join(temp_output_dir, f"{base_name}.svg")
        
        if not os.path.exists(expected_svg):
            logger.error(f"Expected generated SVG file not found at: {expected_svg}")
            # Try to list files in output directory to find any generated SVG
            files = os.listdir(temp_output_dir)
            if files:
                logger.info(f"Files found in output dir: {files}")
                # Fallback to first .svg file found
                svg_files = [f for f in files if f.endswith(".svg")]
                if svg_files:
                    expected_svg = os.path.join(temp_output_dir, svg_files[0])
                    logger.info(f"Falling back to found SVG: {expected_svg}")
                else:
                    return False
            else:
                return False
                
        # Copy file to output_svg_path
        os.makedirs(os.path.dirname(os.path.abspath(output_svg_path)), exist_ok=True)
        shutil.copy2(expected_svg, output_svg_path)
        logger.info(f"Copied generated sketch SVG to: {output_svg_path}")
        return True

    except subprocess.CalledProcessError as e:
        logger.error(f"SwiftSketch execution failed with exit code {e.returncode}")
        logger.error(f"Stdout:\n{e.stdout}")
        logger.error(f"Stderr:\n{e.stderr}")
        return False
    except Exception as e:
        logger.error(f"An unexpected error occurred during SwiftSketch run: {str(e)}")
        return False
    finally:
        if os.path.exists(temp_output_dir):
            shutil.rmtree(temp_output_dir)
