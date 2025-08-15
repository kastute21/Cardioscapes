#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on Thu May 22 11:40:44 2025

@author: kasteivanauskaite
"""
#%% imports
import pygame
import socket
import time
import math

#%% setup

# --- UDP Setup ---
UDP_IP = "127.0.0.1"
UDP_PORT = 5005
sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)

# --- Pygame Setup ---
pygame.init()

#screen = pygame.display.set_mode((1000,800))
#screen = pygame.display.set_mode((0, 0), pygame.FULLSCREEN)
info = pygame.display.Info()
screen = pygame.display.set_mode((info.current_w, info.current_h), pygame.NOFRAME)

pygame.display.set_caption("Breathing Pacer")

font = pygame.font.SysFont(None, 48)
clock = pygame.time.Clock()

WHITE = (255, 255, 255)
BLACK = (0, 0, 0)
GREEN = (100, 200, 100)
RED = (200, 100, 100)
GRAY = (80, 80, 80)

# --- Function Setup ---

def show_text(lines):
    screen.fill(BLACK)
    
    total_height = len(lines) * 60
    start_y = (screen.get_height() - total_height) // 2

    for i, line in enumerate(lines):
        text = font.render(line, True, WHITE)
        text_rect = text.get_rect(center=(screen.get_width() // 2, start_y + i * 60))
        screen.blit(text, text_rect)

    pygame.display.flip()

def wait_for_space():
    while True:
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                pygame.quit()
                exit()
            elif event.type == pygame.KEYDOWN and event.key == pygame.K_SPACE:
                return
        clock.tick(60)

def breathing_loop(duration):
    min_r = 50 #circle parameters
    max_r = 150
    cycle = 10  #breathing cycle
    start_time = time.time()

    while time.time() - start_time < duration:
        screen.fill(BLACK)
        elapsed = time.time() - start_time
        cycle_time = elapsed % cycle
        t = cycle_time / cycle

        if t < 0.5:
            phase_t = t / 0.5
            radius_factor = 0.5 * (1 - math.cos(math.pi * phase_t))
            color = GREEN
            label_text = "Inhale"
        else:
            phase_t = (t - 0.5) / 0.5
            radius_factor = 0.5 * (1 + math.cos(math.pi * phase_t))
            color = RED
            label_text = "Exhale"

        radius = min_r + (max_r - min_r) * radius_factor
        pygame.draw.circle(screen, GRAY,(screen.get_width() // 2, screen.get_height() // 2), max_r, width=2)
        pygame.draw.circle(screen, color, (screen.get_width() // 2, screen.get_height() // 2), int(radius))

        label = font.render(label_text, True, WHITE)
        screen.blit(label, label.get_rect(center=(screen.get_width() // 2, screen.get_height() // 2)))

        pygame.display.flip()

        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                pygame.quit()
                exit()
        clock.tick(60)

#%% --- main code ---

# instructions
show_text([
    "Welcome to this short breathing experiment.",
    "Press SPACE to begin a short practice."
])
wait_for_space()

# practice session
show_text(["Practice Round", "Follow the pacer."])
time.sleep(2)
breathing_loop(30) 

# real session
show_text([
    "Now you're ready.", 
    "Press SPACE to start the real session."
])
wait_for_space()

# sending UDP signal and running the pacer
sock.sendto(b"start", (UDP_IP, UDP_PORT))
breathing_loop(60*5.5)  

show_text(["Finished"])
