"""Source of truth for the evaluation cases.

Run `python tests/evaluation/build_cases.py` to regenerate `cases/*.json`.
Each case is one realistic embedded bug with the evidence a developer would
paste into the debugger, short datasheet/reference excerpts that stand in for
RAG retrieval, and the expected diagnosis used for scoring.

Scoring keywords are lists of groups. A response passes a check when EVERY group
has at least one regex that matches (case-insensitive).

Reference excerpts: `reference_sources.json` holds verbatim excerpts checked
against the official documents (document, revision, page, section, url).
`apply_verified_sources()` swaps them into DEV cases only. Holdout cases keep
their original excerpts until the user approves the holdout corrections
(see HOLDOUT_PROPOSALS.md). Every change to a case is logged in CORRECTIONS.md;
the pre-correction case files are kept in `cases_original/`.

Insufficient-evidence cases (`expected.abstain = true`) have no single right
root cause: the correct answer says the evidence is not enough and asks for
the specific missing information (`needed_info_keywords`).
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

CASES_DIR = Path(__file__).parent / "cases"

ESP32_DS = "ESP32 Series Datasheet (Espressif)"
ESP32_TRM = "ESP32 Technical Reference Manual (Espressif)"
ESP_IDF = "ESP-IDF Programming Guide (Espressif)"
STM32_RM = "STM32F4 Reference Manual RM0090 (ST)"
STM32F103_DS = "STM32F103x8/xB Datasheet (ST)"
STM32_HAL = "STM32F4 HAL and LL Drivers User Manual UM1725 (ST)"
CM4_GUIDE = "Cortex-M4 Devices Generic User Guide (Arm)"
FREERTOS = "FreeRTOS Kernel Documentation (freertos.org)"
MPU6050_DS = "MPU-6050 Product Specification (InvenSense)"
ADXL345_DS = "ADXL345 Datasheet (Analog Devices)"
I2C_SPEC = "I2C-bus Specification UM10204 (NXP)"
ATMEGA_DS = "ATmega328P Datasheet (Microchip)"
ARDUINO_REF = "Arduino Language Reference (arduino.cc)"
GCC_DOCS = "GNU C / ld Documentation"


def ref(title: str, section: str, snippet: str, content_type: str = "text") -> dict[str, Any]:
    return {
        "title": title,
        "section": section,
        "snippet": snippet,
        "content_type": content_type,
        "page_number": None,
    }


CASES: list[dict[str, Any]] = [
    # ───────────────────────── GPIO ─────────────────────────
    {
        "id": "esp32-gpio34-output",
        "title": "LED on GPIO34 never turns on",
        "category": "gpio",
        "target": "ESP32 / ESP-IDF v4.4",
        "difficulty": "medium",
        "split": "dev",
        "firmware_code": """#include "driver/gpio.h"
#include "freertos/FreeRTOS.h"
#include "freertos/task.h"

#define LED_PIN GPIO_NUM_34

void app_main(void) {
    gpio_reset_pin(LED_PIN);
    gpio_set_direction(LED_PIN, GPIO_MODE_OUTPUT);
    while (1) {
        gpio_set_level(LED_PIN, 1);
        vTaskDelay(pdMS_TO_TICKS(500));
        gpio_set_level(LED_PIN, 0);
        vTaskDelay(pdMS_TO_TICKS(500));
    }
}""",
        "compiler_output": "",
        "serial_logs": """I (312) cpu_start: Starting scheduler on PRO CPU.
I (0) cpu_start: Starting scheduler on APP CPU.
E (322) gpio: gpio_set_direction(277): io_num=34 can only be input""",
        "user_question": "Code builds and flashes fine but the LED on GPIO34 never lights. Wiring checked.",
        "reference_context": [
            ref(
                ESP32_DS,
                "Pin Description / GPIO",
                "GPIO34, GPIO35, GPIO36 (SENSOR_VP) and GPIO39 (SENSOR_VN) are input-only pins. They have no output drivers and no internal pull-up or pull-down resistors.",
                "pin_configuration",
            ),
        ],
        "expected": {
            "root_cause": "GPIO34 is an input-only pin on the ESP32 and has no output driver, so it can never drive the LED.",
            "root_cause_keywords": [
                [r"gpio\s?_?(num_)?34", r"\b34\b"],
                [
                    r"input[- ]only",
                    r"only (be used as )?input",
                    r"no output driver",
                    r"cannot (be used as|drive|act as)( an)? output",
                ],
            ],
            "fix": "Move the LED to an output-capable GPIO such as GPIO2, GPIO4 or GPIO25 and update LED_PIN.",
            "fix_keywords": [
                [
                    r"gpio\s?_?(num_)?(2|4|5|1[2-9]|2[1-7]|3[23])\b",
                    r"output[- ]capable",
                    r"different (gpio|pin)",
                    r"another (gpio|pin)",
                ]
            ],
            "expected_citation": [ESP32_DS],
            "line": 5,
        },
    },
    {
        "id": "esp32-flash-pins",
        "title": "Reset loop after using GPIO7 for a relay",
        "category": "gpio",
        "target": "ESP32-WROOM-32 / ESP-IDF",
        "difficulty": "hard",
        "split": "holdout",
        "firmware_code": """#include "driver/gpio.h"
#define RELAY_PIN GPIO_NUM_7

void app_main(void) {
    gpio_config_t io = {
        .pin_bit_mask = (1ULL << RELAY_PIN),
        .mode = GPIO_MODE_OUTPUT,
    };
    gpio_config(&io);
    gpio_set_level(RELAY_PIN, 1);
}""",
        "compiler_output": "",
        "serial_logs": """I (298) cpu_start: Starting scheduler on PRO CPU.
I (305) gpio: GPIO[7]| InputEn: 0| OutputEn: 1| OpenDrain: 0| Pullup: 0| Pulldown: 0| Intr:0
Guru Meditation Error: Core  0 panic'ed (IllegalInstruction). Exception was unhandled.
Memory dump at 0x400d1a3c: ffffffff ffffffff ffffffff
Rebooting...
ets Jun  8 2016 00:22:57
rst:0xc (SW_CPU_RESET),boot:0x13 (SPI_FAST_FLASH_BOOT)
I (305) gpio: GPIO[7]| InputEn: 0| OutputEn: 1| OpenDrain: 0| Pullup: 0| Pulldown: 0| Intr:0
Guru Meditation Error: Core  0 panic'ed (IllegalInstruction). Exception was unhandled.
Rebooting...""",
        "user_question": "Board keeps rebooting right after I configure the relay pin.",
        "reference_context": [
            ref(
                ESP32_DS,
                "Pin Description / Strapping and Flash Pins",
                "On modules with integrated SPI flash (for example ESP32-WROOM-32), GPIO6 to GPIO11 are connected to the SPI flash and are not recommended for other uses.",
                "pin_configuration",
            ),
        ],
        "expected": {
            "root_cause": "GPIO7 is one of GPIO6-11, which are wired to the module's SPI flash; reconfiguring it breaks flash access so the CPU fetches garbage (0xffffffff) and panics.",
            "root_cause_keywords": [
                [r"gpio\s?_?(num_)?7", r"gpio ?6\s*(-|to|–)\s*(gpio ?)?11"],
                [r"flash"],
            ],
            "fix": "Use a free GPIO (e.g. GPIO4, GPIO16-33) for the relay and never touch GPIO6-11.",
            "fix_keywords": [
                [
                    r"different (gpio|pin)",
                    r"another (gpio|pin)",
                    r"gpio\s?_?(num_)?(4|5|1[2-9]|2[1-7]|3[23])\b",
                    r"avoid gpio ?6",
                    r"free (gpio|pin)",
                ]
            ],
            "expected_citation": [ESP32_DS],
            "line": 2,
        },
    },
    {
        "id": "stm32-gpio-clock",
        "title": "PA5 LED does not blink on Nucleo-F401",
        "category": "gpio",
        "target": "STM32F401 / HAL",
        "difficulty": "easy",
        "split": "dev",
        "firmware_code": """#include "stm32f4xx_hal.h"

