/**
 * Web Serial Service
 * Provides browser-based serial connection layer for ESP32 development
 * Uses Web Serial API for real device connections and Mock streams for offline simulation
 */

// Web Serial API ambient definitions for TypeScript
declare global {
  interface SerialPortInfo {
    usbVendorId?: number;
    usbProductId?: number;
    manufacturer?: string;
    product?: string;
    serialNumber?: string;
  }

  interface SerialOptions {
    baudRate: number;
    dataBits?: number;
    stopBits?: number;
    parity?: "none" | "even" | "odd";
    bufferSize?: number;
    flowControl?: "none" | "hardware";
    xOnXOff?: boolean;
  }

  interface SerialPort {
    readable: ReadableStream<Uint8Array>;
    writable: WritableStream<Uint8Array>;
    open(options: SerialOptions): Promise<void>;
    close(): Promise<void>;
    getInfo(): SerialPortInfo;
  }

  interface Navigator {
    serial: {
      requestPort(options?: { filters?: SerialPortFilter[] }): Promise<SerialPort>;
      getPorts(): Promise<SerialPort[]>;
    };
  }
}

/* ────────────────────────────────────────────────────────────
   Serial Connection Types
   ──────────────────────────────────────────────────────────── */

export interface SerialMessage {
  timestamp: number;
  data: string;
  raw: Uint8Array;
}

export interface SerialConnectionConfig {
  baudRate: number;
  dataBits: number;
  parity: "none" | "even" | "odd";
  stopBits: number;
  xOnXOff: boolean;
  filters?: SerialPortFilter[];
  connectionTimeout?: number;
}

export interface SerialPortFilter {
  usbVendorId?: number;
  usbProductId?: number;
  serialNumber?: string;
  manufacturer?: string;
  product?: string;
}

export interface SerialPortInfo {
  productId?: number;
  vendorId?: number;
  manufacturer?: string;
  product?: string;
  serialNumber?: string;
  path?: string;
  isOpen: boolean;
  state: "detected" | "connecting" | "connected" | "error" | "disconnected";
}

export interface SerialConnectionState {
  info: SerialPortInfo | null;
  isListening: boolean;
  inputStream: ReadableStream<Uint8Array> | null;
  outputStream: WritableStream<Uint8Array> | null;
  error: string | null;
}

/* ────────────────────────────────────────────────────────────
   Serial Monitor Types
   ──────────────────────────────────────────────────────────── */

export interface SerialConnectionEvents {
  onStateChange: (state: SerialConnectionState) => void;
  onRawData: (data: Uint8Array) => void;
  onError: (error: Error) => void;
}

export interface SerialSession {
  id: string;
  portInfo: SerialPortInfo;
  messages: SerialMessage[];
  connectedAt: number;
  disconnectedAt: number | null;
}

/* ────────────────────────────────────────────────────────────
   Mock Serial Stream for Offline Simulation
   ──────────────────────────────────────────────────────────── */

export interface MockSerialConfig {
  deviceType: "esp32" | "esp32-s2" | "esp32-s3" | "esp8266" | "arduino" | "custom";
  crashScenario?: "watchdog" | "brownout" | "panic" | "stack_overflow" | "none";
  outputRate?: number;
  includeBanner?: boolean;
  customLogLines?: string[];
  simulateLatency?: number;
}

export class MockSerialStream {
  private buffer: string = "";
  private intervalId: number | null = null;
  private messageHandlers: ((data: SerialMessage) => void)[] = [];
  private isPaused: boolean = false;
  private portInfo: SerialPortInfo;
  private config: MockSerialConfig;
  private crashTriggered: boolean = false;

  constructor(config: MockSerialConfig) {
    this.config = config;
    this.portInfo = this.generatePortInfo();
  }

