#!/usr/bin/env pybricks-micropython

from sys import argv
#from pybricks import ev3brick as brick
from pybricks.ev3devices import (Motor, TouchSensor, ColorSensor,
                                 InfraredSensor, UltrasonicSensor, GyroSensor)
from pybricks.parameters import (Port, Stop, Direction, Button, Color,
                                 SoundFile, ImageFile, Align)

#from pybricks.tools import print, wait, StopWatch
#from pybricks.robotics import DriveBase

# Write your program here
motorA = Motor(Port.A)
motorB = Motor(Port.B)
motorArm = Motor(Port.C)

command = argv[1]
speed_arg = argv[2]
length_arg = argv[3]

speed = 300.
A = 0.
B = 0.
C = 0.
if command == 'avance':
    A = 1.
    B = 1.
elif command == 'gauche':
    A = 1.
    B = -1.
elif command == 'droite':
    A = -1.
    B = 1.
elif command == 'recule':
    A = -1.
    B = -1.
elif command == 'souleve':
    C = 1

if speed_arg == 'vite':
    speed = 1000.
elif speed_arg == 'lent':
    speed = 100.
elif speed_arg == 'max':
    speed = 5000.

length = float(length_arg) * 90.

motorA.run_angle(speed, length * A, Stop.COAST, False)
motorB.run_angle(speed, length * B, Stop.COAST, True)
motorArm.run_target(100, 0)