int main(void) {
    HAL_Init();
    GPIO_InitTypeDef gpio = {0};
    gpio.Pin = GPIO_PIN_5;
    gpio.Mode = GPIO_MODE_OUTPUT_PP;
    gpio.Pull = GPIO_NOPULL;
    gpio.Speed = GPIO_SPEED_FREQ_LOW;
    HAL_GPIO_Init(GPIOA, &gpio);

    while (1) {
        HAL_GPIO_TogglePin(GPIOA, GPIO_PIN_5);
        HAL_Delay(500);
    }
}""",
        "compiler_output": "",
        "serial_logs": "",
        "user_question": "Builds and flashes fine, debugger shows the loop running, but the LED on PA5 stays off.",
        "reference_context": [
            ref(
                STM32_RM,
                "RCC AHB1 peripheral clock enable register (RCC_AHB1ENR)",
                "GPIOAEN: IO port A clock enable. 0: IO port A clock disabled, 1: IO port A clock enabled. A peripheral's registers cannot be written while its clock is disabled.",
                "register_description",
            ),
        ],
        "expected": {
            "root_cause": "The GPIOA peripheral clock is never enabled in RCC, so HAL_GPIO_Init's register writes are ignored.",
            "root_cause_keywords": [[r"clock"], [r"gpioa", r"rcc", r"ahb1"]],
            "fix": "Call __HAL_RCC_GPIOA_CLK_ENABLE() before HAL_GPIO_Init.",
            "fix_keywords": [
                [r"__hal_rcc_gpioa_clk_enable", r"gpioaen", r"enable the (gpioa )?clock"]
            ],
            "expected_citation": [STM32_RM],
            "line": 10,
        },
    },
    {
        "id": "esp32-gpio-sel-macro",
        "title": "GPIO_SEL_2 undeclared after IDF upgrade",
        "category": "compiler",
        "target": "ESP32-S3 / ESP-IDF v5.0 (code written for v4.4)",
        "difficulty": "easy",
        "split": "dev",
        "firmware_code": """#include "driver/gpio.h"

void app_main(void) {
    gpio_config_t io_conf = {
        .intr_type = GPIO_INTR_DISABLE,
        .mode = GPIO_MODE_OUTPUT,
        .pin_bit_mask = GPIO_SEL_2,
        .pull_down_en = 0,
        .pull_up_en = 0,
    };
    gpio_config(&io_conf);
}""",
        "compiler_output": """/project/main/main.c: In function 'app_main':
/project/main/main.c:7:25: error: 'GPIO_SEL_2' undeclared (first use in this function)
    7 |         .pin_bit_mask = GPIO_SEL_2,
      |                         ^~~~~~~~~~
/project/main/main.c:7:25: note: each undeclared identifier is reported only once for each function it appears in
ninja: build stopped: subcommand failed.""",
        "serial_logs": "",
        "user_question": None,
        "reference_context": [
            ref(
                ESP_IDF,
                "GPIO API reference / gpio_config_t (hal/gpio_types.h, v5.0)",
                "uint64_t pin_bit_mask; GPIO pin: set with bit mask, each bit maps to a GPIO",
                "text",
            ),
        ],
        "expected": {
            "root_cause": "The GPIO_SEL_x macros existed in ESP-IDF v4.4 (hal/gpio_types.h) but are not in v5.0, so GPIO_SEL_2 is an undeclared identifier.",
            "root_cause_keywords": [
                [r"gpio_sel_2"],
                [r"undeclared", r"not (defined|declared|available)", r"removed", r"deprecated"],
            ],
            "fix": "Use a 64-bit bit mask: .pin_bit_mask = (1ULL << GPIO_NUM_2) (or BIT64(GPIO_NUM_2)).",
            "fix_keywords": [[r"1ull\s*<<\s*(gpio_num_)?2", r"bit64\(\s*(gpio_num_)?2\s*\)"]],
            "expected_citation": [ESP_IDF],
            "line": 7,
        },
    },
    # ───────────────────────── I2C ─────────────────────────
    {
        "id": "esp32-mpu6050-address",
        "title": "MPU6050 NACK with AD0 tied high",
        "category": "i2c",
        "target": "ESP32 / ESP-IDF",
        "difficulty": "medium",
        "split": "dev",
        "firmware_code": """#define MPU_ADDR 0x68   // AD0 pin wired to 3V3 on our board
#define WHO_AM_I 0x75

esp_err_t mpu_read_whoami(uint8_t *out) {
    uint8_t reg = WHO_AM_I;
    return i2c_master_write_read_device(I2C_NUM_0, MPU_ADDR, &reg, 1, out, 1,
                                        pdMS_TO_TICKS(100));
}""",
        "compiler_output": "",
        "serial_logs": """I (330) app: I2C init ok, SDA=21 SCL=22, 400kHz
E (342) app: WHO_AM_I read failed: ESP_FAIL
E (1342) app: WHO_AM_I read failed: ESP_FAIL
E (2342) app: WHO_AM_I read failed: ESP_FAIL""",
        "user_question": "Logic analyzer shows the address byte gets NACKed.",
        "reference_context": [
            ref(
                MPU6050_DS,
                "I2C Interface",
                "The slave address of the MPU-60X0 is b110100X which is 7 bits long. The LSB bit of the 7 bit address is determined by the logic level on pin AD0. This allows two MPU-60X0s to be connected to the same I2C bus: 0x68 when AD0 is low, 0x69 when AD0 is high.",
                "table_or_specification",
            ),
        ],
        "expected": {
            "root_cause": "With AD0 tied high the MPU6050 answers at 0x69, but the code addresses 0x68, so the address is NACKed.",
            "root_cause_keywords": [[r"0x69"], [r"ad0"]],
            "fix": "Change MPU_ADDR to 0x69 (or tie AD0 low).",
            "fix_keywords": [[r"0x69", r"ad0 (low|to gnd|to ground)"]],
            "expected_citation": [MPU6050_DS],
            "line": 1,
        },
    },
    {
        "id": "esp32-i2c-no-pullups",
        "title": "I2C timeouts with internal pull-ups disabled",
        "category": "i2c",
        "target": "ESP32 / ESP-IDF",
        "difficulty": "medium",
        "split": "holdout",
        "firmware_code": """i2c_config_t conf = {
    .mode = I2C_MODE_MASTER,
    .sda_io_num = GPIO_NUM_21,
    .scl_io_num = GPIO_NUM_22,
    .sda_pullup_en = GPIO_PULLUP_DISABLE,
    .scl_pullup_en = GPIO_PULLUP_DISABLE,
    .master.clk_speed = 100000,
};
i2c_param_config(I2C_NUM_0, &conf);
i2c_driver_install(I2C_NUM_0, conf.mode, 0, 0, 0);""",
        "compiler_output": "",
        "serial_logs": """E (1210) bme280: read chip id failed: ESP_ERR_TIMEOUT
E (2210) bme280: read chip id failed: ESP_ERR_TIMEOUT
E (3210) bme280: read chip id failed: ESP_ERR_TIMEOUT""",
        "user_question": "Bare BME280 chip on a breadboard, no breakout board. SDA/SCL are wired directly.",
        "reference_context": [
            ref(
                I2C_SPEC,
                "SDA and SCL signals",
                "Both SDA and SCL are bidirectional lines, connected to a positive supply voltage via a current-source or pull-up resistor. When the bus is free, both lines are HIGH. The output stages of devices connected to the bus must have an open-drain or open-collector to perform the wired-AND function.",
                "text",
            ),
        ],
        "expected": {
            "root_cause": "The I2C lines have no pull-up resistors (internal pull-ups disabled and none on the bare chip), so the open-drain bus never returns high and transactions time out.",
            "root_cause_keywords": [[r"pull[- ]?ups?"]],
            "fix": "Add external pull-ups (about 4.7 kΩ to 3.3 V) on SDA and SCL; enabling the weak internal pull-ups is only a stopgap.",
            "fix_keywords": [
                [r"pull[- ]?up"],
                [r"4\.?7\s?k", r"external", r"resistor", r"gpio_pullup_enable"],
            ],
            "expected_citation": [I2C_SPEC],
            "line": 5,
        },
    },
    {
        "id": "stm32-hal-i2c-address-shift",
        "title": "HAL_I2C_Master_Transmit returns HAL_ERROR",
        "category": "i2c",
        "target": "STM32F4 / HAL",
        "difficulty": "medium",
        "split": "dev",
        "firmware_code": """#define SSD1306_ADDR 0x3C

