import os
import cv2
import numpy as np

def capture_image_from_camera(output_raw_path: str) -> bool:
    """
    Opens the default webcam, runs a preview loop with a face centering guide,
    and captures a photo when SPACE is pressed. Press ESC or Q to quit.
    """
    print("Opening webcam... Press SPACE to capture, ESC or Q to exit.")
    cap = cv2.VideoCapture(0)
    
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
        axes_x = int(width * 0.22)
        axes_y = int(height * 0.35)
        
        # Draw dotted oval
        cv2.ellipse(
            display_frame, 
            (center_x, center_y), 
            (axes_x, axes_y), 
            0, 0, 360, 
            (0, 255, 0), 
            2, 
            lineType=cv2.LINE_AA
        )
        
        # Add text guides
        cv2.putText(
            display_frame, 
            "Position Face Inside Oval", 
            (center_x - 150, 40), 
            cv2.FONT_HERSHEY_SIMPLEX, 
            0.7, 
            (0, 255, 0), 
            2, 
            cv2.LINE_AA
        )
        cv2.putText(
            display_frame, 
            "Press SPACE to Capture | ESC to Quit", 
            (center_x - 220, height - 30), 
            cv2.FONT_HERSHEY_SIMPLEX, 
            0.6, 
            (0, 255, 0), 
            2, 
            cv2.LINE_AA
        )
        
        cv2.imshow("Portraitron Camera Preview", display_frame)
        
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

def make_square(img: np.ndarray, size: int = 1024) -> np.ndarray:
    """
    Pads the image with white pixels to make it square and resizes it.
    """
    h, w = img.shape[:2]
    max_dim = max(h, w)
    pad_top = (max_dim - h) // 2
    pad_bottom = max_dim - h - pad_top
    pad_left = (max_dim - w) // 2
    pad_right = max_dim - w - pad_left
    
    padded = cv2.copyMakeBorder(
        img, pad_top, pad_bottom, pad_left, pad_right,
        cv2.BORDER_CONSTANT, value=[255, 255, 255]
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
    
    # Run face detection
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    cascade_path = cv2.data.haarcascades + 'haarcascade_frontalface_default.xml'
    face_cascade = cv2.CascadeClassifier(cascade_path)
    faces = face_cascade.detectMultiScale(gray, scaleFactor=1.1, minNeighbors=5, minSize=(100, 100))
    
    if len(faces) == 0:
        print("Warning: No faces detected. Defaulting to center square crop.")
        crop_size = min(height, width)
        x1 = (width - crop_size) // 2
        y1 = (height - crop_size) // 2
        cropped = img[y1:y1+crop_size, x1:x1+crop_size]
        cv2.imwrite(output_path, cv2.resize(cropped, (1024, 1024), interpolation=cv2.INTER_LANCZOS4))
        return False, [x1, y1, crop_size, crop_size]
        
    # Get largest face
    fx, fy, fw, fh = max(faces, key=lambda f: f[2] * f[3])
    print(f"Detected face at X:{fx}, Y:{fy}, W:{fw}, H:{fh}")
    
    # Calculate crop coordinates centered on face (shifted down for shoulders)
    target_dim = int(fh * 2.8)
    cx = fx + fw // 2
    cy = fy + int(fh * 0.8)
    
    x1 = max(0, cx - target_dim // 2)
    y1 = max(0, cy - target_dim // 2)
    x2 = min(width, cx + target_dim // 2)
    y2 = min(height, cy + target_dim // 2)
    
    cropped = img[y1:y2, x1:x2]
    square_cropped = make_square(cropped, 1024)
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
        # Scale face rect to cropped 1024x1024 coords if needed,
        # but here we assume input_path is already cropped face image (1024x1024)
        # So we can set standard portrait ROI centered in the image
        margin = int(width * 0.1)
        rect = (margin, int(height * 0.1), width - 2 * margin, height - int(height * 0.1))
    else:
        # Default centered portrait box
        margin = int(width * 0.15)
        rect = (margin, int(height * 0.05), width - 2 * margin, height - int(height * 0.05))
        
    # Run GrabCut segmentation
    try:
        cv2.grabCut(img, mask, rect, bgdModel, fgdModel, 5, cv2.GC_INIT_WITH_RECT)
        # 0 = background, 2 = prob background. Let's keep 1 (fgd) and 3 (prob fgd)
        fg_mask = np.where((mask == 2) | (mask == 0), 0, 1).astype('uint8')
    except Exception as e:
        print(f"Warning: GrabCut failed ({e}). Falling back to simple vignette mask.")
        fg_mask = np.ones(img.shape[:2], np.uint8)
        
    # Smooth the GrabCut mask
    fg_mask_blurred = cv2.GaussianBlur(fg_mask * 255, (21, 21), 0) / 255.0
    fg_mask_blurred = np.expand_dims(fg_mask_blurred, axis=-1)
    
    # Create an elliptical vignette mask to guarantee clean edges fading to white
    vignette = np.zeros(img.shape[:2], np.uint8)
    center = (width // 2, int(height * 0.45))
    axes = (int(width * 0.42), int(height * 0.48))
    cv2.ellipse(vignette, center, axes, 0, 0, 360, 255, -1)
    
    # Soften vignette boundary
    vignette_blurred = cv2.GaussianBlur(vignette, (101, 101), 0) / 255.0
    vignette_blurred = np.expand_dims(vignette_blurred, axis=-1)
    
    # Combine GrabCut mask and vignette mask
    combined_mask = fg_mask_blurred * vignette_blurred
    
    # Apply combined mask: blend image with white background
    white_bg = np.ones_like(img) * 255
    output_img = img * combined_mask + white_bg * (1.0 - combined_mask)
    
    cv2.imwrite(output_path, output_img.astype(np.uint8))
    print(f"Background removed and saved to: {output_path}")
    return True
