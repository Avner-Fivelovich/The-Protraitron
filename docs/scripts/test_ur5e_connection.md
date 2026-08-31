<div style="font-family: 'Inter', sans-serif;">
  <h1 style="font-family: 'Space Grotesk', sans-serif; text-transform: uppercase; border-bottom: 2px solid #4a148c; padding-bottom: 5px; color: #4a148c;">
    Test UR5e Connection Script Documentation
  </h1>
  
  <p>
    The <code>scripts/test_ur5e_connection.py</code> script is a diagnostic utility for the Portraitron 3000 robotic sketching platform. It serves as a standalone test to verify Ethernet socket connectivity, read real-time joint positions, TCP poses, and Force/Torque (F/T) sensor telemetry from a Universal Robots UR5e cobot arm.
  </p>

  <h2 style="font-family: 'Space Grotesk', sans-serif; text-transform: uppercase; border-bottom: 2px solid #26a69a; padding-bottom: 5px; color: #26a69a;">
    Purpose
  </h2>
  
  <p>
    Before running complex hardware drawing loops or AI agent integrations, this script ensures that the host PC can successfully communicate with the UR5e controller via the RTDE (Real-Time Data Exchange) protocol on both the control (Port 30003) and receive (Port 30004) channels. It reads actual hardware telemetry, making it an essential first step when starting up the physical robot or troubleshooting communication issues.
  </p>

  <h2 style="font-family: 'Space Grotesk', sans-serif; text-transform: uppercase; border-bottom: 2px solid #26a69a; padding-bottom: 5px; color: #26a69a;">
    How to Use
  </h2>
  
  <p>
    To execute the diagnostic test, run the following command from the project root:
  </p>
  
  <div style="background-color: #0f0f10; padding: 15px; border-radius: 5px;">
    <pre style="font-family: 'JetBrains Mono', monospace; color: #e0e0e0; margin: 0;"><code>./venv/bin/python scripts/test_ur5e_connection.py</code></pre>
  </div>
  
  <p>
    Ensure your virtual environment is active and that the <code>ur_rtde</code> library is installed (<code>pip install -r requirements.txt</code>).
  </p>

  <h2 style="font-family: 'Space Grotesk', sans-serif; text-transform: uppercase; border-bottom: 2px solid #26a69a; padding-bottom: 5px; color: #26a69a;">
    Configuration & Variables
  </h2>
  
  <p>
    The script dynamically loads the robot IP from <code>config/server.yaml</code> (under <code>hardware.robot_ip</code>), falling back to <code>192.168.57.101</code> if unconfigured.
  </p>

  <h2 style="font-family: 'Space Grotesk', sans-serif; text-transform: uppercase; border-bottom: 2px solid #26a69a; padding-bottom: 5px; color: #26a69a;">
    Inner Workings
  </h2>
  
  <p>
    The script operates in a straightforward, sequential manner:
  </p>
  <ol>
    <li>
      <strong>Initialization</strong>: Attempts to import <code>rtde_control</code> and <code>rtde_receive</code>. If missing, it fails fast and advises the user to install the library.
    </li>
    <li>
      <strong>Connection Setup</strong>:
      <ul>
        <li>Establishes a receive channel connection (Port 30004) via <code>RTDEReceiveInterface</code>.</li>
        <li>Establishes a control channel connection (Port 30003) via <code>RTDEControlInterface</code>.</li>
      </ul>
    </li>
    <li>
      <strong>Safety Status Checks</strong>: Queries the robot to see if it is in an Emergency Stop or Protective Stop state.
    </li>
    <li>
      <strong>Telemetry Acquisition</strong>:
      <ul>
        <li>Reads Joint Angles (converted to degrees).</li>
        <li>Reads actual TCP Pose (X, Y, Z in meters/mm, and Rx, Ry, Rz rotation vectors).</li>
        <li>Reads raw TCP Force/Torque sensor data.</li>
      </ul>
    </li>
    <li>
      <strong>Error Handling & Disconnection</strong>: If a connection error occurs, the script prints a structured 4-step troubleshooting guide (Ping, IP config, cabling, Polyscope settings). Finally, it ensures clean shutdown of all sockets in the <code>finally</code> block.
    </li>
  </ol>
</div>
