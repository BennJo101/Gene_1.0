#!/bin/bash
# Gene head: system setup for the Pi 5 that goes inside the head.
# From Head/cleaned/BOM.md + notes_top.md and Brain (Jetson)/README.md.
# Run once:  sudo bash ~/gene/setup_head.sh   then reboot.
#
# WARNING: this removes the Waveshare 3.5" DPI screen overlay. A DPI screen uses almost
# every GPIO pin, including the I2S pins the speaker amps need, so it can't stay in the head.
# After the reboot that screen goes blank: use HDMI or SSH.
set -e
[ "$(id -u)" = 0 ] || { echo "run with sudo"; exit 1; }
CFG=/boot/firmware/config.txt
cp "$CFG" "$CFG.before-gene-$(date +%Y%m%d-%H%M%S)"

# 1. Waveshare DPI touchscreen off (frees GPIO 18/19/21 for I2S)
sed -i 's/^dtoverlay=waveshare-35dpi-5b/#&  # removed for Gene head (GPIO needed for I2S amps)/' "$CFG"

# 2. Gene head settings, appended once
if ! grep -q '^# --- Gene head ---' "$CFG"; then
cat >> "$CFG" <<'EOF'

# --- Gene head ---
[all]
# Pi is fed through its GPIO 5 V pins from the buck, not USB-C: lift the 600 mA USB limit (BOM sec. 4)
usb_max_current_enable=1
# Two MAX98357A I2S amps as a stereo pair (BCLK GPIO18, LRCLK GPIO19, DIN GPIO21).
# Wire one amp's SD pin for left and the other for right.
dtoverlay=hifiberry-dac
# Both MIPI ports are the eye cameras (CAM/DISP 0 = left, 1 = right); camera_auto_detect=1 above finds them.
# The eye displays are on micro-HDMI 0 (right eye) and 1 (left eye).
EOF
fi

# 3. On-screen keyboard always off (no touchscreen in the head)
raspi-config nonint do_squeekboard S3

# 4. SSH on: the Pi is sealed inside the skull
raspi-config nonint do_ssh 0

# 5. DYNAMIXEL U2D2 (FTDI): stable name /dev/dynamixel and 1 ms latency for the jaw servos
cat > /etc/udev/rules.d/99-gene-dynamixel.rules <<'EOF'
SUBSYSTEM=="tty", ATTRS{idVendor}=="0403", ATTRS{idProduct}=="6014", SYMLINK+="dynamixel", MODE="0666"
ACTION=="add", SUBSYSTEM=="usb-serial", DRIVERS=="ftdi_sio", ATTR{latency_timer}="1"
EOF
udevadm control --reload-rules

echo
echo "Done. Changes to $CFG:"
diff "$(ls -t $CFG.before-gene-* | head -1)" "$CFG" || true
echo
echo "Reboot to apply:  sudo reboot"
