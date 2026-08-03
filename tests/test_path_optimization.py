import unittest
import numpy as np
from src.robot.path_optimization import (
    calculate_drawing_distance,
    calculate_air_distance,
    optimize_strokes_tsp
)

class TestPathOptimization(unittest.TestCase):
    def test_calculate_drawing_distance(self):
        # A single stroke with segments of length 1
        strokes = [[[0, 0], [1, 0], [1, 1]]]
        self.assertAlmostEqual(calculate_drawing_distance(strokes), 2.0)
        
        # Two strokes
        strokes2 = [[[0, 0], [1, 0]], [[1, 1], [0, 1]]]
        self.assertAlmostEqual(calculate_drawing_distance(strokes2), 2.0)

    def test_calculate_air_distance(self):
        # Transition from [1, 0] to [2, 0]
        strokes = [[[0, 0], [1, 0]], [[2, 0], [3, 0]]]
        self.assertAlmostEqual(calculate_air_distance(strokes), 1.0)
        
        # Single stroke has no air distance
        strokes_single = [[[0, 0], [1, 0]]]
        self.assertEqual(calculate_air_distance(strokes_single), 0.0)

    def test_optimize_strokes_tsp_basic(self):
        # Two strokes, second is closer to the end of the first if reversed
        # Stroke 0: [0, 0] -> [1, 0]
        # Stroke 1: [3, 0] -> [1.1, 0]
        # If we reverse Stroke 1, its start [1.1, 0] is very close to Stroke 0's end [1, 0]
        strokes = [
            [[0.0, 0.0], [1.0, 0.0]],
            [[3.0, 0.0], [1.1, 0.0]]
        ]
        optimized = optimize_strokes_tsp(strokes)
        self.assertEqual(len(optimized), 2)
        # Stroke 0 should remain as is
        self.assertEqual(optimized[0], strokes[0])
        # Stroke 1 should be reversed because [1.1, 0.0] is closer to [1.0, 0.0] than [3.0, 0.0] is
        self.assertEqual(optimized[1], [[1.1, 0.0], [3.0, 0.0]])
        
        # Check transition distances before and after
        # strokes[0][-1] is [1, 0], strokes[1][0] is [3, 0], so distance is 2.0
        # optimized[0][-1] is [1, 0], optimized[1][0] is [1.1, 0], so distance is 0.1
        self.assertAlmostEqual(calculate_air_distance(strokes), 2.0)
        self.assertAlmostEqual(calculate_air_distance(optimized), 0.1)

    def test_optimize_strokes_tsp_empty(self):
        self.assertEqual(optimize_strokes_tsp([]), [])
        self.assertEqual(optimize_strokes_tsp([[], []]), [])

    def test_merge_close_strokes(self):
        from src.robot.path_optimization import merge_close_strokes
        
        # Test case 1: two strokes that are close (distance 0.001 <= 0.002 threshold)
        strokes = [
            [[0.0, 0.0], [1.0, 0.0]],
            [[1.001, 0.0], [2.0, 0.0]]
        ]
        merged, connections = merge_close_strokes(strokes, threshold_m=0.002)
        # Should be merged into 1 stroke
        self.assertEqual(len(merged), 1)
        self.assertEqual(merged[0], [[0.0, 0.0], [1.0, 0.0], [1.001, 0.0], [2.0, 0.0]])
        self.assertEqual(len(connections), 1)
        
        # Test case 2: two strokes that are far (distance 0.03 * 0.19 = 5.7mm > 2mm threshold)
        strokes2 = [
            [[0.0, 0.0], [1.0, 0.0]],
            [[1.03, 0.0], [2.0, 0.0]]
        ]
        merged2, connections2 = merge_close_strokes(strokes2, threshold_m=0.002)
        # Should NOT be merged
        self.assertEqual(len(merged2), 2)
        self.assertEqual(len(connections2), 0)

if __name__ == '__main__':
    unittest.main()
