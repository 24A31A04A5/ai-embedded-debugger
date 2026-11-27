"use client";

import React, { useEffect, useRef, useState } from "react";
import {
  Code,
  Copy,
  FileDown,
  Heart,
  PlayCircle,
  RotateCcw,
  StopCircle,
} from "lucide-react";

import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { CodeEditor } from "@/components/CodeEditor";

import {
  type MockSerialConfig,
  MockSerialConnectionImpl,
  type MockSerialConnection,
  WebSerialConnection,
  type SerialConnection,
  ESP32_PORT_FILTERS,
  type SerialConnectionConfig,
  parseESP32CrashLog,
  type CrashAnalysis,
} from "@/lib/serial-service";

// Simple inline Label component
const Label = ({ children, ...props }: React.LabelHTMLAttributes<HTMLLabelElement>) => (
  <label className="text-xs font-medium text-muted-foreground leading-none" {...props}>
    {children}
  </label>
);

// Simple inline toast hook replacement
const useToast = () => {
  const [toast, setToast] = useState<{
    title: string;
    description: string;
    open: boolean;
  }>({ title: "", description: "", open: false });

  const toastFn = ({ title, description }: { title: string; description?: string }) => {
    setToast({ title, description: description || "", open: true });
    setTimeout(() => {
      setToast((t) => ({ ...t, open: false }));
    }, 3000);
  };

  return { toast, toastFn };
};

interface SerialMonitorProps {
  onChange?: (v: string) => void;
  isMockMode?: boolean;
  deviceType?: string;
  crashScenario?: "watchdog" | "brownout" | "panic" | "stack_overflow" | "none";
  className?: string;
}

