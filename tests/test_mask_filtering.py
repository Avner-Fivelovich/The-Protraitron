import os
import unittest
import numpy as np
import tempfile
from PIL import Image
from src.robot.mask_filtering import (
    load_binary_mask,
    filter_strokes_with_mask
)

class TestMaskFiltering(unittest.TestCase):
    def setUp(self):
        # Create a temporary binary mask image (100 x 100 pixels)
        # Left half (x < 50) is white (foreground/1)
        # Right half (x >= 50) is black (background/0)
        self.temp_mask_file = tempfile.NamedTemporaryFile(delete=False, suffix=".png")
        self.temp_mask_path = self.temp_mask_file.name
        self.temp_mask_file.close()
        
        mask_data = np.zeros((100, 100), dtype=np.uint8)
        mask_data[:, :50] = 255
        
        img = Image.fromarray(mask_data)
        img.save(self.temp_mask_path)

    def tearDown(self):
        if os.path.exists(self.temp_mask_path):
            os.remove(self.temp_mask_path)

    def test_load_binary_mask(self):
        binary_mask = load_binary_mask(self.temp_mask_path)
        self.assertEqual(binary_mask.shape, (100, 100))
        self.assertEqual(binary_mask[0, 10], 1)
        self.assertEqual(binary_mask[0, 60], 0)

    def test_filter_strokes_with_mask(self):
        binary_mask = load_binary_mask(self.temp_mask_path)
        
        # Stroke 1: entirely on the left half (foreground)
        stroke_in = [[0.1, 0.1], [0.2, 0.2], [0.3, 0.3]]
        
        # Stroke 2: entirely on the right half (background)
        stroke_out = [[0.7, 0.7], [0.8, 0.8], [0.9, 0.9]]
        
        # Stroke 3: crosses the boundary (2 points in foreground, 2 in background)
        stroke_cross = [[0.4, 0.4], [0.45, 0.45], [0.55, 0.55], [0.6, 0.6]]
        
        strokes = [stroke_in, stroke_out, stroke_cross]
        
        # Test Case 1: keep_ratio = 0.7
        # - stroke_in: 3/3 inside (1.0 >= 0.7) -> kept
        # - stroke_out: 0/3 inside (0.0 < 0.7) -> deleted
        # - stroke_cross: 2/4 inside (0.5 < 0.7) -> deleted
        kept, deleted = filter_strokes_with_mask(strokes, binary_mask, keep_ratio=0.7)
        self.assertEqual(len(kept), 1)
        self.assertEqual(kept[0], stroke_in)
        self.assertEqual(len(deleted), 2)
        self.assertIn(stroke_out, deleted)
        self.assertIn(stroke_cross, deleted)
        
        # Test Case 2: keep_ratio = 0.5
        # - stroke_cross: 2/4 inside (0.5 >= 0.5) -> kept
        kept2, deleted2 = filter_strokes_with_mask(strokes, binary_mask, keep_ratio=0.5)
        self.assertEqual(len(kept2), 2)
        self.assertIn(stroke_in, kept2)
        self.assertIn(stroke_cross, kept2)
        self.assertEqual(len(deleted2), 1)
        self.assertEqual(deleted2[0], stroke_out)

if __name__ == '__main__':
    unittest.main()
