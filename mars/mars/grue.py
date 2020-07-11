import socket, ujson, sys
import unicodedata
from time import sleep

from pybricks.ev3devices import (Motor, TouchSensor, ColorSensor,
                                 InfraredSensor, UltrasonicSensor, GyroSensor)
from pybricks.parameters import (Port, Stop, Direction, Button, Color,
                                 SoundFile, ImageFile, Align)

stop_button = TouchSensor(Port.S1)
if len(sys.argv) != 2:
    sys.exit("Port?")

motor = {}
for key, port in (("pince", Port.A), ("coude", Port.B), ("epaule", Port.C), ("bassin", Port.D)):
    try:
        motor[key] = Motor(port)
    except OSError:
        motor[key] = None

torque_sensing = {"pince" : 50,
         "coude" : 40,
         "epaule" : 20,
         "bassin" : 30}

decode_instruction = {
    'epaule' : (-90*70, Stop.COAST),
    'pince' : (180*11, Stop.COAST),
    'bassin' : (30*47, Stop.COAST),
    'coude' : (-180*23, Stop.COAST),
}

def wait_until_finished(channel, stop_type=Stop.COAST, stop_when_pressed=False):
    global motor
    print("waiting for completion")
    if not motor[channel]:
        print("wait_until_finished:", channel, "desactivé")
        return
    local_motor = motor[channel]

    sleep(1)

    pressed = False
    while True:
        if abs(local_motor.speed()) <= 1.:
            break
        if stop_button.pressed():
            if stop_when_pressed:
                break
            else:
                pressed = True
        elif pressed:
            break
    if stop_type == Stop.COAST:
        local_motor.stop()
    elif stop_type == Stop.HOLD:
        local_motor.hold()
    elif stop_type == Stop.BRAKE:
        local_motor.brake()
    print("completion")

def init_motor(channel):
    global motor, torque_sensing, decode_instruction
    if not motor[channel]:
        print("init:", channel, "desactivé")
        return
    torque = torque_sensing[channel]
    local_motor = motor[channel]

    amplitude = decode_instruction[channel][0]
    if amplitude > 0:
        local_motor.dc(torque)
    else:
        local_motor.dc(-torque)
    wait_until_finished(channel, Stop.COAST, True)
    local_motor.reset_angle(0)
    print("init:", channel)
    local_motor.run_target(500, -amplitude * 10. / 100., Stop.COAST, False)
    wait_until_finished(channel)
    print("init:", channel)

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

def main_loop_emojis():
    global motor
    try:
        executed = []
        received = receive()
        for length, channel in received:
            if channel in decode_instruction:
                angle, stop_type = decode_instruction[channel]
                if motor[channel]:
                    executed.append(channel + ' : ' + str(length))
                    motor[channel].run_target(500, angle * float(-length) / 100., stop_type, False)
                    wait_until_finished(channel, stop_type)
                else:
                    executed.append("moteur de " + channel + " deconnecté")
        if not executed:
            send("@Elie : Je n'ai pas compris '" + ':'.join(received) + "'")
        else:
            send("J'ai exécuté : " + ', '.join(executed))
    except ValueError as e:
        send("@Elie : Je n'ai pas compris '" + str(e) + "'")

bot = None
server = None
try:
    motor['bassin'].set_run_settings(800, 100)
    motor['coude'].set_run_settings(800, 400)
    motor['epaule'].set_run_settings(800, 300)
    init_motor('epaule')
    init_motor('coude')
    init_motor('pince')
    init_motor('bassin')
    motor['pince'].run_target(500, -decode_instruction['pince'][0] * 20. / 100., Stop.COAST, False)
    wait_until_finished('pince')
    motor['pince'].reset_angle(0)
    init_socket()
    while True:
        main_loop_emojis()
finally:
    print("Closing")
    if bot is not None:
        bot.close()
    if server is not None:
        server.close()