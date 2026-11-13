/**
 * Static "Sample project: ESP32 Blink" shown on the homepage (Phase 8B).
 *
 * This is a hard-coded illustration only. It is never written to the
 * database, never sent to the API, and never mixed into a user's project
 * list. Everything rendered from it is labelled "Sample".
 */

export const SAMPLE_PROJECT = {
  id: "sample-esp32-blink",
  isSample: true as const,
  name: "ESP32 Blink",
  board: "ESP32-DevKitC (ESP-IDF)",
  bug: {
    title: "LED on GPIO2 never lights, but the log says it is toggling",
    file: "main/blink_example_main.c",
    code: [
      "#define BLINK_GPIO 2",
      "",
      "void app_main(void)",
      "{",
      "    gpio_reset_pin(BLINK_GPIO);",
      "    /* missing: gpio_set_direction(BLINK_GPIO, GPIO_MODE_OUTPUT); */",
      "    while (1) {",
      '        ESP_LOGI(TAG, "Turning the LED %s", s_led_state ? "ON" : "OFF");',
      "        gpio_set_level(BLINK_GPIO, s_led_state);",
      "        s_led_state = !s_led_state;",
      "        vTaskDelay(1000 / portTICK_PERIOD_MS);",
      "    }",
      "}",
    ],
    serialLog: [
      "I (312) example: Turning the LED ON",
      "I (1312) example: Turning the LED OFF",
      "I (2312) example: Turning the LED ON",
    ],
  },
  datasheet: {
    document: "ESP32 Technical Reference Manual",
    section: "IO MUX and GPIO Matrix: GPIO output enable (GPIO_ENABLE_REG)",
    excerpt:
      "A GPIO pad drives its output only when its bit in the GPIO output-enable register is set; writing the output-value register alone does not drive the pin.",
    note: "Paraphrased excerpt for this demo. In a real session the citation points at the page of the datasheet you uploaded.",
  },
  session: {
    title: "Blink LED stays dark",
    rootCause:
      "gpio_reset_pin() leaves GPIO2 with its output driver disabled. gpio_set_level() only updates the output value, so the pin is never driven even though the loop and the log run normally.",
    fixDiff: [
      "   gpio_reset_pin(BLINK_GPIO);",
      "+  gpio_set_direction(BLINK_GPIO, GPIO_MODE_OUTPUT);",
    ],
    confidence: "Grounded: cites the GPIO output-enable section above",
  },
} as const;

export type SampleProject = typeof SAMPLE_PROJECT;
