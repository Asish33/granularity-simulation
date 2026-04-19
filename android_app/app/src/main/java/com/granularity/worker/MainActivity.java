package com.granularity.worker;

import android.os.BatteryManager;
import android.os.Bundle;
import android.os.Handler;
import android.os.Looper;
import android.content.Context;
import android.content.Intent;
import android.content.IntentFilter;
import android.widget.Button;
import android.widget.EditText;
import android.widget.TextView;
import android.widget.ScrollView;
import androidx.appcompat.app.AppCompatActivity;
import org.json.JSONObject;
import org.json.JSONArray;
import java.io.*;
import java.net.*;
import java.util.UUID;
import java.util.concurrent.ExecutorService;
import java.util.concurrent.Executors;

public class MainActivity extends AppCompatActivity {

    // ── UI Elements ──────────────────────────────────────────
    EditText etServerIP, etPhoneName;
    Button btnConnect, btnDisconnect;
    TextView tvStatus, tvLog, tvStats;
    ScrollView scrollLog;

    // ── State ─────────────────────────────────────────────────
    String serverIP = "";
    String workerID = UUID.randomUUID().toString();
    String phoneName = "Phone-Worker";
    boolean connected = false;
    boolean running = false;

    int tasksCompleted = 0;
    int tasksFailed = 0;
    long totalComputeMs = 0;

    Handler mainHandler = new Handler(Looper.getMainLooper());
    ExecutorService executor = Executors.newFixedThreadPool(3);

    // ── Activity Lifecycle ────────────────────────────────────
    @Override
    protected void onCreate(Bundle savedInstanceState) {
        super.onCreate(savedInstanceState);
        setContentView(R.layout.activity_main);

        etServerIP   = findViewById(R.id.etServerIP);
        etPhoneName  = findViewById(R.id.etPhoneName);
        btnConnect   = findViewById(R.id.btnConnect);
        btnDisconnect= findViewById(R.id.btnDisconnect);
        tvStatus     = findViewById(R.id.tvStatus);
        tvLog        = findViewById(R.id.tvLog);
        tvStats      = findViewById(R.id.tvStats);
        scrollLog    = findViewById(R.id.scrollLog);

        // Default phone name from device name
        phoneName = android.os.Build.MODEL;
        etPhoneName.setText(phoneName);

        btnConnect.setOnClickListener(v -> connectToCluster());
        btnDisconnect.setOnClickListener(v -> disconnectFromCluster());

        setStatus("OFFLINE", "#ff6b35");
        appendLog("Welcome! Enter your PC's IP address and tap CONNECT.");
        appendLog("Make sure your phone and PC are on the same Wi-Fi.");
    }

    @Override
    protected void onDestroy() {
        super.onDestroy();
        running = false;
        executor.shutdown();
    }

    // ── Connection ────────────────────────────────────────────
    void connectToCluster() {
        serverIP  = etServerIP.getText().toString().trim();
        phoneName = etPhoneName.getText().toString().trim();

        if (serverIP.isEmpty()) {
            appendLog("❌ Please enter the PC's IP address first.");
            return;
        }

        setStatus("CONNECTING...", "#ffcc00");
        appendLog("Connecting to " + serverIP + ":5000 ...");

        executor.execute(() -> {
            try {
                // Register with server
                JSONObject payload = new JSONObject();
                payload.put("worker_id", workerID);
                payload.put("name", phoneName);
                payload.put("cpu_mips", estimateCPUMips());
                payload.put("battery", getBatteryLevel());

                String response = httpPost("http://" + serverIP + ":5000/register", payload.toString());
                JSONObject resp = new JSONObject(response);

                if ("ok".equals(resp.getString("status"))) {
                    connected = true;
                    running = true;
                    mainHandler.post(() -> {
                        setStatus("CONNECTED – IDLE", "#7fff6e");
                        appendLog("✅ Registered with cluster!");
                        appendLog("Worker ID: " + workerID.substring(0, 8) + "…");
                        appendLog("Waiting for tasks from server…");
                        btnConnect.setEnabled(false);
                        btnDisconnect.setEnabled(true);
                    });
                    // Start background loops
                    executor.execute(this::heartbeatLoop);
                    executor.execute(this::taskPollLoop);
                }
            } catch (Exception e) {
                mainHandler.post(() -> {
                    setStatus("CONNECTION FAILED", "#ff4444");
                    appendLog("❌ Could not connect: " + e.getMessage());
                    appendLog("Check: Is server.py running on PC? Same Wi-Fi?");
                });
            }
        });
    }

