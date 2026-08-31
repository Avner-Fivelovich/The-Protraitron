# Network Setup — Connecting to the Robot Controller

This guide explains how to establish and troubleshoot a direct Ethernet connection between the host development computer (macOS / Linux / Windows) and the **Universal Robots UR5e** robot controller.

---

## 1. Network Architecture & IP Scheme

The UR5e robot controller and the host workstation communicate over a **direct, point-to-point Ethernet connection** (or via a dedicated lab switch). Because the robot controller does not run a DHCP server by default, the host machine must be assigned a **static IP** on the same `/24` subnet.

### Subnet Specifications

| Parameter | Configuration Value | Description |
| :--- | :--- | :--- |
| **Subnet Mask** | `255.255.255.0` (`/24`) | Required subnet mask |
| **Robot Controller IP** | `192.168.57.101` | Default UR5e IP configured on the PolyScope controller |
| **Host Computer IP** | `192.168.57.100` | Recommended static IP for your Mac / PC |
| **Usable Host IP Range**| `192.168.57.2` – `192.168.57.254` | Any address except `.101` (robot) and `.1` (gateway) |
| **Default Gateway / Router** | *(leave blank)* | Do not set a gateway so internet traffic stays on Wi-Fi |

> [!IMPORTANT]
> The robot IP (`192.168.57.101`) is configured in the central hardware config: [`config/server.yaml`](../config/server.yaml). Never assign `192.168.57.101` to your host computer, as this causes an IP address collision.

---

## 2. macOS Configuration

### Method A: macOS System Settings (GUI)

1. Connect an Ethernet cable directly from your Mac (or USB-C Ethernet adapter) to the UR5e controller.
2. Open **System Settings** → **Network**.
3. Select your **Ethernet** interface (or your USB-C LAN adapter name, e.g. *USB 10/100/1000 LAN* or *Belkin USB-C LAN*).
4. Click **Details...** → **TCP/IP**.
5. Change **Configure IPv4** to `Manually`.
6. Enter the static network details:
   - **IP Address**: `192.168.57.100`
   - **Subnet Mask**: `255.255.255.0`
   - **Router**: *(leave completely blank)*
7. Click **OK**, then click **Apply**.

> [!TIP]
> Leaving the **Router** field blank is critical. It ensures that macOS routes only `192.168.57.0/24` traffic through the Ethernet adapter while routing all general internet traffic through your Wi-Fi connection.

---

### Method B: macOS Terminal (CLI)

For command-line configuration, you can use the native macOS `networksetup` utility:

1. **List available network services to identify your Ethernet interface name**:
   ```bash
   networksetup -listallnetworkservices
   ```
   *(Typical names: `Ethernet`, `USB 10/100/1000 LAN`, `AX88179A`, or `Thunderbolt Ethernet`)*

2. **Assign the static IP address**:
   ```bash
   sudo networksetup -setmanual "Ethernet" 192.168.57.100 255.255.255.0
   ```
   *(Replace `"Ethernet"` with your exact service name from step 1).*

3. **Verify the assigned IP**:
   ```bash
   networksetup -getinfo "Ethernet"
   ```

4. **(Optional) Revert back to DHCP when disconnecting from the robot**:
   ```bash
   sudo networksetup -setdhcp "Ethernet"
   ```

---

## 3. Alternative Workstations (Linux & Windows)

<details>
<summary><strong>Linux (Ubuntu / Debian CLI & NetworkManager)</strong></summary>

Using `nmcli`:
```bash
# Identify your Ethernet interface name
nmcli device status

# Configure static IP
nmcli connection modify "Wired connection 1" \
  ipv4.method manual \
  ipv4.addresses 192.168.57.100/24

# Reactivate the connection
nmcli connection up "Wired connection 1"
```
</details>

<details>
<summary><strong>Windows 10 / 11</strong></summary>

1. Press <kbd>Win</kbd> + <kbd>R</kbd>, type `ncpa.cpl`, and press **Enter**.
2. Right-click your **Ethernet** adapter → **Properties**.
3. Double-click **Internet Protocol Version 4 (TCP/IPv4)**.
4. Select **Use the following IP address**:
   - **IP Address**: `192.168.57.100`
   - **Subnet Mask**: `255.255.255.0`
   - **Default Gateway**: *(blank)*
5. Click **OK** to save.
</details>

---

## 4. Robot Controller & PolyScope Verification

Verify that the robot controller is configured with the matching IP:

1. On the PolyScope Teach Pendant:
   - Go to **Settings** → **System** → **Network**.
   - Ensure the IP address is set to `192.168.57.101` and the subnet mask is `255.255.255.0`.
