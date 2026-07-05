#!/bin/bash
set -e

apt-get update
DEBIAN_FRONTEND=noninteractive apt-get install -y python3 python3-opencv fswebcam v4l-utils usbutils

echo "Board dependencies are ready."
