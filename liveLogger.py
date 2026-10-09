
import csv
import math
import queue
import threading
import time
from datetime import datetime
from pathlib import Path

import serial
import matplotlib.pyplot as plt
from matplotlib.animation import FuncAnimation


# =====================================================
# 1. PROJECT SETTINGS
# =====================================================

PORT = "COM5"
BAUD_RATE = 9600
UPDATE_INTERVAL_MS = 1000
MAX_GRAPH_POINTS = 300
TABLE_ROWS = 12

PROJECT_FOLDER = Path(__file__).resolve().parent
DATA_FOLDER = PROJECT_FOLDER / "Data"
DATA_FOLDER.mkdir(parents=True, exist_ok=True)

timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
CSV_FILE = DATA_FOLDER / f"Solar_Cooker_Data_{timestamp}.csv"


# =====================================================
# 2. SHARED DATA
# =====================================================

data_queue = queue.Queue()
stop_event = threading.Event()

serial_error = None
readings = []


# =====================================================
# 3. READ ARDUINO DATA AND SAVE CSV
# =====================================================

def read_arduino():
    global serial_error

    try:
        with serial.Serial(PORT, BAUD_RATE, timeout=1) as arduino:
            # Arduino may restart when the serial connection opens.
            time.sleep(2)
            arduino.reset_input_buffer()

            print(f"Connected to Arduino on {PORT}")
            print(f"Saving CSV to: {CSV_FILE}")

            with open(
                CSV_FILE, "w", newline="", encoding="utf-8"
            ) as file:
                writer = csv.writer(file)

                writer.writerow([
                    "Time_s",
                    "Thermocouple_C",
                    "Ambient_C",
                    "Humidity_pct",
                    "Status"
                ])
                file.flush()

                while not stop_event.is_set():
                    raw_line = arduino.readline().decode(
                        "utf-8", errors="ignore"
                    ).strip()

                    if not raw_line:
                        continue

                    # Ignore the Arduino CSV header.
                    if raw_line.lower().startswith("time_s"):
                        continue

                    parts = raw_line.split(",")

                    if len(parts) != 4:
                        print(f"Skipped invalid line: {raw_line}")
                        continue

                    try:
                        elapsed = float(parts[0])
                        thermocouple = float(parts[1])
                        ambient = float(parts[2])
                        humidity = float(parts[3])

                        values = [
                            elapsed, thermocouple, ambient, humidity
                        ]

                        if not all(math.isfinite(v) for v in values):
                            continue

                    except ValueError:
                        print(f"Skipped unreadable line: {raw_line}")
                        continue

                    if thermocouple == 0 and ambient > 10:
                        status = "CHECK THERMOCOUPLE"
                    else:
                        status = "OK"

                    row = {
                        "time": elapsed,
                        "thermocouple": thermocouple,
                        "ambient": ambient,
                        "humidity": humidity,
                        "status": status
                    }

                    # Save each measurement immediately.
                    writer.writerow([
                        elapsed,
                        thermocouple,
                        ambient,
                        humidity,
                        status
                    ])
                    file.flush()

                    data_queue.put(row)

    except (serial.SerialException, OSError) as error:
        serial_error = str(error)
        print("\nSERIAL CONNECTION ERROR:", serial_error)
        print("Check COM5 and close the PlatformIO Serial Monitor.")

    except Exception as error:
        serial_error = str(error)
        print("\nLOGGER ERROR:", serial_error)

    finally:
        stop_event.set()
        print(f"\nCSV file: {CSV_FILE}")


# =====================================================
# 4. CONNECT TO ARDUINO IN THE BACKGROUND
# =====================================================

reader_thread = threading.Thread(
    target=read_arduino,
    daemon=True
)
reader_thread.start()


# =====================================================
# 5. CREATE THE LIVE DASHBOARD
# =====================================================

fig = plt.figure(figsize=(15, 8))
fig.canvas.manager.set_window_title(
    "Solar Cooker Live Logger"
)

fig.suptitle(
    "SOLAR BOX COOKER - LIVE MONITORING",
    fontsize=16,
    fontweight="bold"
)

layout = fig.add_gridspec(
    2, 2,
    width_ratios=[2, 1],
    height_ratios=[1, 1]
)

# Temperature graph
ax_temp = fig.add_subplot(layout[0, 0])

line_thermo, = ax_temp.plot(
    [], [], label="Thermocouple / Absorber (°C)"
)
line_ambient, = ax_temp.plot(
    [], [], label="Ambient Temperature (°C)"
)

