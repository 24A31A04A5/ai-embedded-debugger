/**
 * Unit tests for serial-service.ts
 * Run with: npx tsx apps/web/lib/serial-service.test.ts
 */

import {
  MockSerialStream,
  MockSerialConfig,
  parseESP32CrashLog,
  CrashType,
  classifySerialLogEvents,
} from "./serial-service";

// Test helper
function assert(condition: boolean, message: string) {
  if (!condition) {
    throw new Error(`FAILED: ${message}`);
  }
  console.log(`✓ ${message}`);
}

// Tests for MockSerialStream
function testMockSerialStream() {
  console.log("\n=== Testing MockSerialStream ===");

  const config: MockSerialConfig = {
    deviceType: "esp32",
    outputRate: 10,
    includeBanner: true,
  };

  const stream = new MockSerialStream(config);
  const portInfo = stream.getPortInfo();

  assert(portInfo.isOpen === true, "Port info is open");
  assert(portInfo.state === "connected", "Port state is connected");
  assert(portInfo.manufacturer === "Espressif", "Manufacturer is Espressif");
  assert(portInfo.product === "USB Serial Port", "Product is USB Serial Port");
}

function testMockSerialStreamCrashScenarios() {
  console.log("\n=== Testing Mock Serial Stream Crash Scenarios ===");

  // Test watchdog crash
  const watchdogConfig: MockSerialConfig = {
    deviceType: "esp32",
    crashScenario: "watchdog",
    outputRate: 10,
    includeBanner: false,
  };

  const watchdogStream = new MockSerialStream(watchdogConfig);
  watchdogStream.triggerCrash("watchdog");
  const watchdogLog = watchdogStream.getBuffer();

  assert(
    watchdogLog.toLowerCase().includes("watchdog"),
    "Watchdog crash triggers watchdog log"
  );

  // Test brownout crash
  const brownoutStream = new MockSerialStream({ deviceType: "esp32", crashScenario: "brownout" });
  brownoutStream.triggerCrash("brownout");
  const brownoutLog = brownoutStream.getBuffer();

  assert(
    brownoutLog.toLowerCase().includes("brownout"),
    "Brownout crash triggers brownout log"
  );
}

function testCrashParser() {
  console.log("\n=== Testing ESP32 Crash Parser ===");

  // Test Guru Meditation
  const guruLog = `Guru Meditation Error: Core  0 panic! (Reset caused by fatal exception)
xtensa-esp32-elf-addr2line failed to parse the backtrace
0x400e8284 pc: 0x400d1234
Backtrace: 0x40081234\`0x400d5678
`;

  const guruResult = parseESP32CrashLog(guruLog);
  assert(guruResult !== null, "Guru Meditation parsed");
  if (guruResult) {
    assert(guruResult.type === CrashType.GURU_MEDITATION, "Crash type is guru_meditation");
    assert(guruResult.likelyCause !== undefined, "Likely cause is defined");
  }

  // Test Watchdog
  const watchdogLog = `ets_task_core: reset due to watchdog timeout
Guru Meditation Error: Core  0 panic!
Watchdog timeout detected
`;

  const watchdogResult = parseESP32CrashLog(watchdogLog);
  assert(watchdogResult !== null, "Watchdog parsed");
  if (watchdogResult) {
    assert(watchdogResult.type === CrashType.WATCHDOG, "Crash type is watchdog");
  }

  // Test Brownout
  const brownoutLog = `Brownout detector was triggered
Reset reason: Brownout reset
Guru Meditation Error: Core  0 panic! (Reset was caused by brownout)
`;

  const brownoutResult = parseESP32CrashLog(brownoutLog);
  assert(brownoutResult !== null, "Brownout parsed");
  if (brownoutResult) {
    assert(brownoutResult.type === CrashType.BROWNOUT, "Crash type is brownout");
  }

  // Test Unknown
  const unknownLog = `Some random crash log
No specific pattern here
`;

  const unknownResult = parseESP32CrashLog(unknownLog);
  assert(unknownResult !== null, "Unknown crash parsed");
  if (unknownResult) {
    assert(unknownResult.type === CrashType.UNKNOWN, "Crash type is unknown");
  }
}

function testSerializeLogClassification() {
  console.log("\n=== Testing Serial Log Classification ===");

  const crashLog = `[2024-01-01 12:00:00] Guru Meditation Error: Core  0 panic! (Reset caused by fatal exception)
[2024-01-01 12:00:01] Crash occurred
`;

  const events = classifySerialLogEvents(crashLog);

  assert(events.length > 0, "Events are classified");
  assert(events[0].event_type === "crash_fault", "Event type is crash_fault");
  assert(events[0].severity === "critical", "Severity is critical");
}

function testMockSerialStreamBuffer() {
  console.log("\n=== Testing Mock Serial Stream Buffer ===");

  const stream = new MockSerialStream({
    deviceType: "esp32",
    outputRate: 10,
    includeBanner: false,
  });

  // Initial buffer should be empty
  assert(stream.getBuffer() === "", "Initial buffer is empty");

  // Write some data
  stream["emitMessage"]("test output\n");

  // Buffer should contain test output
  assert(stream.getBuffer().includes("test output"), "Buffer contains written data");

  // Clear buffer
  stream.clearBuffer();
  assert(stream.getBuffer() === "", "Buffer cleared");
}

function testMockSerialStreamPauseResume() {
  console.log("\n=== Testing Mock Serial Stream Pause/Resume ===");

  const stream = new MockSerialStream({
    deviceType: "esp32",
    includeBanner: false,
  });

  // Pause should work without error
  stream.pause();

  // Resume should work without error
  stream.resume();
}

function testMockSerialStreamDestroy() {
  console.log("\n=== Testing Mock Serial Stream Destroy ===");

  const stream = new MockSerialStream({
    deviceType: "esp32",
    includeBanner: false,
  });

  // Destroy should stop the stream and clean up
  stream.destroy();

  // After destroy, buffer should still be accessible but stream stopped
  assert(stream.getBuffer() === "", "Buffer accessible after destroy");
}

// Run all tests
function runAllTests() {
  console.log("\n========================================");
  console.log("Running Phase 10 Serial Service Tests");
  console.log("========================================");

  try {
    testMockSerialStream();
    testMockSerialStreamCrashScenarios();
    testCrashParser();
    testSerializeLogClassification();
    testMockSerialStreamBuffer();
    testMockSerialStreamPauseResume();
    testMockSerialStreamDestroy();

    console.log("\n========================================");
    console.log("ALL TESTS PASSED ✓");
    console.log("========================================");
    process.exit(0);
  } catch (error) {
    console.error("\n========================================");
    console.error("TESTS FAILED");
    console.error("========================================");
    console.error(error);
    process.exit(1);
  }
}

runAllTests();