    void disconnectFromCluster() {
        running = false;
        connected = false;
        setStatus("OFFLINE", "#ff6b35");
        appendLog("Disconnected from cluster.");
        btnConnect.setEnabled(true);
        btnDisconnect.setEnabled(false);
    }

    // ── Heartbeat Loop (every 3 seconds) ─────────────────────
    void heartbeatLoop() {
        while (running) {
            try {
                JSONObject hb = new JSONObject();
                hb.put("worker_id", workerID);
                hb.put("battery", getBatteryLevel());
                hb.put("status", "idle");
                httpPost("http://" + serverIP + ":5000/heartbeat", hb.toString());
                Thread.sleep(3000);
            } catch (Exception e) {
                try { Thread.sleep(5000); } catch (Exception ignored) {}
            }
        }
    }

    // ── Task Poll Loop (every 1 second) ──────────────────────
    void taskPollLoop() {
        while (running) {
            try {
                String response = httpGet("http://" + serverIP + ":5000/get_task/" + workerID);
                JSONObject resp = new JSONObject(response);

                if (resp.getBoolean("has_task")) {
                    JSONObject subtask = resp.getJSONObject("subtask");
                    String jobId = resp.getString("job_id");
                    executeSubtask(jobId, subtask);
                } else {
                    Thread.sleep(1000);
                }
            } catch (Exception e) {
                try { Thread.sleep(2000); } catch (Exception ignored) {}
            }
        }
    }

    // ── Task Execution Engine ─────────────────────────────────
    void executeSubtask(String jobId, JSONObject subtask) {
        try {
            String type = subtask.getString("type");
            int subtaskId = subtask.getInt("subtask_id");
            double G = subtask.getDouble("granularity");

            mainHandler.post(() -> {
                setStatus("COMPUTING – G=" + G, "#00d4ff");
                appendLog("▶ Task #" + subtaskId + " | Type: " + type + " | G=" + G);
            });

            long startTime = System.currentTimeMillis();
            long resultSize = 0;

            if ("matrix".equals(type)) {
                resultSize = computeMatrix(subtask);
            } else if ("image".equals(type)) {
                resultSize = computeImage(subtask);
            }

            long computeMs = System.currentTimeMillis() - startTime;

            // Submit result to server
            JSONObject result = new JSONObject();
            result.put("job_id", jobId);
            result.put("subtask_id", subtaskId);
            result.put("worker_id", workerID);
            result.put("computation_time_ms", computeMs);
            result.put("result_size_bytes", resultSize);

            httpPost("http://" + serverIP + ":5000/submit_result", result.toString());

            tasksCompleted++;
            totalComputeMs += computeMs;

            mainHandler.post(() -> {
                setStatus("CONNECTED – IDLE", "#7fff6e");
                appendLog("✅ Done #" + subtaskId + " in " + computeMs + "ms (G=" + G + ")");
                updateStats();
            });

        } catch (Exception e) {
            tasksFailed++;
            mainHandler.post(() -> {
                setStatus("CONNECTED – IDLE", "#7fff6e");
                appendLog("❌ Task failed: " + e.getMessage());
            });
        }
    }

