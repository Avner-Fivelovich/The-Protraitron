import unittest
import os
from src.robot.swiftsketch_integration import run_swiftsketch_inference
from src.common.config_utils import load_config_from_yaml
from src.robot.svg_drawing import load_svg_file

class TestSwiftSketchIntegration(unittest.TestCase):
    def setUp(self):
        self.project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
        self.config_path = os.path.join(self.project_root, "config", "marker.yaml")
        self.config = load_config_from_yaml(self.config_path)
        
        # We can use one of the pre-shipped images in swiftsketch examples
        swiftsketch_cfg = self.config.get("swiftsketch", {})
        repo_rel_path = swiftsketch_cfg.get("repo_path", "SwiftSketch-Protraitron")
        self.examples_dir = os.path.abspath(
            os.path.join(self.project_root, repo_rel_path, "SwiftSketch", "examples")
        )
        self.test_image_path = os.path.join(self.examples_dir, "robot.png")
        self.test_output_svg = os.path.join(self.project_root, "plots", "test_robot_sketch.svg")

    def test_swiftsketch_inference_and_svg_parsing(self):
        # 1. Skip if repository, test image, or model is not set up
        if not os.path.exists(self.test_image_path):
            self.skipTest(f"Test image not found at {self.test_image_path}")

        swiftsketch_cfg = self.config.get("swiftsketch", {})
        repo_rel_path = swiftsketch_cfg.get("repo_path", "SwiftSketch-Protraitron")
        model_rel_path = swiftsketch_cfg.get("model_path", "SwiftSketch/save/sketch-diffusion/model000450000.pt")
        swiftsketch_dir = os.path.abspath(os.path.join(self.project_root, repo_rel_path))
        model_path = os.path.abspath(os.path.join(swiftsketch_dir, model_rel_path))
        if not os.path.exists(model_path):
            self.skipTest(f"SwiftSketch model checkpoint not found at {model_path}")

        # 2. Run inference (uses MPS under the hood on macOS!)
        logger_name = "SwiftSketchIntegration"
        print(f"\nRunning SwiftSketch inference on {self.test_image_path}...")
        success = run_swiftsketch_inference(self.test_image_path, self.test_output_svg, self.config)
        self.assertTrue(success, "SwiftSketch generation failed.")
        self.assertTrue(os.path.exists(self.test_output_svg), "Output SVG file was not created.")

        # 3. Verify that the generated SVG is valid and can be loaded by our parser
        strokes = load_svg_file(self.test_output_svg)
        self.assertTrue(len(strokes) > 0, "No strokes loaded from generated SVG.")
        
        # Verify that strokes have coordinates
        for stroke in strokes:
            self.assertTrue(len(stroke) > 0, "Stroke is empty.")
            for point in stroke:
                self.assertEqual(len(point), 2, "Coordinate point must have x and y.")

        # Clean up output
        if os.path.exists(self.test_output_svg):
            os.remove(self.test_output_svg)

if __name__ == '__main__':
    unittest.main()
