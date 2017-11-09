#!/usr/bin/env python3
import serial
import datetime
import time
import pymongo
import Adafruit_DHT
import sys
import Adafruit_GPIO.SPI as SPI
import Adafruit_SSD1306
from PIL import Image
from PIL import ImageDraw
from PIL import ImageFont


class sensorsIO():
    def __init__(self):
        self.pm_device = '/dev/ttyUSB0'
        self.sensor_args = {'11': Adafruit_DHT.DHT11,
                            '22': Adafruit_DHT.DHT22}
        self.sensor = '22'
        self.GPIO_pin = '4'  # BCM4

    def open_pm_port(self):
        self.port = serial.Serial(self.pm_device, baudrate=9600, timeout=2.0)
        self.port.write(b'\x42\x4D\xE1\x00\x00\x01\x70')

    def read_pm_line(self):
        rv = b''
        while True:
            ch1 = self.port.read()
            if ch1 == b'\x42':
                ch2 = self.port.read()
                if ch2 == b'\x4d':
                    rv += ch1 + ch2
                    rv += self.port.read(30)
                    return rv

    def get_pm_data(self):
        self.port.write(b'\x42\x4D\xE2\x00\x00\x01\x71')
        rcv = self.read_pm_line()
        # checksum
        if sum(rcv[:-2]) == rcv[-2] * 256 + rcv[-1]:
            res = {'timestamp': datetime.datetime.now(),
                   'apm10': rcv[4] * 256 + rcv[5],
                   'apm25': rcv[6] * 256 + rcv[7],
                   'apm100': rcv[8] * 256 + rcv[9],
                   'pm10': rcv[10] * 256 + rcv[11],
                   'pm25': rcv[12] * 256 + rcv[13],
                   'pm100': rcv[14] * 256 + rcv[15],
                   'gt03um': rcv[16] * 256 + rcv[17],
                   'gt05um': rcv[18] * 256 + rcv[19],
                   'gt10um': rcv[20] * 256 + rcv[21],
                   'gt25um': rcv[22] * 256 + rcv[23],
                   'gt50um': rcv[24] * 256 + rcv[25],
                   'gt100um': rcv[26] * 256 + rcv[27]}
            return res
        else:
            return False

    def get_HaT_data(self):
        humidity, temperature = Adafruit_DHT.read_retry(
            self.sensor_args[self.sensor], self.GPIO_pin)
        if humidity is not None and temperature is not None:
            return {'temperature': round(temperature, 2),
                    'humidity': round(humidity, 2)}
        else:
            return False


class mongodbIO():
    def __init__(self):
        self.ip = 'localhost'
        self.port = 27017

    def connect_db(self):
        self.client = pymongo.MongoClient(self.ip, self.port)
        return self.client

    def close_db(self):
        return self.client.close()

    def insert_db(self, db, set, data):
        used_db = self.client[db]
        used_set = used_db[set]
        used_set.insert(data)
        # return self.close_db()
        return


class oledDraw():
    def __init__(self):
        self.disp = Adafruit_SSD1306.SSD1306_128_64()
        self.disp.begin()
        self.disp.clear()
        self.width = self.disp.width
        self.height = self.disp.height
        self.image = Image.new('1', (self.width, self.height))
        self.draw = ImageDraw.Draw(self.image)
        self.font = ImageFont.load_default()
        self.padding = 2
        self.shape_width = 20
        self.top = self.padding

    def dataDraw(self, second='#', third='##', fourth='###', fifth='####', sixth='#####'):
        self.draw.rectangle((0, 0, self.width, self.height), outline=0, fill=0)
        x = self.padding
        x += self.shape_width + self.padding
        self.draw.text((x, self.top), time.strftime(
            '%m-%d %H:%M:%S', time.localtime(time.time())),  font=self.font, fill=255)
        self.draw.text((x, self.top + 10), second,  font=self.font, fill=255)
        self.draw.text((x, self.top + 20), third,  font=self.font, fill=255)
        self.draw.text((x, self.top + 30), fourth,  font=self.font, fill=255)
        self.draw.text((x, self.top + 40), fifth,  font=self.font, fill=255)
        self.draw.text((x, self.top + 50), sixth,  font=self.font, fill=255)
        # Display image.
        self.disp.image(self.image)
        self.disp.display()


def yield_init():
    ss = sensorsIO()
    ss.open_pm_port()
    db = mongodbIO()
    db.ip = '127.0.0.1'
    db.connect_db()
    oled = oledDraw()
    oled.dataDraw("init done")
    print("init done")
    while True:
        pm_res = ss.get_pm_data()
        HaT_res = ss.get_HaT_data()
        if pm_res == False or HaT_res == False:
            continue
        res = pm_res.copy()
        res.update(HaT_res)
        db.insert_db('AQI', 'AQI_0', res)
        oled.dataDraw('H&T:{0}* {1}%'.format(res['temperature'], res['humidity']),
                      'apm2.5:{0}ug/m^3'.format(res['apm25']),
                      'apm10:{0}ug/m^3'.format(res['apm100']),
                      'pm2.5:{0}ug/m^3'.format(res['pm25']),
                      'pm10:{0}ug/m^3'.format(res['pm100']))
        # if quiet != True:
        print(res)
        yield {'db': db, 'oled': oled}


def main():
    f1 = yield_init()
    while True:
        try:
            obj = f1.__next__()
            time.sleep(5)
        except:
            obj['oled'].dataDraw("exit!")
            print('exit!')
            break
        finally:
            obj['db'].close_db()


if __name__ == '__main__':
    main()
