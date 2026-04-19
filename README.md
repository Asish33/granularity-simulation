# Granularity Optimization – Distributed Mobile Clusters
### SRM University AP | Akhil Teja Rayala, Dharani Shankar K, Balaji Asish Atukuri
### Supervisor: Dr. Vijaya Bhaskar Adusumalli

---

## WHAT THIS PROJECT DOES

Your PC acts as the **Orchestrator/Server**. The phones act as **Worker Nodes**.

1. Phones connect to the PC over Wi-Fi
2. PC splits a job (matrix multiplication or image processing) into subtasks
3. Subtasks are assigned to phones using a modified HEFT algorithm
4. Each phone does real computation and sends results back
5. PC measures Makespan, CCR, Throughput at different Granularity values (G)
6. Dashboard shows optimal G range (where makespan is minimized)

---

## STEP 1 — SETUP THE PC SERVER

### Requirements
- Python 3.8 or higher
- All phones and PC on the SAME Wi-Fi network

### Install dependencies
Open a terminal/command prompt and run:
```
pip install flask numpy pillow
```

### Run the server
```
cd server
python server.py
```

You will see:
```
  Dashboard : http://localhost:5000
  Your IP   : 192.168.x.x        ← NOTE THIS IP
```

Open http://localhost:5000 in your browser. This is your control center.

---

## STEP 2 — BUILD AND INSTALL THE ANDROID APP

### Option A: Using Android Studio (Recommended)
1. Download and install Android Studio from https://developer.android.com/studio
2. Open Android Studio → "Open an Existing Project"
3. Navigate to the `android_app/` folder and open it
4. Wait for Gradle sync to finish (takes 2-5 minutes first time)
5. Enable USB Debugging on each phone:
   - Settings → About Phone → tap "Build Number" 7 times
   - Settings → Developer Options → enable "USB Debugging"
6. Connect each phone via USB
7. Click the green ▶ Run button in Android Studio
8. The app will install on the connected phone
9. Repeat for each phone

### Option B: Build APK and share
1. In Android Studio: Build → Build Bundle(s) / APK(s) → Build APK(s)
2. The APK will be in: android_app/app/build/outputs/apk/debug/app-debug.apk
3. Share this APK file to all phones via WhatsApp/Google Drive
4. On each phone: open the APK file and install it
   (You may need to enable "Install from unknown sources" in phone settings)

---

## STEP 3 — CONNECT PHONES TO CLUSTER

On each phone:
1. Open the **Granularity Worker** app
2. In "PC Server IP Address" field, enter your PC's IP (from Step 1)
3. Change the phone name to something unique (e.g., "Akhil-Phone", "Dharani-Phone")
4. Tap **CONNECT**
5. You should see "● CONNECTED – IDLE" in green

Back on the PC dashboard (refresh http://localhost:5000), you'll see each phone appear under "Connected Worker Phones".

---

## STEP 4 — RUN THE EXPERIMENT

### Manual Testing
1. Go to http://localhost:5000
2. Under "Submit a Job", choose:
   - Task Type: Matrix Multiplication
   - Granularity G: try different values (0.1, 1.0, 5.0, 50.0)
   - Matrix Size: 128×128
3. Click **▶ SUBMIT JOB**
4. Watch phones show "COMPUTING" and results appear in the table

### Auto Sweep (Best for Demo!)
Click **⚡ AUTO GRANULARITY SWEEP** — this automatically runs jobs at G = 0.1, 0.5, 1.0, 2.0, 5.0, 10.0, 50.0 and shows you exactly which G value gives optimal performance.

---

## STEP 5 — INTERPRETING RESULTS

| G Value | Meaning | Expected Behavior |
|---------|---------|-------------------|
| G < 1.0 | Fine-grained | High communication overhead, slow |
| 1 < G < 10 | Medium-grained | **OPTIMAL ZONE** — best makespan |
| G > 10 | Coarse-grained | Less parallelism, slow again |

The dashboard shows:
- **Makespan**: Total job time in milliseconds
- **CCR**: Communication-to-Computation Ratio (lower = better)
- **Throughput**: Tasks completed per second
- **Optimal G Range**: Values within 10% of best makespan

---

## PROJECT ARCHITECTURE

```
PC (server.py)
│
│  Wi-Fi Network
│
├── Phone 1 (Worker) ──┐
├── Phone 2 (Worker) ──┤── Poll for tasks → Compute → Submit results
├── Phone 3 (Worker) ──┘
```

### Key Files
```
granularity_project/
├── server/
│   └── server.py          ← Run this on PC
└── android_app/
    └── app/src/main/
        ├── java/com/granularity/worker/
        │   └── MainActivity.java    ← Phone app logic
        ├── res/layout/
        │   └── activity_main.xml    ← Phone UI
        └── AndroidManifest.xml
```

---

## TROUBLESHOOTING

**Phone can't connect to PC:**
- Make sure both are on the SAME Wi-Fi network
- Disable Windows Firewall temporarily, or allow port 5000
- Try pinging the PC from phone's browser: http://[PC-IP]:5000

**App won't install:**
- Enable "Install from unknown sources" on the phone
- Or use Android Studio to install directly via USB

**Tasks not being received:**
- Check that server.py is still running on PC
- Try disconnecting and reconnecting the phone app

**Gradle sync fails in Android Studio:**
- Make sure you have internet connection (it downloads dependencies)
- File → Invalidate Caches → Restart

---

## FOR YOUR DEMO TO SIR

1. Start server on laptop
2. Show the dashboard on projector/screen
3. Have 2-3 phones connect (show phones appearing in table)
4. Click "Auto Granularity Sweep"
5. Point to the Granularity vs Makespan table
6. Show that G = 1–10 gives optimal makespan (matches Kumar & Liu [2])
7. Explain: "This proves our model — medium-grained tasks minimize makespan"

---

*Project: Granularity Optimization in Distributed Mobile Clusters*
*SRM University AP — March 2026*
