"use client";

import React from "react";
import { FileCode, FileText, Terminal, Sparkles, ArrowRight } from "lucide-react";
import Link from "next/link";
import { Card, CardContent, CardHeader, CardTitle, CardDescription, CardFooter } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { CodeViewer } from "@/components/CodeViewer";

const SAMPLE_FIRMWARE = `#include <stdio.h>
#include "driver/gpio.h"
#include "freertos/FreeRTOS.h"
#include "freertos/task.h"
#include "esp_log.h"

#define LED_GPIO 2
#define BLINK_DELAY_MS 500

static const char *TAG = "blink_example";

void app_main(void) {
    // Configure GPIO
    gpio_config_t io_conf = {
        .pin_bit_mask = GPIO_SEL_2,  // BUG: GPIO_SEL_2 not defined for all ESP32 variants
        .mode = GPIO_MODE_OUTPUT,
        .pull_up_en = GPIO_PULLUP_DISABLE,
        .pull_down_en = GPIO_PULLDOWN_DISABLE,
        .intr_type = GPIO_INTR_DISABLE,
    };
    gpio_config(&io_conf);

    ESP_LOGI(TAG, "Starting blink task");

    while (1) {
        gpio_set_level(LED_GPIO, 1);
        vTaskDelay(BLINK_DELAY_MS / portTICK_PERIOD_MS);
        gpio_set_level(LED_GPIO, 0);
        vTaskDelay(BLINK_DELAY_MS / portTICK_PERIOD_MS);
    }
}`;

const SAMPLE_COMPILER_OUTPUT = `main.c: In function 'app_main':
main.c:13:23: error: 'GPIO_SEL_2' undeclared (first use in this function)
     .pin_bit_mask = GPIO_SEL_2;
                       ^~~~~~~~~~
main.c:13:23: note: each undeclared identifier is reported only once for each function it appears in

main.c: At top level:
main.c:25:1: warning: control reaches end of non-void function [-Wreturn-type]
 }`;

const SAMPLE_DATASHEET = `ESP32-S3 Technical Reference Manual - GPIO Section

4.1 GPIO Matrix
The ESP32-S3 has 45 GPIO pins (GPIO0-GPIO21, GPIO26-GPIO48). Each GPIO can be configured as
input, output, or peripheral function through the GPIO matrix.

4.2 GPIO Register Summary
- GPIO_OUT_REG: Output register for GPIO0-31
- GPIO_OUT1_REG: Output register for GPIO32-48
- GPIO_ENABLE_REG: Output enable register
- GPIO_STRAP_REG: Strapping pin register

4.3 Bitmask Definitions
For ESP32-S3, GPIO bitmasks use 1ULL shift N format:
- GPIO0: (1ULL << 0)
- GPIO2: (1ULL << 2)
- GPIO_NUM_2: Predefined constant = 2

Note: GPIO_SEL_N macros are legacy ESP32 definitions. For ESP32-S3, use
(1ULL shift GPIO_NUM_N) or GPIO_NUM_N directly.

4.4 Example: LED Blink on GPIO2
gpio_config_t io_conf = {
    .pin_bit_mask = (1ULL shift GPIO_NUM_2),
    .mode = GPIO_MODE_OUTPUT,
}`;

export function SampleProjectCard() {
  return (
    <Card variant="glassCard" className="relative overflow-hidden border-[var(--accent-purple)]/20">
      <div className="absolute -right-10 -top-10 w-32 h-32 bg-[var(--accent-purple)]/5 rounded-full blur-2xl pointer-events-none" />

      <CardHeader>
        <div className="flex items-center justify-between gap-2 mb-2">
          <Badge variant="ai" className="gap-1.5">
            <Sparkles className="h-3 w-3" />
            <span>Sample Project</span>
          </Badge>
          <Badge variant="outline" className="text-[10px] text-[var(--color-emerald)] border-[var(--color-emerald)]/30">
            ESP32-S3 Blink Demo
          </Badge>
        </div>
        <CardTitle className="text-base font-semibold text-foreground">
          ESP32-S3 LED Blink with Intentional Bug
        </CardTitle>
        <CardDescription className="text-xs text-muted-foreground">
          Demonstrates the diagnostic pipeline: compiler error to RAG lookup to grounded fix.
          Try it in the workspace to see the full AI analysis.
        </CardDescription>
      </CardHeader>

      <CardContent className="pb-4">
        <Tabs defaultValue="code" className="space-y-3">
          <TabsList className="bg-card/60 border border-border/40 rounded-lg p-1">
            <TabsTrigger value="code" className="text-xs px-3 py-1.5">
              <FileCode className="h-3 w-3 mr-1" /> Firmware (.c)
            </TabsTrigger>
            <TabsTrigger value="compiler" className="text-xs px-3 py-1.5">
              <Terminal className="h-3 w-3 mr-1" /> Compiler Output
            </TabsTrigger>
            <TabsTrigger value="datasheet" className="text-xs px-3 py-1.5">
              <FileText className="h-3 w-3 mr-1" /> Datasheet (RAG)
            </TabsTrigger>
          </TabsList>

          <TabsContent value="code" className="min-h-[200px] max-h-[300px]">
            <CodeViewer
              code={SAMPLE_FIRMWARE}
              language="c"
              showLineNumbers={true}
              highlightLines={[13]}
              className="text-[11px]"
            />
          </TabsContent>

          <TabsContent value="compiler" className="min-h-[150px] max-h-[300px]">
            <CodeViewer
              code={SAMPLE_COMPILER_OUTPUT}
              language="text"
              showLineNumbers={false}
              className="text-[11px] bg-[var(--color-code-bg)]"
            />
          </TabsContent>

          <TabsContent value="datasheet" className="min-h-[200px] max-h-[300px]">
            <CodeViewer
              code={SAMPLE_DATASHEET}
              language="text"
              showLineNumbers={false}
              className="text-[11px]"
            />
          </TabsContent>
        </Tabs>
      </CardContent>

      <CardFooter className="pt-2 border-t border-border/30 flex items-center justify-between">
        <span className="text-[10px] text-muted-foreground">
          Bug: GPIO_SEL_2 undefined, Fix: 1ULL shift GPIO_NUM_2
        </span>
        <Button variant="ai" size="sm" asChild className="gap-1.5">
          <Link href="/workspace">
            <span>Try in Workspace</span>
            <ArrowRight className="h-3.5 w-3.5" />
          </Link>
        </Button>
      </CardFooter>
    </Card>
  );
}