  private generatePortInfo(): SerialPortInfo {
    const vendorIds: Record<string, number> = {
      esp32: 0x303A,
      esp8266: 0x1A86,
      arduino: 0x2341,
    };

    const productNames: Record<string, string> = {
      esp32: "USB Serial Port",
      esp8266: "USB to Serial",
      arduino: "Arduino Uno",
      custom: "Custom Device",
    };

    const vendorId = vendorIds[this.config.deviceType] || 0x303A;
    const product = productNames[this.config.deviceType] || "USB Serial Port";
    const manufacturer = this.config.deviceType === "esp32" ? "Espressif" : "Unknown";

    return {
      vendorId,
      productId: 0x0001,
      manufacturer,
      product,
      serialNumber: `MOCK-${Date.now()}`,
      path: `COM${Math.floor(Math.random() * 10) + 1}`,
      isOpen: true,
      state: "connected",
    };
  }

  getPortInfo(): SerialPortInfo {
    return this.portInfo;
  }

  onMessage(handler: (data: SerialMessage) => void): () => void {
    this.messageHandlers.push(handler);
    return () => {
      const idx = this.messageHandlers.indexOf(handler);
      if (idx > -1) this.messageHandlers.splice(idx, 1);
    };
  }

  start(): void {
    if (this.intervalId) return;

    this.generateStartupBanner();
    const rate = this.config.outputRate || 10;
    const interval = 1000 / rate;

    this.intervalId = window.setInterval(() => {
      if (!this.isPaused) {
        this.generateRandomOutput();
      }
    }, interval);
  }

  stop(): void {
    if (this.intervalId) {
      window.clearInterval(this.intervalId);
      this.intervalId = null;
    }
  }

  pause(): void {
    this.isPaused = true;
  }

  resume(): void {
    this.isPaused = false;
  }

  private generateStartupBanner(): void {
    if (!this.config.includeBanner) return;

    const banner = [
      "================= ESP32 Boot ==================",
      `Boot: 2024-01-01 00:00:00`,
      `Chip: ESP32-D0WDQ6 (revision 1)`,
      `Crystal frequency: 40MHz`,
      `SPIRAM: disabled`,
      "===============================================",
      "",
    ];

    banner.forEach((line, index) => {
      setTimeout(() => {
        this.emitMessage(line + "\n");
      }, index * 50);
    });
  }

  private generateRandomOutput(): void {
    if (this.crashTriggered) {
      return;
    }

    const scenarios: Record<string, () => string[]> = {
      watchdog: () => this.generateWatchdogLog(),
      brownout: () => this.generateBrownoutLog(),
      panic: () => this.generatePanicLog(),
      stack_overflow: () => this.generateStackOverflowLog(),
      none: () => this.generateNormalLog(),
    };

    const generator = scenarios[this.config.crashScenario || "none"];
    const lines = generator();

    lines.forEach((line) => {
      this.emitMessage(line + "\n");
    });
  }

  private emitMessage(data: string): void {
    if (this.isPaused) return;

    const message: SerialMessage = {
      timestamp: Date.now(),
      data,
      raw: new TextEncoder().encode(data),
    };

    this.buffer += data;

    this.messageHandlers.forEach((handler) => {
      try {
        handler(message);
      } catch (e) {
        console.error("Error in message handler:", e);
      }
    });
  }

  getBuffer(): string {
    return this.buffer;
  }

  clearBuffer(): void {
    this.buffer = "";
  }

  triggerCrash(scenario: "watchdog" | "brownout" | "panic" | "stack_overflow" | "none" = "panic"): void {
    this.crashTriggered = true;

    const scenarios: Record<string, () => string[]> = {
      watchdog: () => this.generateWatchdogLog(),
      brownout: () => this.generateBrownoutLog(),
      panic: () => this.generatePanicLog(),
      stack_overflow: () => this.generateStackOverflowLog(),
      none: () => [],
    };

    const crashLines = scenarios[scenario]();
    crashLines.forEach((line) => {
      this.emitMessage(line + "\n");
    });
  }