void oled_cmd(uint8_t cmd) {
    uint8_t buf[2] = {0x00, cmd};
    HAL_StatusTypeDef st = HAL_I2C_Master_Transmit(&hi2c1, SSD1306_ADDR, buf, 2, 100);
    if (st != HAL_OK) {
        printf("I2C err %d, code 0x%lx\\r\\n", st, HAL_I2C_GetError(&hi2c1));
    }
}""",
        "compiler_output": "",
        "serial_logs": """I2C err 1, code 0x4
I2C err 1, code 0x4
I2C err 1, code 0x4""",
        "user_question": "The same OLED works on Arduino with address 0x3C.",
        "reference_context": [
            ref(
                STM32_HAL,
                "HAL I2C Generic Driver / HAL_I2C_Master_Transmit",
                "DevAddress: Target device address. The device 7 bits address value in datasheet must be shifted to the left before calling the interface.",
                "text",
            ),
            ref(
                STM32_HAL,
                "HAL I2C error codes",
                "HAL_I2C_ERROR_AF (0x00000004U): Acknowledge failure.",
                "table_or_specification",
            ),
        ],
        "expected": {
            "root_cause": "HAL expects the 7-bit address shifted left by one; passing 0x3C addresses 0x1E, so the device NACKs (HAL_I2C_ERROR_AF).",
            "root_cause_keywords": [[r"shift", r"<<\s*1", r"8[- ]bit", r"0x78"]],
            "fix": "Pass (0x3C << 1), i.e. 0x78, as DevAddress.",
            "fix_keywords": [[r"0x3c\s*<<\s*1", r"0x78", r"ssd1306_addr\s*<<\s*1"]],
            "expected_citation": [STM32_HAL],
            "line": 5,
        },
    },
    # ───────────────────────── UART ─────────────────────────
    {
        "id": "esp32-uart-baud-mismatch",
        "title": "Serial monitor shows garbage characters",
        "category": "uart",
        "target": "ESP32 / Arduino core",
        "difficulty": "easy",
        "split": "dev",
        "firmware_code": """void setup() {
  Serial.begin(9600);
}

void loop() {
  Serial.println("Temperature: 24.5 C");
  delay(1000);
}""",
        "compiler_output": "",
        "serial_logs": """--- Miniterm on /dev/ttyUSB0  115200,8,N,1 ---
\u0000\u00f8\u0000\u00e0x\u0000\u0080\u00f8\u0000\u0000\u00f8x\u00f8
\u00e0\u0000\u00f8\u0000\u00f8\u0000\u00e0\u0080\u0000x""",
        "user_question": "Monitor prints random symbols instead of my text.",
        "reference_context": [
            ref(
                ARDUINO_REF,
                "Serial.begin()",
                "Sets the data rate in bits per second (baud) for serial data transmission. For communicating with Serial Monitor, make sure to use one of the baud rates listed in the menu at the bottom right corner of its screen.",
                "text",
            ),
        ],
        "expected": {
            "root_cause": "Baud-rate mismatch: the sketch transmits at 9600 baud while the monitor listens at 115200.",
            "root_cause_keywords": [[r"baud"], [r"9600|115200"]],
            "fix": "Set the monitor to 9600 or change Serial.begin to 115200 so both sides match.",
            "fix_keywords": [[r"9600|115200"], [r"match", r"serial\.begin", r"monitor"]],
            "expected_citation": [ARDUINO_REF],
            "line": 2,
        },
    },
    {
        "id": "stm32-uart-hal-not-enabled",
        "title": "undefined reference to HAL_UART_Init",
        "category": "linker",
        "target": "STM32F4 / HAL",
        "difficulty": "medium",
        "split": "holdout",
        "firmware_code": """/* stm32f4xx_hal_conf.h (excerpt) */
#define HAL_MODULE_ENABLED
#define HAL_GPIO_MODULE_ENABLED
#define HAL_RCC_MODULE_ENABLED
/* #define HAL_UART_MODULE_ENABLED */
#define HAL_CORTEX_MODULE_ENABLED

/* main.c */
UART_HandleTypeDef huart2;
void MX_USART2_UART_Init(void) {
    huart2.Instance = USART2;
    huart2.Init.BaudRate = 115200;
    HAL_UART_Init(&huart2);
}""",
        "compiler_output": """arm-none-eabi-gcc -o build/app.elf build/main.o build/stm32f4xx_hal.o ... -Wl,--gc-sections
build/main.o: In function `MX_USART2_UART_Init':
main.c:(.text.MX_USART2_UART_Init+0x24): undefined reference to `HAL_UART_Init'
build/main.o: In function `log_write':
main.c:(.text.log_write+0x12): undefined reference to `HAL_UART_Transmit'
collect2: error: ld returned 1 exit status""",
        "serial_logs": "",
        "user_question": None,
        "reference_context": [
            ref(
                STM32_HAL,
                "HAL configuration file (stm32f4xx_hal_conf.h)",
                "The HAL_PPP_MODULE_ENABLED defines select which HAL peripheral drivers are compiled. A module whose define is commented out is excluded from the build.",
                "text",
            ),
        ],
        "expected": {
            "root_cause": "HAL_UART_MODULE_ENABLED is commented out in stm32f4xx_hal_conf.h, so the UART HAL driver (and stm32f4xx_hal_uart.c) is not compiled, leaving HAL_UART_* unresolved at link time.",
            "root_cause_keywords": [
                [r"hal_uart_module_enabled", r"hal_conf", r"stm32f4xx_hal_uart\.c"]
            ],
            "fix": "Uncomment #define HAL_UART_MODULE_ENABLED and make sure stm32f4xx_hal_uart.c is in the build.",
            "fix_keywords": [[r"hal_uart_module_enabled", r"stm32f4xx_hal_uart\.c"]],
            "expected_citation": [STM32_HAL],
            "line": 5,
        },
    },
    # ───────────────────────── SPI ─────────────────────────
    {
        "id": "esp32-adxl345-spi-mode",
        "title": "ADXL345 DEVID reads 0x00 over SPI",
        "category": "spi",
        "target": "ESP32 / ESP-IDF",
        "difficulty": "hard",
        "split": "dev",
        "firmware_code": """spi_device_interface_config_t devcfg = {
    .clock_speed_hz = 1 * 1000 * 1000,
    .mode = 0,
    .spics_io_num = GPIO_NUM_5,
    .queue_size = 1,
};
spi_bus_add_device(SPI2_HOST, &devcfg, &adxl);

uint8_t adxl_read(uint8_t reg) {
    spi_transaction_t t = {
        .flags = SPI_TRANS_USE_RXDATA | SPI_TRANS_USE_TXDATA,
        .length = 16,
        .tx_data = {0x80 | reg, 0x00},
    };
    spi_device_polling_transmit(adxl, &t);
    return t.rx_data[1];
}""",
        "compiler_output": "",
        "serial_logs": """I (402) adxl: DEVID = 0x00 (expected 0xE5)
