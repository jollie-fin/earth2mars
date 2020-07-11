import socket, ujson, sys
import unicodedata

import pybricks.tools
from pybricks.hubs import EV3Brick
from pybricks.ev3devices import (Motor, TouchSensor, ColorSensor,
                                 InfraredSensor, UltrasonicSensor, GyroSensor)
from pybricks.parameters import (Port, Stop, Direction, Button, Color,
                                 SoundFile, ImageFile, Align)

if len(sys.argv) != 2:
    sys.exit("Port?")

motor = {}
for key, port in (("propulsionL", Port.A), ("propulsionR", Port.B), ("grab", Port.C)):
    try:
        motor[key] = Motor(port)
    except OSError:
        motor[key] = None

brick = EV3Brick()
color_sensor = ColorSensor(Port.S1)
touch_sensor = TouchSensor(Port.S2)

def wait_and_check_if_lost():
    global color_sensor

    while motor['propulsionL'].speed() != 0 and motor['propulsionL'].speed() != 0:
        if color_sensor.color() != Color.WHITE:
            lost = True
            motor['propulsionL'].brake()
            motor['propulsionR'].brake()
            set_angle('grab', 10)
            sad_emoji()
            return True
    return False

def sad_emoji():
    global brick
    brick.speaker.play_file(SoundFile.GAME_OVER)

def wait_for_reset():
    global touch_sensor
    while not touch_sensor.pressed():
        tools.sleep(100)

torque_sensing = {"propulsionL" : 50,
        "propulsionR" : 50,
         "grab" : 100}
motor_finite_rotation = set()
angle_bounds = {}

def init_motor(channel):
    global angle_bounds, motor, torque_sensing
    if not motor[channel]:
        print("init:", channel, "desactivé")
        return
    torque = torque_sensing[channel]
    print(torque)
    local_motor = motor[channel]
    local_motor.run_until_stalled(-300, Stop.COAST, torque)
    min_angle = local_motor.angle()
    local_motor.run_until_stalled(300, Stop.COAST, torque)
    max_angle = local_motor.angle()
    print("init:", channel, min_angle, max_angle)
    angle_bounds[channel] = (min_angle, max_angle)
    set_angle(channel, -10, 300)

def set_angle(channel, angle, speed=100, stop_type=Stop.COAST):
    global angle_bounds, motor
    if angle < -10. or angle > 10.:
        raise ValueError(str(angle) + " n'est pas un angle acceptable, l'angle doit être entre -10 et 10")
    if speed < 1:
        raise ValueError(str(speed) + " n'est pas une vitesse acceptable, la vitesse doit être 1 ou plus")
    local_motor = motor[channel]
    bounds = angle_bounds[channel]
    next_angle = (angle + 10.) / 20. * (bounds[1] - bounds[0]) + bounds[0]
    if angle == 10:
        local_motor.run_until_stalled(speed, stop_type, torque_sensing[channel])
    elif angle == -10:
        local_motor.run_until_stalled(-speed, stop_type, torque_sensing[channel])
    else:
        local_motor.run_target(speed, next_angle, stop_type)
    print('set_angle', channel, speed, next_angle)

def init_socket():
    global server
    global bot, bot_addr
    print("Creating socket")
    server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    print("Opening port")
    host = "ev3dev.local"
    port = int(sys.argv[1])
    server.bind((host, port))
    print("Waiting for connection...")
    server.listen(5)
    bot, bot_addr = server.accept()
    print("Connected")

#for channel in ("lift",):
#    init(channel)
#    set_angle(channel, 0., 1000.)

def receive():
    buffer = bot.recv(4096)
    try:
        return ujson.loads(buffer.decode())
    except ValueError:
        raise ValueError("Impossible to decode '" + buffer.decode() + "'")

def send(data):
    global bot
    bot.send(ujson.dumps(data).encode())

def parse_int(string):
    try:
        return int(string)
    except ValueError:
        raise ValueError("'" + string + "' n'est pas un nombre")

def strip_accents(s):
    return s.replace('é', 'e').replace('è', 'e').replace('à', 'a')


def interpret(received):
    global motor

    has_lost = False
    try:
        executed = []
        decode_instruction = {
            'close' : ('grab', -10, 'closing', Stop.COAST),
            'open' : ('grab', 10, 'opening', Stop.COAST)
        }
        for length, each in received:
            if motor['propulsionL'] and motor['propulsionR']:
                right = 0
                left = 0
                if 'NW' in each:
                    right = 1.0
                    left = 0.5
                elif 'W' in each:
                    right = 0.4
                    left = -0.4
                elif 'SW' in each:
                    right = -1.0
                    left = -0.5
                elif 'S' in each:
                    right = -1.0
                    left = -1.0
                elif 'SE' in each:
                    right = -0.5
                    left = -1.0
                elif 'E' in each:
                    right = -0.4
                    left = 0.4
                elif 'NE' in each:
                    right = 0.5
                    left = 1.0
                elif 'N' in each:
                    right = 1.0
                    left = 1.0

                if right != 0 and left != 0:
                    if left != 0:
                        motor['propulsionL'].run_angle(600 * abs(left), 120. * length * left, Stop.HOLD, False)
                    if right != 0:
                        motor['propulsionR'].run_angle(600 * abs(right), 120. * length * right, Stop.HOLD, False)
                    has_lost = wait_and_check_if_lost()
                    if not has_lost:
                        executed.append("moved (" + str(left * length) + "," + str(right * length) + ")")

            else:
                executed.append('propulsion disconnected')

            if each in decode_instruction:
                channel, angle, message, stop_type = decode_instruction[each]
                if motor[channel]:
                    executed.append(message)
                    set_angle(channel, angle, 300, stop_type)
                else:
                    executed.append(channel + " is disconnected")

        if has_lost:
            return False
        if not executed:
            return "@Elie : Could not understand '" + ':'.join(received) + "'"
        else:
            return "Have executed : " + ', '.join(executed)
    except ValueError as e:
        return "@Elie : Could not understand '" + str(e) + "'"

def main_loop_emojis():
    while True:      
        received = receive()
        answer = interpret(received)
        send(answer)
        if not answer:
            wait_and_check_if_lost()
            send(True)

bot = None
server = None
try:
    init_socket()
    init_motor('grab')
    motor['propulsionL'].set_run_settings(800, 200)
    motor['propulsionR'].set_run_settings(800, 200)
    while True:
        main_loop_emojis()
finally:
    print("Closing")
    if bot is not None:
        bot.close()
    if server is not None:
        server.close()