export function SerialMonitor({
  onChange,
  isMockMode = true,
  deviceType = "esp32",
  crashScenario = "none",
  className = "",
}: SerialMonitorProps) {
  const [connection, setConnection] = useState<MockSerialConnection | SerialConnection | null>(null);
  const [portInfo, setPortInfo] = useState<string>("Not connected");
  const [isListening, setIsListening] = useState(false);
  const [baudRate, setBaudRate] = useState(115200);
  const [outputRate, setOutputRate] = useState(10);
  const [showCrashAnalysis, setShowCrashAnalysis] = useState(false);
  const [crashAnalysis, setCrashAnalysis] = useState<CrashAnalysis | null>(null);
  const [connectionError, setConnectionError] = useState<string | null>(null);
  const { toastFn } = useToast();

  const serialRef = useRef<MockSerialConnection | SerialConnection | null>(null);
  const bufferRef = useRef<string>("");

  // Initialize mock connection on mount (if in mock mode)
  useEffect(() => {
    if (isMockMode) {
      const mockConfig: MockSerialConfig = {
        deviceType: deviceType as MockSerialConfig["deviceType"],
        crashScenario,
        outputRate,
        includeBanner: true,
      };

      const mockConnection = new MockSerialConnectionImpl(mockConfig) as MockSerialConnection;

      mockConnection.onRawData = (data: Uint8Array) => {
        const decoded = new TextDecoder().decode(data);
        bufferRef.current += decoded;
        if (onChange) {
          onChange(bufferRef.current);
        }

        // Auto-scroll to bottom
        const event = new CustomEvent("serialDataReceived");
        window.dispatchEvent(event);
      };

      mockConnection.onStateChange = (state: Parameters<MockSerialConnection["onStateChange"]>[0]) => {
        setIsListening(state.isListening);
        if (!state.info?.isOpen) {
          setPortInfo("Not connected");
        } else {
          const info = state.info;
          setPortInfo(`${info.manufacturer || ""} ${info.product || "Unknown Device"} (${info.path || "Port"}`);
        }
      };

      mockConnection.onError = (err: Error) => {
        setConnectionError(err.message);
        toastFn({
          title: "Connection Error",
          description: err.message,
        });
      };

      const info = mockConnection.getState().info;
      if (info) {
        setPortInfo(`${info.manufacturer || "Espressif"} ${info.product || "Unknown Device"} (${info.path || "Port"}`);
      }

      serialRef.current = mockConnection;
      setConnection(mockConnection);
      mockConnection.start();
    }
  }, [isMockMode, deviceType, crashScenario, outputRate, onChange, toastFn]);

  // Connect to real serial port (browser-only)
  const handleConnect = async () => {
    if (!navigator.serial) {
      setConnectionError("Web Serial API not supported in this browser");
      toastFn({
        title: "Not Supported",
        description: "Web Serial API is not available in your browser. Use Chrome, Edge, or Opera.",
      });
      return;
    }

    try {
      const config: SerialConnectionConfig = {
        baudRate,
        dataBits: 8,
        parity: "none",
        stopBits: 1,
        xOnXOff: false,
        filters: ESP32_PORT_FILTERS,
      };

      const conn = new WebSerialConnection();

      conn.onRawData = (data: Uint8Array) => {
        const decoded = new TextDecoder().decode(data);
        bufferRef.current += decoded;
        if (onChange) {
          onChange(bufferRef.current);
        }

        const event = new CustomEvent("serialDataReceived");
        window.dispatchEvent(event);
      };

      conn.onStateChange = (state) => {
        setIsListening(state.isListening);
        const info = state.info;
        if (info) {
          setPortInfo(`${info.manufacturer || ""} ${info.product || "Unknown Device"} (${info.serialNumber || info.product || "Port"})`);
        } else {
          setPortInfo("Not connected");
        }
      };

      conn.onError = (err: Error) => {
        setConnectionError(err.message);
        toastFn({
          title: "Connection Error",
          description: err.message,
        });
      };

      await conn.connect(config);

      const info = conn.getState().info;
      if (info) {
        setPortInfo(`${info.manufacturer || ""} ${info.product || "Unknown Device"} (${info.serialNumber || "Port"})`);
      }

      serialRef.current = conn;
      setConnection(conn);
      setIsListening(true);
    } catch (err) {
      setConnectionError((err as Error).message);
      toastFn({
        title: "Connection Failed",
        description: (err as Error).message,
      });
    }
  };

  const handleDisconnect = async () => {
    if (serialRef.current) {
      await serialRef.current.disconnect();
    }
    serialRef.current = null;
    setConnection(null);
    setIsListening(false);
    setPortInfo("Not connected");
  };

  // For mock mode, use start/stop; for real serial, connection is always "listening"
  const handleStart = () => {
    if (serialRef.current && isMockMode) {
      (serialRef.current as MockSerialConnection).start();
      setIsListening(true);
    }
  };

  const handleStop = () => {
    if (serialRef.current && isMockMode) {
      (serialRef.current as MockSerialConnection).stop();
      setIsListening(false);
    }
  };

  const handleClear = () => {
    bufferRef.current = "";
    if (onChange) {
      onChange("");
    }
  };

  const handleCopy = async () => {
    await navigator.clipboard.writeText(bufferRef.current);
    toastFn({
      title: "Copied",
      description: "Serial logs copied to clipboard",
    });
  };

  const handleDownload = () => {
    const blob = new Blob([bufferRef.current], { type: "text/plain" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = `serial-logs-${new Date().toISOString().split("T")[0]}.txt`;
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
    URL.revokeObjectURL(url);
  };

  const handleTriggerCrash = () => {
    if (serialRef.current && isMockMode) {
      (serialRef.current as MockSerialConnection).triggerCrash("panic");
    }
  };

  const handleAnalyzeCrash = () => {
    const analysis = parseESP32CrashLog(bufferRef.current);
    if (analysis) {
      setCrashAnalysis(analysis);
      setShowCrashAnalysis(true);
    } else {
      toastFn({
        title: "No crash found",
        description: "Paste a crash log first",
      });
    }
  };

  return (
    <div className={`flex flex-col h-full ${className}`}>
      {/* Connection Controls */}
      <div className="flex items-center justify-between p-3 bg-muted/30 border-b border-border/30">
        <div className="flex items-center gap-3">
          <div className="text-sm">
            <div className="font-medium text-foreground">{portInfo}</div>
            <div className="text-xs text-muted-foreground">
              {isListening ? "Streaming..." : "Stopped"}
            </div>
          </div>

          <div className="flex items-center gap-2">
            <Label htmlFor="baud-rate" className="text-xs mr-1">Baud:</Label>
            <Input
              id="baud-rate"
              type="number"
              value={baudRate}
              onChange={(e) => setBaudRate(Number(e.target.value))}
              className="w-20 h-6 text-xs"
              disabled={isListening || (!isMockMode && !!connection)}
            />
            <span className="text-xs text-muted-foreground">bps</span>
          </div>

          {isMockMode && (
            <>
              <Label htmlFor="output-rate" className="text-xs mr-1">Rate:</Label>
              <Input
                id="output-rate"
                type="number"
                value={outputRate}
                onChange={(e) => setOutputRate(Number(e.target.value))}
                className="w-16 h-6 text-xs"
              />
              <span className="text-xs text-muted-foreground">msg/s</span>
            </>
          )}
        </div>

        <div className="flex items-center gap-2">
          {!isMockMode && (
            <>
              {!isListening ? (
                <Button
                  size="sm"
                  variant="outline"
                  onClick={connection ? handleDisconnect : handleConnect}
                  className="h-7 px-3 text-xs"
                >
                  {connection ? "Disconnect" : "Connect Device"}
                </Button>
              ) : (
                <Button
                  size="sm"
                  variant="outline"
                  onClick={handleDisconnect}
                  className="h-7 px-3 text-xs"
                >
                  Disconnect
                </Button>
              )}
            </>
          )}

          {isListening && (
            <Button
              size="sm"
              variant="ghost"
              onClick={handleStop}
              className="h-7 px-2 text-xs"
            >
              <StopCircle className="h-3 w-3 mr-1" />
              Stop
            </Button>
          )}

          {!isListening && connection && (
            <Button
              size="sm"
              variant="ghost"
              onClick={handleStart}
              className="h-7 px-2 text-xs"
            >
              <PlayCircle className="h-3 w-3 mr-1" />
              Start
            </Button>
          )}
        </div>
      </div>

      {/* Action Buttons */}
      <div className="flex items-center gap-1 p-2 bg-muted/20 border-b border-border/30">
        <Button
          size="sm"
          variant="ghost"
          onClick={handleClear}
          className="h-6 px-2 text-xs"
          disabled={!bufferRef.current}
        >
          <RotateCcw className="h-3 w-3 mr-1" />
          Clear
        </Button>

        <Button
          size="sm"
          variant="ghost"
          onClick={handleCopy}
          className="h-6 px-2 text-xs"
          disabled={!bufferRef.current}
        >
          <Copy className="h-3 w-3 mr-1" />
          Copy
        </Button>

        <Button
          size="sm"
          variant="ghost"
          onClick={handleDownload}
          className="h-6 px-2 text-xs"
          disabled={!bufferRef.current}
        >
          <FileDown className="h-3 w-3 mr-1" />
          Save
        </Button>

        <div className="flex-1" />

        {isMockMode && (
          <Button
            size="sm"
            variant="ghost"
            onClick={handleTriggerCrash}
            className="h-6 px-2 text-xs"
            title="Simulate crash for testing"
          >
            <Heart className="h-3 w-3 text-red-500 mr-1" />
            Trigger Crash
          </Button>
        )}

        {bufferRef.current && (
          <Button
            size="sm"
            variant="ghost"
            onClick={handleAnalyzeCrash}
            className="h-6 px-2 text-xs"
            title="Analyze crash log"
          >
            <Code className="h-3 w-3 mr-1" />
            Analyze
          </Button>
        )}
      </div>

      {/* Main Output Area */}
      <div className="flex-1 overflow-hidden">
        <CodeEditor
          value={bufferRef.current}
          onChange={() => {}}
          language="text"
        />
      </div>

      {/* Crash Analysis Modal */}
      {showCrashAnalysis && crashAnalysis && (
        <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50 p-4"
             onClick={() => setShowCrashAnalysis(false)}>
          <Card className="max-w-2xl w-full max-h-[90vh] flex flex-col"
                onClick={(e) => e.stopPropagation()}>
            <CardHeader>
              <CardTitle>ESP32 Crash Analysis</CardTitle>
            </CardHeader>
            <CardContent className="flex-1 overflow-auto">
              <div className="space-y-3">
                <div>
                  <h4 className="font-medium text-sm">Crash Type</h4>
                  <p className="text-sm text-muted-foreground">{crashAnalysis.type.replace("_", " ").toUpperCase()}</p>
                </div>

                <div>
                  <h4 className="font-medium text-sm">Likely Cause</h4>
                  <p className="text-sm">{crashAnalysis.likelyCause}</p>
                </div>

                {crashAnalysis.reason && (
                  <div>
                    <h4 className="font-medium text-sm">Reason</h4>
                    <p className="text-sm text-muted-foreground">{crashAnalysis.reason}</p>
                  </div>
                )}

                {crashAnalysis.suggestedActions && crashAnalysis.suggestedActions.length > 0 && (
                  <div>
                    <h4 className="font-medium text-sm">Suggested Actions</h4>
                    <ul className="text-sm list-disc list-inside text-muted-foreground">
                      {crashAnalysis.suggestedActions.map((action, i) => (
                        <li key={i}>{action}</li>
                      ))}
                    </ul>
                  </div>
                )}

                {crashAnalysis.registers && (
                  <div>
                    <h4 className="font-medium text-sm">Registers</h4>
                    <pre className="text-xs bg-muted/30 p-2 rounded">
                      {JSON.stringify(crashAnalysis.registers, null, 2)}
                    </pre>
                  </div>
                )}
              </div>
            </CardContent>
            <div className="p-3 border-t border-border/30">
              <Button
                size="sm"
                variant="outline"
                onClick={() => setShowCrashAnalysis(false)}
              >
                Close
              </Button>
            </div>
          </Card>
        </div>
      )}

      {connectionError && !connectionError.includes("API not supported") && (
        <div className="fixed top-4 right-4 z-[100] p-4 w-full max-w-sm">
          <Card className="bg-destructive text-destructive-foreground border-destructive shadow-lg">
            <CardHeader>
              <CardTitle>Error</CardTitle>
            </CardHeader>
            <CardContent>
              <p className="text-sm">{connectionError}</p>
              <Button
                size="sm"
                variant="outline"
                className="mt-2"
                onClick={() => setConnectionError(null)}
              >
                Dismiss
              </Button>
            </CardContent>
          </Card>
        </div>
      )}
    </div>
  );
}