ax_temp.set_title("Live Temperature")
ax_temp.set_xlabel("Elapsed Time (seconds)")
ax_temp.set_ylabel("Temperature (°C)")
ax_temp.grid(True, alpha=0.3)
ax_temp.legend()

# Humidity graph
ax_humidity = fig.add_subplot(layout[1, 0])

line_humidity, = ax_humidity.plot(
    [], [], label="Relative Humidity (%)"
)

ax_humidity.set_title("Live Relative Humidity")
ax_humidity.set_xlabel("Elapsed Time (seconds)")
ax_humidity.set_ylabel("Humidity (%)")
ax_humidity.set_ylim(0, 100)
ax_humidity.grid(True, alpha=0.3)
ax_humidity.legend()

# Readings table
ax_table = fig.add_subplot(layout[:, 1])
ax_table.axis("off")
ax_table.set_title(
    "LATEST READINGS",
    fontsize=12,
    fontweight="bold"
)

column_labels = [
    "Time (s)", "Thermo (°C)", "Ambient (°C)", "RH (%)"
]

table = ax_table.table(
    cellText=[["Waiting...", "", "", ""]],
    colLabels=column_labels,
    cellLoc="center",
    loc="center"
)

table.auto_set_font_size(False)
table.set_fontsize(8)
table.scale(1.1, 1.5)

status_text = fig.text(
    0.5, 0.015,
    "Waiting for Arduino data...",
    ha="center",
    fontsize=10
)

fig.tight_layout(rect=[0, 0.04, 1, 0.94])


# =====================================================
# 6. UPDATE THE GRAPHS AND TABLE
# =====================================================

def update_dashboard(_frame):
    global readings

    while True:
        try:
            readings.append(data_queue.get_nowait())
        except queue.Empty:
            break

    # Keep the display responsive during long experiments.
    if len(readings) > MAX_GRAPH_POINTS:
        readings = readings[-MAX_GRAPH_POINTS:]

    if readings:
        times = [r["time"] for r in readings]
        thermo = [r["thermocouple"] for r in readings]
        ambient = [r["ambient"] for r in readings]
        humidity = [r["humidity"] for r in readings]

        line_thermo.set_data(times, thermo)
        line_ambient.set_data(times, ambient)
        line_humidity.set_data(times, humidity)

        for axis, values in (
            (ax_temp, thermo + ambient),
            (ax_humidity, humidity)
        ):
            axis.relim()
            axis.autoscale_view(scalex=False, scaley=True)

            # Display approximately the last ten minutes.
            right = max(60, times[-1] + 5)
            axis.set_xlim(max(0, right - 600), right)

        # Replace the old table with the latest readings.
        recent = list(reversed(readings[-TABLE_ROWS:]))

        cell_text = [
            [
                f"{r['time']:.1f}",
                f"{r['thermocouple']:.2f}",
                f"{r['ambient']:.1f}",
                f"{r['humidity']:.1f}"
            ]
            for r in recent
        ]

        while len(cell_text) < TABLE_ROWS:
            cell_text.append(["", "", "", ""])

        table_data = table.get_celld()

        for key in list(table_data):
            row_index, column_index = key
            if row_index > 0:
                table_data[key].get_text().set_text("")

        for row_index, row in enumerate(cell_text, start=1):
            for column_index, value in enumerate(row):
                if (row_index, column_index) in table.get_celld():
                    table[(row_index, column_index)].get_text().set_text(
                        value
                    )

        latest = readings[-1]

        if latest["status"] != "OK":
            status_text.set_text(
                "WARNING: Thermocouple reads 0°C. "
                "Check the MAX6675 and thermocouple."
            )
        else:
            status_text.set_text(
                f"Recording | Latest ambient: {latest['ambient']:.1f}°C"
            )

    elif serial_error:
        status_text.set_text(f"Connection error: {serial_error}")

    return line_thermo, line_ambient, line_humidity


# =====================================================
# 7. START AND STOP THE DASHBOARD
# =====================================================

animation = FuncAnimation(
    fig,
    update_dashboard,
    interval=UPDATE_INTERVAL_MS,
    blit=False,
    cache_frame_data=False
)


def close_dashboard(_event):
    stop_event.set()


fig.canvas.mpl_connect("close_event", close_dashboard)

try:
    plt.show()
finally:
    stop_event.set()

    if reader_thread.is_alive():
        reader_thread.join(timeout=3)

    print("\nRecording stopped.")
    print(f"Recorded data is saved in:\n{CSV_FILE}")