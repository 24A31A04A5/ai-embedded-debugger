#!/usr/bin/env sh
# Reproduces the real failure stage for stm32-uart-hal-not-enabled (syntax check only, no link).
# Needs: STM32CubeF4 HAL driver v1.8.6, cmsis-device-f4, CMSIS_5 Core headers, and clang
# (pip install ziglang; python -m ziglang cc ...) or arm-none-eabi-gcc.
set -e
H=${HAL_ROOT:-/tmp/hal}
sed -e 's|^#define HAL_UART_MODULE_ENABLED|/* #define HAL_UART_MODULE_ENABLED */|' \
  "$H/stm32f4xx-hal-driver/Inc/stm32f4xx_hal_conf_template.h" > stm32f4xx_hal_conf.h
python3 -m ziglang cc -target thumb-freestanding-eabihf -mcpu=cortex_m4 -std=gnu11 -fsyntax-only \
  -DSTM32F401xE -DUSE_HAL_DRIVER -I. -I"$H/stm32f4xx-hal-driver/Inc" \
  -I"$H/cmsis-device-f4/Include" -I"$H/CMSIS_5/CMSIS/Core/Include" main.c
