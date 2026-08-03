import unittest
import numpy as np
import os
import tempfile
from src.robot.svg_drawing import (
    tokenize_path,
    interpolate_bezier_quadratic,
    interpolate_bezier_cubic,
    parse_svg_path,
    normalize_svg_strokes,
    load_svg_file
)

class TestSVGDrawing(unittest.TestCase):
    def test_tokenize_path(self):
        # Basic parsing
        d = "M 10,20 L 30 40 Z"
        tokens = tokenize_path(d)
        self.assertEqual(tokens, ["M", "10", "20", "L", "30", "40", "Z"])

        # Omission of spaces and negative numbers
        d_no_spaces = "M10-20.5L-30.5e-2 40"
        tokens = tokenize_path(d_no_spaces)
        self.assertEqual(tokens, ["M", "10", "-20.5", "L", "-30.5e-2", "40"])

    def test_interpolate_bezier_quadratic(self):
        p0 = np.array([0.0, 0.0])
        p1 = np.array([0.5, 1.0])
        p2 = np.array([1.0, 0.0])
        steps = 10
        points = interpolate_bezier_quadratic(p0, p1, p2, steps)
        
        self.assertEqual(len(points), steps)
        # Last point should be close to p2
        np.testing.assert_allclose(points[-1], p2, atol=1e-7)

    def test_interpolate_bezier_cubic(self):
        p0 = np.array([0.0, 0.0])
        p1 = np.array([0.25, 1.0])
        p2 = np.array([0.75, -1.0])
        p3 = np.array([1.0, 0.0])
        steps = 15
        points = interpolate_bezier_cubic(p0, p1, p2, p3, steps)
        
        self.assertEqual(len(points), steps)
        # Last point should be close to p3
        np.testing.assert_allclose(points[-1], p3, atol=1e-7)

    def test_parse_svg_path_basic(self):
        # Simple line
        d = "M 0 0 L 10 10 Z"
        strokes = parse_svg_path(d)
        self.assertEqual(len(strokes), 1)
        # M starts at 0,0, L goes to 10,10, Z returns to 0,0
        self.assertEqual(strokes[0], [[0.0, 0.0], [10.0, 10.0], [0.0, 0.0]])

    def test_parse_svg_path_commands(self):
        # Test absolute and relative commands H, V, C, S, Q, T
        d = "M 0 0 H 10 V 10 h 5 v 5 Z"
        strokes = parse_svg_path(d)
        self.assertEqual(len(strokes), 1)
        # M 0 0 -> (0,0)
        # H 10 -> (10,0)
        # V 10 -> (10,10)
        # h 5 -> (15,10)
        # v 5 -> (15,15)
        # Z -> (0,0)
        expected = [[0.0, 0.0], [10.0, 0.0], [10.0, 10.0], [15.0, 10.0], [15.0, 15.0], [0.0, 0.0]]
        np.testing.assert_allclose(strokes[0], expected, atol=1e-7)

    def test_parse_svg_path_curves(self):
        # Test cubic, smooth cubic, quad, smooth quad curves
        d = "M 0 0 C 1 1, 2 1, 3 0 S 5 -1, 6 0 Q 7 1, 8 0 T 10 0"
        strokes = parse_svg_path(d, bezier_steps=2)
        # We expect some points interpolated. We just check it runs and produces strokes.
        self.assertEqual(len(strokes), 1)
        # First point should be the start (0,0)
        self.assertEqual(strokes[0][0], [0.0, 0.0])
        # End point should be close to 10,0
        np.testing.assert_allclose(strokes[0][-1], [10.0, 0.0], atol=1e-7)

    def test_normalize_svg_strokes(self):
        # A simple stroke from x in [10, 20], y in [10, 30]
        strokes = [[[10.0, 10.0], [20.0, 30.0]]]
        canvas_width = 0.19
        canvas_height = 0.27
        padding = 0.01

        normalized = normalize_svg_strokes(strokes, canvas_width, canvas_height, padding)
        self.assertEqual(len(normalized), 1)
        
        # Check that all points fit in normalized [0, 1] bounds
        for stroke in normalized:
            for pt in stroke:
                self.assertTrue(0.0 <= pt[0] <= 1.0, f"x coordinate {pt[0]} out of [0, 1] range")
                self.assertTrue(0.0 <= pt[1] <= 1.0, f"y coordinate {pt[1]} out of [0, 1] range")

        # Let's verify that physical coordinates fit inside target canvas bounds with padding
        # Physical points = normalized * canvas_dimension
        for stroke in normalized:
            for pt in stroke:
                px = pt[0] * canvas_width
                py = pt[1] * canvas_height
                self.assertTrue(padding - 1e-7 <= px <= canvas_width - padding + 1e-7)
                self.assertTrue(padding - 1e-7 <= py <= canvas_height - padding + 1e-7)

    def test_load_svg_file(self):
        # Create a temporary SVG file to test loading
        svg_content = """<?xml version="1.0" encoding="utf-8"?>
        <svg version="1.1" xmlns="http://www.w3.org/2000/svg" width="100" height="100">
            <path d="M 0 0 L 10 10 Z" />
            <path d="M 10 10 L 20 20" />
        </svg>
        """
        with tempfile.NamedTemporaryFile(mode='w', suffix='.svg', delete=False) as f:
            f.write(svg_content)
            temp_path = f.name

        try:
            strokes = load_svg_file(temp_path)
            self.assertEqual(len(strokes), 2)
            self.assertEqual(strokes[0], [[0.0, 0.0], [10.0, 10.0], [0.0, 0.0]])
            self.assertEqual(strokes[1], [[10.0, 10.0], [20.0, 20.0]])
        finally:
            os.remove(temp_path)

if __name__ == '__main__':
    unittest.main()
