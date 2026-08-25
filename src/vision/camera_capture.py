import os
import cv2
import numpy as np

# Try loading from common config utils, otherwise fallback to empty dict
try:
    from src.common.config_utils import load_config_from_yaml
    VISION_CONFIG = load_config_from_yaml("config/vision.yaml")
except ImportError:
    import yaml
    def _load_backup_config():
        path = "config/vision.yaml"
        if os.path.exists(path):
            with open(path, 'r') as f:
                return yaml.safe_load(f) or {}
        return {}
    VISION_CONFIG = _load_backup_config()

def capture_image_from_camera(output_raw_path: str) -> bool:
    """
    Opens the default webcam, runs a preview loop with a face centering guide,
    and captures a photo when SPACE is pressed. Press ESC or Q to quit.
    """
    camera_index = VISION_CONFIG.get('camera_index', 0)
    guide_color = tuple(VISION_CONFIG.get('guide_color', [0, 255, 0]))
    guide_thickness = VISION_CONFIG.get('guide_thickness', 2)
    guide_text1 = VISION_CONFIG.get('guide_text1', "Position Face Inside Oval")
    guide_text2 = VISION_CONFIG.get('guide_text2', "Press SPACE to Capture | ESC to Quit")
    window_name = VISION_CONFIG.get('window_name', "Portraitron Camera Preview")
    
    print(f"Opening webcam... Press SPACE to capture, ESC or Q to exit.")
    cap = cv2.VideoCapture(camera_index)
    
    if not cap.isOpened():
        print("Error: Could not access the webcam.")
        return False
        
    captured = False
    
    while True:
        ret, frame = cap.read()
        if not ret:
            print("Error: Could not read frame from camera.")
            break
            
        # Create a copy for drawing overlays
        display_frame = frame.copy()
        height, width = frame.shape[:2]
        
        # Draw a face guide overlay (oval in the center)
        center_x = width // 2
        center_y = height // 2
        axes_x = int(width * VISION_CONFIG.get('guide_axes_x_ratio', 0.22))
        axes_y = int(height * VISION_CONFIG.get('guide_axes_y_ratio', 0.35))
        
        # Draw dotted oval
        cv2.ellipse(
            display_frame, 
            (center_x, center_y), 
            (axes_x, axes_y), 
            0, 0, 360, 
            guide_color, 
            guide_thickness, 
            lineType=cv2.LINE_AA
        )
        
        # Add text guides
        cv2.putText(
            display_frame, 
            guide_text1, 
            (center_x - 150, 40), 
            cv2.FONT_HERSHEY_SIMPLEX, 
            0.7, 
            guide_color, 
            guide_thickness, 
            cv2.LINE_AA
        )
        cv2.putText(
            display_frame, 
            guide_text2, 
            (center_x - 220, height - 30), 
            cv2.FONT_HERSHEY_SIMPLEX, 
            0.6, 
            guide_color, 
            guide_thickness, 
            cv2.LINE_AA
        )
        
        cv2.imshow(window_name, display_frame)
        
        key = cv2.waitKey(1) & 0xFF
        if key == 32:  # SPACE
            cv2.imwrite(output_raw_path, frame)
            captured = True
            print(f"Raw image captured and saved to: {output_raw_path}")
            break
        elif key == 27 or key == ord('q') or key == ord('Q'):  # ESC or Q
            print("Camera capture cancelled by user.")
            break
            
    cap.release()
    cv2.destroyAllWindows()
    cv2.waitKey(1)  # Extra wait to ensure window closes on macOS
    return captured

def make_square(img: np.ndarray, size: int = None) -> np.ndarray:
    """
    Pads the image with white pixels to make it square and resizes it.
    """
    if size is None:
        size = VISION_CONFIG.get('target_square_size', 1024)
        
    bg_color = VISION_CONFIG.get('square_bg_color', [255, 255, 255])
    
    h, w = img.shape[:2]
    max_dim = max(h, w)
    pad_top = (max_dim - h) // 2
    pad_bottom = max_dim - h - pad_top
    pad_left = (max_dim - w) // 2
    pad_right = max_dim - w - pad_left
    
    padded = cv2.copyMakeBorder(
        img, pad_top, pad_bottom, pad_left, pad_right,
        cv2.BORDER_CONSTANT, value=bg_color
    )
    return cv2.resize(padded, (size, size), interpolation=cv2.INTER_LANCZOS4)