2. Ensure **Remote Control** mode is enabled:
   - In PolyScope (or PolyScope X), switch the operational mode to **Automatic**.
   - Toggle control mode to **Remote Control** so external RTDE commands are accepted.

---

## 5. Verification & Diagnostics

Follow these verification steps in order to confirm full end-to-end communication:

### Step 1: Low-Level ICMP Ping Test

Test basic Layer-3 network reachability:

```bash
ping -c 4 192.168.57.101
```

**Expected output**:
```text
64 bytes from 192.168.57.101: icmp_seq=0 ttl=64 time=0.452 ms
64 bytes from 192.168.57.101: icmp_seq=1 ttl=64 time=0.389 ms
--- 192.168.57.101 ping statistics ---
4 packets transmitted, 4 packets received, 0.0% packet loss
```

### Step 2: UR RTDE Socket & Telemetry Diagnostic

Run the project's built-in RTDE diagnostic tool:

```bash
./venv/bin/python scripts/test_ur5e_connection.py
```

This verifies:
- Connection to **Port 30004** (`RTDEReceiveInterface` telemetry).
- Connection to **Port 30003** (`RTDEControlInterface` motion control).
- Real-time joint angles, TCP pose (XYZ / RxRyRz), and Force/Torque sensor data.

### Step 3: PolyScope X REST API Verification (PolyScope X Only)

If operating on PolyScope X, open the interactive REST API documentation in your browser:
```text
http://192.168.57.101/universal-robots/robot-api/docs
```
Or test via `curl`:
```bash
curl -I http://192.168.57.101/universal-robots/robot-api/docs
```

### Step 4: Robotiq Gripper Port Check (Port 63352)

Test connectivity to the Robotiq Gripper socket interface:

```bash
nc -zv 192.168.57.101 63352
```

---

## 6. Key Network Ports Reference

The Portraitron system communicates over the following network ports:

| Port | Protocol | Service | Description |
| :--- | :--- | :--- | :--- |
| **`30003`** | TCP | UR RTDE Control | Motion execution, trajectory streaming, and URScript commands |
| **`30004`** | TCP | UR RTDE Telemetry | Real-time state feedback (joint angles, TCP pose, F/T sensor) |
| **`63352`** | TCP | Robotiq Gripper | Custom socket control for 2F-85 / 2F-140 gripper (via ToolComm Forwarder) |
| **`80` / `443`** | HTTP/S | PolyScope X API | Modern PolyScope X RESTful API and web interface |
| **`29999`** | TCP | Dashboard Server | Legacy PolyScope 5 dashboard control (play, pause, power on) |

---

## 7. Troubleshooting Guide

### Issue 1: `Request timeout` / `100.0% packet loss` on ping

```text
$ ping 192.168.57.101
PING 192.168.57.101 (192.168.57.101): 56 data bytes
Request timeout for icmp_seq 0
100.0% packet loss
```

* **Cause A (Self-Assigned IP)**: macOS defaulted to a `169.254.x.x` link-local IP because DHCP failed. Ensure you selected **Manually** in TCP/IP settings.
* **Cause B (Wrong Interface)**: Check `ifconfig` or Network Settings. Ensure the static IP was applied to the active physical adapter, not an unused virtual or Wi-Fi adapter.
* **Cause C (Physical Link Down)**: Ensure the Ethernet cable is securely seated in both the Mac adapter and the UR5e controller Ethernet port. Check that link LEDs are illuminated on the RJ45 port.

---

### Issue 2: `ping` succeeds, but `test_ur5e_connection.py` fails

```text
Failed to establish RTDE communication channel.
```

* **Remote Control Disabled**: Check the Teach Pendant header. The robot must be in **Remote** control mode to accept RTDE connections.
* **Safety Stop Engaged**: Release any active Emergency Stops (E-stop button) or Protective Stops via the Teach Pendant.
* **Port Conflict**: Only one primary RTDE control client can connect at a time. Ensure no background scripts or secondary workstations are running active control loops.
* **macOS Firewall**: Check **System Settings → Network → Firewall**. Temporarily disable the firewall or add Python to allowed incoming connections.

---

### Issue 3: Gripper Connection Refused (`nc: connect to 192.168.57.101 port 63352 failed`)

* On PolyScope X, the standard Robotiq URCap does not expose port `63352` automatically.
* You must install and configure the **ToolComm Forwarder URCapX** to bridge the RS-485 tool communication to network port `63352`.
* Refer to the [PolyScope X Connection Guide](PolyScopeX_Connection_Guide.md) for installation and configuration instructions.

---

## 8. Related Resources

* [Central Server Configuration](../config/server.yaml) — Robot IP and port definitions.
* [Workspace Calibration Documentation](scripts/calibrate_workspace.md) — Documentation for compliant drawing surface calibration.