  private generateWatchdogLog(): string[] {
    return [
      "ets_task_core: reset due to watchdog timeout",
      "ets_task_core: calling reset task reset 0x3ffb8000",
      "ets_sys: stack pointer 0x3ffb8000",
      "",
      "Guru Meditation Error: Core  0 panic! (IDF view is available at https://docs.espressif.com/projects/esp-idf/en/latest/esp32/api-guides/debugging/guru-meditation.html)",
      "WDT reset occurred",
    ];
  }

  private generateBrownoutLog(): string[] {
    return [
      "Brownout detector was triggered",
      "Reset reason: Brownout reset",
      "Guru Meditation Error: Core  0 panic! (Reset was caused by brownout)",
    ];
  }

  private generatePanicLog(): string[] {
    return [
      "Panic: 0x400D1234 (Abort routine)",
      "Waiting for core 0 to exit...",
      "Core  0 did not reset, waiting 15 seconds for manual reset",
      "Guru Meditation Error: Core  0 panic!",
    ];
  }

  private generateStackOverflowLog(): string[] {
    return [
      "Exception caused by breakpoint (TBE)",
      "Register dump:",
      "PC      : 0x40081234",
      "PS      : 0x81200000",
      "A1      : 0x3ffb8000",
      "...",
      "Backtrace: 0x40081234w 0x400D5678w |<-CFPoint",
    ];
  }

  private generateNormalLog(): string[] {
    const now = new Date();
    const timestamp = now.toISOString().replace("T", " ").substring(0, 19);

    const normalLines = [
      `[${timestamp}] System started`,
      `[${timestamp}] WiFi connected: 192.168.1.100`,
      `[${timestamp}] Task: Main loop running`,
      `[${timestamp}] Free heap: ${Math.floor(Math.random() * 20000) + 100000} bytes`,
    ];

    if (Math.random() < 0.1) {
      normalLines.push(`[${timestamp}] WARNING: Low memory condition`);
    }

    return normalLines;
  }

  destroy(): void {
    this.stop();
    this.messageHandlers.length = 0;
  }
}

/* ────────────────────────────────────────────────────────────
   Web Serial Connection Implementation
   ──────────────────────────────────────────────────────────── */

export interface SerialConnection extends SerialConnectionEvents {
  connect(config: SerialConnectionConfig, port?: SerialPort): Promise<void>;
  disconnect(): Promise<void>;
  write(data: string | Uint8Array): Promise<void>;
  close(): Promise<void>;
  getState(): SerialConnectionState;
}

export class WebSerialConnection implements SerialConnection {
  private port: SerialPort | null = null;
  private reader: ReadableStreamDefaultReader<Uint8Array> | null = null;
  private writer: WritableStreamDefaultWriter<Uint8Array> | null = null;
  private state: SerialConnectionState = {
    info: null,
    isListening: false,
    inputStream: null,
    outputStream: null,
    error: null,
  };
  private stateChangeCallbacks: ((state: SerialConnectionState) => void)[] = [];
  private dataCallbacks: ((data: SerialMessage) => void)[] = [];
  private errorCallbacks: ((error: Error) => void)[] = [];
  private readLoopActive: boolean = false;

  async connect(config: SerialConnectionConfig, port?: SerialPort): Promise<void> {
    try {
      this.updateState({ ...this.state, error: null });

      if (port) {
        this.port = port;
      } else {
        const options: SerialOptions = {
          baudRate: config.baudRate,
          dataBits: config.dataBits,
          parity: config.parity,
          stopBits: config.stopBits,
          xOnXOff: config.xOnXOff,
        };

        const serialPort = await navigator.serial.requestPort();
        this.port = serialPort;
        await this.port.open(options);
      }

      const portInfo: SerialPortInfo = {
        vendorId: this.port?.getInfo().usbVendorId,
        productId: this.port?.getInfo().usbProductId,
        manufacturer: this.port?.getInfo().manufacturer,
        product: this.port?.getInfo().product,
        serialNumber: this.port?.getInfo().serialNumber,
        isOpen: true,
        state: "connected",
      };

      const { readable, writable } = this.port;

      this.state = {
        info: portInfo,
        isListening: false,
        inputStream: readable,
        outputStream: writable,
        error: null,
      };

      this.reader = this.state.inputStream?.getReader() ?? null;
      this.writer = this.state.outputStream?.getWriter() ?? null;

      this.readLoopActive = true;
      this.startReadLoop();

      this.notifyStateChange();
    } catch (error) {
      const err = error as Error;
      this.state = { ...this.state, error: err.message };
      this.notifyStateChange();
      this.notifyError(err);
      throw error;
    }
  }