E (403) adxl: sensor not found""",
        "user_question": "Wiring double-checked, 4-wire SPI.",
        "reference_context": [
            ref(
                ADXL345_DS,
                "SPI",
                "For SPI, either 3- or 4-wire configuration is possible. The maximum SPI clock speed is 5 MHz. The timing scheme follows clock polarity (CPOL) = 1 and clock phase (CPHA) = 1.",
                "table_or_specification",
            ),
            ref(
                ADXL345_DS,
                "Register 0x00 - DEVID",
                "The DEVID register holds a fixed device ID code of 0xE5.",
                "register_description",
            ),
        ],
        "expected": {
            "root_cause": "The ADXL345 uses SPI mode 3 (CPOL=1, CPHA=1) but the device is configured for mode 0, so data is sampled on the wrong edge.",
            "root_cause_keywords": [[r"mode\s*3", r"cpol\s*=\s*1", r"cpol.{0,20}cpha"]],
            "fix": "Set .mode = 3 in spi_device_interface_config_t.",
            "fix_keywords": [[r"\.?mode\s*=\s*3", r"mode 3", r"spi mode\s*3"]],
            "expected_citation": [ADXL345_DS],
            "line": 3,
        },
    },
    # ───────────────────────── ADC ─────────────────────────
    {
        "id": "esp32-adc2-wifi",
        "title": "ADC2 read fails once Wi-Fi connects",
        "category": "adc",
        "target": "ESP32 / ESP-IDF v4.4 (legacy ADC driver)",
        "difficulty": "hard",
        "split": "dev",
        "firmware_code": """// Soil sensor on GPIO4 (ADC2_CHANNEL_0)
void sensor_task(void *arg) {
    int raw;
    while (1) {
        esp_err_t r = adc2_get_raw(ADC2_CHANNEL_0, ADC_WIDTH_BIT_12, &raw);
        if (r != ESP_OK) {
            ESP_LOGE("soil", "adc2_get_raw failed: %s", esp_err_to_name(r));
        } else {
            ESP_LOGI("soil", "raw=%d", raw);
        }
        vTaskDelay(pdMS_TO_TICKS(1000));
    }
}""",
        "compiler_output": "",
        "serial_logs": """I (1203) soil: raw=2310
I (2203) soil: raw=2298
I (2650) wifi:connected with HomeNet, aid = 3, channel 6
E (3203) soil: adc2_get_raw failed: ESP_ERR_TIMEOUT
E (4203) soil: adc2_get_raw failed: ESP_ERR_TIMEOUT
E (5203) soil: adc2_get_raw failed: ESP_ERR_TIMEOUT""",
        "user_question": "Readings work for two seconds then fail forever.",
        "reference_context": [
            ref(
                ESP_IDF,
                "ADC / Hardware Limitations",
                "ADC2 is used by the Wi-Fi driver. Therefore the application can only use ADC2 when the Wi-Fi driver has not started. ADC1 channels (GPIO32-39) can be used while Wi-Fi is running.",
                "text",
            ),
        ],
        "expected": {
            "root_cause": "ADC2 is shared with the Wi-Fi driver; once Wi-Fi starts, adc2_get_raw cannot get the peripheral and returns ESP_ERR_TIMEOUT.",
            "root_cause_keywords": [[r"adc2"], [r"wi-?fi"]],
            "fix": "Move the sensor to an ADC1 pin (GPIO32-39) and read it with the ADC1 API.",
            "fix_keywords": [[r"adc1", r"gpio\s?_?(num_)?3[2-9]"]],
            "expected_citation": [ESP_IDF],
            "line": 5,
        },
    },
    # ───────────────────────── Interrupts ─────────────────────────
    {
        "id": "stm32-exti-nvic-disabled",
        "title": "Button EXTI callback never fires",
        "category": "interrupts",
        "target": "STM32F4 / HAL",
        "difficulty": "medium",
        "split": "dev",
        "firmware_code": """void MX_GPIO_Init(void) {
    __HAL_RCC_GPIOA_CLK_ENABLE();
    GPIO_InitTypeDef g = {0};
    g.Pin = GPIO_PIN_0;
    g.Mode = GPIO_MODE_IT_FALLING;
    g.Pull = GPIO_PULLUP;
    HAL_GPIO_Init(GPIOA, &g);
}

void EXTI0_IRQHandler(void) {
    HAL_GPIO_EXTI_IRQHandler(GPIO_PIN_0);
}

void HAL_GPIO_EXTI_Callback(uint16_t pin) {
    if (pin == GPIO_PIN_0) presses++;
}""",
        "compiler_output": "",
        "serial_logs": """presses=0
presses=0
presses=0""",
        "user_question": "Scope shows PA0 going low when pressed but the counter never changes.",
        "reference_context": [
            ref(
                STM32_HAL,
                "HAL CORTEX Generic Driver",
                "HAL_NVIC_SetPriority() and HAL_NVIC_EnableIRQ() must be called to configure and enable the interrupt line in the NVIC; configuring the EXTI line alone does not route the interrupt to the CPU.",
                "text",
            ),
        ],
        "expected": {
            "root_cause": "The EXTI0 interrupt is never enabled in the NVIC, so the IRQ handler is never invoked.",
            "root_cause_keywords": [[r"nvic"], [r"exti0", r"enable", r"irq"]],
            "fix": "Add HAL_NVIC_SetPriority(EXTI0_IRQn, 5, 0); HAL_NVIC_EnableIRQ(EXTI0_IRQn); after HAL_GPIO_Init.",
            "fix_keywords": [[r"hal_nvic_enableirq\s*\(\s*exti0_irqn", r"nvic_enableirq"]],
            "expected_citation": [STM32_HAL],
            "line": 7,
        },
    },
    {
        "id": "stm32-missing-volatile",
        "title": "Main loop never sees flag set in ISR at -O2",
        "category": "interrupts",
        "target": "STM32F4 / GCC -O2",
        "difficulty": "medium",
        "split": "holdout",
        "firmware_code": """static uint8_t data_ready = 0;

void TIM2_IRQHandler(void) {
    if (TIM2->SR & TIM_SR_UIF) {
        TIM2->SR &= ~TIM_SR_UIF;
        data_ready = 1;
    }
}

int main(void) {
    init_timer();
    while (1) {
        while (!data_ready) { }
        data_ready = 0;
        sample_and_send();
    }
}""",
        "compiler_output": "",
        "serial_logs": "",
        "user_question": "Works with -O0 in debug, hangs forever with -O2 in release. Breakpoint in the ISR does hit.",
        "reference_context": [
            ref(
                GCC_DOCS,
                "Volatile objects",
                "Accesses to volatile objects are evaluated strictly according to the rules of the abstract machine. Without volatile, the compiler may keep a variable in a register and assume it does not change unless the current code modifies it.",
                "text",
            ),
        ],
        "expected": {
            "root_cause": "data_ready is shared with an ISR but not declared volatile, so at -O2 the compiler hoists the load out of the busy-wait loop and spins forever.",
            "root_cause_keywords": [[r"volatile"]],
            "fix": "Declare it as static volatile uint8_t data_ready.",
            "fix_keywords": [[r"volatile\s+(uint8_t|bool|sig_atomic_t)", r"static volatile"]],
            "expected_citation": [GCC_DOCS],
            "line": 1,
        },
    },
    {
        "id": "esp32-printf-in-isr",
        "title": "Interrupt WDT timeout when logging from ISR",
        "category": "interrupts",
        "target": "ESP32 / ESP-IDF",
        "difficulty": "medium",
        "split": "dev",
        "firmware_code": """static void IRAM_ATTR button_isr(void *arg) {
    press_count++;
    ESP_LOGI("btn", "pressed %d times", press_count);
}

void app_main(void) {
    gpio_install_isr_service(0);
    gpio_isr_handler_add(GPIO_NUM_0, button_isr, NULL);
}""",
        "compiler_output": "",
        "serial_logs": """Guru Meditation Error: Core  0 panic'ed (Interrupt wdt timeout on CPU0).
Core  0 register dump:
PC      : 0x4008c3a2  PS      : 0x00060a34  A0      : 0x8008b0c1
Backtrace: 0x4008c39f:0x3ffb0b70 0x4008b0be:0x3ffb0b90 0x400d6f8a:0x3ffb0bb0 0x400d2e44:0x3ffb0bd0
  #0  vPortEnterCritical
  #1  xQueueSemaphoreTake
  #2  esp_log_write
  #3  button_isr at main/main.c:3
