import socket, ujson, sys
import unicodedata

from pybricks.ev3devices import (Motor, TouchSensor, ColorSensor,
                                 InfraredSensor, UltrasonicSensor, GyroSensor)
from pybricks.parameters import (Port, Stop, Direction, Button, Color,
                                 SoundFile, ImageFile, Align)

if len(sys.argv) != 2:
    sys.exit("Port?")

motor = {}
for key, port in (("propulsion", Port.A), ("direction", Port.B), ("grab", Port.C), ("lift", Port.D)):
    try:
        motor[key] = Motor(port)
    except OSError:
        motor[key] = None

torque_sensing = {"propulsion" : 50,
         "direction" : 100,
         "grab" : 50,
         "lift" : 80}
motor_finite_rotation = set()
angle_bounds = {}

def init_motor(channel):
    global angle_bounds, motor, torque_sensing
    if not motor[channel]:
        print("init:", channel, "desactivé")
        return
    torque = torque_sensing[channel]
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

def main_loop():
    global motor
    try:
        instruction_to_split = receive()
        if not isinstance(instruction_to_split, str):
            raise ValueError("Erreur interne")
        instruction = instruction_to_split.split()
        instruction = list(strip_accents(lexem) for lexem in instruction)

        commands = ['tourne gauche', 'tourne droite', 'ne tourne pas', 'leve', 'baisse', 'ferme', 'ouvre', 'avance', 'recule']

        help = 'Commandes connues:'
        for command in commands:
            help += '- ' + command + '\n'
        if len(instruction) <= 1:
            raise ValueError("Oui ?")

        verb = instruction[1]
        instruction = instruction[2:]
        print("'" + verb + "'", "'" + "tourne" + "'", verb == "tourne")
        if verb == "tourne" or (verb == 'ne' and 'tourne' in instruction and 'pas' in instruction):
            if 'gauche' in instruction:
                set_angle("direction", -10, 300)
            elif 'droite' in instruction:
                set_angle("direction", 10, 300)
            else:
                set_angle("direction", 0, 300)
        elif verb == "avance" or verb == "recule":
            angle = 3.
            if 'peu' in instruction:
                angle = 1.
            if 'beaucoup' in instruction:
                angle = 10.
            speed = 300.
            if 'vite' in instruction:
                if 'tres' in instruction:
                    speed = 3000.
                else:
                    speed = 1000.
            if 'lentement' in instruction:
                speed = 100.
            angle = angle if verb == 'avance' else -angle
            motor['propulsion'].run_angle(speed, angle * 360.)
        elif verb == "leve" or verb == "baisse":
            set_angle("lift", -10 if verb == "baisse" else 10)
        elif verb == "ferme" or verb == "ouvre":
            set_angle("grab", -10 if verb == "ouvre" else 10)
        else:
            raise ValueError("Je ne comprends pas '" + verb + "'")
    except ValueError as e:
        send(str(e) + "\n" + help)
    else:
        send("Instruction '" + instruction_to_split + "' exécutée avec succès")

def main_loop_emojis():
    global motor
    try:
        executed = []
        decode_instruction = {
            'up' : ('lift', 10, 'soulève la pince', Stop.COAST),
            'down' : ('lift', -8, 'baisse la pince', Stop.COAST),
            'close' : ('grab', 10, 'ferme la pince', Stop.COAST),
            'open' : ('grab', -10, 'ouvre la pince', Stop.COAST)
        }
        received = receive()
        for length, each in received:
            if motor['direction']:
                if 'W' in each:
                    set_angle("direction", 10, 300)
                    executed.append('pointe à gauche')
                elif 'E' in each:
                    set_angle("direction", -10, 300)
                    executed.append('pointe à droite')
                elif motor['direction']:
                    set_angle("direction", 0, 300, Stop.HOLD)
                    executed.append('pointe tout droit')
            elif 'W' in each or 'E' in each:
                executed.append('moteur de direction déconnecté')

            print('Propulsion ?')
            if motor['propulsion']:
                if 'N' in each:
                    print('N ?')
                    motor['propulsion'].run_angle(600, -120. * length)
                    executed.append('avance de ' + str(length))
                elif 'S' in each:
                    print('S ?')
                    motor['propulsion'].run_angle(600, 120. * length)
                    executed.append('recule de ' + str(length))
                print('Done')
            elif 'N' in each or 'S' in each:
                executed.append('moteur de propulsion déconnecté')

            motor['direction'].stop(Stop.COAST)
            if each in decode_instruction:
                channel, angle, message, stop_type = decode_instruction[each]
                if motor[channel]:
                    executed.append(message)
                    set_angle(channel, angle, 300, stop_type)
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
    init_socket()
    init_motor('direction')
    init_motor('lift')
    init_motor('grab')
    motor['propulsion'].set_run_settings(800, 200)
    while True:
        main_loop_emojis()
finally:
    print("Closing")
    if bot is not None:
        bot.close()
    if server is not None:
        server.close()