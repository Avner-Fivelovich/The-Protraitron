import rtde_control
import rtde_receive

HOST = "192.168.57.100"
rtde_r = rtde_receive.RTDEReceiveInterface(HOST)
print("receive connected")
flags = rtde_control.RTDEControlInterface.FLAG_DISABLE_REMOTE_CONTROL_CHECK | rtde_control.RTDEControlInterface.FLAG_USE_EXT_UR_CAP
next = rtde_r.getActualQ()
rtde_c = rtde_control.RTDEControlInterface(HOST, flags=flags, ur_cap_port=50002)
print("control connected")