Rebooting...""",
        "user_question": None,
        "reference_context": [
            ref(
                ESP_IDF,
                "Logging library / ISR usage",
                "ESP_LOGx macros must not be called from an interrupt handler because they may block on a lock. Use ESP_DRAM_LOGx or ESP_EARLY_LOGx in ISRs, or defer work to a task.",
                "text",
            ),
        ],
        "expected": {
            "root_cause": "ESP_LOGI is called inside the ISR; the logging path takes a lock and blocks, so the interrupt watchdog fires.",
            "root_cause_keywords": [
                [r"esp_logi?", r"log(ging)?", r"printf"],
                [r"isr", r"interrupt"],
            ],
            "fix": "Remove logging from the ISR: set a flag or send to a queue with xQueueSendFromISR and log in a task (or use ESP_DRAM_LOGI).",
            "fix_keywords": [
                [r"fromisr", r"queue", r"flag", r"esp_dram_log", r"esp_early_log", r"defer"]
            ],
            "expected_citation": [ESP_IDF],
            "line": 3,
        },
    },
    {
        "id": "freertos-isr-priority-assert",
        "title": "configASSERT in vPortValidateInterruptPriority",
        "category": "interrupts",
        "target": "STM32F4 / FreeRTOS",
        "difficulty": "hard",
        "split": "holdout",
        "firmware_code": """/* FreeRTOSConfig.h: configMAX_SYSCALL_INTERRUPT_PRIORITY = (5 << 4) */

void MX_USART2_Init(void) {
    /* ... */
    HAL_NVIC_SetPriority(USART2_IRQn, 0, 0);
    HAL_NVIC_EnableIRQ(USART2_IRQn);
}

void USART2_IRQHandler(void) {
    BaseType_t woken = pdFALSE;
    uint8_t c = USART2->DR;
    xQueueSendFromISR(rx_queue, &c, &woken);
    portYIELD_FROM_ISR(woken);
}""",
        "compiler_output": "",
        "serial_logs": """[boot] scheduler started
ASSERT FAILED: port.c vPortValidateInterruptPriority
  ucCurrentPriority=0x00 ucMaxSysCallPriority=0x50
System halted.""",
        "user_question": "Crashes on the first byte received.",
        "reference_context": [
            ref(
                FREERTOS,
                "Running the RTOS on an ARM Cortex-M Core",
                "Interrupt service routines that use the RTOS API (functions ending in FromISR) must have a logical priority at or below configMAX_SYSCALL_INTERRUPT_PRIORITY, i.e. a numerical priority value equal to or greater than it. Priority 0 is the highest and must not call FreeRTOS API functions. configASSERT in vPortValidateInterruptPriority traps this error.",
                "text",
            ),
        ],
        "expected": {
            "root_cause": "USART2_IRQn is set to NVIC priority 0, which is above configMAX_SYSCALL_INTERRUPT_PRIORITY (5), yet its ISR calls xQueueSendFromISR, tripping the configASSERT.",
            "root_cause_keywords": [
                [r"priority"],
                [r"configmax_syscall_interrupt_priority", r"max_?syscall", r"\b0\b", r"too high"],
            ],
            "fix": "Set the USART2 priority to 5 or higher numerically, e.g. HAL_NVIC_SetPriority(USART2_IRQn, 5, 0).",
            "fix_keywords": [
                [
                    r"hal_nvic_setpriority\s*\(\s*usart2_irqn\s*,\s*([5-9]|1[0-5])",
                    r"priority (of |to )?([5-9]|1[0-5])",
                    r"numerically (higher|greater|lower urgency)",
                ]
            ],
            "expected_citation": [FREERTOS],
            "line": 5,
        },
    },
    # ───────────────────────── Stack / memory ─────────────────────────
    {
        "id": "esp32-task-stack-overflow",
        "title": "Stack overflow in sensor_task",
        "category": "memory",
        "target": "ESP32 / ESP-IDF",
        "difficulty": "easy",
        "split": "dev",
        "firmware_code": """void sensor_task(void *arg) {
    char json[2048];
    while (1) {
        build_payload(json, sizeof(json));
        mqtt_publish("sensors/room1", json);
        vTaskDelay(pdMS_TO_TICKS(5000));
    }
}

void app_main(void) {
    xTaskCreate(sensor_task, "sensor_task", 1024, NULL, 5, NULL);
}""",
        "compiler_output": "",
        "serial_logs": """***ERROR*** A stack overflow in task sensor_task has been detected.
Backtrace: 0x40081e7a:0x3ffb5b60 0x40089c45:0x3ffb5b80 0x4008a9b2:0x3ffb5ba0
Rebooting...""",
        "user_question": None,
        "reference_context": [
            ref(
                ESP_IDF,
                "FreeRTOS (IDF) / xTaskCreate",
                "On ESP-IDF, usStackDepth is specified in bytes (not words). Local arrays are allocated on the task stack.",
                "text",
            ),
        ],
        "expected": {
            "root_cause": "sensor_task has a 1024-byte stack but allocates a 2048-byte local buffer, overflowing the stack.",
            "root_cause_keywords": [
                [r"stack"],
                [r"1024", r"2048", r"json", r"local (array|buffer)"],
            ],
            "fix": "Increase the stack (e.g. 4096) and/or make the buffer static or heap-allocated.",
            "fix_keywords": [[r"[3-9]\d{3}", r"increase", r"static", r"malloc", r"heap"]],
            "expected_citation": [ESP_IDF],
            "line": 11,
        },
    },
    {
        "id": "esp32-null-loadprohibited",
        "title": "LoadProhibited with EXCVADDR 0x00000008",
        "category": "memory",
        "target": "ESP32 / ESP-IDF",
        "difficulty": "medium",
        "split": "dev",
        "firmware_code": """typedef struct { float temp; float hum; uint32_t ts; } reading_t;

static reading_t *last;

reading_t *sensor_get_latest(void) {
    return last;   // set in sensor_poll() once the first sample arrives
}

void report_task(void *arg) {
    while (1) {
        reading_t *r = sensor_get_latest();
        printf("ts=%lu\\n", r->ts);
        vTaskDelay(pdMS_TO_TICKS(1000));
    }
}""",
        "compiler_output": "",
        "serial_logs": """Guru Meditation Error: Core  1 panic'ed (LoadProhibited). Exception was unhandled.
