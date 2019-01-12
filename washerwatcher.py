import ujson
import urequests
import time
import machine
from umqtt.robust import MQTTClient

""" Config file format

    {
        "mqtt":{
            "key":"XXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXX",
            "device_name":"laundry-esp8266",
            "port":8883,
            "host":"io.adafruit.com",
            "user":"bobobox",
            "ssl":true
        },
        "prowl":{
            "key":"XXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXX"
        }
    }

"""

def run():
    """Run app."""

    config = get_config()

    mqtt_client = MQTTClient(
        config['mqtt']['device_name'],
        config['mqtt']['host'],
        user=config['mqtt']['user'],
        password=config['mqtt']['key'],
        ssl=config['mqtt'].get('ssl', True),
        port=8883 if config['mqtt'].get('ssl', True) else 1883
    )

    washer = WasherDryer('Washing Machine', 4)

    send_mqtt_data(
        mqtt_client,
        '{}/feeds/{}'.format(
            config['mqtt']['user'],
            'washer-running'),
        0
    )

    send_prowl_alert(config['prowl']['key'], "Starting WasherWatcher", -2)

    while True:

        old_washer_state = washer.state

        washer.update_state()

        if old_washer_state != washer.state:

            # Notify that state has changed.
            send_mqtt_data(
                mqtt_client,
                '{}/feeds/{}'.format(
                    config['mqtt']['user'],
                    'washer-running'),
                1 if washer.state == 'running' else 0
            )

            prowl_msg = '{} Started...' if washer.state == 'running' else '{} Done!'
            # -1 == moderate, 1 == high
            prowl_priority = -1 if washer.state == 'running' else 1

            send_prowl_alert(
                config['prowl']['key'],
                prowl_msg.format(washer.name),
                prowl_priority
            )


def get_config(path='washerwatcher.json'):
    """Gets config from JSON file.
    
    Returns dict."""

    with open(path, 'r') as config_fh:
        return ujson.load(config_fh)


def send_mqtt_data(mqtt_client, topic, data):
    
    mqtt_client.connect()
    mqtt_client.publish(topic, str(data))
    mqtt_client.disconnect()


def send_prowl_alert(api_key, msg, priority):
    """Sends alert to Prowl."""

    prowl_url = 'https://prowlapp.com/publicapi/add'

    payload = {
        'apikey': api_key,
        'application': 'Laundry:',
        'description': msg.replace(' ', '%20'),
        'priority': priority
    }
    param_string = '&'.join(['{}={}'.format(k,v) for k,v in payload.items()])
    req = urequests.get('{}?{}'.format(prowl_url, param_string))
    print(req.status_code)

    
class WasherDryer:

    def __init__(self, name, sensor_pin):

        self.name = name
        self.sensor = machine.Pin(sensor_pin, machine.Pin.IN)
        self.state = 'stopped'
        self.test_sample_count = 1000
        self.test_sample_period_ms = 5
        self.test_running_threshold = 10
        self.state_change_result_threshold = 4
        self.state_change_test_gap_s = 7

    def test_state(self):

        counter = self.test_sample_count
        test_accumulator = 0 

        while counter > 0:

            test_accumulator += self.sensor.value()

            time.sleep_ms(self.test_sample_period_ms)
            counter -= 1

        print(test_accumulator)
        print(test_accumulator / self.test_sample_count * 100)

        if test_accumulator / self.test_sample_count * 100 >= self.test_running_threshold:

            return 'running'

        else:

            return 'stopped'

    def update_state(self):

        # Require multiple checks all returning the same result to consider
        # state changed.
        for test in range(self.state_change_result_threshold):

            print("Test {}".format(test + 1))

            result = self.test_state()

            if result == self.state:
            
                print('State unchanged.')
                return

            time.sleep(self.state_change_test_gap_s)

        self.state = result

        print("State changed. Now {}.".format(self.state))

        return