  async disconnect(): Promise<void> {
    this.readLoopActive = false;

    if (this.reader) {
      try {
        this.reader.cancel();
      } catch {
      }
      this.reader = null;
    }

    if (this.writer) {
      try {
        await this.writer.close();
      } catch {
      }
      this.writer = null;
    }

    if (this.port) {
      try {
        await this.port.close();
      } catch {
      }
      this.port = null;
    }

    this.state = {
      info: null,
      isListening: false,
      inputStream: null,
      outputStream: null,
      error: null,
    };

    this.notifyStateChange();
  }

  async write(data: string | Uint8Array): Promise<void> {
    if (!this.writer || this.readLoopActive === false) {
      throw new Error("Serial port not open or not listening");
    }

    const bytes = typeof data === "string"
      ? new TextEncoder().encode(data)
      : data;

    await this.writer!.write(bytes);
  }

  async close(): Promise<void> {
    await this.disconnect();
  }

  getState(): SerialConnectionState {
    return this.state;
  }

  onStateChange: (state: SerialConnectionState) => void = () => {};

  onRawData: (data: Uint8Array) => void = () => {};

  onError: (error: Error) => void = () => {};

  private startReadLoop(): void {
    if (!this.reader || !this.readLoopActive) return;

    const read = async () => {
      if (!this.readLoopActive) return;

      try {
        const { done, value } = await this.reader!.read();

        if (done) {
          this.readLoopActive = false;
          return;
        }

        this.notifyRawData(value);
        read();
      } catch (error) {
        if (this.readLoopActive) {
          const err = error as Error;
          this.state = { ...this.state, error: err.message };
          this.notifyStateChange();
          this.notifyError(err);
        }
      }
    };

    read();
  }

  private notifyStateChange(): void {
    this.onStateChange(this.state);
    this.stateChangeCallbacks.forEach(cb => cb(this.state));
  }

  private notifyRawData(data: Uint8Array): void {
    this.onRawData(data);
    this.dataCallbacks.forEach(cb => {
      cb({
        timestamp: Date.now(),
        data: new TextDecoder().decode(data),
        raw: data,
      });
    });
  }

  private notifyError(error: Error): void {
    this.onError(error);
    this.errorCallbacks.forEach(cb => cb(error));
  }

  private updateState(newState: SerialConnectionState): void {
    this.state = newState;
    this.notifyStateChange();
  }
}

/* ────────────────────────────────────────────────────────────
   Mock Serial Implementation for Testing
   ──────────────────────────────────────────────────────────── */

export interface MockSerialConnection extends SerialConnection {
  start(): void;
  stop(): void;
  pause(): void;
  resume(): void;
  clearBuffer(): void;
  getBuffer(): string;
  triggerCrash(scenario?: "watchdog" | "brownout" | "panic" | "stack_overflow" | "none"): void;
}

export class MockSerialConnectionImpl implements MockSerialConnection {
  private mockStream: MockSerialStream;
  private messageHandlers: ((data: SerialMessage) => void)[] = [];
  private state: SerialConnectionState;

  constructor(config: MockSerialConfig) {
    this.mockStream = new MockSerialStream(config);
    this.state = {
      info: this.mockStream.getPortInfo(),
      isListening: false,
      inputStream: null,
      outputStream: null,
      error: null,
    };
  }

  async connect(_config?: SerialConnectionConfig): Promise<void> {
    this.state.isListening = true;
    this.mockStream.start();

    const unpatch = this.mockStream.onMessage((message) => {
      this.messageHandlers.forEach(h => h(message));
    });
    (this as Record<string, unknown>)._cleanup = unpatch;
  }