    // ── Matrix Multiplication Task ────────────────────────────
    long computeMatrix(JSONObject subtask) throws Exception {
        int matrixSize = subtask.getInt("matrix_size");
        int startRow   = subtask.getInt("start_row");
        int endRow     = subtask.getInt("end_row");
        int rows       = endRow - startRow;

        // Generate matrices A and B (deterministic from subtask params)
        double[][] A = new double[rows][matrixSize];
        double[][] B = new double[matrixSize][matrixSize];

        for (int i = 0; i < rows; i++)
            for (int j = 0; j < matrixSize; j++)
                A[i][j] = (startRow + i + j + 1) * 0.01;

        for (int i = 0; i < matrixSize; i++)
            for (int j = 0; j < matrixSize; j++)
                B[i][j] = (i * matrixSize + j + 1) * 0.01;

        // Actual matrix multiply (real computation!)
        double[][] C = new double[rows][matrixSize];
        for (int i = 0; i < rows; i++)
            for (int j = 0; j < matrixSize; j++)
                for (int k = 0; k < matrixSize; k++)
                    C[i][j] += A[i][k] * B[k][j];

        // Result size estimate: rows * matrixSize * 8 bytes (doubles)
        return (long) rows * matrixSize * 8;
    }

    // ── Image Processing Task ─────────────────────────────────
    long computeImage(JSONObject subtask) throws Exception {
        int tileW = subtask.getInt("tile_w");
        int tileH = subtask.getInt("tile_h");

        // Create a synthetic image tile (random pixels)
        int[] pixels = new int[tileW * tileH];
        for (int i = 0; i < pixels.length; i++) {
            int r = (i * 37) % 256;
            int g = (i * 53) % 256;
            int b = (i * 71) % 256;
            pixels[i] = 0xFF000000 | (r << 16) | (g << 8) | b;
        }

        // Apply Gaussian blur (real computation!)
        int[] blurred = gaussianBlur(pixels, tileW, tileH, 3);

        // Apply edge detection (Sobel operator)
        int[] edges = sobelEdge(blurred, tileW, tileH);

        return (long) tileW * tileH * 4; // result bytes
    }

    int[] gaussianBlur(int[] pixels, int width, int height, int radius) {
        float[] kernel = {1/16f, 2/16f, 1/16f,
                          2/16f, 4/16f, 2/16f,
                          1/16f, 2/16f, 1/16f};
        int[] result = new int[pixels.length];
        for (int y = 1; y < height - 1; y++) {
            for (int x = 1; x < width - 1; x++) {
                float r = 0, g = 0, b = 0;
                int ki = 0;
                for (int dy = -1; dy <= 1; dy++) {
                    for (int dx = -1; dx <= 1; dx++) {
                        int px = pixels[(y + dy) * width + (x + dx)];
                        r += ((px >> 16) & 0xFF) * kernel[ki];
                        g += ((px >> 8)  & 0xFF) * kernel[ki];
                        b += ( px        & 0xFF) * kernel[ki];
                        ki++;
                    }
                }
                result[y * width + x] = 0xFF000000 | ((int)r << 16) | ((int)g << 8) | (int)b;
            }
        }
        return result;
    }

    int[] sobelEdge(int[] pixels, int width, int height) {
        int[] result = new int[pixels.length];
        int[] gx = {-1, 0, 1, -2, 0, 2, -1, 0, 1};
        int[] gy = {-1,-2,-1,  0, 0, 0,  1, 2, 1};
        for (int y = 1; y < height - 1; y++) {
            for (int x = 1; x < width - 1; x++) {
                float sx = 0, sy = 0;
                int ki = 0;
                for (int dy = -1; dy <= 1; dy++) {
                    for (int dx = -1; dx <= 1; dx++) {
                        int px = pixels[(y + dy) * width + (x + dx)];
                        float gray = 0.299f * ((px >> 16) & 0xFF)
                                   + 0.587f * ((px >> 8)  & 0xFF)
                                   + 0.114f * ( px        & 0xFF);
                        sx += gray * gx[ki];
                        sy += gray * gy[ki];
                        ki++;
                    }
                }
                int mag = Math.min((int) Math.sqrt(sx * sx + sy * sy), 255);
                result[y * width + x] = 0xFF000000 | (mag << 16) | (mag << 8) | mag;
            }
        }
        return result;
    }