Core  1 register dump:
PC      : 0x400d2b6e  PS      : 0x00060830  A0      : 0x800d2c10
EXCVADDR: 0x00000008
Backtrace: 0x400d2b6b:0x3ffb8f50 0x400d2c0d:0x3ffb8f70
  #0  report_task at main/report.c:12""",
        "user_question": None,
        "reference_context": [
            ref(
                ESP_IDF,
                "Fatal Errors / LoadProhibited, StoreProhibited",
                "These CPU exceptions happen when an application attempts to read from or write to an invalid memory location. If the EXCVADDR value is zero or close to zero, it typically means the application tried to dereference a NULL pointer.",
                "text",
            ),
        ],
        "expected": {
            "root_cause": "report_task dereferences r->ts while last is still NULL (before the first sample); offset 8 of a NULL struct pointer gives EXCVADDR 0x8.",
            "root_cause_keywords": [[r"null"], [r"last", r"r->ts", r"sensor_get_latest", r"\br\b"]],
            "fix": "Check for NULL before dereferencing (or wait until the first sample is available).",
            "fix_keywords": [[r"null"], [r"check", r"if\s*\(\s*!?\s*r", r"guard", r"wait"]],
            "expected_citation": [ESP_IDF],
            "line": 12,
        },
    },
    {
        "id": "stm32-hardfault-null-fnptr",
        "title": "HardFault with INVSTATE after calling callback",
        "category": "memory",
        "target": "STM32F4 / Cortex-M4",
        "difficulty": "hard",
        "split": "holdout",
        "firmware_code": """typedef void (*rx_cb_t)(uint8_t);
static rx_cb_t on_rx;   // set via uart_register_cb()

void uart_poll(void) {
    if (USART2->SR & USART_SR_RXNE) {
        uint8_t b = USART2->DR;
        on_rx(b);
    }
}""",
        "compiler_output": "",
        "serial_logs": """HardFault!
CFSR = 0x00020000  HFSR = 0x40000000
PC   = 0x00000000  LR = 0x08000a3b
MMFAR= 0xE000EDF4  BFAR = 0xE000EDF8""",
        "user_question": "Happens on first received byte. uart_register_cb() is only called in some build configs.",
        "reference_context": [
            ref(
                CM4_GUIDE,
                "UsageFault Status Register (UFSR)",
                "INVSTATE (CFSR bit 17): the processor has attempted to execute an instruction that makes illegal use of the EPSR, e.g. a branch to an address with bit[0]=0 so the T bit is cleared.",
                "register_description",
            ),
            ref(
                CM4_GUIDE,
                "HardFault Status Register",
                "FORCED (HFSR bit 30): indicates a forced hard fault, generated by escalation of a fault with configurable priority that cannot be handled.",
                "register_description",
            ),
        ],
        "expected": {
            "root_cause": "on_rx is still NULL; calling it branches to 0x00000000 with the Thumb bit clear, raising a UsageFault INVSTATE that escalates to HardFault.",
            "root_cause_keywords": [
                [r"null", r"0x0+\b", r"uninitiali[sz]ed"],
                [r"on_rx", r"function pointer", r"callback"],
            ],
            "fix": "Check on_rx != NULL before calling it, or give it a default no-op handler.",
            "fix_keywords": [
                [r"null", r"default", r"no-?op"],
                [r"check", r"if", r"handler", r"initiali[sz]e"],
            ],
            "expected_citation": [CM4_GUIDE],
            "line": 7,
        },
    },
    {
        "id": "arduino-strcpy-overflow",
        "title": "Variables corrupted after setting device name",
        "category": "memory",
        "target": "Arduino Uno (ATmega328P)",
        "difficulty": "medium",
        "split": "dev",
        "firmware_code": """struct Config {
  char deviceName[8];
  int threshold;
};
Config cfg = {"", 512};

void setup() {
  Serial.begin(115200);
  strcpy(cfg.deviceName, "greenhouse-node-01");
  Serial.print("threshold=");
  Serial.println(cfg.threshold);
}

void loop() {}""",
        "compiler_output": "",
        "serial_logs": """threshold=25971""",
        "user_question": "threshold should be 512 but prints a random number.",
        "reference_context": [
            ref(
                ARDUINO_REF,
                "char arrays / strings",
                "Arrays are not bounds-checked. Writing past the end of an array corrupts adjacent memory. A string needs one extra byte for the null terminator.",
                "text",
            ),
        ],
        "expected": {
            "root_cause": "strcpy writes an 18-character string (19 bytes with terminator) into an 8-byte buffer, overflowing into the next struct member, threshold (bytes 's','e' = 0x6573 = 25971).",
            "root_cause_keywords": [
                [r"overflow", r"out of bounds", r"overrun"],
                [r"devicename", r"strcpy", r"\b8\b"],
            ],
            "fix": "Enlarge deviceName (at least 19 bytes) or use strncpy/strlcpy with sizeof(deviceName).",
            "fix_keywords": [
                [
                    r"strlcpy",
                    r"strncpy",
                    r"snprintf",
                    r"devicename\[\s*(19|2\d|3[0-2])\s*\]",
                    r"larger",
                    r"increase",
                ]
            ],
            "expected_citation": [ARDUINO_REF],
            "line": 9,
        },
    },
    {
        "id": "stm32f103-ram-overflow",
        "title": "region RAM overflowed",
        "category": "linker",
        "target": "STM32F103C8 (Blue Pill)",
        "difficulty": "easy",
        "split": "dev",
        "firmware_code": """#define LOG_BUF_SIZE 24576
static uint8_t log_buf[LOG_BUF_SIZE];""",
        "compiler_output": """arm-none-eabi-ld: build/app.elf section `.bss' will not fit in region `RAM'
arm-none-eabi-ld: region `RAM' overflowed by 6312 bytes
collect2: error: ld returned 1 exit status""",
        "serial_logs": "",
        "user_question": None,
        "reference_context": [
            ref(
                STM32F103_DS,
                "Device overview",
                "STM32F103x8: 64 Kbytes of Flash memory and 20 Kbytes of SRAM.",
                "table_or_specification",
            ),
        ],
        "expected": {
            "root_cause": "The 24 KB static log_buf in .bss alone exceeds the 20 KB of SRAM on the STM32F103C8.",
            "root_cause_keywords": [
                [r"log_buf", r"24576", r"24\s?k"],
                [r"20\s?k", r"ram", r"sram"],
            ],
            "fix": "Shrink LOG_BUF_SIZE (e.g. 4096) or move constant data to flash.",
            "fix_keywords": [
                [r"reduce", r"shrink", r"smaller", r"log_buf_size\s+\d{3,4}\b", r"const"]
            ],
            "expected_citation": [STM32F103_DS],
            "line": 1,
        },
    },
    # ───────────────────────── Watchdog / power ─────────────────────────
    {
        "id": "esp32-task-wdt-busy-loop",
        "title": "Task watchdog got triggered (IDLE0)",
        "category": "runtime",
        "target": "ESP32 / ESP-IDF",
        "difficulty": "easy",
        "split": "dev",
        "firmware_code": """void wait_for_button(void) {
    while (gpio_get_level(GPIO_NUM_0) == 1) {
        // spin until pressed
    }
}

void app_main(void) {
    wait_for_button();
    start_measurement();
}""",
        "compiler_output": "",
        "serial_logs": """E (5310) task_wdt: Task watchdog got triggered. The following tasks did not reset the watchdog in time:
E (5310) task_wdt:  - IDLE0 (CPU 0)
E (5310) task_wdt: Tasks currently running:
E (5310) task_wdt: CPU 0: main
E (5310) task_wdt: CPU 1: IDLE1""",
        "user_question": None,
        "reference_context": [
            ref(
                ESP_IDF,
                "Watchdogs / Task Watchdog Timer",
                "By default the TWDT watches the idle task of each CPU. If a task busy-loops without blocking, the idle task cannot run and the TWDT is triggered.",
                "text",
            ),
        ],
        "expected": {
            "root_cause": "wait_for_button busy-waits without yielding, starving IDLE0 so the task watchdog fires.",
            "root_cause_keywords": [
                [
                    r"busy[- ]?(wait|loop)",
                    r"spin",
                    r"not yield",
                    r"without (yielding|blocking|delay)",
                    r"starv",
                    r"while",
                ],
                [r"idle", r"watchdog"],
            ],
            "fix": "Add vTaskDelay(pdMS_TO_TICKS(10)) inside the loop or use a GPIO interrupt.",
            "fix_keywords": [[r"vtaskdelay", r"interrupt", r"semaphore", r"taskyield"]],
            "expected_citation": [ESP_IDF],
            "line": 2,
        },
    },
    {
        "id": "esp32-brownout-wifi",
        "title": "Brownout detector triggered when Wi-Fi starts",
        "category": "runtime",
        "target": "ESP32 DevKit / Arduino core",
        "difficulty": "medium",
        "split": "holdout",
        "firmware_code": """void setup() {
  Serial.begin(115200);
  servo.attach(13);
  WiFi.begin(SSID, PASS);
  while (WiFi.status() != WL_CONNECTED) delay(100);
}""",
        "compiler_output": "",
        "serial_logs": """ets Jun  8 2016 00:22:57
rst:0x1 (POWERON_RESET),boot:0x13 (SPI_FAST_FLASH_BOOT)
Brownout detector was triggered

ets Jun  8 2016 00:22:57
rst:0xc (SW_CPU_RESET),boot:0x13 (SPI_FAST_FLASH_BOOT)
Brownout detector was triggered""",
        "user_question": "Powered from laptop USB through a long thin cable; SG90 servo on the same 5V rail.",
        "reference_context": [
            ref(
                ESP32_DS,
                "RF Power-Consumption Specifications",
                "Wi-Fi transmit current can reach about 240 mA peak (802.11b at maximum output power). The power supply must be able to deliver these current peaks without the supply voltage dropping.",
                "table_or_specification",
            ),
        ],
        "expected": {
            "root_cause": "Supply voltage sags when the Wi-Fi radio transmits (plus servo load on a weak USB/long cable), tripping the brownout detector.",
            "root_cause_keywords": [
                [r"brownout", r"voltage (drop|sag|dip)", r"power supply", r"supply"],
                [r"wi-?fi", r"servo", r"current"],
            ],
            "fix": "Use a stronger supply/short cable, power the servo separately, add bulk capacitance near the ESP32; do not just disable the brownout detector.",
            "fix_keywords": [[r"capacitor", r"separate", r"supply", r"cable", r"\d+\s?(µ|u)f"]],
            "expected_citation": [ESP32_DS],
            "line": 4,
        },
    },
    # ───────────────────────── Compiler / linker / types ─────────────────────────
    {
        "id": "arduino-missing-semicolon-cascade",
        "title": "Error cascade from one missing semicolon",
        "category": "compiler",
        "target": "Arduino Uno",
        "difficulty": "easy",
        "split": "dev",
        "firmware_code": """int sensorPin = A0
int ledPin = 9;

void setup() {
  pinMode(ledPin, OUTPUT);
}

void loop() {
  int v = analogRead(sensorPin);
  analogWrite(ledPin, v / 4);
}""",
        "compiler_output": """sketch.ino:2:1: error: expected ',' or ';' before 'int'
 int ledPin = 9;
 ^~~
sketch.ino: In function 'void setup()':
sketch.ino:5:11: error: 'ledPin' was not declared in this scope
   pinMode(ledPin, OUTPUT);
           ^~~~~~
sketch.ino: In function 'void loop()':
sketch.ino:10:15: error: 'ledPin' was not declared in this scope
exit status 1""",
        "serial_logs": "",
        "user_question": None,
        "reference_context": [
            ref(
                GCC_DOCS,
                "Diagnostics",
                "After a syntax error the parser recovers and may report further errors that are consequences of the first one; fix the first error and rebuild.",
                "text",
            ),
        ],
        "expected": {
            "root_cause": "Line 1 is missing a semicolon after `int sensorPin = A0`, so ledPin is never declared and the later errors cascade from it.",
            "root_cause_keywords": [[r"semicolon", r"';'"], [r"line 1", r"sensorpin", r"a0"]],
            "fix": "Add the semicolon: int sensorPin = A0;",
            "fix_keywords": [[r"sensorpin\s*=\s*a0\s*;", r"add (a |the )?semicolon"]],
            "expected_citation": [GCC_DOCS],
            "line": 1,
        },
    },
    {
        "id": "arduino-multiple-definition",
        "title": "multiple definition of `counter'",
        "category": "linker",
        "target": "Arduino / PlatformIO",
        "difficulty": "medium",
        "split": "dev",
        "firmware_code": """// globals.h
#pragma once
int counter = 0;

// main.cpp
#include "globals.h"
void loop() { counter++; }

// display.cpp
#include "globals.h"
void showCount() { Serial.println(counter); }""",
        "compiler_output": """.pio/build/uno/src/main.cpp.o (symbol from plugin): In function `counter':
(.text+0x0): multiple definition of `counter'
.pio/build/uno/src/display.cpp.o (symbol from plugin):(.text+0x0): first defined here
collect2: error: ld returned 1 exit status""",
        "serial_logs": "",
        "user_question": None,
        "reference_context": [
            ref(
                GCC_DOCS,
                "Linker: multiple definitions",
                "A variable defined (not just declared) in a header is defined in every translation unit that includes it, producing multiple definition errors at link time. Declare it extern in the header and define it in exactly one source file.",
                "text",
            ),
        ],
        "expected": {
            "root_cause": "counter is defined (with an initializer) in globals.h, which is included by two .cpp files, so it is defined twice at link time.",
            "root_cause_keywords": [[r"header", r"globals\.h"], [r"defin", r"include"]],
            "fix": "Use `extern int counter;` in globals.h and `int counter = 0;` in one .cpp file.",
            "fix_keywords": [[r"extern"]],
            "expected_citation": [GCC_DOCS],
            "line": 3,
        },
    },
    {
        "id": "arduino-millis-int-overflow",
        "title": "Timer stops after about 32 seconds",
        "category": "logic",
        "target": "Arduino Uno (ATmega328P)",
        "difficulty": "medium",
        "split": "holdout",
        "firmware_code": """int lastBlink = 0;

void loop() {
  int now = millis();
  if (now - lastBlink >= 1000) {
    digitalWrite(LED_BUILTIN, !digitalRead(LED_BUILTIN));
    lastBlink = now;
  }
}""",
        "compiler_output": "",
        "serial_logs": """t=31000 blink
t=32000 blink
t=-32536 ...
(no further blinks)""",
        "user_question": "LED blinks for ~32 s then stops.",
        "reference_context": [
            ref(
                ARDUINO_REF,
                "int / millis()",
                "On the Arduino Uno (ATmega-based boards) an int stores a 16-bit value, range -32,768 to 32,767. millis() returns an unsigned long; store it in an unsigned long.",
                "text",
            ),
        ],
        "expected": {
            "root_cause": "millis() is stored in a 16-bit int, which overflows at 32,767 ms and goes negative, breaking the comparison.",
            "root_cause_keywords": [
                [r"overflow", r"wrap", r"16[- ]bit", r"32,?767"],
                [r"int", r"millis"],
            ],
            "fix": "Use unsigned long for now and lastBlink.",
            "fix_keywords": [[r"unsigned long", r"uint32_t"]],
            "expected_citation": [ARDUINO_REF],
            "line": 4,
        },
    },
    {
        "id": "stm32-adc-signed-compare",
        "title": "Over-temperature check never triggers",
        "category": "adc",
        "target": "STM32F4 / HAL",
        "difficulty": "hard",
        "split": "dev",
        "firmware_code": """#define TEMP_LIMIT_MV  1500

int8_t read_temp_mv(void) {
    HAL_ADC_Start(&hadc1);
    HAL_ADC_PollForConversion(&hadc1, 10);
    uint32_t raw = HAL_ADC_GetValue(&hadc1);
    return (raw * 3300) / 4095;
}

void check(void) {
    if (read_temp_mv() > TEMP_LIMIT_MV) fan_on();
}""",
        "compiler_output": """main.c: In function 'read_temp_mv':
main.c:7:12: warning: conversion from 'uint32_t' {aka 'long unsigned int'} to 'int8_t' {aka 'signed char'} may change value [-Wconversion]""",
        "serial_logs": """raw=2482 mv_func=-48
raw=2490 mv_func=-42""",
        "user_question": "ADC raw values look right (~2 V) but the fan never turns on.",
        "reference_context": [
            ref(
                STM32_RM,
                "ADC data register",
                "In 12-bit resolution the conversion result ranges from 0 to 4095.",
                "register_description",
            ),
        ],
        "expected": {
            "root_cause": "read_temp_mv returns int8_t, truncating millivolt values (up to 3300) to -128..127, so the comparison with 1500 is never true.",
            "root_cause_keywords": [[r"int8_t", r"truncat", r"signed char", r"8[- ]bit"]],
            "fix": "Return uint16_t/uint32_t (or int32_t) from read_temp_mv.",
            "fix_keywords": [[r"uint16_t", r"uint32_t", r"int32_t", r"int16_t"]],
            "expected_citation": [STM32_RM],
            "line": 3,
        },
    },
]