  async disconnect(): Promise<void> {
    if (this.state.isListening) {
      this.state.isListening = false;
    }
    this.mockStream.stop();
    const cleanup = (this as Record<string, unknown>)._cleanup;
    if (typeof cleanup === "function") {
      cleanup();
    }
  }

  async write(_data: string | Uint8Array): Promise<void> {
    // Mock doesn't support write
  }

  async close(): Promise<void> {
    await this.disconnect();
  }

  getState(): SerialConnectionState {
    return this.state;
  }

  onStateChange: (state: SerialConnectionState) => void = () => {};

  onRawData: (data: Uint8Array) => void = () => {};

  onError: (error: Error) => void = () => {};

  start(): void {
    if (!this.state.isListening) {
      this.mockStream.start();
      this.state.isListening = true;
    }
  }

  stop(): void {
    this.mockStream.stop();
    this.state.isListening = false;
  }

  pause(): void {
    this.mockStream.pause();
  }

  resume(): void {
    this.mockStream.resume();
  }

  clearBuffer(): void {
    this.mockStream.clearBuffer();
  }

  getBuffer(): string {
    return this.mockStream.getBuffer();
  }

  triggerCrash(scenario: "watchdog" | "brownout" | "panic" | "stack_overflow" | "none" = "panic"): void {
    this.mockStream.triggerCrash(scenario);
  }
}

/* ────────────────────────────────────────────────────────────
   Crash Type Enum
   ──────────────────────────────────────────────────────────── */

export enum CrashType {
  GURU_MEDITATION = "guru_meditation",
  WATCHDOG = "watchdog",
  BROWNOUT = "brownout",
  PANIC = "panic",
  STACK_OVERFLOW = "stack_overflow",
  ASSERTION = "assertion",
  UNKNOWN = "unknown",
}

/* ────────────────────────────────────────────────────────────
   ESP32 Crash Log Parser (Backend Service)
   ──────────────────────────────────────────────────────────── */

export interface CrashFrame {
  function?: string;
  offset?: number;
  module?: string;
}

export interface CrashBacktrace {
  frames: CrashFrame[];
  full: string;
}

export interface CrashAnalysis {
  type: "guru_meditation" | "watchdog" | "brownout" | "panic" | "stack_overflow" | "assertion" | "unknown";
  reason?: string;
  crash?: string;
  registers?: Record<string, string>;
  backtrace?: CrashBacktrace;
  likelyCause: string;
  suggestedActions: string[];
  rawLog: string;
}

/**
 * Parse ESP32 crash log and extract structured information
 */
