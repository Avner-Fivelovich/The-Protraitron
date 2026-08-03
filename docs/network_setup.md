# Network Setup — Connecting to the Robot (192.168.57.101)

## Overview

The robot controller is accessible at IP `192.168.57.101` via a **direct Ethernet connection**.
To communicate with it, your Mac must have a static IP in the same `192.168.57.x` subnet on the Ethernet interface.

---

## Problem Symptom

```
$ ping 192.168.57.101
PING 192.168.57.101 (192.168.57.101): 56 data bytes
Request timeout for icmp_seq 0
Request timeout for icmp_seq 1
100.0% packet loss
```

This happens when your Mac's Ethernet interface does not have an IP in the `192.168.57.x` subnet (e.g. it received a `169.254.x.x` self-assigned address or no IP at all).

---

## Solution — Set a Static IP on macOS (GUI)

1. Open **System Settings → Network**
2. Select your **Ethernet** interface (the one with the cable connected to the robot)
3. Click **Details → TCP/IP**
4. Set **Configure IPv4** → `Manually`
5. Enter the following:

   | Field        | Value           |
   |-------------|-----------------|
   | IP Address  | `192.168.57.100` |
   | Subnet Mask | `255.255.255.0`  |
   | Router      | *(leave blank)*  |

6. Click **OK** and then **Apply**

### Verify

```bash
ping 192.168.57.101
```

You should see responses with no packet loss.

---

## Notes

- Only one computer can be connected to the robot at a time via Ethernet.
- The robot's IP (`192.168.57.101`) is fixed — do **not** use it as your Mac's IP.
- You can use any address in `192.168.57.2`–`192.168.57.254` for your Mac (`.100` is recommended).
- This setting persists across reboots — you only need to set it once per machine.