    // ── Network Helpers ───────────────────────────────────────
    String httpPost(String urlStr, String jsonBody) throws Exception {
        URL url = new URL(urlStr);
        HttpURLConnection conn = (HttpURLConnection) url.openConnection();
        conn.setRequestMethod("POST");
        conn.setRequestProperty("Content-Type", "application/json");
        conn.setDoOutput(true);
        conn.setConnectTimeout(5000);
        conn.setReadTimeout(10000);
        try (OutputStream os = conn.getOutputStream()) {
            os.write(jsonBody.getBytes("UTF-8"));
        }
        BufferedReader br = new BufferedReader(new InputStreamReader(conn.getInputStream()));
        StringBuilder sb = new StringBuilder();
        String line;
        while ((line = br.readLine()) != null) sb.append(line);
        return sb.toString();
    }

    String httpGet(String urlStr) throws Exception {
        URL url = new URL(urlStr);
        HttpURLConnection conn = (HttpURLConnection) url.openConnection();
        conn.setRequestMethod("GET");
        conn.setConnectTimeout(5000);
        conn.setReadTimeout(10000);
        BufferedReader br = new BufferedReader(new InputStreamReader(conn.getInputStream()));
        StringBuilder sb = new StringBuilder();
        String line;
        while ((line = br.readLine()) != null) sb.append(line);
        return sb.toString();
    }

    // ── Device Helpers ────────────────────────────────────────
    int getBatteryLevel() {
        IntentFilter ifilter = new IntentFilter(Intent.ACTION_BATTERY_CHANGED);
        Intent batteryStatus = registerReceiver(null, ifilter);
        if (batteryStatus == null) return 50;
        int level = batteryStatus.getIntExtra(BatteryManager.EXTRA_LEVEL, -1);
        int scale = batteryStatus.getIntExtra(BatteryManager.EXTRA_SCALE, -1);
        return (int) ((level / (float) scale) * 100);
    }

    int estimateCPUMips() {
        // Quick benchmark: count operations in 50ms
        long start = System.currentTimeMillis();
        long ops = 0;
        double x = 1.0;
        while (System.currentTimeMillis() - start < 50) {
            x = Math.sqrt(x + 1.0001);
            ops++;
        }
        // Rough MIPS estimate (1 op ≈ a few instructions)
        return (int) Math.min(ops * 20, 5000);
    }

    // ── UI Helpers ────────────────────────────────────────────
    void setStatus(String text, String color) {
        tvStatus.setText("● " + text);
        tvStatus.setTextColor(android.graphics.Color.parseColor(color));
    }

    void appendLog(String msg) {
        String current = tvLog.getText().toString();
        String newLog = current + "\n" + android.text.format.DateFormat.format("HH:mm:ss", new java.util.Date()) + "  " + msg;
        // Keep last 50 lines
        String[] lines = newLog.split("\n");
        if (lines.length > 50) {
            StringBuilder sb = new StringBuilder();
            for (int i = lines.length - 50; i < lines.length; i++)
                sb.append(lines[i]).append("\n");
            tvLog.setText(sb.toString());
        } else {
            tvLog.setText(newLog);
        }
        scrollLog.post(() -> scrollLog.fullScroll(ScrollView.FOCUS_DOWN));
    }

    void updateStats() {
        String avg = tasksCompleted > 0 ? (totalComputeMs / tasksCompleted) + "ms" : "—";
        tvStats.setText("Tasks Done: " + tasksCompleted + "  |  Failed: " + tasksFailed + "  |  Avg Compute: " + avg);
    }
}