export function parseESP32CrashLog(log: string): CrashAnalysis | null {
  const logLower = log.toLowerCase();

  // Watchdog Timeout - check first as it's a specific reset cause
  if (logLower.includes("watchdog") && logLower.includes("timeout")) {
    return {
      type: "watchdog",
      reason: "Watchdog timer triggered",
      crash: "Task watchdog was triggered",
      likelyCause: "Task blocked too long - ISR took too long or task hung",
      suggestedActions: [
        "Reduce time spent in ISR or critical sections",
        "Check for infinite loops or very slow operations",
        "Increase watchdog timeout in menuconfig if processing needs time",
        "Use xTaskNotify or semaphores for inter-task communication",
      ],
      rawLog: log,
    };
  }

  // Brownout Reset - check before guru meditation as it's a specific reset cause
  if (logLower.includes("brownout") || logLower.includes("reset") && logLower.includes("power")) {
    return {
      type: "brownout",
      reason: "Brownout detector triggered",
      crash: "Reset caused by power supply instability",
      likelyCause: "Voltage dropped below brownout threshold",
      suggestedActions: [
        "Check power supply stability and decoupling capacitors",
        "Verify VCC is within specifications",
        "Add bulk capacitors near VCC",
        "Check for noisy peripherals causing power spikes",
      ],
      rawLog: log,
    };
  }

  // Panic - check for specific "Panic: 0x..." pattern before guru meditation
  if (log.match(/Panic:\s*0x[0-9a-fA-F]+/)) {
    const panicMatch = log.match(/Panic:\s*(0x[0-9a-fA-F]+)/);
    return {
      type: "panic",
      reason: "Runtime panic occurred",
      crash: panicMatch?.[1] || "Unknown",
      likelyCause: "Unhandled exception or abort in firmware",
      suggestedActions: [
        "Decode panic reason from register dump",
        "Check for null pointer dereference or invalid memory access",
        "Review assertion failures or abort() calls",
      ],
      rawLog: log,
    };
  }

  // Stack Overflow
  if (logLower.includes("stack overflow") || logLower.includes("abort") || logLower.includes("frame")) {
    return {
      type: "stack_overflow",
      reason: "Stack overflow or corruption detected",
      crash: "Task stack overflow",
      likelyCause: "Stack size insufficient or corrupted stack",
      suggestedActions: [
        "Increase task stack size in CONFIG_xxx_TASK_STACK_SIZE",
        "Check for recursive function calls",
        "Use uxTaskGetStackHighWaterMark to monitor stack usage",
      ],
      rawLog: log,
    };
  }

  // Assertion Failure
  if (logLower.includes("assertion") || logLower.includes("assert")) {
    const assertMatch = log.match(/assertion.*failed:(.+)/i);
    return {
      type: "assertion",
      reason: "Runtime assertion failed",
      crash: assertMatch?.[1]?.trim(),
      likelyCause: "Debug assertion hit in firmware",
      suggestedActions: [
        "Fix the failed assertion condition",
        "Check preconditions before the assertion point",
        "Enable configASSERT to get more details",
      ],
      rawLog: log,
    };
  }

  // Guru Meditation Error - check after specific crash types
  if (logLower.includes("guru meditation error")) {
    const guruMatch = log.match(/Guru Meditation Error.*?:\s*(.+?)(?:\n|$)/i);
    const reasonMatch = log.match(/reason:\s*(.+?)(?:\n|$)/i);

    return {
      type: "guru_meditation",
      reason: reasonMatch?.[1]?.trim(),
      crash: guruMatch?.[1]?.trim(),
      likelyCause: "Fatal exception occurred - check backtrace and core dump",
      suggestedActions: [
        "Decode backtrace using addr2line or ESP-IDF's xtensa-esp32-elf-addr2line",
        "Check crash registers for fault cause (EXCCAUSE, EXCVADDR)",
        "Analyze stack overflow or null pointer dereference",
      ],
      rawLog: log,
    };
  }

  // Unknown crash type
  return {
    type: "unknown",
    reason: "Unknown crash type",
    likelyCause: "Unrecognized crash signature - requires manual analysis",
    suggestedActions: [
      "Decode backtrace using addr2line",
      "Check for patterns in crash frequency",
      "Add debug logging before suspected code",
    ],
    rawLog: log,
  };
}

/**
 * Parse backtrace from crash log
 */
export function parseBacktrace(log: string): CrashBacktrace | null {
  const backtraceMatch = log.match(/Backtrace:\s*(.+)/);
  if (!backtraceMatch) return null;

  const backtraceStr = backtraceMatch[1];
  const frameTokens = backtraceStr.match(/0x[0-9a-fA-F]+/g);

  if (!frameTokens || frameTokens.length === 0) return null;

  const frames: CrashFrame[] = [];
  for (let i = 0; i < frameTokens.length; i += 2) {
    if (i + 1 < frameTokens.length) {
      frames.push({
        offset: parseInt(frameTokens[i], 16),
        module: frameTokens[i + 1],
      });
    }
  }

  return {
    frames,
    full: backtraceStr,
  };
}

/**
 * Classify serial log into typed events for AI analysis
 */
export interface SerialLogEvent {
  event_type: string;
  severity: "critical" | "high" | "medium" | "low" | "info";
  is_repeated: boolean;
  repeat_count?: number | null;
  timestamp?: string | null;
  message: string;
  evidence: string;
  likely_cause?: string | null;
  suggested_action?: string | null;
}

