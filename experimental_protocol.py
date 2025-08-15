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
import serial
import matplotlib.pyplot as plt
import seaborn as sns
import pandas as pd
from datetime import datetime
import tabulate
from bokeh.plotting import show

#systole-specific
from systole.plots import plot_frequency
from systole.reports import frequency_table
from systole.hrv import frequency_domain, psd
from systole.detection import ppg_peaks
from systole import import_ppg
from systole.detection import ppg_peaks
from systole.recording import Oximeter
from systole.plots import plot_raw
from systole.utils import input_conversion
from systole import serialSim

#%% midi function setup

# map of the cc addresses mapped to buttons and toggles in Ableton: 
   #the start and stop button
   #volume of each track (track_1, track_2, etc.)
   #reverb of each track (reverb_1, reverb_2, etc.)
   #group volume of all harmony tracks (group_vol)
# IMPORTANT: 
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
    'group_vol': 40
}

#presses the start button
def start_ableton_playback():
    start_play_message = [0xB0, 20, 127]
    midiout.send_message(start_play_message)
    print("Ableton playback started.")

#mutes all tracks that are default listed or specified (can also be used to set all tracks to preferred volume)
def mute_tracks(cc_to_mute = [23, 25, 26], volume=0):
    for track, cc_number in cc_map.items():
        if cc_number in cc_to_mute:
            for value in reversed(range(volume, 100, max(1, int(100 / 20)))):
                midiout.send_message([0xB0, cc_number, value])
                time.sleep(2 / 20)

#list of all original reverb values (depends on the mixing of the music piece)
original_reverb_values = {
    31: 20,  # reverb_1
    32: 20,  # reverb_2
    33: 20,  # reverb_3
    34: 20,  # reverb_4
    35: 20,  # reverb_5
    36: 20   # reverb_6
}

#resets all reverb levels to original
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
        ser = serial.Serial('/dev/tty.usbserial-FT0QKFGA') #name of oximeter (check through terminal)
        oxi = Oximeter(serial=ser, sfreq=75).setup() #setting up oximeter to record
        print("Oximeter initialized.")
    except serial.SerialException as e:
        raise RuntimeError(f"Failed to connect to serial device: {e}")
    
    # --- UDP Receiver Setup ---
    #waits for the pacer code to send the message that the block has started
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
        
        #checking if the time has elapsed for the while loop
        while True:
            if time.time() - tbegin > max_duration*60:
                print("Finished")
                ser.close() #closes oximeter signal
                sock.close() #closes UDP
                break
            #wait 1 sec (however long the step is set to)
            while time.time() - tstart < step_sec:
                oxi.readInWaiting()
            tstart = time.time()  #reset time

            #grab latest recording (ppg) and times
            recording = np.array(oxi.recording)
            times = np.array(oxi.times)

            #get last 30 sec and calculate HRV based on them
            if len(recording) >= buffer_len:
                last_ppg = recording[-buffer_len:]
                last_times = times[-buffer_len:]

                signal, peaks = ppg_peaks(signal=last_ppg, sfreq=sfreq, method="rolling_average")
                freq_dom = frequency_domain(peaks, input_type="peaks", sfreq=sfreq)
                
                #the LF HRV power calulation 
                lf_power = freq_dom.at[7, "Values"]
                lf_vals.append(lf_power)
                
                #prints the HRV and time
                print(f"[{time.strftime('%H:%M:%S')}] LF Power: {lf_power:.4f}")
                
                #saves log
                with open(os.path.join(participant_folder, "log_1.txt"), "a") as log:
                    log.write(f"{datetime.now()} - LF Power: {lf_power:.4f}\n")
                
                #saves data every round of the while loop
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
    
    data_rows = []

    sfreq = 75
    window_sec = 30 #window duration
    step_sec = 1 #pause duration
    max_duration = 5.5 #max run time (min)
    buffer_len = sfreq * window_sec 

    reverb_ccs = [31, 32, 33, 34, 35, 36]
    reverb_level = 0  # current reverb value 
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
    start_ableton_playback() #starts ableton immediately after UDP is triggered 

    print("Recording initial 30 seconds...")
    oxi.read(duration=30)  # fill buffer

    recording = np.array(oxi.recording)
    times = np.array(oxi.times)

    tbegin = time.time()
    tstart = time.time()

    modulated_cc = 40  # Only modulate this CC (group volume of all harmony tracks)
    previous_volume = -1

    try:
        while True:
            if time.time() - tbegin > max_duration*60:  # checks whether the while loop should be finished
                print("Finished")
                stop_play_message = [0xB0, 19, 127]
                midiout.send_message(stop_play_message)
                ser.close()
                sock.close()
                break

            while time.time() - tstart < step_sec:  
                oxi.readInWaiting()
            tstart = time.time()

            recording = np.array(oxi.recording)
            times = np.array(oxi.times)

            if len(recording) >= buffer_len:  # checking whether the buffer has been filled
                last_ppg = recording[-buffer_len:] #saving ppg data for the buffer
                last_times = times[-buffer_len:]

                # LF Power Calculation
                signal, peaks = ppg_peaks(signal=last_ppg, sfreq=sfreq, method="rolling_average")
                freq_dom = frequency_domain(peaks, input_type="peaks", sfreq=sfreq)
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

                # reverb reward logic
                if lf_power >= 70:
                    if reward_hold_start is None:
                        reward_hold_start = current_time  # start reward timer
                    elif current_time - reward_hold_start >= 60:
                        # sustained above 70 for 1 minute
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
                    reverb_decay_start = None  # stable zone (60–70), no increase or decay

                
                # ---- printing ---
                print("No active track.")
                print(f"[{time.strftime('%H:%M:%S')}] LF Power: {lf_power:.4f}")
                
                with open(os.path.join(participant_folder, "log_2.txt"), "a") as log:
                    log.write(f"{datetime.now()} - LF Power: {lf_power:.4f}\n")

                #records the data in a df
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
# odd - cond 1 and cond 2
# even - cond 2 and cond 1

if participant_id % 2 == 1:
    condition_1()
elif participant_id % 2 == 0:
    condition_2()

input("Press enter to continue experiment:")

if participant_id % 2 == 1:
    condition_2()
elif participant_id % 2 == 0:
    condition_1()




