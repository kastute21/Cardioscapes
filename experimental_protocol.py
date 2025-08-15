#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on Thu May 22 14:45:02 2025

@author: kasteivanauskaite
"""

#%% imports
import socket
import time
import os
import numpy as np
import rtmidi
from systole.plots import plot_frequency
from systole.reports import frequency_table
from systole.hrv import frequency_domain, psd
from systole.detection import ppg_peaks
from systole import import_ppg
from systole.detection import ppg_peaks
import tabulate
from systole.recording import Oximeter
import serial
import matplotlib.pyplot as plt
import numpy as np
import seaborn as sns
from bokeh.io import output_notebook
from bokeh.plotting import show
from systole.detection import ecg_peaks
from systole.plots import plot_raw
from systole.utils import input_conversion

from systole import import_dataset1, import_ppg
import pandas as pd

from systole import serialSim
import time
import numpy as np
import matplotlib.pyplot as plt
import serial
import pandas as pd
from datetime import datetime
import rtmidi
import time
import numpy as np
import matplotlib.pyplot as plt
from datetime import datetime

#%% midi function setup

cc_map = {
    'start': 20,
    'stop': 19,
    'track_1': 21,
    'track_2': 22,
    'track_3': 23,
    'track_4': 24,
    'track_5': 25,
    'track_6': 26,
    'reverb_1': 31,
    'reverb_2': 32,
    'reverb_3': 33,
    'reverb_4': 34,
    'reverb_5': 35,
    'reverb_6': 36,
}


def start_ableton_playback():
    start_play_message = [0xB0, 20, 127]
    midiout.send_message(start_play_message)
    print("Ableton playback started.")
    
def mute_tracks(cc_to_mute = [23, 25, 26], volume=0):

    for track, cc_number in cc_map.items():
        if cc_number in cc_to_mute:
            for value in reversed(range(volume, 100, max(1, int(100 / 20)))):
                midiout.send_message([0xB0, cc_number, value])
                time.sleep(2 / 20)

def get_threshold_bin(lf_mean, previous_threshold=None):
    # Hysteresis logic for (40, 65, 80)
    if previous_threshold == 80:
        if lf_mean > 75:
            return 80
    elif previous_threshold == 65:
        if 55 < lf_mean <= 75:
            return 65
    elif previous_threshold == 40:
        if 30 < lf_mean <= 55:
            return 40
    else:
        # No previous threshold
        if lf_mean > 75:
            return 80
        elif lf_mean > 55:
            return 65
        elif lf_mean > 30:
            return 40
    return None  # falls below all thresholds

original_reverb_values = {
    31: 20,  # reverb_1
    32: 20,  # reverb_2
    33: 20,  # reverb_3
    34: 20,  # reverb_4
    35: 20,  # reverb_5
    36: 20   # reverb_6
}

def reset_reverb_to_original():
    for cc_number, original_value in original_reverb_values.items():
        midiout.send_message([0xB0, cc_number, original_value])
    print("Reverb reset to original values.")

#%% condition functions
def condition_1():
    
    assert participant_id is not None, "participant_id must be defined."
    assert os.path.isdir(participant_folder), f"{participant_folder} not found."

    # --- reset ---
    data_rows = []

    sfreq = 75
    window_sec = 30 #window duration
    step_sec = 1 #pause duration
    buffer_len = sfreq * window_sec
    max_duration = 5.5 #max run time (min)
    lf_vals = []
    
    # --- connection with oximeter ---
    
    try:
        ser = serial.Serial('/dev/tty.usbserial-FT0QKFGA')
        oxi = Oximeter(serial=ser, sfreq=75).setup()
        print("Oximeter initialized.")
    except serial.SerialException as e:
        raise RuntimeError(f"Failed to connect to serial device: {e}")
    
    # --- UDP Receiver Setup ---
    UDP_IP = "127.0.0.1"
    UDP_PORT = 5005

    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.bind((UDP_IP, UDP_PORT))

    print("Waiting for signal from pacer...")
    data, addr = sock.recvfrom(1024)  # Blocks until pacer sends a message
    msg = data.decode()
    if msg == "start":
        print("Received 'start' from pacer.")
    else:
        print(f"Unexpected message: {msg}")

    # --- main code ---

    try:
        recording = np.array(oxi.recording)
        times = np.array(oxi.times)

        tbegin = time.time()
        tstart = time.time()
        
        while True:
            if time.time() - tbegin > max_duration*60:
                print("Finished")
                ser.close()
                sock.close()
                break
            #wait 2 sec
            while time.time() - tstart < step_sec:
                oxi.readInWaiting()
            tstart = time.time()  #reset time

            #grab latest rec and times
            recording = np.array(oxi.recording)
            times = np.array(oxi.times)

            #get last 30 sec
            if len(recording) >= buffer_len:
                last_ppg = recording[-buffer_len:]
                last_times = times[-buffer_len:]

                signal, peaks = ppg_peaks(signal=last_ppg, sfreq=sfreq, method="rolling_average")
                freq_dom = frequency_domain(peaks, input_type="peaks", sfreq=sfreq)
                lf_power = freq_dom.at[7, "Values"]
                lf_vals.append(lf_power)

                print(f"[{time.strftime('%H:%M:%S')}] LF Power: {lf_power:.4f}")
                
                with open(os.path.join(participant_folder, "log_1.txt"), "a") as log:
                    log.write(f"{datetime.now()} - LF Power: {lf_power:.4f}\n")
                
                data_rows.append({
                    "id": participant_id,
                    "condition": 1,
                    "time": datetime.now().strftime("%H:%M:%S"),
                    "lf_power": lf_power
                })

    except KeyboardInterrupt:
        print("Stopped real-time monitoring.")
        ser.close()
        sock.close()
        
        # --- saving ---
    df = pd.DataFrame(data_rows)
    df.to_csv(os.path.join(participant_folder, "ppg_data_cond_1.csv"), index=False)
        
        
def condition_2():
    
    assert participant_id is not None, "participant_id must be defined."
    assert os.path.isdir(participant_folder), f"{participant_folder} not found."

    # --- reset ---
    
    max_duration = 5.5 * 60
    data_rows = []

    reverb_ccs = [31, 32, 33, 34, 35, 36]
    reverb_level = 0  # current reverb value (0–127)
    reverb_max = 100
    reverb_step = 15  # how much to increase when reward is triggered
    reward_hold_start = None  # time when lf_power went above 70
    reverb_decay_start = None  # time when lf_power fell below 60
    reverb_decay_delay = 30  # seconds to wait before starting reverb fadeout
    reverb_fade_step = 5
    reverb_fade_interval = 2  # seconds between fades
    last_reverb_fade = 0  # last time we faded
    reset_reverb_to_original()
    
    # --- check and open midi port ---

    midiout = rtmidi.MidiOut()
    available_ports = midiout.get_ports()
    print(available_ports)

    if available_ports:
        midiout.open_port(0)
        
    # --- connection with oximeter ---
    
    try:
        ser = serial.Serial('/dev/tty.usbserial-FT0QKFGA')
        oxi = Oximeter(serial=ser, sfreq=75).setup()
        print("Oximeter initialized.")
    except serial.SerialException as e:
        raise RuntimeError(f"Failed to connect to serial device: {e}")
    
    # --- UDP Receiver Setup ---
    UDP_IP = "127.0.0.1"
    UDP_PORT = 5005

    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.bind((UDP_IP, UDP_PORT))

    print("Waiting for signal from pacer...")
    data, addr = sock.recvfrom(1024)  # Blocks until pacer sends a message
    msg = data.decode()
    if msg == "start":
        print("Received 'start' from pacer.")
    else:
        print(f"Unexpected message: {msg}")
    
    ##### main experiment code start#########
    print("Starting Ableton...")
    start_ableton_playback()

    print("Recording initial 30 seconds...")
    oxi.read(duration=30)  # fill buffer

    recording = np.array(oxi.recording)
    times = np.array(oxi.times)

    tbegin = time.time()
    tstart = time.time()

    modulated_cc = 40  # Only modulate this CC
    previous_volume = -1

    try:
        while True:
            if time.time() - tbegin > max_duration:  # max_duration
                print("Finished")
                stop_play_message = [0xB0, 19, 127]
                midiout.send_message(stop_play_message)
                ser.close()
                sock.close()
                break

            while time.time() - tstart < 1:  # step_sec
                oxi.readInWaiting()
            tstart = time.time()

            recording = np.array(oxi.recording)
            times = np.array(oxi.times)

            if len(recording) >= 75 * 30:  # buffer_len for 30 sec data
                last_ppg = recording[-75 * 30:]
                last_times = times[-75 * 30:]

                # LF Power Calculation
                signal, peaks = ppg_peaks(signal=last_ppg, sfreq=75, method="rolling_average")
                freq_dom = frequency_domain(peaks, input_type="peaks", sfreq=75)
                lf_power = freq_dom.at[7, "Values"]
                
                # vol control
                if lf_power < 30:
                    volume = 0
                elif 30 <= lf_power <= 80:
                    volume = int(np.interp(lf_power, [30, 80], [20, 90]))
                else:
                    volume = int(np.interp(lf_power, [81, 100], [90, 127]))
                
                # send midi only if its changed
                if volume != previous_volume:
                    midiout.send_message([0xB0, modulated_cc, volume])
                    previous_volume = volume
                    
                current_time = time.time()

                # Handle reverb reward logic
                if lf_power >= 70:
                    if reward_hold_start is None:
                        reward_hold_start = current_time  # start reward timer
                    elif current_time - reward_hold_start >= 60:
                        # Sustained above 70 for 1 minute
                        if reverb_level < reverb_max:
                            reverb_level = min(reverb_level + reverb_step, reverb_max)
                            for cc in reverb_ccs:
                                midiout.send_message([0xB0, cc, reverb_level])
                            print(f"[{time.strftime('%H:%M:%S')}] Reverb increased to {reverb_level}")
                        reward_hold_start = current_time  # restart 60s hold window
                    reverb_decay_start = None  # reset decay
                elif lf_power < 60:
                    reward_hold_start = None
                    if reverb_decay_start is None:
                        reverb_decay_start = current_time  # begin decay timing
                    elif current_time - reverb_decay_start >= reverb_decay_delay:
                        if current_time - last_reverb_fade >= reverb_fade_interval and reverb_level > 0:
                            reverb_level = max(0, reverb_level - reverb_fade_step)
                            for cc in reverb_ccs:
                                midiout.send_message([0xB0, cc, reverb_level])
                            print(f"[{time.strftime('%H:%M:%S')}] Reverb faded to {reverb_level}")
                            last_reverb_fade = current_time
                else:
                    reverb_decay_start = None  # stable zone (60–70), don't increase or decay

                
                # ---- printing ---
                print("No active track.")
                print(f"[{time.strftime('%H:%M:%S')}] LF Power: {lf_power:.4f}")
                
                with open(os.path.join(participant_folder, "log_2.txt"), "a") as log:
                    log.write(f"{datetime.now()} - LF Power: {lf_power:.4f}\n")

                
                data_rows.append({
                    "id": participant_id,
                    "condition": 2,
                    "time": datetime.now().strftime("%H:%M:%S"),
                    "lf_power": lf_power,
                    "volume": volume,
                    "reverb_level": reverb_level
                })

    except KeyboardInterrupt:
        print("Stopped real-time monitoring.")
        stop_play_message = [0xB0, 19, 127]
        midiout.send_message(stop_play_message)
        ser.close()
        sock.close()
        
    del midiout
    
    # --- saving ---
    df = pd.DataFrame(data_rows)
    df.to_csv(os.path.join(participant_folder, "ppg_data_cond_2.csv"), index=False)

#%% check check
# --- checking if oximeter working ---

try:
    ser = serial.Serial('/dev/tty.usbserial-FT0QKFGA')
    oxi = Oximeter(serial=ser, sfreq=75).setup()
    print("Oximeter initialized.")
except serial.SerialException as e:
    raise RuntimeError(f"Failed to connect to serial device: {e}")
    
tstart = time.time()
while time.time() - tstart < 5:
    while oxi.serial.inWaiting() >= 5:
        paquet = list(oxi.serial.read(5))
        oxi.add_paquet(paquet[2])  # Add new data point
        if oxi.peaks[-1] == 1:
            print("Heartbeat detected")

# --- check and open midi port ---

midiout = rtmidi.MidiOut()
available_ports = midiout.get_ports()
print(available_ports)

if available_ports:
    midiout.open_port(0)
#%% Protocol
# --- participant info ---
participant_id = int(input("Enter participant ID: "))

# --- creating data save ---

base_dir = os.path.expanduser("~/Desktop/ResMas/data_trial")

timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
os.makedirs(base_dir, exist_ok=True)

participant_folder = os.path.join(base_dir, f"sub-{participant_id}")

if os.path.exists(participant_folder):
    raise FileExistsError(f"Participant folder already exists: {participant_folder}\nAborting to avoid overwriting.")
else:
    os.makedirs(participant_folder)
    print(f"Saving all files to: {participant_folder}")

print(f"Data for this session will be saved in:\n{participant_folder}")

# --- sorting conditions ---

if participant_id % 2 == 1:
    condition_1()
elif participant_id % 2 == 0:
    condition_2()
    
input("Press enter to continue experiment:")

if participant_id % 2 == 1:
    condition_2()
elif participant_id % 2 == 0:
    condition_1()



