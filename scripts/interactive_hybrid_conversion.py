import yaml
import time
import rtde_control
import rtde_receive
import sys
import os

def main():
    print("Connecting to robot...")
    try:
        rtde_c = rtde_control.RTDEControlInterface("192.168.57.100")
        rtde_r = rtde_receive.RTDEReceiveInterface("192.168.57.100")
    except Exception as e:
        print(f"Failed to connect: {e}")
        return

    # Load from hybrid file if it exists so progress isn't lost between runs
    output_path = "config/paper_manipulation_hybrid.yaml"
    source_path = "config/paper_manipulation.yaml"
    
    if os.path.exists(output_path):
        print(f"Resuming progress from {output_path}...")
        with open(output_path, "r") as f:
            config = yaml.safe_load(f)
    else:
        print(f"Starting fresh from {source_path}...")
        with open(source_path, "r") as f:
            config = yaml.safe_load(f)
            
    locations = config.get("locations", {})
    
    while True:
        print("\n" + "="*40)
        print("  INTERACTIVE HYBRID CONVERSION MENU")
        print("="*40)
        
        # Build an indexed list
        loc_names = list(locations.keys())
        for i, name in enumerate(loc_names):
            # Check if it's already a hybrid
            pose_data = locations[name]
            status = "[HYBRID (Pose+Joints)]" if isinstance(pose_data, dict) and "joints" in pose_data else "[Pose Only]"
            print(f"{i+1:2d}. {name:25s} {status}")
            
        print("\n0. Quit")
        
        choice = input(f"\nSelect a location number (0-{len(loc_names)}): ").strip()
        
        if choice == '0':
            break
            
        try:
            idx = int(choice) - 1
            if idx < 0 or idx >= len(loc_names):
                print("Invalid selection.")
                continue
        except ValueError:
            print("Please enter a valid number.")
            continue
            
        name = loc_names[idx]
        current_data = locations[name]
        
        if isinstance(current_data, dict):
            pose = current_data["pose"]
        else:
            pose = current_data
            
        print(f"\n--- Selected: {name} ---")
        print("Target (Pose):", [round(x, 4) for x in pose])
        
        action = input("Press [Enter] to move slowly to this pose, or [c] to cancel: ").strip().lower()
        if action == 'c':
            continue
            
        if isinstance(current_data, dict) and "joints" in current_data:
            print(f"Moving to {name} via moveJ (FASTER, since it is already verified)...")
            success = rtde_c.moveJ(current_data["joints"], 0.8, 0.8)
        else:
            print(f"Moving to {name} via moveJ_IK (SLOWLY for safety)...")
            success = rtde_c.moveJ_IK(pose, 0.1, 0.1)
        
        if success:
            q = rtde_r.getActualQ()
            print(f"Arrived safely! Captured Joints: {[round(x, 4) for x in q]}")
            save_action = input("Save this location with BOTH Pose and Joints? [y/n]: ").strip().lower()
            if save_action == 'y':
                locations[name] = {
                    "pose": pose,
                    "joints": q
                }
                config["locations"] = locations
                
                # Auto-save immediately to prevent data loss
                with open(output_path, "w") as f:
                    yaml.safe_dump(config, f, default_flow_style=False)
                print(f"Saved {name} as Hybrid! Progress automatically saved to disk.")
            else:
                print("Did not save.")
        else:
            print(f"WARNING: Robot failed to reach {name}!")

    print(f"\nExiting! Your progress is safely stored in: {output_path}")

if __name__ == "__main__":
    main()
