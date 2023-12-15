import time
import json
from datetime import datetime, timezone, timedelta
import Adafruit_DHT
import RPi.GPIO as GPIO
from AWSIoTPythonSDK.MQTTLib import AWSIoTMQTTClient
from AWSIoTPythonSDK.MQTTLib import AWSIoTMQTTShadowClient


# 温湿度センサーのピン番号と種類を指定
sensor_pin = 14  # 例: Raspberry PiのGPIOピン番号
sensor_type = Adafruit_DHT.DHT11  # センサーの種類に合わせて変更

# LEDの設定
led_pin = 23  # GPIOピン番号
led_state = GPIO.LOW
GPIO.setmode(GPIO.BCM)
GPIO.setup(led_pin, GPIO.OUT)

# AWS IoT Coreの設定
iot_client_id = "xx-iot-device"
iot_endpoint = "XXX.iot.ap-northeast-1.amazonaws.com"
iot_root_ca = "XXX.pem"
iot_private_key = "XXX-private.pem.key"
iot_cert = "XXX-certificate.pem.crt"
topic = "data/xx-iot-device"

# AWS IoT MQTTクライアントの初期化
mqtt_client = AWSIoTMQTTClient(iot_client_id)
mqtt_client.configureEndpoint(iot_endpoint, 8883)
mqtt_client.configureCredentials(iot_root_ca, iot_private_key, iot_cert)

# AWS IoT Shadowの設定
shadow_handler = AWSIoTMQTTShadowClient(iot_client_id)
shadow_handler.configureEndpoint(iot_endpoint, 8883)
shadow_handler.configureCredentials(iot_root_ca, iot_private_key, iot_cert)

# AWS IoT Coreに接続
mqtt_client.connect()

# AWS IoT Shadowに接続
shadow_handler.connect()

# シャドウハンドラを作成
shadow = shadow_handler.createShadowHandlerWithName(iot_client_id, True)

# 待ち時間制御(初期状態)
wait_time = 6

def customCallback(payload, responseStatus, token):
    global wait_time
    global led_state

    result = {
        "responseStatus": responseStatus,
        "payload": payload,
    }

    if responseStatus == "accepted":
        # print("Shadow Update Accepted")
        # print("Payload: " + json.dumps(payload))

        # デバイスシャドウから取得したデータを解析
        try:
            data = json.loads(payload)
            if 'state' in data and 'desired' in data['state']:
                desired_state = data['state']['desired']
                wait_time = desired_state.get('wait-time')
                led_state = desired_state.get('LED-state')

        except Exception as e:
            print(f"Error parsing Shadow data: {e}")

    elif responseStatus == "rejected":
        print("Shadow Update Rejected")
    elif responseStatus == "timeout":
        print("Shadow Update Timed Out")

    return result

def get_shadow_data():
    # デバイスシャドウを取得
    result = shadow.shadowGet(customCallback, 5)
    return result

def get_current_time():
    # タイムゾーンをJSTに設定
    jst = timezone(timedelta(hours=9))

    # 現在時刻を取得
    current_time = datetime.now(jst)

    # 指定された形式で文字列に変換
    formatted_time = current_time.strftime("%Y-%m-%dT%H:%M:%S")

    return formatted_time

def main():
    global wait_time
    global led_state
    global led_pin
    global iot_client_id
    global sensor_type
    global sensor_pin

    print(f"初期待ち時間：{wait_time}")
    print(f"初期LED状態：{led_state}")

    while True:
        try:

            # デバイスシャドウからデータを取得
            get_shadow_data()

            print(f"待ち時間：{wait_time}")
            print(f"LED状態：{led_state}")

            # led_stateがGPIO.HIGHだったら1、LOWだったら0を出力
            if led_state == "GPIO.HIGH":
                led_set = 1
            else:
                led_set = 0

            GPIO.output(led_pin, led_set)
            
            # 温湿度センサーからデータを読み取る
            humidity, temperature = Adafruit_DHT.read_retry(sensor_type, sensor_pin)
            # 現在時刻取得
            current_time = get_current_time()

            if humidity is not None and temperature is not None:
                # 温度と湿度を整数に変換
                temperature = int(temperature)
                humidity = int(humidity)

                # 送信するメッセージのデータ
                data = {"DEVICE_NAME": iot_client_id, "TIMESTAMP": current_time, "TEMPERATURE": temperature, "HUMIDITY": humidity}
                # メッセージをJSON形式に変換
                message = json.dumps(data)

                # メッセージをAWS IoT Coreに送信
                mqtt_client.publish(topic, message, 1)

                print(f"Data sent: {message}")
                print("------------------------------")

            else:
                print("Failed to retrieve sensor data.")

            # 待機（待ち時間はdevice shadowにより変化）
            time.sleep(int(wait_time))

        except Exception as e:
            print(f"Error: {e}")
            time.sleep(6)

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("Program terminated by user")
        shadow_handler.disconnect()
        mqtt_client.disconnect()
        GPIO.cleanup()
        print("切断完了1")
    except Exception as e:
        print(f"Error: {e}")
        time.sleep(6)
    finally:
        # 接続のクリーンアップ
        shadow_handler.disconnect()
        mqtt_client.disconnect()
        GPIO.cleanup()
        print("切断完了")