def detect_and_crop_face(input_path: str, output_path: str) -> tuple[bool, list]:
    """
    Loads an image, detects the primary face using Haar Cascades,
    crops to portrait proportions (head and shoulders), and saves the result.
    Returns (success, face_rectangle [fx, fy, fw, fh]).
    """
    if not os.path.exists(input_path):
        print(f"Error: Input path {input_path} does not exist.")
        return False, []
        
    img = cv2.imread(input_path)
    height, width = img.shape[:2]
    
    faces = []
    try:
        if hasattr(cv2, 'CascadeClassifier'):
            gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
            cascade_file = VISION_CONFIG.get('cascade_file', 'haarcascade_frontalface_default.xml')
            cascade_path = cv2.data.haarcascades + cascade_file
            face_cascade = cv2.CascadeClassifier(cascade_path)
            
            scale_factor = VISION_CONFIG.get('face_detect_scale_factor', 1.1)
            min_neighbors = VISION_CONFIG.get('face_detect_min_neighbors', 5)
            min_size = tuple(VISION_CONFIG.get('face_detect_min_size', [100, 100]))
            
            faces = face_cascade.detectMultiScale(
                gray, 
                scaleFactor=scale_factor, 
                minNeighbors=min_neighbors, 
                minSize=min_size
            )
    except Exception as e:
        print(f"Face detector warning: {e}. Using center crop.")
    
    target_square_size = VISION_CONFIG.get('target_square_size', 1024)
    
    if len(faces) == 0:
        print("Using center square crop.")
        crop_size = min(height, width)
        x1 = (width - crop_size) // 2
        y1 = (height - crop_size) // 2
        cropped = img[y1:y1+crop_size, x1:x1+crop_size]
        cv2.imwrite(output_path, cv2.resize(cropped, (target_square_size, target_square_size), interpolation=cv2.INTER_LANCZOS4))
        return False, [x1, y1, crop_size, crop_size]
        
    # Get largest face
    fx, fy, fw, fh = max(faces, key=lambda f: f[2] * f[3])
    print(f"Detected face at X:{fx}, Y:{fy}, W:{fw}, H:{fh}")
    
    # Calculate crop coordinates centered on face (shifted down for shoulders)
    crop_height_ratio = VISION_CONFIG.get('crop_height_ratio', 2.8)
    crop_center_y_ratio = VISION_CONFIG.get('crop_center_y_ratio', 0.8)
    
    target_dim = int(fh * crop_height_ratio)
    cx = fx + fw // 2
    cy = fy + int(fh * crop_center_y_ratio)
    
    x1 = max(0, cx - target_dim // 2)
    y1 = max(0, cy - target_dim // 2)
    x2 = min(width, cx + target_dim // 2)
    y2 = min(height, cy + target_dim // 2)
    
    cropped = img[y1:y2, x1:x2]
    square_cropped = make_square(cropped, target_square_size)
    cv2.imwrite(output_path, square_cropped)
    
    print(f"Face cropped and saved to: {output_path}")
    return True, [fx, fy, fw, fh]

def apply_background_removal_vignette(input_path: str, output_path: str, face_rect: list = None) -> bool:
    """
    Applies GrabCut foreground extraction using face location,
    and blends the edges to pure white using an elliptical vignette.
    """
    if not os.path.exists(input_path):
        print(f"Error: Input path {input_path} does not exist.")
        return False
        
    img = cv2.imread(input_path)
    height, width = img.shape[:2]
    
    # Initialize GrabCut mask
    mask = np.zeros(img.shape[:2], np.uint8)
    bgdModel = np.zeros((1, 65), np.float64)
    fgdModel = np.zeros((1, 65), np.float64)
    
    # Setup region of interest (ROI) for GrabCut
    if face_rect and len(face_rect) == 4:
        margin_ratio = VISION_CONFIG.get('face_rect_margin_ratio', 0.1)
        top_ratio = VISION_CONFIG.get('face_rect_top_ratio', 0.1)
        margin = int(width * margin_ratio)
        rect = (margin, int(height * top_ratio), width - 2 * margin, height - int(height * top_ratio))
    else:
        margin_ratio = VISION_CONFIG.get('default_rect_margin_ratio', 0.15)
        top_ratio = VISION_CONFIG.get('default_rect_top_ratio', 0.05)
        margin = int(width * margin_ratio)
        rect = (margin, int(height * top_ratio), width - 2 * margin, height - int(height * top_ratio))
        
    # Run GrabCut segmentation
    grabcut_iter = VISION_CONFIG.get('grabcut_iter', 5)
    try:
        cv2.grabCut(img, mask, rect, bgdModel, fgdModel, grabcut_iter, cv2.GC_INIT_WITH_RECT)
        # 0 = background, 2 = prob background. Let's keep 1 (fgd) and 3 (prob fgd)
        fg_mask = np.where((mask == 2) | (mask == 0), 0, 1).astype('uint8')
    except Exception as e:
        print(f"Warning: GrabCut failed ({e}). Falling back to simple vignette mask.")
        fg_mask = np.ones(img.shape[:2], np.uint8)
        
    # Smooth the GrabCut mask
    mask_blur_kernel = tuple(VISION_CONFIG.get('mask_blur_kernel', [21, 21]))
    fg_mask_blurred = cv2.GaussianBlur(fg_mask * 255, mask_blur_kernel, 0) / 255.0
    fg_mask_blurred = np.expand_dims(fg_mask_blurred, axis=-1)
    
    # Create an elliptical vignette mask to guarantee clean edges fading to white
    vignette = np.zeros(img.shape[:2], np.uint8)
    center_x = int(width * VISION_CONFIG.get('vignette_center_x_ratio', 0.5))
    center_y = int(height * VISION_CONFIG.get('vignette_center_y_ratio', 0.45))
    axes_x = int(width * VISION_CONFIG.get('vignette_axes_x_ratio', 0.42))
    axes_y = int(height * VISION_CONFIG.get('vignette_axes_y_ratio', 0.48))
    
    cv2.ellipse(vignette, (center_x, center_y), (axes_x, axes_y), 0, 0, 360, 255, -1)
    
    # Soften vignette boundary
    vignette_blur_kernel = tuple(VISION_CONFIG.get('vignette_blur_kernel', [101, 101]))
    vignette_blurred = cv2.GaussianBlur(vignette, vignette_blur_kernel, 0) / 255.0
    vignette_blurred = np.expand_dims(vignette_blurred, axis=-1)
    
    # Combine GrabCut mask and vignette mask
    combined_mask = fg_mask_blurred * vignette_blurred
    
    # Apply combined mask: blend image with white background
    white_bg_value = VISION_CONFIG.get('white_bg_value', 255)
    white_bg = np.ones_like(img) * white_bg_value
    output_img = img * combined_mask + white_bg * (1.0 - combined_mask)
    
    cv2.imwrite(output_path, output_img.astype(np.uint8))
    print(f"Background removed and saved to: {output_path}")
    return True