# ───────────────────── Insufficient-evidence (abstention) cases ─────────────────────
# Added 2026-11-05. The evidence deliberately cannot determine one root cause.

ABSTAIN_CASES: list[dict[str, Any]] = [
    {
        "id": "abstain-esp32-stops-responding",
        "title": "ESP32 stops responding after a few hours, no log captured",
        "category": "insufficient-evidence",
        "target": "ESP32 / ESP-IDF v5.0",
        "difficulty": "hard",
        "split": "dev",
        "firmware_code": """void app_main(void) {
    sensor_init();
    wifi_start();
    while (1) {
        float t = sensor_read();
        publish(t);
        vTaskDelay(pdMS_TO_TICKS(5000));
    }
}""",
        "compiler_output": "",
        "serial_logs": "",
        "user_question": "My board stops sending data after 3-6 hours. No serial monitor was attached. What is wrong?",
        "reference_context": [],
        "expected": {
            "abstain": True,
            "root_cause": "Insufficient evidence: no log, reset reason or implementation of sensor_read/publish/wifi_start is given, so no single root cause can be identified.",
            "root_cause_keywords": [
                [
                    r"insufficient",
                    r"not enough",
                    r"cannot (?:be )?determin",
                    r"need more",
                    r"more information",
                ]
            ],
            "needed_info_keywords": [
                [
                    r"serial log",
                    r"monitor",
                    r"reset reason",
                    r"panic",
                    r"backtrace",
                    r"heap",
                    r"implementation",
                    r"publish\(",
                    r"sensor_read",
                ]
            ],
            "fix": "Capture the serial log (reset reason, panic/backtrace), log free heap over time, and share the sensor_read/publish/wifi_start code.",
            "fix_keywords": [[r"serial log", r"monitor", r"reset reason", r"backtrace", r"heap"]],
            "expected_citation": [],
            "line": None,
        },
    },
    {
        "id": "abstain-stm32-i2c-hal-error",
        "title": "HAL_I2C_Master_Transmit returns HAL_ERROR, nothing else known",
        "category": "insufficient-evidence",
        "target": "STM32F4 / HAL",
        "difficulty": "medium",
        "split": "dev",
        "firmware_code": """HAL_StatusTypeDef st = HAL_I2C_Master_Transmit(&hi2c1, dev_addr, buf, 2, 100);
if (st != HAL_OK) {
    printf("i2c failed: %d\\r\\n", st);
}""",
        "compiler_output": "",
        "serial_logs": "i2c failed: 1\ni2c failed: 1",
        "user_question": "I2C write fails every time. Why?",
        "reference_context": [],
        "expected": {
            "abstain": True,
            "root_cause": "Insufficient evidence: status 1 (HAL_ERROR) covers NACK, bus error and arbitration loss; the device, its address value, wiring/pull-ups and HAL_I2C_GetError() are unknown.",
            "root_cause_keywords": [
                [
                    r"insufficient",
                    r"not enough",
                    r"cannot (?:be )?determin",
                    r"need more",
                    r"more information",
                    r"several (?:possible )?causes",
                    r"could be",
                ]
            ],
            "needed_info_keywords": [
                [
                    r"hal_i2c_geterror",
                    r"error ?code",
                    r"dev_addr",
                    r"address",
                    r"pull-?up",
                    r"schematic",
                    r"logic analy[sz]er",
                    r"oscilloscope",
                ]
            ],
            "fix": "Print HAL_I2C_GetError(&hi2c1), share the device part number and dev_addr value, and check SDA/SCL pull-ups with a scope or logic analyzer.",
            "fix_keywords": [
                [r"hal_i2c_geterror", r"dev_addr", r"pull-?up", r"logic analy[sz]er", r"scope"]
            ],
            "expected_citation": [],
            "line": None,
        },
    },
    {
        "id": "abstain-arduino-analog-wrong",
        "title": "analogRead value is 'wrong', sensor and wiring unknown",
        "category": "insufficient-evidence",
        "target": "Arduino Uno",
        "difficulty": "medium",
        "split": "holdout",
        "firmware_code": """void loop() {
  int v = analogRead(A0);
  Serial.println(v);
  delay(500);
}""",
        "compiler_output": "",
        "serial_logs": "612\n598\n640\n603",
        "user_question": "The readings are wrong. How do I fix it?",
        "reference_context": [],
        "expected": {
            "abstain": True,
            "root_cause": "Insufficient evidence: the sensor, its expected value, wiring and analog reference are not given, so it cannot be determined whether ~600 counts is wrong or why.",
            "root_cause_keywords": [
                [
                    r"insufficient",
                    r"not enough",
                    r"cannot (?:be )?determin",
                    r"need more",
                    r"more information",
                    r"unclear",
                    r"what (?:value|reading) (?:do )?you expect",
                ]
            ],
            "needed_info_keywords": [
                [
                    r"sensor",
                    r"part number",
                    r"expected",
                    r"wiring",
                    r"schematic",
                    r"aref",
                    r"reference voltage",
                ]
            ],
            "fix": "Share the sensor model, the expected reading, the wiring and the analog reference used.",
            "fix_keywords": [[r"sensor", r"expected", r"wiring", r"aref", r"reference"]],
            "expected_citation": [],
            "line": None,
        },
    },
    {
        "id": "abstain-esp32-undecoded-backtrace",
        "title": "StoreProhibited panic, faulting code not provided",
        "category": "insufficient-evidence",
        "target": "ESP32 / ESP-IDF v5.0",
        "difficulty": "hard",
        "split": "holdout",
        "firmware_code": """void app_main(void) {
    app_init();      /* defined in another file, not provided */
    app_run();
}""",
        "compiler_output": "",
        "serial_logs": """Guru Meditation Error: Core  1 panic'ed (StoreProhibited). Exception was unhandled.
PC      : 0x400d2a1c  PS      : 0x00060730  A0      : 0x800d2b44  A1      : 0x3ffb5f70
EXCVADDR: 0x00000010
Backtrace: 0x400d2a19:0x3ffb5f70 0x400d2b41:0x3ffb5f90 0x400d1f2e:0x3ffb5fb0""",
        "user_question": "What line is crashing and how do I fix it?",
        "reference_context": [],
        "expected": {
            "abstain": True,
            "root_cause": "Insufficient evidence: a store to address 0x10 (likely a NULL struct pointer plus offset) happened, but the backtrace is not decoded and the faulting code is not provided, so the line and variable cannot be identified.",
            "root_cause_keywords": [
                [
                    r"insufficient",
                    r"not enough",
                    r"cannot (?:be )?(?:determin|identif)",
                    r"need",
                    r"not provided",
                    r"decod",
                ]
            ],
            "needed_info_keywords": [
                [
                    r"addr2line",
                    r"idf\.py monitor",
                    r"decod",
                    r"elf",
                    r"source",
                    r"app_init",
                    r"app_run",
                ]
            ],
            "fix": "Decode the backtrace with idf.py monitor or xtensa-esp32-elf-addr2line against the ELF, and share the source of the reported functions.",
            "fix_keywords": [[r"addr2line", r"idf\.py monitor", r"decod", r"elf"]],
            "expected_citation": [],
            "line": None,
        },
    },
]

