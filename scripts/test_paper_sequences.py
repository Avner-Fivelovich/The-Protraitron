import sys
import argparse
import yaml
import time
from src.common.logger import get_logger
from src.robot.controller import RobotController
from src.robot.paper_handler import PaperHandler

logger = get_logger("TestSequences")

def main():
    parser = argparse.ArgumentParser(description="Test Paper Manipulation Sequences")
    parser.add_argument("--sequence", type=str, required=True, 
                        help="Name of the sequence to test (e.g. 'Handover Drawing')")
    parser.add_argument("--ip", type=str, default="192.168.57.100", help="Robot IP")
    args = parser.parse_args()

    controller = RobotController(args.ip)
    if not controller.connect():
        logger.error("Failed to connect to robot.")
        sys.exit(1)
        
    paper_handler = PaperHandler(controller.rtde_c, controller.rtde_r)
    sequences = paper_handler.get_partial_sequences()
    
    if args.sequence == "all":
        logger.info("Executing full paper swap...")
        success = paper_handler.execute_paper_swap()
    elif args.sequence in sequences:
        logger.info(f"Executing partial sequence: {args.sequence}")
        paper_handler.connect_gripper()
        success = paper_handler.execute_sequence(sequences[args.sequence])
    else:
        logger.error(f"Unknown sequence: {args.sequence}")
        logger.info(f"Available sequences: {list(sequences.keys())} or 'all'")
        sys.exit(1)
        
    if success:
        logger.success("Sequence completed successfully.")
    else:
        logger.error("Sequence failed.")
        
    paper_handler.disconnect()
    controller.disconnect()

if __name__ == "__main__":
    main()