export function classifySerialLogEvents(log: string): SerialLogEvent[] {
  const events: SerialLogEvent[] = [];
  const lines = log.split("\n").filter(l => l.trim());

  for (const line of lines) {
    const event = classifyLogLine(line);
    if (event) events.push(event);
  }

  return events;
}

function classifyLogLine(line: string): SerialLogEvent | null {
  const timestampMatch = line.match(/\[(\d+\.?\d*[a-z]?)\s*(?:s|ms)\]|(\d{2}:\d{2}:\d{2}\.\d{3})/i);
  const timestamp = timestampMatch ? (timestampMatch[1] || timestampMatch[2]) : null;

  const lower = line.toLowerCase();

  if (lower.includes("guru meditation") || lower.includes("panic")) {
    return {
      event_type: "crash_fault",
      severity: "critical",
      is_repeated: false,
      timestamp,
      message: "ESP32 crash detected",
      evidence: line,
      likely_cause: "Fatal exception in firmware execution",
      suggested_action: "Check backtrace and crash registers",
    };
  }

  if (lower.includes("watchdog")) {
    return {
      event_type: "watchdog_reset",
      severity: "critical",
      is_repeated: false,
      timestamp,
      message: "Watchdog timer triggered",
      evidence: line,
      likely_cause: "Task blocked too long or ISR took too much time",
      suggested_action: "Reduce blocking operations or increase watchdog timeout",
    };
  }

  if (lower.includes("brownout")) {
    return {
      event_type: "brownout_reset",
      severity: "critical",
      is_repeated: false,
      timestamp,
      message: "Brownout detector triggered",
      evidence: line,
      likely_cause: "Power supply voltage dropped below threshold",
      suggested_action: "Check power supply stability and add decoupling",
    };
  }

  if (lower.includes("heap") && (lower.includes("error") || lower.includes("overflow"))) {
    return {
      event_type: "runtime_error",
      severity: "high",
      is_repeated: false,
      timestamp,
      message: "Heap memory error",
      evidence: line,
      likely_cause: "Memory corruption or allocation failure",
      suggested_action: "Check malloc/free pairs and buffer sizes",
    };
  }

  if (lower.includes("task") && lower.includes("exception")) {
    return {
      event_type: "runtime_error",
      severity: "high",
      is_repeated: false,
      timestamp,
      message: "Task exception occurred",
      evidence: line,
      likely_cause: "Task encountered an error condition",
      suggested_action: "Check task function and error handling",
    };
  }

  if (lower.includes("warning")) {
    return {
      event_type: "warning",
      severity: "medium",
      is_repeated: false,
      timestamp,
      message: "Runtime warning",
      evidence: line,
      likely_cause: null,
      suggested_action: "Review warning for potential issues",
    };
  }

  return null;
}

/* ────────────────────────────────────────────────────────────
   Default Configurations
   ──────────────────────────────────────────────────────────── */

export const ESP32_PORT_FILTERS: SerialPortFilter[] = [
  { usbVendorId: 0x303A, product: "USB Serial Port" },
  { usbVendorId: 0x2341, product: "Arduino*" },
  { usbVendorId: 0x1A86, product: "USB Serial" },
];

export const DEFAULT_CONFIGS = {
  ESP32_DEFAULT: {
    baudRate: 115200,
    dataBits: 8,
    parity: "none" as const,
    stopBits: 1,
    xOnXOff: false,
  },
  ESP32_SLOW: {
    baudRate: 9600,
    dataBits: 8,
    parity: "none" as const,
    stopBits: 1,
    xOnXOff: false,
  },
  ESP8266: {
    baudRate: 74880,
    dataBits: 8,
    parity: "none" as const,
    stopBits: 1,
    xOnXOff: false,
  },
  ARDUINO_SLOW: {
    baudRate: 9600,
    dataBits: 8,
    parity: "none" as const,
    stopBits: 1,
    xOnXOff: false,
  },
} as const;