REFERENCE_SOURCES = Path(__file__).parent / "reference_sources.json"


def apply_verified_sources(cases: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Replace DEV case excerpts with verbatim, page-referenced excerpts.

    Holdout cases are left untouched until the user approves their corrections.
    The case's canonical `title` is kept so `expected_citation` still matches.
    """
    sources = json.loads(REFERENCE_SOURCES.read_text(encoding="utf-8"))
    by_key = {(s["case"], s["idx"]): s for s in sources}
    out = []
    for case in cases:
        case = json.loads(json.dumps(case))
        if case["split"] == "dev":
            for i, r in enumerate(case["reference_context"]):
                s = by_key.get((case["id"], i))
                if not s or s["status"] == "not_found":
                    continue
                case["reference_context"][i] = {
                    "title": r["title"],
                    "document": s["document"],
                    "revision": s["revision"],
                    "section": s["section"],
                    "snippet": s["verbatim_snippet"],
                    "content_type": r.get("content_type", "text"),
                    "page_number": s["page"],
                    "page_kind": s["page_kind"],
                    "url": s["url"],
                    "verification": s["status"],
                }
        out.append(case)
    return out


def main() -> None:
    CASES_DIR.mkdir(exist_ok=True)
    for old in CASES_DIR.glob("*.json"):
        old.unlink()
    for case in apply_verified_sources(CASES) + ABSTAIN_CASES:
        path = CASES_DIR / f"{case['id']}.json"
        path.write_text(json.dumps(case, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(f"Wrote {len(CASES) + len(ABSTAIN_CASES)} cases to {CASES_DIR}")


if __name__ == "__main__":
    main()
